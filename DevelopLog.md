# 后端App
## 记忆管理
使用LangChain内置的短期记忆管理
 - `create_agent` 中配置`checkpointer = CHECKPOINTER` 
 - `CHECKPOINTER = InMemorySaver()`  单例模式，进程级生命周期。
 - 使用`Agent.stream()` 时传入`config = {"configurable": {"thread_id": session_id}}` 即可，会自动注入`SystemMessage` 和短期记忆
## 流式传输 SSE
 - `def sse_event(event: str, data: dict) -> str:` 