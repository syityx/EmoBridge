from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
import logging

from core.database import get_db
from schemas.auth import CurrentUser, LoginRequest, LoginResponse, RegisterRequest, RegisterResponse
from services.auth_service import (
    AuthTemporaryError,
    authenticate_user,
    blacklist_access_token,
    create_access_token,
    extract_bearer_token,
    get_current_user,
    register_user,
)
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        authenticated = authenticate_user(db, payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AuthTemporaryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not authenticated:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user_id, user_name = authenticated
    token = create_access_token(user_id)
    return LoginResponse(access_token=token, user_id=user_id, user_name=user_name)


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    try:
        user_id, user_name = register_user(db, payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AuthTemporaryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    token = create_access_token(user_id)
    return RegisterResponse(access_token=token, user_id=user_id, user_name=user_name)


@router.get("/me", response_model=CurrentUser)
def get_me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user


@router.post("/logout")
def logout(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> dict[str, str]:
    token = extract_bearer_token(authorization)
    try:
        blacklist_access_token(db, token, current_user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AuthTemporaryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"message": "已退出登录"}
