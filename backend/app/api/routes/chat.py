import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.api.deps import get_db
from app.db.base import AsyncSessionLocal
from app.db.models import Thread
from app.memory.ltm_store import get_profile
from app.agent.nodes.memory_writer import memory_writer_node
from app.agent.graph import get_graph_with_checkpointer, get_db_path
from app.memory.checkpointer import use_postgres_checkpointer
from app.schemas.chat import ChatRequest, ChatMessage, ChatHistoryRead
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def build_ltm_context(db: AsyncSession) -> str:
    entries = await get_profile(db)
    if not entries:
        return ""
    lines = [f"{e.key}: {e.value}" for e in entries]
    return "\n".join(lines)


async def generate_title(message: str) -> str:
    try:
        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.google_api_key,
            temperature=0.7,
        )
        prompt = (
            f"Generate a short 4-5 word title for a conversation "
            f"that starts with this message: '{message}'. "
            f"Return ONLY the title, nothing else. No quotes, no punctuation at end."
        )
        response = await llm.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        logger.error(f"Title generation failed: {str(e)}")
        return "New Chat"


def format_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def extract_text_content(content) -> str:
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return content or ""


def get_checkpointer_context(db_path: str):
    if use_postgres_checkpointer():
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        settings = get_settings()
        return AsyncPostgresSaver.from_conn_string(settings.database_url)
    else:
        return AsyncSqliteSaver.from_conn_string(db_path)


def parse_tool_output(tool_name: str, raw_output) -> tuple[str, list[dict]]:
    """
    Returns (tool_output_text, sources_list).
    Sources only populated for Tavily web search.
    """
    sources = []

    if "tavily" in tool_name.lower():
        try:
            if isinstance(raw_output, list):
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


async def stream_agent_response(
    thread_id: str,
    message: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    try:
        db_path = get_db_path()
        ltm_context = await build_ltm_context(db)

        config = {"configurable": {"thread_id": thread_id}}
        input_state = {
            "messages": [HumanMessage(content=message)],
            "ltm_context": ltm_context,
        }

        async with get_checkpointer_context(db_path) as checkpointer:
            graph_with_memory = get_graph_with_checkpointer(checkpointer)

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

            # Fresh session for memory writer
            # original db session may be closed by StreamingResponse lifecycle
            state = await graph_with_memory.aget_state(config)
            if state and state.values.get("messages"):
                async with AsyncSessionLocal() as fresh_db:
                    try:
                        await memory_writer_node(state.values, fresh_db)
                        await fresh_db.commit()
                    except Exception as e:
                        await fresh_db.rollback()
                        logger.error(f"Memory writer failed: {str(e)}")

        yield format_sse({"type": "done"})

    except Exception as e:
        logger.error(f"Stream error: {str(e)}", exc_info=True)
        yield format_sse({"type": "error", "message": str(e)})


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(Thread.id == request.thread_id)
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")

    if not thread.is_titled:
        title = await generate_title(request.message)
        thread.title = title
        thread.is_titled = True
        await db.flush()

    return StreamingResponse(
        stream_agent_response(request.thread_id, request.message, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{thread_id}", response_model=ChatHistoryRead)
async def get_chat_history(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")

    db_path = get_db_path()
    config = {"configurable": {"thread_id": thread_id}}

    async with get_checkpointer_context(db_path) as checkpointer:
        graph_with_memory = get_graph_with_checkpointer(checkpointer)
        state = await graph_with_memory.aget_state(config)

    messages = []
    if state and state.values.get("messages"):
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
            elif isinstance(msg, ToolMessage):
                messages.append(ChatMessage(role="tool", content=msg.content))

    return ChatHistoryRead(thread_id=thread_id, messages=messages)