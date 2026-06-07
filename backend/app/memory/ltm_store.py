from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import UserProfile
from app.core.logging import get_logger

logger = get_logger(__name__)


async def get_profile(db: AsyncSession) -> list[UserProfile]:
    result = await db.execute(select(UserProfile).order_by(UserProfile.key))
    return list(result.scalars().all())


async def upsert_profile_entry(
    db: AsyncSession,
    key: str,
    value: str,
) -> UserProfile:
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


async def delete_profile(db: AsyncSession) -> None:
    await db.execute(delete(UserProfile))
    await db.flush()
    logger.info("LTM profile cleared.")


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