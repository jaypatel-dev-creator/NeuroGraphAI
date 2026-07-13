from pathlib import Path
from app.core.exceptions import RAGException
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

#constants 
COLLECTION_NAME = "neurograph_docs"  # single global collection for now (per-user after auth)
EMBEDDING_DIMENSION = 768            # gemini-embedding-001 with output_dimensionality=768

#module level variables and functions 
_store = None  # will be either ChromaVectorStore or PineconeVectorStore instance 

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
            metadata={"hnsw:space": "cosine"},
        )
        _store = ChromaVectorStore(collection)
        logger.info(f"RAG store: ChromaDB — path: {settings.chroma_path}")

#chroma vector store class 
class ChromaVectorStore:
    def __init__(self, collection):
        self.collection = collection

    def add(self, ids: list[str], embeddings: list[list[float]], documents: list[str], metadatas: list[dict]) -> None:
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(self, embedding: list[float], k: int = 3, threshold: float = 0.5) -> list[dict]:
        # Guard: never request more results than exist in collection
        count = self.collection.count()
        if count == 0:
            return []
        n_results = min(k, count)

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
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
        self.collection.delete(where={"sha256": sha256})

    def has_sha256(self, sha256: str) -> bool:
        results = self.collection.get(where={"sha256": sha256}, limit=1)
        return len(results["ids"]) > 0


#pinecone vector store class 
class PineconeVectorStore:
    def __init__(self, index):
        self.index = index

    def add(self, ids: list[str], embeddings: list[list[float]], documents: list[str], metadatas: list[dict]) -> None:
        vectors = []
        for chunk_id, embedding, doc, meta in zip(ids, embeddings, documents, metadatas):
            pinecone_meta = {**meta, "text": doc}
            vectors.append({"id": chunk_id, "values": embedding, "metadata": pinecone_meta})
        self.index.upsert(vectors=vectors)

    def query(self, embedding: list[float], k: int = 3, threshold: float = 0.5) -> list[dict]:
        results = self.index.query(vector=embedding, top_k=k, include_metadata=True)
        chunks = []
        for match in results["matches"]:
            if match["score"] >= threshold:
                meta = dict(match["metadata"])
                text = meta.pop("text", "")
                chunks.append({"document": text, "metadata": meta})
        return chunks

    def delete_by_sha256(self, sha256: str) -> None:
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
        results = self.index.query(
            vector=[0.0] * EMBEDDING_DIMENSION,
            top_k=1,
            filter={"sha256": {"$eq": sha256}},
            include_metadata=False,
        )
        return len(results["matches"]) > 0