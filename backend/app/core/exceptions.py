from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


#Base class 
class NeuroGraphException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AgentException(NeuroGraphException):
    pass

class ThreadNotFoundException(NeuroGraphException):
    def __init__(self, thread_id: str):
        super().__init__(
            message=f"Thread '{thread_id}' not found.",
            status_code=404,
        )

class ProfileEntryNotFoundException(NeuroGraphException):
    def __init__(self, key: str):
        super().__init__(
            message=f"Profile entry '{key}' not found.",
            status_code=404,
        )

class LTMException(NeuroGraphException):
    pass

class RAGException(NeuroGraphException):
    pass

class DocumentNotFoundException(NeuroGraphException):
    def __init__(self, sha256: str):
        super().__init__(
            message=f"Document '{sha256}' not found.",
            status_code=404,
        )


# --- Exception Handlers ---

async def neurograph_exception_handler(
    request: Request,
    exc: NeuroGraphException,
) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error(
            f"{exc.__class__.__name__} on {request.method} {request.url.path}: {exc.message}",
            exc_info=True,
        )
    else:
        logger.warning(
            f"{exc.__class__.__name__} on {request.method} {request.url.path}: {exc.message}"
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
        },
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred.",
        },
    )