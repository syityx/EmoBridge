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
    summary_model_name: str
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
    chroma_host: str
    chroma_port: int
    chroma_collection_name: str
    embedding_model_name: str


# 只会构造一次并复用同一个对象
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        model_name=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        summary_model_name=os.getenv("SUMMARY_MODEL_NAME", "gpt-4o-mini"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=_int_env("PORT", 8080),
        default_system_prompt=os.getenv(
            "DEFAULT_SYSTEM_PROMPT",
            """
你是 EmoBridge 的心理健康聊天助手，提供情绪支持和心理健康建议。
请以同理心和理解的态度与用户交流，帮助他们应对情绪困扰和心理压力。

【高风险处置】
发现用户存在心理健康问题且中高风险时候，例如抑郁、轻生想法，请立即调用工具通知管理員，并提供用戶的相关信息和对话内容，以便管理员及时干预和提供帮助。

【RAG 检索规则】
凡满足以下任一条件，必须先调用 rag_search 工具再作答，禁止凭空编造：
  1. 问题涉及项目文档、知识库内容、内部流程、业务规则、接口参数或配置细节；
  2. 用户提到"根据文档/知识库/系统里/之前的内容"等措辞；
  3. 你对答案不确定，且答错会误导实现或判断（如：步骤、代码参数、流程规范）。
纯闲聊、纯常识或用户明确要求不查知识库时，可跳过检索。

【rag_search 调用规范】
- 入参：
    - query: string — 从用户问题提炼关键词（保留模块名/接口名/错误词/约束条件），不要整段照抄
    - top_k: 3（固定）
- 失败重试：若 top-3 结果均不相关，最多改写 query 重试一次；两次均未命中则明确告知用户"知识库未命中"，并说明需要补充哪些信息。

【结果使用规范】
- 优先阅读 window 字段（上下文窗口）理解语义，再用 text 字段作精确引用；
- 回答中用 [KB1][KB2][KB3] 标注所依据的检索条目编号；
- 若多条结果存在冲突，指出冲突并说明选择依据；
- 要求写代码时，代码中的关键参数必须有检索证据支撑，否则注明"示例假设"。
"""
            ,
        ),
        auth_jwt_secret=os.getenv("AUTH_JWT_SECRET", "demo-dev-secret-change-me"),
        auth_jwt_exp_minutes=_int_env("AUTH_JWT_EXP_MINUTES", 10080),
        auth_db_url=os.getenv(
            "AUTH_DB_URL",
            "mysql+pymysql://root:123456@127.0.0.1:3306/emobridge?charset=utf8mb4",
        ),
        mcp_server_enabled=_bool_env("MCP_SERVER_ENABLED", True),
        # mcp 服务器地址
        mcp_server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8081/mcp"),
        mcp_server_name=os.getenv("MCP_SERVER_NAME", "emobridge-mcp"),
        mcp_retry_cooldown_seconds=_int_env("MCP_RETRY_COOLDOWN_SECONDS", 15),
        # 是否展示agent执行的每一步细节日志
        agent_stream_trace_enabled=_bool_env("AGENT_STREAM_TRACE_ENABLED", True),
        chroma_host=os.getenv("CHROMA_HOST", "localhost"),
        chroma_port=_int_env("CHROMA_PORT", 8000),
        chroma_collection_name=os.getenv("CHROMA_COLLECTION_NAME", "emobridge_docs"),
        embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-8B"),
    )
