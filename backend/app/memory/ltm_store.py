from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserProfile
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

#getting all enteries 
async def get_profile(db: AsyncSession) -> list[UserProfile]:
    result = await db.execute(select(UserProfile).order_by(UserProfile.key))
    return list(result.scalars().all())

#upsert based on environment 
async def upsert_profile_entry(
    db: AsyncSession,
    key: str,
    value: str,
) -> UserProfile:
    settings = get_settings()

    if settings.database_url:
        # Production — Postgres dialect
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
        # Local dev — SQLite dialect
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

#deleting all enteries 
async def delete_profile(db: AsyncSession) -> None:
    await db.execute(delete(UserProfile))
    await db.flush()
    logger.info("LTM profile cleared.")

#deleting specific entry
async def delete_profile_entry(db: AsyncSession, key: str) -> bool:
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

#updating specific entry 
async def update_profile_entry(db: AsyncSession, key: str, value: str) -> UserProfile | None:
    result = await db.execute(select(UserProfile).where(UserProfile.key == key))
    entry = result.scalar_one_or_none()

    if not entry:
        return None

    entry.value = value
    await db.flush()
    return entry
