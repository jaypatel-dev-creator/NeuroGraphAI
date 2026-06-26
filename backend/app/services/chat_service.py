import json
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.db.base import AsyncSessionLocal
from app.memory.ltm_store import get_profile
from app.agent.nodes.memory_writer import memory_writer_node
from app.agent.graph import get_graph_with_checkpointer
from app.memory.checkpointer import get_db_path, use_postgres_checkpointer
from app.schemas.chat import ChatMessage
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)



# LLM client for title generation — created once at module load

def _build_title_llm() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
        temperature=0.7,
    )

_title_llm = _build_title_llm()


def format_sse(data: dict) -> str:
    """Format a dict as an SSE event string."""
    return f"data: {json.dumps(data)}\n\n"


def extract_text_content(content) -> str:
    """Normalize Gemini content — handles both string and list of parts."""
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return content or ""


def get_checkpointer_context(db_path: str):
    """Return the correct checkpointer based on environment — SQLite local, Postgres prod."""
    if use_postgres_checkpointer():
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        settings = get_settings()
        return AsyncPostgresSaver.from_conn_string(settings.database_url)
    else:
        return AsyncSqliteSaver.from_conn_string(db_path)


def parse_tool_output(tool_name: str, raw_output) -> tuple[str, list[dict]]:
    sources = []

   
    is_tavily = (
        "tavily" in tool_name.lower()
        or (
            isinstance(raw_output, dict)
            and "results" in raw_output
            and "query" in raw_output
        )
    )

    if is_tavily:
        try:
            # raw_output can be a dict (Tavily response) or list
            if isinstance(raw_output, dict) and "results" in raw_output:
                results = raw_output.get("results", [])
                sources = [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                    }
                    for r in results
                    if isinstance(r, dict) and r.get("url")
                ]
                tool_output = " ".join(
                    r.get("content", "")
                    for r in results
                    if isinstance(r, dict)
                )
            elif isinstance(raw_output, list):
                sources = [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                    }
                    for r in raw_output
                    if isinstance(r, dict) and r.get("url")
                ]
                tool_output = " ".join(
                    r.get("content", "")
                    for r in raw_output
                    if isinstance(r, dict)
                )
            else:
                tool_output = str(raw_output)
        except Exception:
            tool_output = str(raw_output)
    else:
        tool_output = str(raw_output)

    return tool_output, sources


async def build_ltm_context(db: AsyncSession) -> str:
    """Load all LTM profile entries from DB and return as formatted string."""
    entries = await get_profile(db)
    if not entries:
        return ""
    lines = [f"{e.key}: {e.value}" for e in entries]
    return "\n".join(lines)


async def generate_title(message: str) -> str:
    """Generate a short 4-5 word title for a conversation. Falls back to 'New Chat' on failure."""
    try:
        prompt = (
            f"Generate a short 4-5 word title for a conversation "
            f"that starts with this message: '{message}'. "
            f"Return ONLY the title, nothing else. No quotes, no punctuation at end."
        )
        response = await _title_llm.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        logger.warning(f"Title generation failed: {str(e)}")
        return "New Chat"



#streaming function ==> yields chunks one by one . 
async def stream_agent_response(
    thread_id: str,
    message: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Core streaming function — runs the LangGraph ReAct agent and yields SSE events.
    Handles text streaming, tool start/end events, memory writing, and errors.
    Emits a memory_update SSE event when LTM keys are saved.
    """
    try:
        db_path = get_db_path()#for local, returns  checkpoint_db_path: str = "./data/checkpoints.db", while for prod , returns empty string 
        ltm_context = await build_ltm_context(db) #get all enteries 

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 10,  # prevent infinite ReAct loops — 5 tool calls max
        }
        input_state = {
            "messages": [HumanMessage(content=message)],
            "ltm_context": ltm_context,
        }

        async with get_checkpointer_context(db_path) as checkpointer:
            graph_with_memory = get_graph_with_checkpointer(checkpointer) #actual graph compilation based on checkpointer 
           ##invoking graph with astream_events to support streaming 
            async for event in graph_with_memory.astream_events(
                input_state,
                config=config,
                version="v2",
            ):
                event_name = event.get("event")
                event_data = event.get("data", {})

                if event_name == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        text = extract_text_content(chunk.content)
                        if text.strip():
                            yield format_sse({
                                "type": "text",
                                "content": text,
                            })

                elif event_name == "on_tool_start":
                    tool_name = event.get("name", "")
                    tool_input = event_data.get("input", {})
                    yield format_sse({
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                    })

                elif event_name == "on_tool_end":
                    tool_name = event.get("name", "")
                    raw_output = event_data.get("output", "")
                    tool_output, sources = parse_tool_output(tool_name, raw_output)
                    yield format_sse({
                        "type": "tool_end",
                        "tool_name": tool_name,
                        "tool_output": tool_output,
                        "sources": sources,
                    })

            state = await graph_with_memory.aget_state(config)
            if state and state.values.get("messages"):
                async with AsyncSessionLocal() as fresh_db:
                    try:
                        saved_keys = await memory_writer_node(state.values, fresh_db)
                        await fresh_db.commit()
                        # Emit memory_update event if any keys were saved
                        if saved_keys:
                            yield format_sse({
                                "type": "memory_update",
                                "keys": saved_keys,
                            })
                    except Exception as e:
                        await fresh_db.rollback()
                        logger.error(f"Memory writer failed: {str(e)}")

        yield format_sse({"type": "done"})

    except Exception as e:
        logger.error(f"Stream error: {str(e)}", exc_info=True)
        yield format_sse({"type": "error", "message": "Something went wrong. Please try again."})


def build_chat_history(state) -> list[ChatMessage]:
    """
    Parse LangGraph state messages into ChatMessage list.
    - HumanMessage and AIMessage are returned.
    - ToolMessage is intentionally skipped — raw checkpoint data is not
      suitable for display. Tool badges and sources are shown during live
      streaming only. This is Pattern A, same as ChatGPT's behavior.
    - MEMORY_UPDATE lines are stripped from AIMessage content.
    """
    messages = []
    if not state or not state.values.get("messages"):
        return messages

    for msg in state.values["messages"]:
        if isinstance(msg, HumanMessage):
            messages.append(ChatMessage(role="human", content=msg.content))
        elif isinstance(msg, AIMessage):
            content = extract_text_content(msg.content)
            clean_lines = [
                line for line in content.split("\n")
                if not line.strip().startswith("MEMORY_UPDATE:")
            ]
            clean_content = "\n".join(clean_lines).strip()
            if clean_content:
                messages.append(ChatMessage(role="ai", content=clean_content))
        # ToolMessage intentionally skipped — see docstring above

    return messages