# agent_1 —— 从调通 LLM 到有记忆的 Agent

```
调通 LLM → RAG（建库 / 检索问答）→ Tool Calling（闭环 / 循环 / 并行 / 架构 / 健壮性）
        → 两条线合流 → 有状态多轮 Agent → 摘要记忆 → 长期记忆提取 → 记忆存储
        → 记忆检索 + 记忆注入 → 工具运行时整合 + 套上 Agent Loop → MCP 标准工具协议
```

每个目录的 README 里有该阶段的架构总览（ASCII 流程图）、文件清单和一条主线，从这里进：

| 目录 | 阶段 | 一句话 |
|------|------|--------|
| [src/a01_rag](src/a01_rag/README.md) | LLM 入门 + RAG | 调通 DeepSeek；文档建库 → 向量检索问答 |
| [src/a02_tool_calling](src/a02_tool_calling/README.md) | Tool Calling | 最小闭环 → Agent Loop → 并行 → 架构化 → 校验 → 超时重试 |
| [src/a03_agent](src/a03_agent/README.md) | Agent | RAG as a Tool 合流 → 有状态多轮 Agent → 摘要记忆 |
| [src/a04_memory](src/a04_memory/README.md) | 长期记忆 | LLM 提取 → SQLite 存储（CRUD）→ 检索 → 注入 Agent |
| [src/a05_agent_runtime](src/a05_agent_runtime/README.md) | 运行时整合 | 工具链路合成可复用模块，Agent 执行统一走 dispatch |
| [src/a06_MCP](src/a06_MCP/README.md) | MCP | Server 提供工具/资源 → Client 标准协议访问 → Agent 动态发现工具 |

## 核心概念速查

| 概念 | 一句话 |
|------|--------|
| `tool_call_id` | 把工具结果和对应的那次调用绑定，LLM 靠它对上号 |
| Agent Loop | `while True` 调 LLM → 执行工具 → 回传结果，直到 LLM 不再要求调工具 |
| Tool Schema vs Registry | 给 LLM 看的说明书 vs 给 Python 用的查找表，靠工具名连接 |
| Dispatcher | 解析参数 → 查表 → 校验 → 执行 → 包装结果，失败都转成 tool 消息 |
| `asyncio.gather` | 多工具并发执行，总耗时从求和变取最大值 |
| RAG as a Tool | 检索从"写死的流程"变成"LLM 决定要不要调的工具" |
| `AgentState` | Agent = 一份状态 + 一个推进状态的循环；state 外置才有多轮对话 |
| `MAX_STEPS` | 防 LLM 工具死循环的刹车 |
| Summary Memory | 记忆 = 最近消息原文 + 更早历史的滚动摘要，发送前由 `build_context` 拼接 |
| 摘要切分边界 | 切分点必须落在 user 消息上，否则拆散 tool_calls/tool 配对，请求报错 |
| Memory Extractor | 用 Prompt 规则 + JSON 输出，从用户消息里筛出值得跨会话保存的事实 |
| `MemoryStore` | SQLite 存取长期记忆，`user_id` 隔离不同用户 |
| LLM 提取检索关键词 | 用户问题 → 同义词关键词 → 查库；自然语言和存储格式之间的翻译层 |
| Memory Read | 每轮对话前检索长期记忆，注入 system prompt 供 LLM 参考 |
| ToolRuntime.dispatch | 查找 → JSON 解析 → 校验 → 授权 → 执行（超时+重试），失败全兜底成 JSON |
| MCP | 工具抽成独立服务：Server 提供，Client 按协议发现调用，`list_tools` 替代手工注册 |
| Tool vs Resource | 工具 = LLM 主动调用来做动作；资源 = 客户端主动读取拿数据（类 GET） |
