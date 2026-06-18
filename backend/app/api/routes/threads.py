from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.thread import ThreadCreate, ThreadRead, ThreadUpdate
from app.core.logging import get_logger
from app.services.thread_service import (
    create_thread,
    list_threads,
    get_thread_by_id,
    rename_thread,
    delete_thread,
)

logger = get_logger(__name__)
router = APIRouter()

#post thread 
@router.post("", response_model=ThreadRead, status_code=201)
async def create_thread_route(
    payload: ThreadCreate,
    db: AsyncSession = Depends(get_db),
):
    thread = await create_thread(db, payload.title)
    return ThreadRead.model_validate(thread)


#get all threads 
@router.get("", response_model=list[ThreadRead])
async def list_threads_route(
    db: AsyncSession = Depends(get_db),
):
    threads = await list_threads(db)
    return [ThreadRead.model_validate(t) for t in threads]

#get thread by id 
@router.get("/{thread_id}", response_model=ThreadRead)
async def get_thread_route(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
):
    thread = await get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")
    return ThreadRead.model_validate(thread)

#update thread 
@router.patch("/{thread_id}", response_model=ThreadRead)
async def rename_thread_route(
    thread_id: str,
    payload: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
):
    thread = await get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")
    thread = await rename_thread(db, thread, payload.title)
    return ThreadRead.model_validate(thread)

#delete thread 
@router.delete("/{thread_id}", status_code=204)
async def delete_thread_route(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
):
    thread = await get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")
    await delete_thread(db, thread_id)