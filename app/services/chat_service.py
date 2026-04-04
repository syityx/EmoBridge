from __future__ import annotations

import json
from typing import AsyncIterator

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from core.config import Settings
from schemas.chat import ChatMessageRequest, SessionMessage
from services.mcp_service import get_mcp_tools


CHECKPOINTER = InMemorySaver()

# TODO(shared-user-memory):
# Keep full conversation memory isolated by `user_id + session_id`.
# If we add cross-session memory later, introduce a separate user-level
# memory layer keyed only by `user_id` for stable profile facts
# (for example name, preferences, long-term background), rather than
# sharing full chat history across sessions.


def build_llm(settings: Settings, temperature: float, stream: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=temperature,
        streaming=stream,
    )


def _normalize_chunk_content(content: object) -> str:
    if not content:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )

    return str(content)


def _message_role(message: BaseMessage) -> str:
    message_type = getattr(message, "type", "")
    if message_type == "human":
        return "user"
    if message_type == "ai":
        return "assistant"
    return ""


def get_thread_messages(session_id: str) -> list[SessionMessage]:
    config = {"configurable": {"thread_id": session_id}}
    checkpoint_tuple = CHECKPOINTER.get_tuple(config)
    if checkpoint_tuple is None:
        return []

    raw_messages = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
    result: list[SessionMessage] = []
    for message in raw_messages:
        if not isinstance(message, BaseMessage):
            continue
        role = _message_role(message)
        if not role:
            continue
        content = _normalize_chunk_content(getattr(message, "content", "")).strip()
        if not content:
            continue
        result.append(SessionMessage(role=role, content=content))
    return result


async def build_chat_agent(
    settings: Settings,
    temperature: float,
    system_prompt: str,
):
    llm = build_llm(settings, temperature, stream=True)
    tools = await get_mcp_tools(settings)

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=CHECKPOINTER,
    )


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_chat_chunks(
    settings: Settings,
    thread_id: str,
    session_id: str,
    payload: ChatMessageRequest,
) -> AsyncIterator[str]:
    system_prompt = payload.system_prompt or settings.default_system_prompt
    agent = await build_chat_agent(settings, payload.temperature, system_prompt)

    config = {"configurable": {"thread_id": thread_id}}
    assistant_parts: list[str] = []

    yield sse_event(
        "start",
        {
            "session_id": session_id,
            "model": settings.model_name,
            "mcp_enabled": settings.mcp_server_enabled,
        },
    )

    try:
        async for chunk, _metadata in agent.astream(
            {"messages": [{"role": "user", "content": payload.input_text}]},
            config=config,
            stream_mode="messages",
        ):
            if not isinstance(chunk, (AIMessage, AIMessageChunk)):
                continue

            token = _normalize_chunk_content(chunk.content)
            if not token:
                continue
            assistant_parts.append(token)
            yield sse_event("token", {"token": token})

        assistant_text = "".join(assistant_parts).strip()
        yield sse_event("done", {"reply": assistant_text})
    except Exception as exc:
        yield sse_event("error", {"error": f"Model or MCP tool call failed: {exc}"})
