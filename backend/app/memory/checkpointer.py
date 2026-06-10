
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# local==> save checkpoints in sqlite 
def get_db_path() -> str:
    settings = get_settings()
    return settings.checkpoint_db_path if not settings.database_url else ""

#prod==> save checkpoints in postgre
def use_postgres_checkpointer() -> bool:
    settings = get_settings()
    return bool(settings.database_url)