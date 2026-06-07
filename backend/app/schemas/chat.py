from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    thread_id: str
    message: str


class ToolCall(BaseModel):
    tool_name: str
    tool_input: dict
    tool_output: str


class ChatMessage(BaseModel):
    role: str                           # "human" | "ai" | "tool"
    content: str
    tool_call: Optional[ToolCall] = None


class ChatHistoryRead(BaseModel):
    thread_id: str
    messages: list[ChatMessage]