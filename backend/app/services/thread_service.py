import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.models import Thread
from app.core.logging import get_logger
from app.core.exceptions import ThreadServiceException

logger = get_logger(__name__)


#post thread route
async def create_thread(db: AsyncSession, title: str) -> Thread:
    """Create a new thread with a UUID and return it."""
    try:
        thread_id = str(uuid.uuid4()) #generate a random uuid manually
        thread = Thread( #create a thread ORM object
            id=thread_id,
            title=title,
            is_titled=False,
        )
        db.add(thread)
        await db.flush()
        await db.refresh(thread)
        logger.info(f"Thread created: {thread_id}")
        return thread
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to create thread: {str(e)}")


#get all threads route
async def list_threads(db: AsyncSession) -> list[Thread]:
    """Return all threads ordered by most recently updated."""
    try:
        result = await db.execute(
            select(Thread).order_by(Thread.updated_at.desc()) #return by default in descending order of updated at
        )
        return list(result.scalars().all())
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to list threads: {str(e)}")


#get thread by id route
async def get_thread_by_id(db: AsyncSession, thread_id: str) -> Thread | None:
    """Return a thread by ID or None if not found."""
    try:
        result = await db.execute(
            select(Thread).where(Thread.id == thread_id)
        )
        return result.scalar_one_or_none()
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to fetch thread '{thread_id}': {str(e)}")


#patch thread route
async def rename_thread(db: AsyncSession, thread: Thread, title: str) -> Thread:
    """Rename a thread and mark it as titled."""
    try:
        thread.title = title
        thread.is_titled = True
        await db.flush()
        await db.refresh(thread)
        logger.info(f"Thread renamed: {thread.id} → {title}")
        return thread
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to rename thread '{thread.id}': {str(e)}")


#delete thread route
async def delete_thread(db: AsyncSession, thread_id: str) -> None:
    """Delete a thread by ID."""
    try:
        await db.execute(delete(Thread).where(Thread.id == thread_id))
        await db.flush()
        logger.info(f"Thread deleted: {thread_id}")
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to delete thread '{thread_id}': {str(e)}")