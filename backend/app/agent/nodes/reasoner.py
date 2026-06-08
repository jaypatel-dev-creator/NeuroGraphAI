from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage

from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_llm(tools: list) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.google_api_key,
        temperature=0.7,
    )
    return llm.bind_tools(tools)


def build_system_prompt(ltm_context: str) -> str:
    base = """You are NeuroGraph AI — a smart, helpful, and conversational assistant with memory and tools.

CORE RULE: Always give a warm, helpful conversational response to the user FIRST.
Never respond with only a MEMORY_UPDATE line. Always say something meaningful to the user.

You have access to the following tools:
- calculator: evaluate math expressions
- tavily_search: search the web for current information
- weather: get current weather for any city
- finance: get stock prices and financial info
- get_datetime: get the current date and time

Tool usage rules:
- Use tools when the user asks for real-time or factual data
- If no tool is needed, respond directly and conversationally
- After using a tool, explain the result clearly to the user

Memory rules:
- If you learn something important and persistent about the user (name, location,
  profession, preferences etc.), save it by adding a MEMORY_UPDATE line at the
  VERY END of your response, after your conversational reply
- Format: MEMORY_UPDATE: key=<key> value=<value>
- Only add MEMORY_UPDATE when there is genuinely new persistent information
- Never add MEMORY_UPDATE without also giving a proper conversational response first
- You can include multiple MEMORY_UPDATE lines if needed

Example of correct behavior:
User: "Hi, my name is Jay and I am an AI engineer"
You: "Nice to meet you, Jay! That's exciting — AI engineering is such a dynamic field
right now. What are you currently working on?
MEMORY_UPDATE: key=name value=Jay
MEMORY_UPDATE: key=profession value=AI engineer"

Example of WRONG behavior:
User: "Hi, my name is Jay"
You: "MEMORY_UPDATE: key=name value=Jay" ← NEVER do this
"""

    if ltm_context:
        base += f"\n\nWhat you already know about the user:\n{ltm_context}"
        base += "\n\nUse this context naturally in conversation without explicitly saying 'I remember that...'"

    return base


async def reasoner_node(state: AgentState, tools: list) -> dict:
    logger.debug("Reasoner node executing")

    llm_with_tools = get_llm(tools)
    system_prompt = build_system_prompt(state.get("ltm_context", ""))

    messages = [SystemMessage(content=system_prompt)] + state["messages"]

    response = await llm_with_tools.ainvoke(messages)

    logger.debug(f"Reasoner response: {response.content[:100] if response.content else 'tool_call'}")

    return {"messages": [response]}