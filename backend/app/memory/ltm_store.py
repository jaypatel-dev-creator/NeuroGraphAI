from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserProfile
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import LTMException  # ← added

logger = get_logger(__name__)


#getting all entries
async def get_profile(db: AsyncSession) -> list[UserProfile]:
    try:
        result = await db.execute(select(UserProfile).order_by(UserProfile.key))
        return list(result.scalars().all())
    except Exception as e:
        raise LTMException(f"Failed to fetch LTM profile: {str(e)}")


#upsert based on environment
async def upsert_profile_entry(
    db: AsyncSession,
    key: str,
    value: str,
) -> UserProfile:
    settings = get_settings()

    try:
        if settings.database_url:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = (
                pg_insert(UserProfile)
                .values(key=key, value=value)
                .on_conflict_do_update(
                    index_elements=["key"],
                    set_={"value": value},
                )
            )
        else:
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            stmt = (
                sqlite_insert(UserProfile)
                .values(key=key, value=value)
                .on_conflict_do_update(
                    index_elements=["key"],
                    set_={"value": value},
                )
            )

        await db.execute(stmt)
        await db.flush()

        result = await db.execute(
            select(UserProfile).where(UserProfile.key == key)
        )
        entry = result.scalar_one()
        logger.info(f"LTM upsert — key: {key}")
        return entry
    except LTMException:
        raise  # ← don't re-wrap, let it propagate as-is
    except Exception as e:
        raise LTMException(f"Failed to upsert LTM entry '{key}': {str(e)}")


#deleting all entries
async def delete_profile(db: AsyncSession) -> None:
    try:
        await db.execute(delete(UserProfile))
        await db.flush()
        logger.info("LTM profile cleared.")
    except Exception as e:
        raise LTMException(f"Failed to clear LTM profile: {str(e)}")


#deleting specific entry
async def delete_profile_entry(db: AsyncSession, key: str) -> bool:
    try:
        result = await db.execute(
            select(UserProfile).where(UserProfile.key == key)
        )
        entry = result.scalar_one_or_none()

        if not entry:
            return False

        await db.execute(delete(UserProfile).where(UserProfile.key == key))
        await db.flush()
        logger.info(f"LTM entry deleted — key: {key}")
        return True
    except LTMException:
        raise
    except Exception as e:
        raise LTMException(f"Failed to delete LTM entry '{key}': {str(e)}")


#updating specific entry
async def update_profile_entry(db: AsyncSession, key: str, value: str) -> UserProfile | None:
    try:
        result = await db.execute(select(UserProfile).where(UserProfile.key == key))
        entry = result.scalar_one_or_none()

        if not entry:
            return None

        entry.value = value
        await db.flush()
        return entry
    except LTMException:
        raise
    except Exception as e:
        raise LTMException(f"Failed to update LTM entry '{key}': {str(e)}")