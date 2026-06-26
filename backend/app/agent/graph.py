from functools import partial

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.reasoner import reasoner_node, build_llm_with_tools
from app.agent.nodes.tool_executor import tool_executor_node
from app.agent.tools.calculator import calculator
from app.agent.tools.search import get_search_tool
from app.agent.tools.weather import weather
from app.agent.tools.finance import finance
from app.agent.tools.datetime_tool import get_datetime
from app.core.logging import get_logger
from app.core.exceptions import AgentException  # ← added

logger = get_logger(__name__)

_builder: StateGraph | None = None #module level private builder variable to store graph structure 


#get all the tools in list 
def get_tools() -> list[BaseTool]:
    return [
        calculator,#passed by reference 
        get_search_tool(),#called because get_search_tool() is factory function 
        weather,#passed by reference 
        finance,#passed by reference 
        get_datetime,#passed by reference 
    ]

#get all the tools in dict 
def get_tools_by_name(tools: list[BaseTool]) -> dict[str, BaseTool]:
    return {tool.name: tool for tool in tools}

#conditional edge function  (route function)
def should_use_tool(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tool_executor"
    return "end"

#creating  graph structure  (at startup once)
def compile_graph() -> None:
    global _builder#accessing module level variable 

    tools = get_tools()#needed by reasoner_node in reasoner.py as well as build llm with tools 
    tools_by_name = get_tools_by_name(tools) #needed by tool_executor node  in tool_executor.py

    llm_with_tools = build_llm_with_tools(tools) #binding llm with tools 

    builder = StateGraph(AgentState)

    builder.add_node(
        "reasoner",
        partial(reasoner_node, llm_with_tools=llm_with_tools, tools=tools),
    )
    builder.add_node(
        "tool_executor",
        partial(tool_executor_node, tools_by_name=tools_by_name),
    )

    builder.set_entry_point("reasoner")#START=reasoner node 


    builder.add_conditional_edges(
        "reasoner",
        should_use_tool,
        {
            "tool_executor": "tool_executor",
            "end": END,
        },
    )
    builder.add_edge("tool_executor", "reasoner") #actual REACT loop created here 

    _builder = builder #store graph structure in module level _builder variable so same structure is used each request 
    logger.info("LangGraph ReAct graph builder ready.")

#compile graph each request 
def get_graph_with_checkpointer(checkpointer):
    if _builder is None: #access module level _builder and compile fresh per request 
        raise AgentException("Graph builder not initialized. Call compile_graph() on startup.")  # ← changed
    return _builder.compile(checkpointer=checkpointer)