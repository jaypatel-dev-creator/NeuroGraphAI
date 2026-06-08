from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    # Full conversation history — add_messages reducer
    # appends new messages instead of overwriting
    messages: Annotated[list[BaseMessage], add_messages]

    # LTM profile injected at start of each conversation
    # as a formatted string into system prompt
    ltm_context: str