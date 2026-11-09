# agent_1 —— 从调通 LLM 到有记忆的 Agent


```
调通 LLM → RAG（建库 / 检索问答）→ Tool Calling（闭环 / 循环 / 并行 / 架构 / 健壮性）
        → 两条线合流 → 有状态多轮 Agent → 摘要记忆 → 长期记忆提取
```

---

## 学习路径总览

| # | 文件 | 阶段 | 一句话说明 |
|---|------|------|-----------|
| 1 | `a01_ping_api.py` | LLM 入门 | 用 OpenAI SDK 调通 DeepSeek，拿到第一个回答 |
| 2 | `a02_rag_ingest.py` | RAG 建库 | 文档 → 切分 → Embedding → 存进 ChromaDB |
| 3 | `a03_rag_query.py` | RAG 问答 | 问题 → 向量检索 → 拼 Prompt → LLM 生成答案 |
| 4 | `a04_tool_calling_0.py` | Tool Calling 起步 | 最小闭环：一次工具调用 + 一次结果回传 |
| 5 | `a05_tool_calling.py` | Agent Loop | `while True` 循环：多轮工具调用 + 异常兜底 |
| 6 | `a06_multi_tool_calling.py` | 多工具调用 | 一次响应返回多个 tool_call，遍历执行 |
| 7 | `a07_async_tool_calling.py` | 异步并行 | `asyncio.gather` 同时执行多个工具 |
| 8 | `a08_tool_registry.py` | Agent 架构 | 抽出 Tool Registry + Dispatcher，LLM 只认名字 |
| 9 | `a09_tool_validation.py` | 参数校验 | 缺参数、类型不对都要在进入业务代码前拦住 |
| 10 | `a10_tool_runtime.py` | 工具运行时 | 超时 + 重试，工具挂了不拖垮 Agent |
| 11 | `a11_rag_agent.py` | 合流 | RAG 检索封装成工具，LLM 自己决定何时查库 |
| 12 | `a12_agent.py` | 有状态的 Agent | `AgentState` 外置 + 多轮对话 + `MAX_STEPS` |
| 13 | `a13_summary_memory.py` | 摘要记忆 | 消息超阈值就滚动摘要压缩历史 |
| 14 | `a14_memory_extractor.py` | 长期记忆提取 | LLM 从用户消息里提取值得长期保存的信息（当前进度） |

---

## 每一步做了什么

### 1. `a01_ping_api.py` —— 调通大模型

四步：读 API Key → 建 OpenAI 客户端（`base_url` 指向 DeepSeek 兼容接口）→ 发一条对话（`extra_body` 关掉思考模式，让链路最简单）→ 打印回答和 token 用量。

> 关键认知：**LLM 调用 = 一个 HTTP 请求 + 一个 JSON 响应**，token 是要花钱的。

### 2. `a02_rag_ingest.py` —— RAG 建库（入库半边）

`main()` 串起整条流水线：

```
data/ 下的 txt/md
  ↓ 读取文档            读原文 + 记录来源文件名
  ↓ 切分 Chunk          200 字符一片，相邻重叠 50 字符（避免知识点被切断）
  ↓ 加载 Embedding 模型 BAAI/bge-small-zh-v1.5（512 维，中文小模型）
  ↓ 生成向量            每个 Chunk → 一个 512 维向量
  ↓ 存入 ChromaDB       向量 + 原文 + metadata(source/chunk) 持久化到 chroma_db/
  ↓ 验证                抽查 5 条，确认写进去了
```

> 关键认知：**RAG 检索靠向量距离，不是关键词匹配**；Chunk 大小和重叠策略直接决定检索质量。
> `data/` 和 `chroma_db/` 都已 gitignore，换机器要重新跑一次建库。

### 3. `a03_rag_query.py` —— RAG 问答（检索半边）

```
用户问题 → 向量化（必须和入库用同一个模型！）→ ChromaDB 检索 Top-3
        → 拼进 Prompt（片段带编号和来源，并要求"查不到就如实说"）
        → DeepSeek 生成最终回答
```

> 关键认知：**入库和查询必须用同一个 Embedding 模型**，否则向量空间对不上，检索全是噪声。

### 4. `a04_tool_calling_0.py` —— 最小工具调用闭环

一次调用、一个工具、没有循环。看清三件事：

