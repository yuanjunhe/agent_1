# Agent Runtime：工具运行时整合 + 套上 Agent Loop

## 架构总览

```
演进流程（t01 → t05，每个文件在上一个基础上加一件事）：

  t01 工具运行时整合（独立可复用模块）
  ─────────────────────────────────────────────
  dispatch(tool_name, arguments) 唯一入口
       │
       ▼
   1. 查找工具 ──── 查不到返回 JSON 错误
       ▼
   2. JSON 解析 ─── 解析失败返回 JSON 错误
       ▼
   3. 参数校验 ──── 缺参数 / 类型不对拦住（来自 t06）
       ▼
   4. 授权检查 ──── requires_confirmation 先拦截
       ▼
   5. 执行 ──────── wait_for 超时 + 重试（来自 t07）
       │             同步工具丢线程池，不阻塞事件循环
       ▼
   结果包成 {"success": ..., "data"/"error"} JSON
   ——任何一步失败都不抛异常，全链路兜底

  t02 运行时测试：四个工具七个测试逐项验证五步链路

  t03-t05 套上 Agent Loop
  ─────────────────────────────────────────────
  main() 多轮循环（t05）
       │  messages 只创建一次，上下文跨轮保留
       ▼
   agent()（t04）：调 LLM（带 tools_schema）
       │
       ▼
   没有 tool_calls？ ── 是 ──► 返回最终答案
       │ 否
       ▼
   逐个 tool_call 交给 runtime.dispatch（★ 不再自己解析/执行）
       │
       └────► 结果包成 tool 消息回传，进入下一步

  对比 a03_agent/t02_agent.py：
  Schema 不再手写 TOOLS 列表 → get_schemas() 自动生成
  执行不再自己查表/校验/兜底 → dispatch 一行搞定
  工具函数拆到 t03_tools.py，定义和注册分离
```

## 文件清单

| 文件 | 角色 | 关键点 |
|---|---|---|
| `t01_tool_runtime.py` | 工具运行时（库） | ToolSpec + Registry + 校验 + 调度整合成模块，dispatch 五步链路，失败全兜底 |
| `t02_test_tool_runtime.py` | 运行时测试 | 加法 / 异常 / 超时 / 需授权四个工具，七个测试对应 dispatch 各环节 |
| `t03_tools.py` | 工具集 | add / multiply / get_weather 三个纯函数，Schema 定义和 handler 分离 |
| `t04_agent.py` | Agent 核心 | Agent Loop + create_runtime()；Schema 自动生成，执行统一走 dispatch |
| `t05_agent_demo.py` | 多轮对话入口 | main() 循环读输入，串起 t01/t03/t04 |

## 一条主线

Tool Calling 线造好的零件（a02 的 t05 架构、t06 校验、t07 超时重试）在这里合成一个**可复用模块**：dispatch 是唯一入口，健壮性收在模块内部，调用方拿到的永远是 JSON、永远不用 try/except。然后套上 a03 造好的 Agent Loop——对比 a03_agent/t02_agent.py，agent() 里连参数解析都不剩了。

> 关键认知：**从"教学脚本"到"可复用模块"的跨越 = 一个稳定入口 + 全链路错误兜底**。


## 需要理解的三个关键概念
1. Agent 和 Runtime 的职责不同
- Agent：决定做什么。
- Runtime：负责安全、可靠地执行。
2. Tool Schema 和 Python 函数是两回事
- Tool Schema：给 LLM 看，让 LLM 知道如何调用。
- Python 函数：真正执行业务逻辑。
- Registry：把二者关联起来。
3. Dispatcher 是工具执行的统一入口

以后无论接入 Memory、RAG、MCP 还是外部 API，都可以通过统一的执行机制管理工具.