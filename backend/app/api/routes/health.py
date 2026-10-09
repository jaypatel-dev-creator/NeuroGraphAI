from fastapi import APIRouter, Response
from sqlalchemy import text

from app.db.base import AsyncSessionLocal
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", tags=["Health"])
async def health(response: Response):
    """Liveness check. Returns 200 if the database is reachable, 503 if not."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check DB ping failed: {e}")
        response.status_code = 503
        return {"status": "degraded", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}