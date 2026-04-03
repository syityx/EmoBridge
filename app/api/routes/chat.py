from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.config import get_settings
from schemas.chat import ChatMessageRequest, SessionMessagesResponse
from services.chat_service import get_thread_messages, stream_chat_chunks
from services.session_store import validate_session_id


router = APIRouter()
settings = get_settings()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(session_id: str) -> SessionMessagesResponse:
    try:
        validate_session_id(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    messages = get_thread_messages(session_id)
    return SessionMessagesResponse(session_id=session_id, messages=messages)


@router.post("/api/v1/sessions/{session_id}/messages")
def stream_session_message(session_id: str, payload: ChatMessageRequest) -> StreamingResponse:
    try:
        validate_session_id(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stream = stream_chat_chunks(settings=settings, session_id=session_id, payload=payload)

    def stream_with_log() -> Iterator[str]:
        for token in stream:
            # 控制台输出流式响应的 token，方便调试和观察
            # print(f"[{session_id}] \n{token}", flush=True)
            # yield 用在函数里，作用是“产出一个值并暂停函数”，下次继续从暂停位置往下执行。
            yield token

    return StreamingResponse(
        stream_with_log(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )