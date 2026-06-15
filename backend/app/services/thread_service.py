import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.models import Thread
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_thread(db: AsyncSession, title: str) -> Thread:
    """Create a new thread with a UUID and return it."""
    thread_id = str(uuid.uuid4())
    thread = Thread(
        id=thread_id,
        title=title,
        is_titled=False,
    )
    db.add(thread)
    await db.flush()
    await db.refresh(thread)
    logger.info(f"Thread created: {thread_id}")
    return thread


async def list_threads(db: AsyncSession) -> list[Thread]:
    """Return all threads ordered by most recently updated."""
    result = await db.execute(
        select(Thread).order_by(Thread.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_thread_by_id(db: AsyncSession, thread_id: str) -> Thread | None:
    """Return a thread by ID or None if not found."""
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    return result.scalar_one_or_none()


async def rename_thread(db: AsyncSession, thread: Thread, title: str) -> Thread:
    """Rename a thread and mark it as titled."""
    thread.title = title
    thread.is_titled = True
    await db.flush()
    await db.refresh(thread)
    logger.info(f"Thread renamed: {thread.id} → {title}")
    return thread


async def delete_thread(db: AsyncSession, thread_id: str) -> None:
    """Delete a thread by ID."""
    await db.execute(delete(Thread).where(Thread.id == thread_id))
    await db.flush()
    logger.info(f"Thread deleted: {thread_id}")