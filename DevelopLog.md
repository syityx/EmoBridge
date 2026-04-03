# 后端App
## 记忆管理
使用LangChain内置的短期记忆管理
 - `create_agent` 中配置`checkpointer = CHECKPOINTER` 
 - `CHECKPOINTER = InMemorySaver()`  单例模式，进程级生命周期。
 - 使用`Agent.stream()` 时传入`config = {"configurable": {"thread_id": session_id}}` 即可，会自动注入`SystemMessage` 和短期记忆

## 流式传输 SSE
 - `def sse_event(event: str, data: dict) -> str:` 

## 登录鉴权(Demo)
 - 不校验密码
 - 使用`fastapi.Depends` 来实现简单的鉴权
 - 使用PyJWT库生成JWT-token
 - https://zhuanlan.zhihu.com/p/1976612326070317065

# 前端Client
 - 登录页面
  - 每次访问网页都检查一下权限，