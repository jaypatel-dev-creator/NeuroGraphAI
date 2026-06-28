from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.models import Document
from app.rag.ingestor import ingest_file, IngestResult
from app.rag.store import get_store
from app.core.logging import get_logger
from app.core.exceptions import RAGException

logger = get_logger(__name__)


async def ingest_and_persist(
    db: AsyncSession,
    content: bytes,
    filename: str,
    content_type: str,
) -> IngestResult:
    """
    Run the full ingest pipeline for a single file and persist metadata to DB.
    If duplicate (already_existed=True), skips DB write — document row already exists.
    Returns IngestResult so the route can build the response message.
    """
    try:
        result = await ingest_file(
            content=content,
            filename=filename,
            content_type=content_type,
        )

        if not result.already_existed:
            doc = Document(
                sha256=result.sha256,
                filename=result.filename,
                chunk_count=result.chunk_count,
            )
            db.add(doc)
            await db.flush()
            logger.info(f"Document persisted to DB: {filename} ({result.sha256[:8]}...)")

        return result

    except RAGException:
        raise  # don't re-wrap — let it propagate as-is to global handler
    except Exception as e:
        raise RAGException(f"Failed to ingest '{filename}': {str(e)}")


async def list_documents(db: AsyncSession) -> list[Document]:
    """Return all documents ordered by most recently uploaded."""
    try:
        result = await db.execute(
            select(Document).order_by(Document.uploaded_at.desc())
        )
        return list(result.scalars().all())
    except Exception as e:
        raise RAGException(f"Failed to list documents: {str(e)}")


async def get_document_by_sha256(db: AsyncSession, sha256: str) -> Document | None:
    """Return a document by sha256 or None if not found."""
    try:
        result = await db.execute(
            select(Document).where(Document.sha256 == sha256)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        raise RAGException(f"Failed to fetch document '{sha256[:8]}...': {str(e)}")


async def delete_document(db: AsyncSession, sha256: str) -> None:
    """
    Hard delete — removes all chunks from vector store and the document row from DB.
    Caller must verify document exists before calling this.
    """
    try:
        store = get_store()
        store.delete_by_sha256(sha256)
        await db.execute(delete(Document).where(Document.sha256 == sha256))
        await db.flush()
        logger.info(f"Document deleted from vector store and DB: {sha256[:8]}...")
    except RAGException:
        raise
    except Exception as e:
        raise RAGException(f"Failed to delete document '{sha256[:8]}...': {str(e)}")