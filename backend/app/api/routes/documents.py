from typing import List

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.models import User
from app.services.document_service import (
    ingest_and_persist,
    list_documents,
    delete_document,
)
from app.schemas.document import DocumentRead, DocumentUploadResponse

router = APIRouter()


@router.post("/upload", response_model=List[DocumentUploadResponse])
async def upload_documents(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = []

    for file in files:
        content = await file.read()

        result = await ingest_and_persist(
            db=db,
            user_id=current_user.id,
            content=content,
            filename=file.filename,
            content_type=file.content_type,
        )

        if result.already_existed:
            message = f"{result.filename} already indexed — ready to query"
        else:
            message = f"{result.filename} indexed successfully — {result.chunk_count} chunks created"

        results.append(DocumentUploadResponse(
            filename=result.filename,
            sha256=result.sha256,
            chunk_count=result.chunk_count,
            already_existed=result.already_existed,
            message=message,
        ))

    return results


@router.get("/", response_model=List[DocumentRead])
async def list_documents_route(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = await list_documents(db, current_user.id)
    return [DocumentRead.model_validate(d) for d in docs]

@router.delete("/{sha256}", status_code=204)
async def delete_document_route(
    sha256: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await delete_document(db, current_user.id, sha256)