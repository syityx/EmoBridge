from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import get_db
from models.token_blacklist import TokenBlacklist
from models.user import User
from schemas.auth import CurrentUser


USER_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")


class AuthTemporaryError(RuntimeError):
    pass


def normalize_username(username: str) -> str:
    value = username.strip().lower()
    if not USER_NAME_PATTERN.fullmatch(value):
        raise ValueError("username 仅允许 1-32 位字母、数字、下划线和中划线")
    return value


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _verify_password(raw_password: str, stored_password: str) -> bool:
    if stored_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(raw_password.encode("utf-8"), stored_password.encode("utf-8"))
        except ValueError:
            return False

    # 兼容旧数据迁移期的明文密码；新注册只会写入 bcrypt 哈希。
    return hmac.compare_digest(raw_password, stored_password)


def _fetch_user_by_username(db: Session, username: str) -> User | None:
    try:
        stmt = select(User).where(User.username == username).limit(1)
        return db.execute(stmt).scalar_one_or_none()
    except SQLAlchemyError as exc:
        raise AuthTemporaryError(f"认证数据库查询失败: {exc}") from exc


def register_user(db: Session, username: str, password: str) -> tuple[int, str]:
    normalized_username = normalize_username(username)
    if not password.strip():
        raise ValueError("password 不能为空")

    existing_user = _fetch_user_by_username(db, normalized_username)
    if existing_user is not None:
        raise ValueError("用户名已存在")

    password_hash = _hash_password(password)

    try:
        user = User(username=normalized_username, password=password_hash)
        db.add(user)
        db.flush()
        user_id = user.id
        if not isinstance(user_id, int):
            raise AuthTemporaryError("注册用户失败: 数据库未返回有效的自增主键")
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise AuthTemporaryError(f"注册用户失败: {exc}") from exc

    return user_id, normalized_username


def authenticate_user(db: Session, username: str, password: str | None) -> tuple[int, str] | None:
    normalized_username = normalize_username(username)
    password_input = password or ""

    user = _fetch_user_by_username(db, normalized_username)

    if user is None:
        return None

    db_user_id = user.id
    db_password = user.password
    if not isinstance(db_user_id, int) or not isinstance(db_password, str):
        return None

    if not _verify_password(password_input, db_password):
        return None

    return db_user_id, user.username


def build_thread_id(user_id: int | str, client_session_id: str) -> str:
    return f"{user_id}:{client_session_id}"


def create_access_token(user_id: int | str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.auth_jwt_exp_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _decode_token_payload(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.auth_jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except InvalidTokenError as exc:
        raise ValueError("无效的 access token") from exc


def blacklist_access_token(db: Session, token: str, user_id: int | str) -> None:
    payload = _decode_token_payload(token)
    exp_ts = payload.get("exp")
    if not isinstance(exp_ts, int):
        raise ValueError("token 缺少有效过期时间")

    token_hash = _hash_token(token)
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc).replace(tzinfo=None)
    revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        existing = db.execute(
            select(TokenBlacklist.id).where(TokenBlacklist.token_hash == token_hash).limit(1)
        ).scalar_one_or_none()
        if existing is not None:
            return

        db.add(
            TokenBlacklist(
                token_hash=token_hash,
                user_id=int(user_id),
                expires_at=expires_at,
                revoked_at=revoked_at,
            )
        )
        db.commit()
    except (TypeError, ValueError) as exc:
        db.rollback()
        raise ValueError(f"无效的 user_id: {exc}") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise AuthTemporaryError(f"写入令牌黑名单失败: {exc}") from exc


def is_token_blacklisted(db: Session, token: str) -> bool:
    token_hash = _hash_token(token)
    try:
        row_id = db.execute(
            select(TokenBlacklist.id).where(TokenBlacklist.token_hash == token_hash).limit(1)
        ).scalar_one_or_none()
        return row_id is not None
    except SQLAlchemyError as exc:
        raise AuthTemporaryError(f"查询令牌黑名单失败: {exc}") from exc


def decode_access_token(token: str) -> int:
    settings = get_settings()
    try:
        # 此处会自动检查是否过期（基于当前UTC时间）
        payload = jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise ValueError("无效或过期的 access token") from exc

    subject = payload.get("sub", "")
    if not isinstance(subject, str) or not subject:
        raise ValueError("token 缺少有效用户标识")

    try:
        return int(subject)
    except ValueError as exc:
        raise ValueError("token 中的用户标识不是有效的整数") from exc


def extract_bearer_token(authorization: str | None) -> str:
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
    db: Session = Depends(get_db),
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> CurrentUser:
    token = extract_bearer_token(authorization)
    try:
        if is_token_blacklisted(db, token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token 已失效，请重新登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except AuthTemporaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        user_id = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return CurrentUser(user_id=user_id)
