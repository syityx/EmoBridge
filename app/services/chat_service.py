from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware, SummarizationMiddleware, ToolRetryMiddleware
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver


from Middleware.MessageLimitMiddleware import MessageLimitMiddleware
from core.config import Settings
from schemas.chat import ChatMessageRequest, SessionMessage
from services.mcp_service import get_mcp_tools

logger = logging.getLogger(__name__)
# 保存到短期记忆中的最大对话轮数
MAX_FULL_ROUNDS = 10
# 保存到短期记忆中的最大消息数（每轮包含用户和助手消息，因此是轮数的两倍）
MAX_FULL_MESSAGES = MAX_FULL_ROUNDS * 2
# 在触发总结之前，允许的最大消息总长度（以 token 数计）。这个值可以根据实际情况调整，以平衡性能和上下文完整性。
SUMMARY_TRIGGER_TOKENS = 4000

_AGENT_CHECKPOINTER = InMemorySaver()
# store = InMemoryStore() 

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


def _normalize_chunk_content(content: object) -> str:
    """这个函数将输入规范化为字符串输出。"""
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


""" 标准化消息角色为 "user", "assistant", 或 "system" """
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


""" 将原始消息列表转换为 SessionMessage 列表，过滤掉无效或空内容的消息 """
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


"""异步获取线程消息的函数，构建一个聊天代理来加载和返回指定线程的消息历史记录"""
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
    agent_tools = tools if tools is not None else await get_mcp_tools(settings)

    return create_agent(
        model=llm,
        tools=agent_tools,
        system_prompt=system_prompt,
        middleware=[
            SummarizationMiddleware(
                    model=build_summary_llm(settings, temperature=0.0, stream=False),
                    max_tokens_before_summary=SUMMARY_TRIGGER_TOKENS,
                    messages_to_keep=MAX_FULL_MESSAGES,
                ),
            # ModelFallbackMiddleware(
            #         "openai:gpt-4o-mini",  # 错误时首先尝试
            #         "anthropic:claude-3-5-sonnet-20241022",  # 然后尝试这个
            #     ),
            ToolRetryMiddleware(
                    max_retries=3,  # 最多重试 3 次
                    backoff_factor=2.0,  # 指数回退乘数
                    initial_delay=1.0,  # 从 1 秒延迟开始
                    max_delay=60.0,  # 将延迟上限设置为 60 秒
                    jitter=True,  # 添加随机抖动以避免“惊群”问题
                ),
            # # 自定义中间件
            # MessageLimitMiddleware(max_messages=3),  # 设置消息限制，防止内存过载
            # ],
        checkpointer=_AGENT_CHECKPOINTER,
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
