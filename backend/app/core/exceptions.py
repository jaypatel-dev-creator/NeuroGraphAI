from fastapi import Request
from fastapi.responses import JSONResponse

#creating custom exception classes 
class NeuroGraphException(Exception):# base exception class
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


class LTMException(NeuroGraphException):
    pass


# --- Exception Handlers ---

async def neurograph_exception_handler(
    request: Request,
    exc: NeuroGraphException,
) -> JSONResponse:
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
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred.",
        },
    )