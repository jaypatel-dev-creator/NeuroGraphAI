from functools import partial

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.reasoner import reasoner_node
from app.agent.nodes.tool_executor import tool_executor_node
from app.agent.tools.calculator import calculator
from app.agent.tools.search import get_search_tool
from app.agent.tools.weather import weather
from app.agent.tools.finance import finance
from app.agent.tools.datetime_tool import get_datetime
from app.core.logging import get_logger

logger = get_logger(__name__)

_builder: StateGraph | None = None


def get_tools() -> list:
    return [
        calculator,
        get_search_tool(),
        weather,
        finance,
        get_datetime,
    ]


def get_tools_by_name(tools: list) -> dict:
    return {tool.name: tool for tool in tools}


def should_use_tool(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tool_executor"
    return "end"


def compile_graph() -> None:
    global _builder

    tools = get_tools()
    tools_by_name = get_tools_by_name(tools)

    builder = StateGraph(AgentState)

    builder.add_node(
        "reasoner",
        partial(reasoner_node, tools=tools),
    )
    builder.add_node(
        "tool_executor",
        partial(tool_executor_node, tools_by_name=tools_by_name),
    )

    builder.set_entry_point("reasoner")

    builder.add_conditional_edges(
        "reasoner",
        should_use_tool,
        {
            "tool_executor": "tool_executor",
            "end": END,
        },
    )
    builder.add_edge("tool_executor", "reasoner")

    _builder = builder
    logger.info("LangGraph ReAct graph builder ready.")


def get_graph_with_checkpointer(checkpointer):
    if _builder is None:
        raise RuntimeError("Graph builder not initialized.")
    return _builder.compile(checkpointer=checkpointer)