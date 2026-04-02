from __future__ import annotations

from typing import Iterator

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from core.config import Settings
from schemas.chat import ChatMessageRequest, SessionMessage
from services.session_store import SessionStore


def build_llm(settings: Settings, temperature: float, stream: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=temperature,
        stream=stream,
    )


def _to_langchain_messages(history: list[SessionMessage]) -> list[HumanMessage | AIMessage]:
    result: list[HumanMessage | AIMessage] = []
    for message in history:
        if message.role == "user":
            result.append(HumanMessage(content=message.content))
        elif message.role == "assistant":
            result.append(AIMessage(content=message.content))
    return result


def stream_chat_chunks(
    settings: Settings,
    store: SessionStore,
    session_id: str,
    payload: ChatMessageRequest,
) -> Iterator[str]:
    # 读取会话历史并先写入当前用户消息，确保多轮上下文连续。
    history = store.read_messages(session_id)
    store.append_message(session_id, "user", payload.input_text)

    # 构造带历史消息占位符的提示模板，后续按流式方式调用模型。
    llm = build_llm(settings, payload.temperature, stream=True)
    system_prompt = payload.system_prompt or settings.default_system_prompt
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("history"),
            ("human", "{input_text}"),
        ]
    )
    chain = prompt | llm

    # assistant_parts 用于累积完整回复，便于最终落盘保存。
    assistant_parts: list[str] = []
    saved = False

    try:
        # 按模型输出分片逐段向上游 yield，实现真正流式返回。
        for chunk in chain.stream({"history": _to_langchain_messages(history), "input_text": payload.input_text}):
            token = getattr(chunk, "content", "")
            if not token:
                continue
            assistant_parts.append(token)
            yield token

        # 正常完成后，将完整助手回复写入会话存储。
        assistant_text = "".join(assistant_parts).strip()
        store.append_message(session_id, "assistant", assistant_text)
        saved = True
    except Exception as exc:
        # 异常时向前端返回可见错误文本，避免静默失败。
        yield f"\n[系统错误] 调用模型失败：{exc}"
    finally:
        # 如果中途异常但已有部分输出，也尽量保存已生成内容，减少上下文丢失。
        if not saved:
            assistant_text = "".join(assistant_parts).strip()
            if assistant_text:
                store.append_message(session_id, "assistant", assistant_text)
