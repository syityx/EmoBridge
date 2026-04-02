from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    input_text: str = Field(..., min_length=1, max_length=4000, description="当前用户输入")
    system_prompt: str | None = Field(default=None, max_length=2000, description="系统提示词")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="生成温度")


class SessionMessage(BaseModel):
    role: str
    content: str


class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: list[SessionMessage]