1. 把工具清单（JSON Schema）发给 LLM，LLM 返回 `tool_calls`——**只有工具名 + 参数 JSON 字符串**
2. Python 自己 `json.loads` 解析参数、调用 `multiply()`——**LLM = 决策者，Python = 执行者**
3. 结果包成 `{"role": "tool", "tool_call_id": ..., "content": ...}` 追加进历史，**再调一次 LLM** 生成最终回答

> 关键认知：`tool_call_id` 是"这条结果对应哪次调用"的凭证。这里用了 `tool_calls[0]`，这个假设在下一步被打破。

### 5. `a05_tool_calling.py` —— Agent Loop（核心文件）

在最小闭环上加 `while True`：`LLM → Tool → LLM → Tool → …`，直到 LLM 不再要求调用工具才结束。三个升级：

- **循环**：两步任务"先 10+20 再 ×5"必须连续调用 `add` → `multiply`，证明循环真的在跑
- **遍历** `tool_calls`：一次响应可能返回多个调用，不能再用 `[0]`
- **异常兜底**：参数非法 JSON / 工具名不存在 / 执行抛异常，三种失败都转成一条 tool 消息**喂回给 LLM**，让它自己纠错，程序不崩

> 关键认知：**把错误当成工具结果返回给 LLM，LLM 就能自己纠错**——这是 Agent 比一次性脚本抗造的原因。

### 6. `a06_multi_tool_calling.py` —— 一次响应，多个工具

用户问"同时计算 10+20 和 8×9"，LLM 一次返回**两个** tool_call，`for` 循环逐个执行、逐个回传（各自带 `tool_call_id`）。
故意写两个独立计算来诱导这种一次多调的响应。

留了个明显问题：**串行执行**——两个各 2 秒的工具要等 4 秒。于是有了下一步。

### 7. `a07_async_tool_calling.py` —— 并行执行工具

工具改成 `async def`（内部 `asyncio.sleep(2)` 模拟网络/数据库耗时），执行抽成 `execute_tool()`，关键三行：

```python
tasks = [execute_tool(tc) for tc in message.tool_calls]
results = await asyncio.gather(*tasks)   # 并发执行，耗时从求和变取最大值
messages.extend(results)
```

> 关键认知：工具是 IO 密集型时并行收益巨大；纯 CPU 计算不受益（那要用多进程）。

### 8. `a08_tool_registry.py` —— Registry + Dispatcher（架构化）

把散在主循环里的工具处理收拢成两个概念：

| 概念 | 是什么 | 给谁用 |
|------|--------|--------|
| `TOOL_REGISTRY` | 工具名 → Python 函数的字典 | **Python** 查表执行 |
| `TOOLS`（JSON Schema） | 工具名 + 描述 + 参数说明 | **LLM** 看的说明书 |

`dispatch_tool()` 是调度中心：取名字 → 解析参数 → 查表 → 执行 → 包装成 tool 消息；工具不存在、执行异常都转成错误字符串回传。主循环只剩"调 LLM → gather → 回灌"。

> 关键认知：**Tool Schema ≠ Python 函数**，两者靠工具名这份"契约"连接。

### 9. `a09_tool_validation.py` —— 参数校验

新增 `validate_arguments()`：检查参数**存在**（缺了抛 `ValueError`）、**类型对**（不对抛 `TypeError`）。Dispatcher 变成流水线：

```
解析 JSON → 查表 → 参数校验 → 执行
   ↓ 任一步失败，都转成 tool 消息交还 LLM
```

> 关键认知：LLM 生成的参数**经常会错**。校验不是防坏人，是在错误进业务代码前拦住、并把原因告诉 LLM 让它重试。（手工 if/elif 是最简实现，生产上一般用 Pydantic 按 Schema 自动校验。）

### 10. `a10_tool_runtime.py` —— 超时 + 重试

校验拦得住坏参数，拦不住"工具本身挂了"。新增 `execute_tool()` 运行时：

- **超时**：`asyncio.wait_for(..., timeout=3)`
- **重试**：失败歇 1 秒再试，最多 3 次
- **最终失败**：重试耗尽抛 `RuntimeError`，由 Dispatcher 转成 tool 消息

专门造了 `slow_tool()`（睡 10 秒 vs 超时 3 秒）来观察完整的"超时 → 重试 → 兜底"日志。

> 关键认知：**重试要有边界**——超时预算要和整体响应时间一起设计。

### 11. `a11_rag_agent.py` —— 两条线合流

把 a03 的检索逻辑原样封装成 `search_knowledge(query)` 工具，注册进 Registry，套上 Agent Loop。关键转变是**谁来决定检索**：

