from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Header, HTTPException, status
from jwt import InvalidTokenError

from core.config import get_settings
from schemas.auth import CurrentUser


USER_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")


def normalize_user_id(username: str) -> str:
    value = username.strip().lower()
    if not USER_NAME_PATTERN.fullmatch(value):
        raise ValueError("username 仅允许 1-32 位字母、数字、下划线和中划线")
    return value


def build_thread_id(user_id: str, client_session_id: str) -> str:
    return f"{user_id}:{client_session_id}"


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.auth_jwt_exp_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str:
    settings = get_settings()
    try:
        # 此处会自动检查是否过期（基于当前UTC时间）
        payload = jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise ValueError("无效或过期的 access token") from exc

    subject = payload.get("sub", "")
    if not isinstance(subject, str) or not subject:
        raise ValueError("token 缺少有效用户标识")
    return subject


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Authorization 头",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 格式错误，应为 Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return value.strip()


def get_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> CurrentUser:
    token = _extract_bearer_token(authorization)
    try:
        user_id = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return CurrentUser(user_id=user_id)
