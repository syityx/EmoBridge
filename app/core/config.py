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


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    auth_db_url: str
    mcp_server_enabled: bool
    mcp_server_url: str
    mcp_server_name: str
    mcp_retry_cooldown_seconds: int
    agent_stream_trace_enabled: bool


# 只会构造一次并复用同一个对象
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        model_name=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=_int_env("PORT", 8080),
        default_system_prompt=os.getenv(
            "DEFAULT_SYSTEM_PROMPT",
            """
            你是一个心理健康聊天助手，提供情绪支持和心理健康建议。
            请以同理心和理解的态度与用户交流，帮助他们应对情绪困扰和心理压力。
            发现用户存在心理健康问题且中高风险时候，例如抑郁、轻生想法，请立即调用工具通知管理員，并提供用戶的相关信息和对话内容，以便管理员及时干预和提供帮助。
            """
            # TODO 实现Agentic RAG：当问题涉及知识库事实时先调用 RAG_Search_tool；证据不足时再改写 query 进行第二次检索；回答要带来源标识
            # + "问题涉及知识库事实时先调用 RAG_Search_tool；证据不足时再改写 query 进行第二次检索；回答要带来源标识"
            ,
        ),
        auth_jwt_secret=os.getenv("AUTH_JWT_SECRET", "demo-dev-secret-change-me"),
        auth_jwt_exp_minutes=_int_env("AUTH_JWT_EXP_MINUTES", 10080),
        auth_db_url=os.getenv(
            "AUTH_DB_URL",
            "mysql+pymysql://emobridge_user:020305@10.12.37.175:3306/emobridge?charset=utf8mb4",
        ),
        mcp_server_enabled=_bool_env("MCP_SERVER_ENABLED", True),
        # mcp 服务器地址
        mcp_server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8081/mcp"),
        mcp_server_name=os.getenv("MCP_SERVER_NAME", "emobridge-mcp"),
        mcp_retry_cooldown_seconds=_int_env("MCP_RETRY_COOLDOWN_SECONDS", 15),
        # 是否展示agent执行的每一步细节日志
        agent_stream_trace_enabled=_bool_env("AGENT_STREAM_TRACE_ENABLED", True),
    )
