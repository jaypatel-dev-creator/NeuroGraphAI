from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "neurograph_docs"  # single global collection for now (per-user after auth)
EMBEDDING_DIMENSION = 768            # Gemini text-embedding-004 output dimension

# Module-level singleton — set once in lifespan, read by document_search tool and ingestor
_store = None  # will be either ChromaVectorStore or PineconeVectorStore instance


def use_pinecone() -> bool:
    """True when PINECONE_API_KEY is set in env — same pattern as use_postgres_checkpointer()."""
    return bool(get_settings().pinecone_api_key)


def get_store():
    """Return the initialized vector store singleton. Raises if init_store() was not called."""
    if _store is None:
        raise RuntimeError("Vector store not initialized. Call init_store() on startup.")
    return _store


def init_store() -> None:
    """
    Initialize the vector store singleton based on environment.
    Called once in lifespan startup — same pattern as compile_graph().
    local  ==> PINECONE_API_KEY absent ==> ChromaDB at chroma_path
    prod   ==> PINECONE_API_KEY present ==> Pinecone index
    """
    global _store
    settings = get_settings()

    if use_pinecone():
        from pinecone import Pinecone
        pc = Pinecone(api_key=settings.pinecone_api_key)
        index = pc.Index(settings.pinecone_index_name)
        _store = PineconeVectorStore(index)
        logger.info(f"RAG store: Pinecone — index: {settings.pinecone_index_name}")
    else:
        import chromadb
        Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=settings.chroma_path)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # cosine similarity for embedding search
        )
        _store = ChromaVectorStore(collection)
        logger.info(f"RAG store: ChromaDB — path: {settings.chroma_path}")


# ── ChromaDB implementation ──────────────────────────────────────────────────

class ChromaVectorStore:
    def __init__(self, collection):
        self.collection = collection

    def add(self, ids: list[str], embeddings: list[list[float]], documents: list[str], metadatas: list[dict]) -> None:
        """Add chunks to the collection."""
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(self, embedding: list[float], k: int) -> list[dict]:
        """
        Return top-k chunks as list of dicts with keys: document, metadata.
        ChromaDB returns results grouped by field — we re-shape into per-chunk dicts.
        """
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=k,
            include=["documents", "metadatas"],
        )
        chunks = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            chunks.append({"document": doc, "metadata": meta})
        return chunks

    def delete_by_sha256(self, sha256: str) -> None:
        """Delete all chunks belonging to a document identified by sha256."""
        self.collection.delete(where={"sha256": sha256})

    def has_sha256(self, sha256: str) -> bool:
        """Check if any chunk with this sha256 exists — used for dedup at ingest time."""
        results = self.collection.get(where={"sha256": sha256}, limit=1)
        return len(results["ids"]) > 0


# ── Pinecone implementation ──────────────────────────────────────────────────

class PineconeVectorStore:
    def __init__(self, index):
        self.index = index

    def add(self, ids: list[str], embeddings: list[list[float]], documents: list[str], metadatas: list[dict]) -> None:
        """Upsert chunks into Pinecone index. Pinecone stores metadata but not raw text —
        we embed the document text into metadata as 'text' field so query() can return it."""
        vectors = []
        for chunk_id, embedding, doc, meta in zip(ids, embeddings, documents, metadatas):
            pinecone_meta = {**meta, "text": doc}  # store raw text in metadata for retrieval
            vectors.append({"id": chunk_id, "values": embedding, "metadata": pinecone_meta})
        self.index.upsert(vectors=vectors)

    def query(self, embedding: list[float], k: int) -> list[dict]:
        """Return top-k chunks. Pinecone returns metadata — we extract 'text' back out."""
        results = self.index.query(vector=embedding, top_k=k, include_metadata=True)
        chunks = []
        for match in results["matches"]:
            meta = dict(match["metadata"])
            text = meta.pop("text", "")  # remove 'text' from meta before returning
            chunks.append({"document": text, "metadata": meta})
        return chunks

    def delete_by_sha256(self, sha256: str) -> None:
        """Delete all vectors with this sha256. Pinecone requires fetch+delete by ID
        since it doesn't support metadata-only deletes on starter plans."""
        # List all IDs with this sha256 via fetch — works for starter/serverless indexes
        results = self.index.query(
            vector=[0.0] * EMBEDDING_DIMENSION,
            top_k=10000,
            filter={"sha256": {"$eq": sha256}},
            include_metadata=False,
        )
        ids_to_delete = [m["id"] for m in results["matches"]]
        if ids_to_delete:
            self.index.delete(ids=ids_to_delete)

    def has_sha256(self, sha256: str) -> bool:
        """Check if any vector with this sha256 exists."""
        results = self.index.query(
            vector=[0.0] * EMBEDDING_DIMENSION,
            top_k=1,
            filter={"sha256": {"$eq": sha256}},
            include_metadata=False,
        )
        return len(results["matches"]) > 0