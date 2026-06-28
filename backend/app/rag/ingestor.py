import asyncio
import hashlib
from dataclasses import dataclass

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import RAGException
from app.rag.store import get_store

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 50
SUPPORTED_TYPES = {"application/pdf", "text/plain"}

CHUNK_SIZE = 1000       # characters per chunk
CHUNK_OVERLAP = 200     # overlap between consecutive chunks
TOP_K = 3               # returned by document_search tool


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


# ── Recursive character text splitter ───────────────────────────────────────

def recursive_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    separators = ["\n\n", "\n", " ", ""]

    def _split(text: str, separators: list[str]) -> list[str]:
        separator = separators[0]
        next_separators = separators[1:]

        if separator == "":
            return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]

        splits = text.split(separator)
        chunks = []
        current = ""

        for split in splits:
            candidate = current + (separator if current else "") + split
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(split) > chunk_size and next_separators:
                    chunks.extend(_split(split, next_separators))
                else:
                    current = split

        if current:
            chunks.append(current)

        return chunks

    raw_chunks = _split(text, separators)

    if overlap == 0 or len(raw_chunks) <= 1:
        return [c for c in raw_chunks if c.strip()]

    overlapped = [raw_chunks[0]]
    for i in range(1, len(raw_chunks)):
        prev_tail = raw_chunks[i - 1][-overlap:]
        overlapped.append(prev_tail + raw_chunks[i])

    return [c for c in overlapped if c.strip()]


# ── Embedding ────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using Gemini gemini-embedding-001.
    Called at ingest time — runs synchronously, offloaded via asyncio.to_thread from ingest_file.
    output_dimensionality=768 keeps vectors consistent with ChromaDB collection and Pinecone index.
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.google_api_key)

    embeddings = []
    for text in texts:
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=768,
            ),
        )
        embeddings.append(result.embeddings[0].values)

    return embeddings


def embed_query(text: str) -> list[float]:
    """
    Embed a single query string at search time.
    Uses RETRIEVAL_QUERY task type — different from document embedding, as per Gemini docs.
    Runs synchronously — called directly from document_search tool (sync @tool).
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.google_api_key)

    result = client.models.embed_content(
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
    4. Chunk
    5. Embed (offloaded to thread — blocking Gemini API calls)
    6. Write to vector store
    Returns IngestResult with already_existed=True if duplicate, False if freshly indexed.
    """

    # 1. Validate
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

    # 4. Chunk
    chunks = recursive_split(text, CHUNK_SIZE, CHUNK_OVERLAP)
    if not chunks:
        raise RAGException(f"'{filename}' produced no text chunks after processing.", status_code=422)

    logger.info(f"Chunked '{filename}' into {len(chunks)} chunks")

    # 5. Embed — offloaded to thread pool to avoid blocking the async event loop
    embeddings = await asyncio.to_thread(embed_texts, chunks)

    # 6. Write to store
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