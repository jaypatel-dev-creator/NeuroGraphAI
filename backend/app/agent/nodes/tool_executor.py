from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

from app.agent.state import AgentState
from app.core.logging import get_logger

logger = get_logger(__name__)


async def tool_executor_node(state: AgentState, tools_by_name: dict) -> dict:
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls

    results = []

    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_input = tool_call["args"]
        tool_id = tool_call["id"]

        logger.info(f"Executing tool: {tool_name} | input: {tool_input}")

        tool: BaseTool = tools_by_name.get(tool_name)

        if not tool:
            output = f"Tool '{tool_name}' not found."
        else:
            try:
                if hasattr(tool, "ainvoke"):
                    output = await tool.ainvoke(tool_input)
                else:
                    output = tool.invoke(tool_input)
                output = str(output)
            except Exception as e:
                output = f"Tool execution error: {str(e)}"
                logger.error(f"Tool {tool_name} failed: {str(e)}")

        logger.info(f"Tool {tool_name} result: {output[:100]}")

        results.append(
            ToolMessage(
                content=output,
                tool_call_id=tool_id,
            )
        )

    return {"messages": results}