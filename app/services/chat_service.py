from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware, ToolRetryMiddleware
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_openai import ChatOpenAI
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from core.config import Settings
from schemas.chat import ChatMessageRequest, SessionMessage
from services.mcp_service import get_mcp_tools

logger = logging.getLogger(__name__)
MAX_FULL_ROUNDS = 10
MAX_FULL_MESSAGES = MAX_FULL_ROUNDS * 2
SUMMARY_TRIGGER_TOKENS = 4000

_AGENT_CHECKPOINTER = InMemorySaver()
_LONG_TERM_STORE = InMemoryStore()
_SANITIZE_KEY_PATTERN = re.compile(r"[^a-zA-Z0-9_-]+")


@dataclass
class ChatRuntimeContext:
    user_id: str

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


def build_summary_llm(settings: Settings, temperature: float, stream: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.summary_model_name,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=temperature,
        streaming=stream,
    )


def _extract_user_id(thread_id: str) -> str:
    if ":" in thread_id:
        user_id, _session_id = thread_id.split(":", 1)
        return user_id
    return thread_id


def _build_user_memory_namespace(user_id: str) -> tuple[str, str, str]:
    return ("users", user_id, "profile")


def _normalize_memory_key(value: str) -> str:
    normalized = _SANITIZE_KEY_PATTERN.sub("_", value.strip().lower()).strip("_")
    return normalized or "memory"


@tool
def save_long_term_memory(
    category: str,
    key: str,
    value: str,
    reason: str,
    runtime: ToolRuntime[ChatRuntimeContext],
) -> str:
    """Save durable user facts (preferences/profile/constraints) into long-term memory."""
    category_value = category.strip()
    key_value = key.strip()
    fact_value = value.strip()
    reason_value = reason.strip()
    if not category_value or not key_value or not fact_value:
        return "保存失败：category、key、value 不能为空。"

    user_id = runtime.context.user_id
    namespace = _build_user_memory_namespace(user_id)
    record_key = f"{_normalize_memory_key(category_value)}:{_normalize_memory_key(key_value)}"
    current_time = datetime.now(timezone.utc).isoformat()

    runtime.store.put(
        namespace,
        record_key,
        {
            "category": category_value,
            "key": key_value,
            "value": fact_value,
            "reason": reason_value,
            "updated_at": current_time,
        },
    )
    return f"已保存长期记忆: {category_value}/{key_value}"


@tool
def list_long_term_memories(runtime: ToolRuntime[ChatRuntimeContext]) -> str:
    """List stored long-term user memories before answering preference-related questions."""
    user_id = runtime.context.user_id
    namespace = _build_user_memory_namespace(user_id)
    items = runtime.store.search(namespace)
    if not items:
        return "当前没有长期记忆。"

    lines: list[str] = []
    for item in items[:20]:
        value = item.value if isinstance(item.value, dict) else {}
        category = str(value.get("category", "unknown"))
        key = str(value.get("key", item.key))
        memory_value = str(value.get("value", ""))
        updated_at = str(value.get("updated_at", ""))
        lines.append(f"- {category}/{key}: {memory_value} (updated_at={updated_at})")
    return "\n".join(lines)


LONG_TERM_MEMORY_POLICY = (
    "你有长期记忆工具。遇到稳定且可复用的用户信息时必须保存，"
    "例如称呼偏好、语言偏好、表达风格偏好、固定约束、长期目标。"
    "调用 save_long_term_memory 时请输出结构化字段：category、key、value、reason。"
    "当问题与个性化偏好有关时，先调用 list_long_term_memories 再回答。"
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


def _normalize_message_role(message: BaseMessage) -> str | None:
    if isinstance(message, (AIMessage, AIMessageChunk)):
        return "assistant"

    message_type = getattr(message, "type", "")
    if message_type in {"human", "user"}:
        return "user"
    if message_type == "ai":
        return "assistant"
    if message_type == "system":
        return "system"
    return None


def _to_session_messages(raw_messages: list[Any]) -> list[SessionMessage]:
    result: list[SessionMessage] = []
    for item in raw_messages:
        if not isinstance(item, BaseMessage):
            continue

        role = _normalize_message_role(item)
        if role is None:
            continue

        content = _normalize_chunk_content(getattr(item, "content", "")).strip()
        if not content:
            continue
        result.append(SessionMessage(role=role, content=content))
    return result


async def get_thread_messages(settings: Settings, thread_id: str) -> list[SessionMessage]:
    agent = await build_chat_agent(
        settings=settings,
        temperature=0.0,
        system_prompt=settings.default_system_prompt,
        tools=[],
    )
    state = await agent.aget_state({"configurable": {"thread_id": thread_id}})
    values = getattr(state, "values", {}) if state is not None else {}

    result: list[SessionMessage] = []
    summary = values.get("summary", "") if isinstance(values, dict) else ""
    if isinstance(summary, str) and summary.strip():
        result.append(SessionMessage(role="system", content=summary.strip()))

    messages = values.get("messages", []) if isinstance(values, dict) else []
    if isinstance(messages, list):
        result.extend(_to_session_messages(messages))
    return result


async def build_chat_agent(
    settings: Settings,
    temperature: float,
    system_prompt: str,
    tools: list[Any] | None = None,
):
    llm = build_llm(settings, temperature, stream=True)
    base_tools = tools if tools is not None else await get_mcp_tools(settings)
    agent_tools = [*base_tools, save_long_term_memory, list_long_term_memories]
    combined_system_prompt = f"{system_prompt}\n\n{LONG_TERM_MEMORY_POLICY}"

    return create_agent(
        model=llm,
        tools=agent_tools,
        system_prompt=combined_system_prompt,
        middleware=[
            SummarizationMiddleware(
                model=build_summary_llm(settings, temperature=0.0, stream=False),
                max_tokens_before_summary=SUMMARY_TRIGGER_TOKENS,
                messages_to_keep=MAX_FULL_MESSAGES,
            ),
            ToolRetryMiddleware(
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
                max_delay=60.0,
                jitter=True,
            ),
        ],
        context_schema=ChatRuntimeContext,
        checkpointer=_AGENT_CHECKPOINTER,
        store=_LONG_TERM_STORE,
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
    user_id = _extract_user_id(thread_id)
    runtime_context = ChatRuntimeContext(user_id=user_id)
    assistant_parts: list[str] = []

    yield sse_event(
        "start",
        {
            "session_id": session_id,
            "model": settings.model_name,
            "summary_model": settings.summary_model_name,
            "mcp_enabled": settings.mcp_server_enabled,
        },
    )

    try:
        last_node = ""
        for chunk, _metadata in agent.stream(
            {"messages": [{"role": "user", "content": payload.input_text}]},
            {"configurable": {"thread_id": thread_id}},
            context=runtime_context,
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
