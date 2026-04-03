from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from schemas.auth import CurrentUser, LoginRequest, LoginResponse
from services.auth_service import create_access_token, get_current_user, normalize_user_id


router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    # demo 登录：不校验密码，仅按用户名签发 token 用于用户隔离演示。
    try:
        # Syit -> Syit
        user_id = normalize_user_id(payload.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = create_access_token(user_id)
    return LoginResponse(access_token=token, user_id=user_id)


@router.get("/me", response_model=CurrentUser)
def get_me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user
