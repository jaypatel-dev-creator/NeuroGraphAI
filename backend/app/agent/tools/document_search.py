from langchain_core.tools import tool

from app.rag.ingestor import embed_query, TOP_K
from app.rag.store import get_store
from app.core.logging import get_logger

logger = get_logger(__name__)


@tool
def document_search(query: str) -> str:
    """
    Search across user-uploaded documents to find relevant information.
    Use this tool ONLY when the user is asking a question about documents they have uploaded.
    Do NOT use this for general knowledge questions or web searches.
    Input must be a search query string describing what to look for in the documents.
    Example: 'What are the key findings in the report?', 'summarize the contract terms'
    """
    try:
        store = get_store()

        # Embed the query using retrieval_query task type
        query_embedding = embed_query(query)

        # Retrieve top-k chunks
        chunks = store.query(embedding=query_embedding, k=TOP_K)

        if not chunks:
            return "No relevant content found in the uploaded documents for this query."

        # Format: [filename, chunk N]: text — agent knows which document each chunk came from
        parts = []
        for i, chunk in enumerate(chunks):
            filename = chunk["metadata"].get("filename", "unknown")
            chunk_index = chunk["metadata"].get("chunk_index", i)
            text = chunk["document"]
            parts.append(f"[{filename}, chunk {chunk_index}]: {text}")

        return "\n\n".join(parts)

    except Exception as e:
        logger.error(f"document_search failed: {str(e)}")
        return f"Document search error: {str(e)}"