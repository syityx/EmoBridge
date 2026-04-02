from __future__ import annotations

from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.config import get_settings
from schemas.chat import ChatMessageRequest, SessionMessagesResponse
from services.chat_service import stream_chat_chunks
from services.session_store import SessionStore


router = APIRouter()
settings = get_settings()
store = SessionStore(root_dir=Path(__file__).resolve().parents[2] / settings.session_dir_name)


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(session_id: str) -> SessionMessagesResponse:
    try:
        store.validate_session_id(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    messages = store.read_messages(session_id)
    return SessionMessagesResponse(session_id=session_id, messages=messages)


@router.post("/api/v1/sessions/{session_id}/messages")
def stream_session_message(session_id: str, payload: ChatMessageRequest) -> StreamingResponse:
    try:
        store.validate_session_id(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stream = stream_chat_chunks(settings=settings, store=store, session_id=session_id, payload=payload)

    def stream_with_log() -> Iterator[str]:
        for token in stream:
            # 控制台输出流式响应的 token，方便调试和观察
            # print(f"[stream token][{session_id}] {token}", flush=True)
            # yield 用在函数里，作用是“产出一个值并暂停函数”，下次继续从暂停位置往下执行。
            yield token

    return StreamingResponse(
        stream_with_log(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )