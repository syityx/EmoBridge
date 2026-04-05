from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from core.config import Settings
from schemas.chat import ChatMessageRequest, SessionMessage
from services.mcp_service import get_mcp_tools

# TODO：记忆持久化 & 管理（压缩、清理）
CHECKPOINTER = InMemorySaver()
logger = logging.getLogger(__name__)

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


def _stringify_tool_calls(tool_calls: object) -> list[dict[str, Any]]:
    if not isinstance(tool_calls, list):
        return []

    normalized: list[dict[str, Any]] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            normalized.append({"raw": str(call)})
            continue

        normalized.append(
            {
                "id": call.get("id"),
                "name": call.get("name"),
                "args": call.get("args"),
                "type": call.get("type"),
            }
        )
    return normalized


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
    tools: list[Any] | None = None,
):
    llm = build_llm(settings, temperature, stream=True)
    agent_tools = tools if tools is not None else await get_mcp_tools(settings)

    return create_agent(
        model=llm,
        tools=agent_tools,
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
    trace_enabled = settings.agent_stream_trace_enabled
    tools = await get_mcp_tools(settings)
    agent = await build_chat_agent(settings, payload.temperature, system_prompt, tools=tools)

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
        last_node = ""
        async for chunk, _metadata in agent.astream(
            {"messages": [{"role": "user", "content": payload.input_text}]},
            config=config,
            stream_mode="messages",
        ):
            if trace_enabled and isinstance(_metadata, dict):
                node = _metadata.get("langgraph_node")
                if node and node != last_node:
                    last_node = node
                    state_name = "tool" if node == "tools" else "model"
                    logger.error("[state:%s] %s", state_name, node)

            chunk_type = getattr(chunk, "type", "")
            if trace_enabled and chunk_type == "tool":
                tool_result = _normalize_chunk_content(getattr(chunk, "content", "")).strip()
                if tool_result:
                    logger.error("[tool-result] %s", tool_result)

            if not isinstance(chunk, (AIMessage, AIMessageChunk)):
                continue

            tool_calls = _stringify_tool_calls(getattr(chunk, "tool_calls", None))
            if trace_enabled and tool_calls:
                logger.error("[tool-call] %s", json.dumps(tool_calls, ensure_ascii=False))

            token = _normalize_chunk_content(chunk.content)
            if not token:
                continue
            assistant_parts.append(token)
            yield sse_event("token", {"token": token})

        assistant_text = "".join(assistant_parts).strip()
        if trace_enabled:
            logger.error("[final-answer] %s", assistant_text)
        yield sse_event("done", {"reply": assistant_text})
    except Exception as exc:
        yield sse_event("error", {"error": f"Model or MCP tool call failed: {exc}"})
