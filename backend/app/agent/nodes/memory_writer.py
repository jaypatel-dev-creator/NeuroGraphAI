import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.memory.ltm_store import upsert_profile_entry
from app.core.logging import get_logger

logger = get_logger(__name__)

MEMORY_UPDATE_PREFIX = "MEMORY_UPDATE:" #if no MEMORY_UPDATE in resopnse, then skip preprocessing entirely 

MEMORY_UPDATE_PATTERN = re.compile( #regex to extract key and value 
    r"MEMORY_UPDATE:\s+key=(\S+)\s+value=(.+)"
)


async def memory_writer_node(state: AgentState, db: AsyncSession) -> dict:
    last_message = state["messages"][-1] #extracting latest message from state which will be AIMessage cause this node will be called after llm generates response 

    # Gemini can return content as list or string
    raw_content = last_message.content #extracting content that actually contains response of llm and so any memory uupdate line 
    if isinstance(raw_content, list):
        content = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in raw_content
        )
    else:
        content = raw_content or ""

    if not content or MEMORY_UPDATE_PREFIX not in content: #if llm does not even generated anything or MEMORY_UPDATE line is not present then skip preprocessing entirely 
        return {} #direct return empty dict and exit 

    try: 
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if not line.startswith(MEMORY_UPDATE_PREFIX):
                continue

          
            match = MEMORY_UPDATE_PATTERN.match(line)
            if not match:
                logger.warning(f"Skipping malformed MEMORY_UPDATE line: {line!r}")
                continue

            key = match.group(1).strip()
            value = match.group(2).strip()

            if not key or not value:
                logger.warning(f"Skipping MEMORY_UPDATE with empty key or value: {line!r}")
                continue

            await upsert_profile_entry(db, key, value)
            logger.info(f"LTM updated — key: {key}, value: {value}")

    except Exception as e:
        logger.error(f"Memory writer failed: {str(e)}")

    return {}