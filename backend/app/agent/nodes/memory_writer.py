from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.memory.ltm_store import upsert_profile_entry
from app.core.logging import get_logger

logger = get_logger(__name__)

MEMORY_UPDATE_PREFIX = "MEMORY_UPDATE:"


async def memory_writer_node(state: AgentState, db: AsyncSession) -> dict:
    last_message = state["messages"][-1]

    # Gemini can return content as list or string
    raw_content = last_message.content
    if isinstance(raw_content, list):
        content = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in raw_content
        )
    else:
        content = raw_content or ""

    if not content or MEMORY_UPDATE_PREFIX not in content:
        return {}

    try:
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith(MEMORY_UPDATE_PREFIX):
                parts = line.replace(MEMORY_UPDATE_PREFIX, "").strip()
                key_part = [p for p in parts.split() if p.startswith("key=")]
                if key_part and "value=" in line:
                    key = key_part[0].replace("key=", "").strip()
                    value = line.split("value=", 1)[1].strip()
                    await upsert_profile_entry(db, key, value)
                    logger.info(f"LTM updated — key: {key}, value: {value}")
    except Exception as e:
        logger.error(f"Memory writer failed: {str(e)}")

    return {}