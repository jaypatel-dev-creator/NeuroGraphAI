from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.db.base import AsyncSessionLocal
from app.db.models import User
from app.schemas.chat import ChatRequest, ChatHistoryRead
from app.core.exceptions import ThreadNotFoundException
from app.core.logging import get_logger
from app.services.chat_service import (
    stream_agent_response,
    generate_title,
    load_chat_history,
)
from app.services.thread_service import get_thread_by_id

router = APIRouter()
logger = get_logger(__name__)


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = await get_thread_by_id(db, current_user.id, request.thread_id)
    if not thread:
        raise ThreadNotFoundException(request.thread_id)
    
    if not thread.is_titled:
        title = await generate_title(request.message)
        async with AsyncSessionLocal() as title_db:
            try:
                title_thread = await get_thread_by_id(title_db, current_user.id, request.thread_id)
                if title_thread:
                    title_thread.title = title
                    title_thread.is_titled = True
                    await title_db.commit()
            except Exception as e:
                logger.warning(f"Title update failed for thread {request.thread_id}: {str(e)}", exc_info=True)
                await title_db.rollback()

    return StreamingResponse(
        stream_agent_response(request.thread_id, request.message, db, current_user.id),
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
    current_user: User = Depends(get_current_user),
):
    messages = await load_chat_history(db, current_user.id, thread_id)
    return ChatHistoryRead(thread_id=thread_id, messages=messages)