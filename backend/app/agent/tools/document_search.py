import asyncio
import concurrent.futures
from langchain_core.tools import tool

from app.rag.ingestor import embed_query, TOP_K, SIMILARITY_THRESHOLD
from app.rag.store import get_store
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level shared thread pool — reused across all document_search calls.
# Avoids spawning and destroying a new ThreadPoolExecutor on every tool invocation.
# embed_query is sync + makes a network call, so it must be offloaded from the
# event loop. document_search itself is a sync @tool (LangGraph calls it
# synchronously), so asyncio.to_thread() can't be used directly here —
# run_coroutine_threadsafe routes the coroutine onto the running event loop instead.
_thread_pool = concurrent.futures.ThreadPoolExecutor(thread_name_prefix="embed_query")


def make_document_search_tool(user_id: str):
    """
    Factory that returns a per-request document_search tool with user_id baked in.

    Why a factory instead of a module-level @tool:
    - LangChain @tool is a singleton — no access to request context.
    - user_id must be injected at request time, not import time.
    - Called once per request in get_tools(user_id) inside chat_service,
      so each request gets its own closure with the correct user scoped in.
    """

    @tool
    def document_search(query: str) -> str:
        """
        Search across user-uploaded documents to find relevant information.
        Only call this tool when the system context confirms documents are uploaded
        and the user is asking about their content.
        Input must be a search query string describing what to look for in the documents.
        Example: 'What are the key findings in the report?', 'summarize the contract terms'
        """
        try:
            store = get_store()

            # embed_query is sync + makes a network call.
            # document_search is called synchronously by LangGraph's tool executor,
            # but we're inside an async FastAPI context — a running event loop exists.
            # run_coroutine_threadsafe schedules asyncio.to_thread onto that loop
            # and blocks until complete, reusing the shared thread pool.
            loop = asyncio.get_event_loop()
            query_embedding = asyncio.run_coroutine_threadsafe(
                asyncio.to_thread(embed_query, query),
                loop,
            ).result()

            # Query scoped to this user's chunks only
            chunks = store.query(
                embedding=query_embedding,
                user_id=user_id,
                k=TOP_K,
                threshold=SIMILARITY_THRESHOLD,
            )

            if not chunks:
                return "No relevant content found in the uploaded documents for this query."

            parts = []
            for i, chunk in enumerate(chunks):
                filename = chunk["metadata"].get("filename", "unknown")
                chunk_index = chunk["metadata"].get("chunk_index", i)
                text = chunk["document"]
                parts.append(f"[{filename}, chunk {chunk_index}]: {text}")

            return "\n\n".join(parts)

        except Exception as e:
            logger.error(f"document_search failed for user {user_id}: {str(e)}")
            return f"Document search error: {str(e)}"

    return document_search