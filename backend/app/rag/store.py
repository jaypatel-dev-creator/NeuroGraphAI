from pathlib import Path
from app.core.exceptions import RAGException
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "neurograph_docs"  # single global collection for now (per-user after auth)
EMBEDDING_DIMENSION = 768            # gemini-embedding-001 with output_dimensionality=768

_store = None  # module level variable ==>  will be either ChromaVectorStore or PineconeVectorStore instance 


def use_pinecone() -> bool:
    return bool(get_settings().pinecone_api_key)



def get_store():
    if _store is None:
        raise RAGException("Vector store not initialized. Call init_store() on startup.")
    return _store


def init_store() -> None:
    
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

    def query(self, embedding: list[float], k: int, threshold: float = None) -> list[dict]:
        
        from app.rag.ingestor import SIMILARITY_THRESHOLD
        if threshold is None:
            threshold = SIMILARITY_THRESHOLD

        # Guard: never request more results than exist in collection
        count = self.collection.count()
        if count == 0:
            return []
        n_results = min(k, count)

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],  # distances needed for threshold
        )
        chunks = []
        for doc, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB cosine distance: similarity = 1 - distance
            similarity = 1 - distance
            if similarity >= threshold:
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

    def query(self, embedding: list[float], k: int, threshold: float = None) -> list[dict]:
        """
        Return top-k chunks. Pinecone returns metadata — we extract 'text' back out.
        Applies similarity threshold using Pinecone score (already cosine similarity, not distance).
        """
        from app.rag.ingestor import SIMILARITY_THRESHOLD
        if threshold is None:
            threshold = SIMILARITY_THRESHOLD

        results = self.index.query(vector=embedding, top_k=k, include_metadata=True)
        chunks = []
        for match in results["matches"]:
            # Pinecone score is cosine similarity directly — no conversion needed
            if match["score"] >= threshold:
                meta = dict(match["metadata"])
                text = meta.pop("text", "")
                chunks.append({"document": text, "metadata": meta})
        return chunks

    def delete_by_sha256(self, sha256: str) -> None:
        """Delete all vectors with this sha256. Pinecone requires fetch+delete by ID
        since it doesn't support metadata-only deletes on starter plans."""
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