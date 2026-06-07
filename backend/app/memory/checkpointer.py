from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_checkpoint_db_path: str = ""
_use_postgres: bool = False


async def init_checkpointer() -> None:
    global _checkpoint_db_path, _use_postgres
    settings = get_settings()

    if settings.database_url:
        _use_postgres = True
        logger.info("STM checkpointer configured — mode: Postgres")
    else:
        _checkpoint_db_path = settings.checkpoint_db_path
        _use_postgres = False
        logger.info(f"STM checkpointer configured — path: {_checkpoint_db_path}")


def get_db_path() -> str:
    return _checkpoint_db_path


def use_postgres_checkpointer() -> bool:
    return _use_postgres