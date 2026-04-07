from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=32, description="演示用户名")
    password: str | None = Field(default=None, max_length=128, description="演示密码，可为空")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    user_name: str | None = None


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=32, description="注册用户名")
    password: str = Field(..., min_length=8, max_length=128, description="注册密码，至少 8 位")


class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    user_name: str


class CurrentUser(BaseModel):
    user_id: int
    user_name: str | None = None