| | 写死的 RAG（a03） | RAG as a Tool（a11） |
|---|---|---|
| 检索时机 | 每个问题都查 | LLM 判断需要时才调 |
| 检索次数 | 固定 1 次 | 可多次，可换问法再查 |
| 闲聊/算术 | 也去查库，白跑 | 直接回答，不触发检索 |

System Prompt 写明三条规矩：需要就调 `search_knowledge`、拿到结果严格按内容回答、查不到就说没查到不编造。

> 关键认知：**Tool 的返回值就是 Prompt**——`search_knowledge` 返回的 `[知识片段 1]…` 文本会直接喂给 LLM，怎么组织它和写 Prompt 是一回事。

### 12. `a12_agent.py` —— 有状态的多轮 Agent

三个增量：

- **`AgentState` 外置**：state 由 `main()` 创建、长期持有，`agent()` 只使用不创建——Agent 从"一次性脚本"变成"常驻服务"，记忆 = 历史消息全留在 `state.messages` 里
- **多轮对话**：外层 `while True` 等用户输入（`exit` 退出），内层 Agent Loop 处理单次任务；System Prompt 只初始化一次
- **`MAX_STEPS`**：`for` 循环限制单次任务最多 10 步（state 跨轮持有，step 每轮重置），防止 LLM 陷入"反复调同一个工具"的死循环烧 token

工具集扩到 4 个：`add` / `multiply` / `subtract` + 从 RAG 线合流来的 `search_knowledge`。可以试 *"JVM 有几个运行时数据区，再乘以 3 等于多少"* 这种既查库又计算的复合问题。

> 关键认知：**Agent Loop 必须能停下来**——正常完成、步数上限、用户退出，三个退出条件各管一层。
> 注意：a12 是"框架骨架"，刻意回退了校验/超时/并行，每个文件只聚焦一个新概念。

### 13. `a13_summary_memory.py` —— 摘要记忆

多轮对话下 `state.messages` 只增不减，聊久了必然顶到上下文上限。解法：把旧历史滚动摘要成一段文本。

- **记忆分两层**：`messages` 存最近原文，`summary` 存更早历史的压缩版；发给 LLM 的上下文由 `build_context()` 现场组装：system prompt + 摘要（包成一条 system 消息）+ 最近消息
- **滚动摘要**：每轮结束后，消息数超过阈值（4）就把旧消息交给 LLM 总结——总结时带着**旧摘要**，在它基础上叠加，最老的信息逐轮被压缩
- **切分必须落在 user 消息边界**：assistant(tool_calls) 消息必须紧跟它的 tool 结果，从中间切开下次请求直接报错，所以切分点要向前回溯到最近的 user 消息——这是本文件最大的坑
- **顺手加固**：assistant 回复无论有无 tool_calls 都先入历史（上一版的遗留 bug）、参数解析失败不崩、空输入跳过

> 关键认知：**摘要本身也是一次 LLM 调用，压缩记忆有成本**；生产上按 token 数而非消息条数触发。

### 14. `a14_memory_extractor.py` —— 长期记忆提取（当前进度）

摘要记忆只记住"聊过什么"，记不住"用户是谁"。这一步把记忆拆出第三个层次：**跨会话的长期记忆**——从用户消息里提取稳定事实（姓名、职业、长期目标），将来存下来供后续会话使用。

- **记忆提取器**：`extract_memories()` 把一条用户消息连同提取规则发给 LLM，返回一个字符串数组，每个元素是一条独立记忆
- **提取规则写进 Prompt**：正例（姓名/职业/长期兴趣/偏好/目标/进行中的重要项目）和反例（一次性计算、闲聊、临时问题）都明确列出，边界靠规则约束
- **结构化输出**：要求 LLM 只输出 JSON 数组；`json.loads` 解析失败或结果不是数组时降级返回 `[]`，不让坏输出崩掉调用方
- **测试脚本**：`a14_test_memory_extractor.py` 用 6 条消息验证——4 条个人信息应提取，计算和闲聊应返回 `[]`

> 关键认知：**提取 = 让 LLM 做分类 + 结构化输出**；和 a13 的摘要对比——摘要是"有损压缩自己的历史"，提取是"从消息里筛出要永久保存的事实"。
> 注意：本文件只做"提取"这一步，记忆的存储和召回（写入向量库 / 注入 system prompt）是后续步骤。

---

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


---
