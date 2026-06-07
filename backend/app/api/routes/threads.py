import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.api.deps import get_db
from app.db.models import Thread
from app.schemas.thread import ThreadCreate, ThreadRead, ThreadUpdate
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=ThreadRead, status_code=201)
async def create_thread(
    payload: ThreadCreate,
    db: AsyncSession = Depends(get_db),
):
    thread_id = str(uuid.uuid4())
    thread = Thread(
        id=thread_id,
        title=payload.title,
        is_titled=False,
    )
    db.add(thread)
    await db.flush()
    await db.refresh(thread)
    logger.info(f"Thread created: {thread_id}")
    return ThreadRead.model_validate(thread)


@router.get("", response_model=list[ThreadRead])
async def list_threads(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).order_by(Thread.updated_at.desc())
    )
    threads = list(result.scalars().all())
    return [ThreadRead.model_validate(t) for t in threads]


@router.get("/{thread_id}", response_model=ThreadRead)
async def get_thread(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")

    return ThreadRead.model_validate(thread)


@router.patch("/{thread_id}", response_model=ThreadRead)
async def rename_thread(
    thread_id: str,
    payload: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")

    thread.title = payload.title
    thread.is_titled = True
    await db.flush()
    await db.refresh(thread)
    logger.info(f"Thread renamed: {thread_id} → {payload.title}")
    return ThreadRead.model_validate(thread)


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")

    # Delete thread record
    await db.execute(delete(Thread).where(Thread.id == thread_id))
    await db.flush()

    logger.info(f"Thread deleted: {thread_id}")