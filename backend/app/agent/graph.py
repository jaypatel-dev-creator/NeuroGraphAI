from functools import partial

from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.reasoner import reasoner_node
from app.agent.nodes.tool_executor import tool_executor_node
from app.agent.tools.calculator import calculator
from app.agent.tools.search import get_search_tool
from app.agent.tools.weather import weather
from app.agent.tools.finance import finance
from app.agent.tools.datetime_tool import get_datetime
from app.agent.tools.document_search import make_document_search_tool
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import AgentException

logger = get_logger(__name__)

_initialized: bool = False  # guards against get_graph_with_checkpointer being called before startup

# --- Module-level singletons — built once at startup, reused across all requests ---
# These tools are stateless and user-agnostic — no reason to rebuild per request
_static_tools: list[BaseTool] = []
_base_llm: ChatGoogleGenerativeAI | None = None  # LLM client without tools bound


def _build_static_tools() -> list[BaseTool]:
    """Stateless tools — same for every user, every request."""
    return [
        calculator,
        get_search_tool(),
        weather,
        finance,
        get_datetime,
    ]


def get_tools(user_id: str) -> list[BaseTool]:
    """
    Build the full tool list for a specific request.
    Reuses module-level static tools — only document_search is built per-request
    because it is a closure that captures user_id and cannot be shared across users.
    """
    return _static_tools + [make_document_search_tool(user_id)]


def get_tools_by_name(tools: list[BaseTool]) -> dict[str, BaseTool]:
    return {tool.name: tool for tool in tools}


def should_use_tool(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tool_executor"
    return "end"


def compile_graph() -> None:
    global _initialized, _static_tools, _base_llm

    # Build static tools once — reused for every request
    _static_tools = _build_static_tools()

    # Build base LLM client once — bind_tools() called per-request with user-scoped tool list
    settings = get_settings()
    _base_llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=settings.google_api_key,
        temperature=0.7,
    )

    #validation run only 
    tools = get_tools("__startup__")
    tools_by_name = get_tools_by_name(tools)
    llm_with_tools = _base_llm.bind_tools(tools)
   #creating graph structure 
    builder = StateGraph(AgentState)
    builder.add_node("reasoner", partial(reasoner_node, llm_with_tools=llm_with_tools, tools=tools))
    builder.add_node("tool_executor", partial(tool_executor_node, tools_by_name=tools_by_name))
    builder.set_entry_point("reasoner")
    builder.add_conditional_edges("reasoner", should_use_tool, {"tool_executor": "tool_executor", "end": END})
    builder.add_edge("tool_executor", "reasoner")#actual react loop created here 
    # builder.compile() intentionally NOT called — no checkpointer available at startup

    _initialized = True
    logger.info("LangGraph ReAct graph builder ready.")


def get_graph_with_checkpointer(checkpointer, user_id: str):
  # safety gate — ensures compile_graph() ran successfully at startup
    if not _initialized:
        raise AgentException("Graph not initialized. Call compile_graph() on startup.")

    # Only document_search is built fresh — all other tools reused from _static_tools singleton 
    tools = get_tools(user_id)
    tools_by_name = get_tools_by_name(tools)
#uses the same gemini client singleton
    llm_with_tools = _base_llm.bind_tools(tools)

    graph = StateGraph(AgentState)
    graph.add_node("reasoner", partial(reasoner_node, llm_with_tools=llm_with_tools, tools=tools))
    graph.add_node("tool_executor", partial(tool_executor_node, tools_by_name=tools_by_name))
    graph.set_entry_point("reasoner")
    graph.add_conditional_edges("reasoner", should_use_tool, {"tool_executor": "tool_executor", "end": END})
    graph.add_edge("tool_executor", "reasoner")

    return graph.compile(checkpointer=checkpointer)