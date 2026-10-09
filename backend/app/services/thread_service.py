import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.models import Thread
from app.core.logging import get_logger
from app.core.exceptions import ThreadServiceException

logger = get_logger(__name__)

#post /threads 
async def create_thread(db: AsyncSession, user_id: str, title: str) -> Thread:
    """Create a new thread scoped to user."""
    try:
        thread_id = str(uuid.uuid4())
        thread = Thread(
            id=thread_id,
            user_id=user_id,
            title=title,
            is_titled=False,
        )

        db.add(thread)
        await db.flush()
        await db.refresh(thread) #so that auto generated field comes i.e created at and updated at 
        logger.info(f"Thread created: {thread_id} — user: {user_id}")
        return thread
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to create thread: {str(e)}")

#get / threads 
async def list_threads(db: AsyncSession, user_id: str) -> list[Thread]:
    """Return all threads scoped to the  user, most recently updated first."""
    try:
        result = await db.execute(
            select(Thread)
            .where(Thread.user_id == user_id)
            .order_by(Thread.updated_at.desc())
        )
        return list(result.scalars().all())
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to list threads: {str(e)}")

#get/threads/id
async def get_thread_by_id(db: AsyncSession, user_id: str, thread_id: str) -> Thread | None:
    """
    Return a thread by ID, scoped to the user.
    Returns None if the thread doesn't exist OR belongs to another user,
    so the caller cannot tell the two cases apart (404 for both).
    """
    try:
        result = await db.execute(
            select(Thread).where(
                Thread.id == thread_id,
                Thread.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to fetch thread '{thread_id}': {str(e)}")

#patch/threads

async def rename_thread(db: AsyncSession, user_id: str, thread_id: str, title: str) -> Thread | None:
    """
    Rename a thread and mark it as titled, scoped to the user.
    Returns None if the thread doesn't exist or belongs to another user.
    """
    try:
        thread = await get_thread_by_id(db, user_id, thread_id)
        if thread is None:
            return None

        thread.title = title
        thread.is_titled = True
        await db.flush()
        await db.refresh(thread)
        logger.info(f"Thread renamed: {thread.id} → {title}")
        return thread
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to rename thread '{thread_id}': {str(e)}")

#delete/thread/id
async def delete_thread(db: AsyncSession, user_id: str, thread_id: str) -> bool:
    """
    Delete a thread by ID, scoped to the user.
    Returns True if a thread was deleted, False if it doesn't exist or belongs to another user.
    """
    try:
        result = await db.execute(
            delete(Thread).where(
                Thread.id == thread_id,
                Thread.user_id == user_id,
            )
        )
        await db.flush()
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Thread deleted: {thread_id}")
        return deleted
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to delete thread '{thread_id}': {str(e)}")