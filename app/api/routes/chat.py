from __future__ import annotations

from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core.config import get_settings
from schemas.auth import CurrentUser
from schemas.chat import ChatMessageRequest, SessionMessagesResponse
from services.auth_service import build_thread_id, get_current_user
from services.chat_service import get_thread_messages, stream_chat_chunks
from services.session_store import validate_session_id


router = APIRouter()
settings = get_settings()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> SessionMessagesResponse:
    try:
        validate_session_id(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    thread_id = build_thread_id(current_user.user_id, session_id)
    messages = get_thread_messages(thread_id)
    return SessionMessagesResponse(session_id=session_id, messages=messages)


@router.post("/api/v1/sessions/{session_id}/messages")
def stream_session_message(
    session_id: str,
    payload: ChatMessageRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    try:
        validate_session_id(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    thread_id = build_thread_id(current_user.user_id, session_id)
    stream = stream_chat_chunks(
        settings=settings,
        thread_id=thread_id,
        session_id=session_id,
        payload=payload,
    )

    async def stream_with_log() -> AsyncIterator[str]:
        async for token in stream:
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
