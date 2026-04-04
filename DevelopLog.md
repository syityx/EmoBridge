# 后端 App

## 记忆管理
使用 LangChain 内置的短期记忆能力。

- 在 `create_agent` 中配置 `checkpointer=CHECKPOINTER`
- 使用 `CHECKPOINTER = InMemorySaver()` 作为进程内会话记忆存储
- 调用 `Agent.stream()` 或 `Agent.astream()` 时传入 `config = {"configurable": {"thread_id": session_id}}`，即可按会话维度保存上下文

## 流式传输 SSE

- 通过 `sse_event(event: str, data: dict) -> str` 生成标准 SSE 帧
- 后端使用流式响应逐步向前端推送 `start`、`token`、`done`、`error` 等事件

## 登录鉴权（Demo）

- 当前为演示模式，不校验密码
- 使用 `fastapi.Depends` 实现简单鉴权
- 使用 PyJWT 生成 JWT token
- 参考：https://zhuanlan.zhihu.com/p/1976612326070317065

# 前端 Client

## 登录页面

- 页面加载时会检查本地登录态
- 登录后保存 token 和 user_id，用于后续接口访问

## 2026-04-04 本次开发简要记录

- App 侧新增 MCP 配置项：`MCP_SERVER_ENABLED`、`MCP_SERVER_URL`、`MCP_SERVER_NAME`、`MCP_RETRY_COOLDOWN_SECONDS`
- App 侧引入 `langchain-mcp-adapters`，支持从 MCP Server 拉取工具定义
- 新增 `app/services/mcp_service.py`，封装 `MultiServerMCPClient` 的工具发现、缓存与失败降级逻辑
- 聊天链路改为异步流式：`chat.py` 与 `chat_service.py` 切换到 `async`/`astream`
- `build_chat_agent()` 会动态注入 MCP tools，使 agent 能按需调用外部工具
- 修复 SSE 无正文问题：兼容 `AIMessage` 与 `AIMessageChunk` 两种消息类型，避免前端只收到 `start` 和 `done`
- 新建 Spring Boot MCP Server 模块配置，补充 `McpToolConfiguration` 与占位工具 `PlaceholderToolService`
- 通过 `MethodToolCallbackProvider` 暴露 MCP 工具能力
- 修复 Java 编译问题：清除 `McpToolConfiguration.java` 文件 BOM，并按 Spring AI 1.1.4 实际可用 API 调整为 `@Tool` / `@ToolParam`
- MCP 配置迁移到 `application.yaml`，`application.properties` 仅保留 `server.port=8081`