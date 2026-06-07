from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.memory.ltm_store import (
    get_profile,
    upsert_profile_entry,
    delete_profile,
    delete_profile_entry,
)
from app.schemas.memory import ProfileRead, ProfileEntry, ProfileUpsert, ProfileEntryUpdate
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/profile", response_model=ProfileRead)
async def read_profile(db: AsyncSession = Depends(get_db)):
    entries = await get_profile(db)
    return ProfileRead(
        entries=[ProfileEntry.model_validate(e) for e in entries]
    )


@router.put("/profile", response_model=ProfileEntry)
async def upsert_profile(
    payload: ProfileUpsert,
    db: AsyncSession = Depends(get_db),
):
    entry = await upsert_profile_entry(db, payload.key, payload.value)
    return ProfileEntry.model_validate(entry)


@router.patch("/profile/{key}", response_model=ProfileEntry)
async def update_profile_entry(
    key: str,
    payload: ProfileEntryUpdate,
    db: AsyncSession = Depends(get_db),
):
    entry = await upsert_profile_entry(db, key, payload.value)
    return ProfileEntry.model_validate(entry)


@router.delete("/profile/{key}", status_code=204)
async def delete_single_profile_entry(
    key: str,
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_profile_entry(db, key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Profile entry '{key}' not found.")


@router.delete("/profile", status_code=204)
async def clear_profile(db: AsyncSession = Depends(get_db)):
    await delete_profile(db)