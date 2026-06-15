from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db
from app.db.models import Thread
from app.memory.checkpointer import get_db_path
from app.schemas.chat import ChatRequest, ChatHistoryRead
from app.core.logging import get_logger
from app.services.chat_service import (
    stream_agent_response,
    generate_title,
    get_checkpointer_context,
    build_chat_history,
)
from app.agent.graph import get_graph_with_checkpointer

logger = get_logger(__name__)
router = APIRouter()


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
        select(Thread).where(Thread.id == thread_id)  # ← fixed
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")

    db_path = get_db_path()
    config = {"configurable": {"thread_id": thread_id}}

    async with get_checkpointer_context(db_path) as checkpointer:
        graph_with_memory = get_graph_with_checkpointer(checkpointer)
        state = await graph_with_memory.aget_state(config)

    messages = build_chat_history(state)
    return ChatHistoryRead(thread_id=thread_id, messages=messages)