import asyncio
import hashlib
from dataclasses import dataclass

from google import genai
from google.genai import types
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import RAGException
from app.rag.store import get_store

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 50
MAX_CHUNKS = 50                          # max chunks per document — controls embedding API calls
SUPPORTED_TYPES = {"application/pdf", "text/plain"}

CHUNK_SIZE = 1000        # characters per chunk
CHUNK_OVERLAP = 200      # overlap between consecutive chunks
TOP_K = 3                # returned by document_search tool
SIMILARITY_THRESHOLD = 0.5  # minimum cosine similarity for a chunk to be returned

# ── Gemini client singleton ──────────────────────────────────────────────────
# Built once at module load — same pattern as _title_llm in chat_service.py

def _build_genai_client() -> genai.Client:
    return genai.Client(api_key=get_settings().google_api_key)

_genai_client = _build_genai_client()

# ── Text splitter singleton ──────────────────────────────────────────────────
# Built once at module load — stateless, safe to reuse across requests

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)

# ── Result dataclass returned to the upload route ────────────────────────────

@dataclass
class IngestResult:
    filename: str
    sha256: str
    chunk_count: int
    already_existed: bool  # True = duplicate, False = freshly indexed


# ── SHA256 ───────────────────────────────────────────────────────────────────

def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ── Text extraction ──────────────────────────────────────────────────────────

def extract_text_from_pdf(content: bytes, filename: str) -> str:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")

        if doc.page_count > MAX_PDF_PAGES:
            raise RAGException(
                f"'{filename}' has {doc.page_count} pages — max allowed is {MAX_PDF_PAGES}.",
                status_code=422,
            )

        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()

        if not text.strip():
            raise RAGException(
                f"'{filename}' appears to be a scanned PDF with no extractable text.",
                status_code=422,
            )

        return text

    except RAGException:
        raise
    except Exception as e:
        raise RAGException(f"Failed to extract text from '{filename}': {str(e)}")


def extract_text_from_txt(content: bytes, filename: str) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return content.decode("latin-1")
        except Exception as e:
            raise RAGException(f"Failed to decode '{filename}': {str(e)}", status_code=422)


# ── Embedding ────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using Gemini gemini-embedding-001.
    Batch embedding — all chunks sent in one API call instead of N sequential calls.
    Runs synchronously — offloaded via asyncio.to_thread from ingest_file.
    output_dimensionality=768 keeps vectors consistent with ChromaDB and Pinecone index.
    """
    result = _genai_client.models.embed_content(
        model="gemini-embedding-001",
        contents=texts,  # full list — one API call for all chunks
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768,
        ),
    )
    return [e.values for e in result.embeddings]


def embed_query(text: str) -> list[float]:
    """
    Embed a single query string at search time.
    Uses RETRIEVAL_QUERY task type — different from document embedding, as per Gemini docs.
    Runs synchronously — called directly from document_search tool (sync @tool).
    """
    result = _genai_client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    return result.embeddings[0].values


# ── Main ingest function ─────────────────────────────────────────────────────

async def ingest_file(content: bytes, filename: str, content_type: str) -> IngestResult:
    """
    Full ingest pipeline for a single file:
    1. Validate size and type
    2. Compute SHA256 — check dedup
    3. Extract text
    4. Chunk via LangChain RecursiveCharacterTextSplitter
    5. Validate chunk count — applies to both PDF and TXT
    6. Embed (batch — one API call, offloaded to thread)
    7. Write to vector store
    Returns IngestResult with already_existed=True if duplicate, False if freshly indexed.
    """

    # 1. Validate size and type
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise RAGException(
            f"'{filename}' exceeds the 10MB limit ({len(content) / 1024 / 1024:.1f}MB uploaded).",
            status_code=422,
        )

    if content_type not in SUPPORTED_TYPES:
        raise RAGException(
            f"'{filename}' has unsupported type '{content_type}'. Only PDF and TXT are allowed.",
            status_code=422,
        )

    # 2. SHA256 dedup
    sha256 = compute_sha256(content)
    store = get_store()

    if store.has_sha256(sha256):
        logger.info(f"Duplicate detected — skipping ingest: {filename} ({sha256[:8]}...)")
        return IngestResult(
            filename=filename,
            sha256=sha256,
            chunk_count=0,
            already_existed=True,
        )

    # 3. Extract text
    if content_type == "application/pdf":
        text = extract_text_from_pdf(content, filename)
    else:
        text = extract_text_from_txt(content, filename)

    # 4. Chunk — LangChain RecursiveCharacterTextSplitter
    # Tries \n\n, \n, space, character boundaries in order — standard production chunking strategy
    chunks = _splitter.split_text(text)
    if not chunks:
        raise RAGException(f"'{filename}' produced no text chunks after processing.", status_code=422)

    # 5. Validate chunk count — enforced for both PDF and TXT
    # Controls max embedding API calls and vector store size per document
    if len(chunks) > MAX_CHUNKS:
        raise RAGException(
            f"'{filename}' produced {len(chunks)} chunks — max allowed is {MAX_CHUNKS}. "
            f"Try a smaller or less dense file.",
            status_code=422,
        )

    logger.info(f"Chunked '{filename}' into {len(chunks)} chunks")

    # 6. Embed — batch call, offloaded to thread pool to avoid blocking the async event loop
    embeddings = await asyncio.to_thread(embed_texts, chunks)

    # 7. Write to store
    chunk_ids = [f"{sha256}_{i}" for i in range(len(chunks))]
    metadatas = [
        {"sha256": sha256, "filename": filename, "chunk_index": i}
        for i in range(len(chunks))
    ]

    store.add(
        ids=chunk_ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    logger.info(f"Indexed '{filename}' — {len(chunks)} chunks written to vector store")

    return IngestResult(
        filename=filename,
        sha256=sha256,
        chunk_count=len(chunks),
        already_existed=False,
    )