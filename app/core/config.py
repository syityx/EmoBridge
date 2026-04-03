from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    model_name: str
    openai_api_key: str | None
    openai_base_url: str
    app_host: str
    app_port: int
    default_system_prompt: str
    auth_jwt_secret: str
    auth_jwt_exp_minutes: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        model_name=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=_int_env("PORT", 8080),
        default_system_prompt=os.getenv("DEFAULT_SYSTEM_PROMPT", "你是一个友好、专业的中文助手。"),
        auth_jwt_secret=os.getenv("AUTH_JWT_SECRET", "demo-dev-secret-change-me"),
        auth_jwt_exp_minutes=_int_env("AUTH_JWT_EXP_MINUTES", 720),
    )
