from __future__ import annotations

import json
from typing import Iterator

from langchain_core.messages import AIMessageChunk
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from core.config import Settings
from schemas.chat import ChatMessageRequest
from services.session_store import SessionStore


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


def build_chat_agent(
    settings: Settings,
    temperature: float,
    system_prompt: str,
):
    llm = build_llm(settings, temperature, stream=True)

    return create_agent(
        model = llm,
        tools = [],
        system_prompt = system_prompt,
        checkpointer = InMemorySaver(),
    )


# 实现标准SSE帧格式的事件生成器，便于前端解析和处理不同类型的事件。
def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_chat_chunks(
    settings: Settings,
    store: SessionStore,
    session_id: str,
    payload: ChatMessageRequest,
) -> Iterator[str]:
    # 会话文件仅用于兼容已有消息查询接口，agent 记忆由 checkpointer 托管。
    store.append_message(session_id, "user", payload.input_text)

    # 使用 LangChain 内置短期记忆：通过 thread_id 自动维护会话上下文。
    system_prompt = payload.system_prompt or settings.default_system_prompt
    agent = build_chat_agent(settings, payload.temperature, system_prompt)

    config = {"configurable": {"thread_id": session_id}}

    # assistant_parts 用于累积完整回复，便于最终落盘保存。
    assistant_parts: list[str] = []
    saved = False

    # 先发 start 事件，便于前端初始化流状态。
    yield sse_event("start", {"session_id": session_id, "model": settings.model_name})

    try:
        # 按 agent 输出分片逐段向上游 yield，实现真正流式返回。
        for chunk, _metadata in agent.stream(
            {"messages": [{"role": "user", "content": payload.input_text}]},
            config=config,
            stream_mode="messages",
        ):
            if not isinstance(chunk, AIMessageChunk):
                continue

            token = _normalize_chunk_content(chunk.content)
            if not token:
                continue
            assistant_parts.append(token)
            yield sse_event("token", {"token": token})

        # 正常完成后，将完整助手回复写入会话存储。
        assistant_text = "".join(assistant_parts).strip()
        # store.append_message(session_id, "assistant", assistant_text)
        yield sse_event("done", {"reply": assistant_text})
        saved = True
    except Exception as exc:
        # 异常时向前端返回可见错误文本，避免静默失败。
        yield sse_event("error", {"error": f"调用模型失败：{exc}"})
    finally:
        # 如果中途异常但已有部分输出，也尽量保存已生成内容，减少上下文丢失。
        if not saved:
            assistant_text = "".join(assistant_parts).strip()
            if assistant_text:
                store.append_message(session_id, "assistant", assistant_text)
