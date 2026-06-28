from pathlib import Path
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import (
    NeuroGraphException,
    neurograph_exception_handler,
    generic_exception_handler,)

from app.api.routes import chat, threads, memory, health
from app.api.routes import documents
from app.db.base import engine, Base
from app.db import models  # noqa: F401

from app.agent.graph import compile_graph
from app.rag.store import init_store

logger = get_logger(__name__)


@asynccontextmanager #creates lifespan function to asynchronous context manager 
async def lifespan(app: FastAPI):
    # --- Startup ---
    settings = get_settings() 

    setup_logging(settings.app_env)
    logger.info("Starting NeuroGraph AI...")

    # LangSmith
    os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    logger.info(f"LangSmith tracing active — project: {settings.langchain_project}")

    # Tavily
    os.environ["TAVILY_API_KEY"] = settings.tavily_api_key
    logger.info("Tavily API key set.")

    # Data directories
    if not settings.database_url: #for local, create neurograph.db file and checkpoints.db file
        Path(settings.sqlite_db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(settings.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"SQLite mode — db: {settings.sqlite_db_path}")
        logger.info(f"Checkpoint db: {settings.checkpoint_db_path}")
    else: #for prod, no need to create db files 
        logger.info("Postgres mode — using DATABASE_URL")

    # DB table creation
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified.")

    # Agent graph compilation
    compile_graph()

    # RAG vector store initialization — ChromaDB local, Pinecone prod (env-driven)
    init_store()

    logger.info("NeuroGraph AI is ready.")
    yield

    # --- Shutdown ---
    await engine.dispose()
    logger.info("Shutting down NeuroGraph AI...")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="NeuroGraph AI",
        description="LangGraph ReAct agent with STM, LTM, and Tools",
        version="1.0.0",
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

#binding exception handlers 
    app.add_exception_handler(NeuroGraphException, neurograph_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
#binding routers 
    app.include_router(chat.router, prefix="/chat", tags=["Chat"])
    app.include_router(threads.router, prefix="/threads", tags=["Threads"])
    app.include_router(memory.router, prefix="/memory", tags=["Memory"])
    app.include_router(documents.router, prefix="/documents", tags=["Documents"])
    app.include_router(health.router)

    return app


app = create_app()