import re
from sqlalchemy.ext.asyncio import AsyncSession
from app.agent.state import AgentState
from app.memory.ltm_store import upsert_profile_entry
from app.core.logging import get_logger

logger = get_logger(__name__)

MEMORY_UPDATE_PREFIX = "MEMORY_UPDATE:"

# regex to extract key and value from sentinel line
# matches: MEMORY_UPDATE: key=<key> value=<value>
MEMORY_UPDATE_PATTERN = re.compile(
    r"MEMORY_UPDATE:\s+key=(\S+)\s+value=(.+)"
)


async def memory_writer_node(state: AgentState, db: AsyncSession, user_id: str) -> list[str]:
    # reasoner always runs last — final message is always AIMessage
    last_message = state["messages"][-1]

    # normalize content — Gemini sometimes returns list of parts, sometimes plain string
    raw_content = last_message.content
    if isinstance(raw_content, list):
        content = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in raw_content
        )
    else:
        content = raw_content or ""

    # early exit — skip processing if no sentinel present
    if not content or MEMORY_UPDATE_PREFIX not in content:
        return []

    saved_keys = []

    try:
        lines = content.split("\n")  # LLM puts each MEMORY_UPDATE on its own line
        for line in lines:
            line = line.strip()
            if not line.startswith(MEMORY_UPDATE_PREFIX):
                continue  # skip normal response lines

            match = MEMORY_UPDATE_PATTERN.match(line)
            if not match:
                # sentinel found but format is wrong — log and skip, don't crash
                logger.warning(f"Skipping malformed MEMORY_UPDATE line: {line!r}")
                continue

            key = match.group(1).strip()
            value = match.group(2).strip()

            if not key or not value:
                logger.warning(f"Skipping MEMORY_UPDATE with empty key or value: {line!r}")
                continue

            # upsert — insert if key doesn't exist for this user, update if it does
            await upsert_profile_entry(db, user_id, key, value)
            logger.info(f"LTM updated — user: {user_id} key: {key}")
            saved_keys.append(key)

    except Exception as e:
        # never crash the response flow — memory write failure is non-fatal
        logger.error(f"Memory writer failed for user {user_id}: {str(e)}", exc_info=True)

    # returned to chat_service.py to fire memory_update SSE event to frontend
    return saved_keys