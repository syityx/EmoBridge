from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=32, description="演示用户名")
    password: str | None = Field(default=None, max_length=128, description="演示密码，可为空")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


class CurrentUser(BaseModel):
    user_id: str
