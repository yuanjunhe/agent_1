# agent_1 —— 从调通 LLM 到有记忆的 Agent


```
调通 LLM → RAG（建库 / 检索问答）→ Tool Calling（闭环 / 循环 / 并行 / 架构 / 健壮性）
        → 两条线合流 → 有状态多轮 Agent → 摘要记忆 → 长期记忆提取 → 记忆存储 → 记忆检索 + 记忆注入
```

---

## 学习路径总览

| # | 文件 | 阶段 | 一句话说明 |
|---|------|------|-----------|
| 1 | `src/a01_rag/t01_ping_api.py` | LLM 入门 | 用 OpenAI SDK 调通 DeepSeek，拿到第一个回答 |
| 2 | `src/a01_rag/t02_rag_ingest.py` | RAG 建库 | 文档 → 切分 → Embedding → 存进 ChromaDB |
| 3 | `src/a01_rag/t03_rag_query.py` | RAG 问答 | 问题 → 向量检索 → 拼 Prompt → LLM 生成答案 |
| 4 | `src/a02_tool_calling/t01_tool_calling_0.py` | Tool Calling 起步 | 最小闭环：一次工具调用 + 一次结果回传 |
| 5 | `src/a02_tool_calling/t02_tool_calling.py` | Agent Loop | `while True` 循环：多轮工具调用 + 异常兜底 |
| 6 | `src/a02_tool_calling/t03_multi_tool_calling.py` | 多工具调用 | 一次响应返回多个 tool_call，遍历执行 |
| 7 | `src/a02_tool_calling/t04_async_tool_calling.py` | 异步并行 | `asyncio.gather` 同时执行多个工具 |
| 8 | `src/a02_tool_calling/t05_tool_registry.py` | Agent 架构 | 抽出 Tool Registry + Dispatcher，LLM 只认名字 |
| 9 | `src/a02_tool_calling/t06_tool_validation.py` | 参数校验 | 缺参数、类型不对都要在进入业务代码前拦住 |
| 10 | `src/a02_tool_calling/t07_tool_runtime.py` | 工具运行时 | 超时 + 重试，工具挂了不拖垮 Agent |
| 11 | `src/a03_agent/t01_rag_agent.py` | 合流 | RAG 检索封装成工具，LLM 自己决定何时查库 |
| 12 | `src/a03_agent/t02_agent.py` | 有状态的 Agent | `AgentState` 外置 + 多轮对话 + `MAX_STEPS` |
| 13 | `src/a03_agent/t03_summary_memory.py` | 摘要记忆 | 消息超阈值就滚动摘要压缩历史 |
| 14 | `src/a04_memory/t01_memory_extractor.py` | 长期记忆提取 | LLM 从用户消息里提取值得长期保存的信息 |
| 15 | `src/a04_memory/t02_memory_store.py` | 记忆存储 | SQLite 存取提取出的记忆，按 `user_id` 隔离 |
| 16 | `src/a04_memory/t05_memory_crud.py` | 记忆存储升级 | 完整 CRUD：分类字段 + 时间戳 + 索引 + 关键词搜索 |
| 17 | `src/a04_memory/t07_memory_retriever.py` | 记忆检索 | LLM 从问题提取关键词，多关键词查库去重（当前进度） |
| 18 | `src/a04_memory/t08_agent_memory_demo.py` | 记忆注入 Agent | 检索到的长期记忆注入 system prompt，按记忆回答 |

---

## 每一步做了什么

### 1. `src/a01_rag/t01_ping_api.py` —— 调通大模型

四步：读 API Key → 建 OpenAI 客户端（`base_url` 指向 DeepSeek 兼容接口）→ 发一条对话（`extra_body` 关掉思考模式，让链路最简单）→ 打印回答和 token 用量。

> 关键认知：**LLM 调用 = 一个 HTTP 请求 + 一个 JSON 响应**，token 是要花钱的。

### 2. `src/a01_rag/t02_rag_ingest.py` —— RAG 建库（入库半边）

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

### 3. `src/a01_rag/t03_rag_query.py` —— RAG 问答（检索半边）

```
用户问题 → 向量化（必须和入库用同一个模型！）→ ChromaDB 检索 Top-3
        → 拼进 Prompt（片段带编号和来源，并要求"查不到就如实说"）
        → DeepSeek 生成最终回答
```

> 关键认知：**入库和查询必须用同一个 Embedding 模型**，否则向量空间对不上，检索全是噪声。

### 4. `src/a02_tool_calling/t01_tool_calling_0.py` —— 最小工具调用闭环

一次调用、一个工具、没有循环。看清三件事：

1. 把工具清单（JSON Schema）发给 LLM，LLM 返回 `tool_calls`——**只有工具名 + 参数 JSON 字符串**
2. Python 自己 `json.loads` 解析参数、调用 `multiply()`——**LLM = 决策者，Python = 执行者**
3. 结果包成 `{"role": "tool", "tool_call_id": ..., "content": ...}` 追加进历史，**再调一次 LLM** 生成最终回答

> 关键认知：`tool_call_id` 是"这条结果对应哪次调用"的凭证。这里用了 `tool_calls[0]`，这个假设在下一步被打破。

### 5. `src/a02_tool_calling/t02_tool_calling.py` —— Agent Loop（核心文件）

在最小闭环上加 `while True`：`LLM → Tool → LLM → Tool → …`，直到 LLM 不再要求调用工具才结束。三个升级：

- **循环**：两步任务"先 10+20 再 ×5"必须连续调用 `add` → `multiply`，证明循环真的在跑
- **遍历** `tool_calls`：一次响应可能返回多个调用，不能再用 `[0]`
- **异常兜底**：参数非法 JSON / 工具名不存在 / 执行抛异常，三种失败都转成一条 tool 消息**喂回给 LLM**，让它自己纠错，程序不崩

> 关键认知：**把错误当成工具结果返回给 LLM，LLM 就能自己纠错**——这是 Agent 比一次性脚本抗造的原因。

### 6. `src/a02_tool_calling/t03_multi_tool_calling.py` —— 一次响应，多个工具

用户问"同时计算 10+20 和 8×9"，LLM 一次返回**两个** tool_call，`for` 循环逐个执行、逐个回传（各自带 `tool_call_id`）。
故意写两个独立计算来诱导这种一次多调的响应。

留了个明显问题：**串行执行**——两个各 2 秒的工具要等 4 秒。于是有了下一步。

### 7. `src/a02_tool_calling/t04_async_tool_calling.py` —— 并行执行工具

工具改成 `async def`（内部 `asyncio.sleep(2)` 模拟网络/数据库耗时），执行抽成 `execute_tool()`，关键三行：

```python
tasks = [execute_tool(tc) for tc in message.tool_calls]
results = await asyncio.gather(*tasks)   # 并发执行，耗时从求和变取最大值
messages.extend(results)
```

> 关键认知：工具是 IO 密集型时并行收益巨大；纯 CPU 计算不受益（那要用多进程）。

### 8. `src/a02_tool_calling/t05_tool_registry.py` —— Registry + Dispatcher（架构化）

把散在主循环里的工具处理收拢成两个概念：

| 概念 | 是什么 | 给谁用 |
|------|--------|--------|
| `TOOL_REGISTRY` | 工具名 → Python 函数的字典 | **Python** 查表执行 |
| `TOOLS`（JSON Schema） | 工具名 + 描述 + 参数说明 | **LLM** 看的说明书 |

`dispatch_tool()` 是调度中心：取名字 → 解析参数 → 查表 → 执行 → 包装成 tool 消息；工具不存在、执行异常都转成错误字符串回传。主循环只剩"调 LLM → gather → 回灌"。

> 关键认知：**Tool Schema ≠ Python 函数**，两者靠工具名这份"契约"连接。

### 9. `src/a02_tool_calling/t06_tool_validation.py` —— 参数校验

新增 `validate_arguments()`：检查参数**存在**（缺了抛 `ValueError`）、**类型对**（不对抛 `TypeError`）。Dispatcher 变成流水线：

```
解析 JSON → 查表 → 参数校验 → 执行
   ↓ 任一步失败，都转成 tool 消息交还 LLM
```

> 关键认知：LLM 生成的参数**经常会错**。校验不是防坏人，是在错误进业务代码前拦住、并把原因告诉 LLM 让它重试。（手工 if/elif 是最简实现，生产上一般用 Pydantic 按 Schema 自动校验。）

### 10. `src/a02_tool_calling/t07_tool_runtime.py` —— 超时 + 重试

校验拦得住坏参数，拦不住"工具本身挂了"。新增 `execute_tool()` 运行时：

- **超时**：`asyncio.wait_for(..., timeout=3)`
- **重试**：失败歇 1 秒再试，最多 3 次
- **最终失败**：重试耗尽抛 `RuntimeError`，由 Dispatcher 转成 tool 消息

专门造了 `slow_tool()`（睡 10 秒 vs 超时 3 秒）来观察完整的"超时 → 重试 → 兜底"日志。

> 关键认知：**重试要有边界**——超时预算要和整体响应时间一起设计。

### 11. `src/a03_agent/t01_rag_agent.py` —— 两条线合流

把 a01_rag/t03_rag_query 的检索逻辑原样封装成 `search_knowledge(query)` 工具，注册进 Registry，套上 Agent Loop。关键转变是**谁来决定检索**：

| | 写死的 RAG（a01_rag） | RAG as a Tool（t01_rag_agent） |
|---|---|---|
| 检索时机 | 每个问题都查 | LLM 判断需要时才调 |
| 检索次数 | 固定 1 次 | 可多次，可换问法再查 |
| 闲聊/算术 | 也去查库，白跑 | 直接回答，不触发检索 |

System Prompt 写明三条规矩：需要就调 `search_knowledge`、拿到结果严格按内容回答、查不到就说没查到不编造。

> 关键认知：**Tool 的返回值就是 Prompt**——`search_knowledge` 返回的 `[知识片段 1]…` 文本会直接喂给 LLM，怎么组织它和写 Prompt 是一回事。

### 12. `src/a03_agent/t02_agent.py` —— 有状态的多轮 Agent

三个增量：

- **`AgentState` 外置**：state 由 `main()` 创建、长期持有，`agent()` 只使用不创建——Agent 从"一次性脚本"变成"常驻服务"，记忆 = 历史消息全留在 `state.messages` 里
- **多轮对话**：外层 `while True` 等用户输入（`exit` 退出），内层 Agent Loop 处理单次任务；System Prompt 只初始化一次
- **`MAX_STEPS`**：`for` 循环限制单次任务最多 10 步（state 跨轮持有，step 每轮重置），防止 LLM 陷入"反复调同一个工具"的死循环烧 token

工具集扩到 4 个：`add` / `multiply` / `subtract` + 从 RAG 线合流来的 `search_knowledge`。可以试 *"JVM 有几个运行时数据区，再乘以 3 等于多少"* 这种既查库又计算的复合问题。

> 关键认知：**Agent Loop 必须能停下来**——正常完成、步数上限、用户退出，三个退出条件各管一层。
> 注意：t02_agent 是"框架骨架"，刻意回退了校验/超时/并行，每个文件只聚焦一个新概念。

### 13. `src/a03_agent/t03_summary_memory.py` —— 摘要记忆

多轮对话下 `state.messages` 只增不减，聊久了必然顶到上下文上限。解法：把旧历史滚动摘要成一段文本。

- **记忆分两层**：`messages` 存最近原文，`summary` 存更早历史的压缩版；发给 LLM 的上下文由 `build_context()` 现场组装：system prompt + 摘要（包成一条 system 消息）+ 最近消息
- **滚动摘要**：每轮结束后，消息数超过阈值（4）就把旧消息交给 LLM 总结——总结时带着**旧摘要**，在它基础上叠加，最老的信息逐轮被压缩
- **切分必须落在 user 消息边界**：assistant(tool_calls) 消息必须紧跟它的 tool 结果，从中间切开下次请求直接报错，所以切分点要向前回溯到最近的 user 消息——这是本文件最大的坑
- **顺手加固**：assistant 回复无论有无 tool_calls 都先入历史（上一版的遗留 bug）、参数解析失败不崩、空输入跳过

> 关键认知：**摘要本身也是一次 LLM 调用，压缩记忆有成本**；生产上按 token 数而非消息条数触发。

### 14. `src/a04_memory/t01_memory_extractor.py` —— 长期记忆提取

摘要记忆只记住"聊过什么"，记不住"用户是谁"。这一步把记忆拆出第三个层次：**跨会话的长期记忆**——从用户消息里提取稳定事实（姓名、职业、长期目标），将来存下来供后续会话使用。

- **记忆提取器**：`extract_memories()` 把一条用户消息连同提取规则发给 LLM，返回一个字符串数组，每个元素是一条独立记忆
- **提取规则写进 Prompt**：正例（姓名/职业/长期兴趣/偏好/目标/进行中的重要项目）和反例（一次性计算、闲聊、临时问题）都明确列出，边界靠规则约束
- **结构化输出**：要求 LLM 只输出 JSON 数组；`json.loads` 解析失败或结果不是数组时降级返回 `[]`，不让坏输出崩掉调用方
- **测试脚本**：`src/a04_memory/t03_test_memory_extractor.py` 用 6 条消息验证——4 条个人信息应提取，计算和闲聊应返回 `[]`
- **入库函数**：`save_user_memory()` 把提取和存储串起来——先调 `extract_memories()`，再逐条 `store.add()` 写库

> 关键认知：**提取 = 让 LLM 做分类 + 结构化输出**；和 a03_agent 的摘要对比——摘要是"有损压缩自己的历史"，提取是"从消息里筛出要永久保存的事实"。
> 注意：本文件只做"提取"这一步，记忆的存储和召回（写入向量库 / 注入 system prompt）是后续步骤。

### 15. `src/a04_memory/t02_memory_store.py` —— 记忆存储

提取出的记忆要落到磁盘才能跨会话使用。`MemoryStore` 用 SQLite 做最简单的持久层：

- **表结构只有三列**：`id`（自增主键）、`user_id`（谁的记忆）、`content`（记忆内容），建表语句 `CREATE TABLE IF NOT EXISTS` 保证重复初始化不报错
- **按用户隔离**：`add(user_id, content)` 写入、`list(user_id)` 按 `user_id` 过滤按序读出，不同用户的记忆互不可见
- **测试脚本**：`src/a04_memory/t04_test_long_term_memory.py` 串起完整链路：5 条用户消息 → 逐条提取 → 写库 → 打印该用户的全部记忆，跑完会在项目根 `temp/` 下生成 `agent_memory.db`（已 gitignore）

> 关键认知：**长期记忆 = 提取（LLM 决定存什么）+ 存储（数据库负责持久和隔离）**；SQLite 一个文件就是一套方案，够用就不上向量库。
> 注意：记忆的"召回"（对话开始时把记忆注入 system prompt）是下一步。

### 16. `src/a04_memory/t05_memory_crud.py` —— 记忆存储升级：完整 CRUD

t02_memory_store 的最简版只有 add/list 两个方法，这一步扩成生产记忆库的样子：

- **五个操作全齐**：`add`（新增，返回自增 id）/ `get`（按 id 查单条）/ `list`（查全部）/ `update`（修改）/ `delete`（删除），update/delete 都返回 `rowcount > 0` 表示是否真的生效
- **新增分类字段**：`category`（profile / career / interest / preference…）给记忆打标，为将来按类别检索留口子
- **时间戳**：`created_at` / `updated_at` 由数据库自动维护，`search` 按 `updated_at` 倒序——最近更新过的记忆排前面
- **索引**：`CREATE INDEX idx_memories_user`，按 `user_id` 查询走索引
- **`sqlite3.Row`**：行结果可以直接 `dict(row)`，也支持 `row['column']` 按列名取值
- **测试脚本**：`src/a04_memory/t06_test_crud.py` 把六个方法各调一遍，每步打印验证

> 关键认知：**所有写操作都带 `WHERE user_id = ?`**——隔离不是"约定不同用户别混"，是每条 SQL 强制保证的。

### 17. `src/a04_memory/t07_memory_retriever.py` —— 记忆检索：LLM 提关键词

存进去的记忆怎么找回来？直接拿用户原话去 LIKE 匹配命中率很低（"我现在做什么工作？"匹配不到"职业是 Java 工程师"）。解法是让 LLM 先把问题翻译成检索关键词：

```
用户问题 → DeepSeek 提取关键词（考虑同义词，如"职业"→["职业", "工作", "工程师"]）
        → 逐个关键词查 SQLite → 按记忆 ID 去重 → 截取 limit 条返回
```

- **关键词提取是独立的 LLM 调用**：System Prompt 里给示例、提要求（同义词、多个关键词、去掉语气词），`temperature=0` 保证输出稳定
- **结构化输出兜底**：和 t01 提取器一样的套路——只要 JSON 数组，解析失败或不是数组就降级返回 `[]`
- **去重**：多个关键词可能命中同一条记忆，用记忆 `id` 做 dict key 去重

> 关键认知：**检索前加一层"LLM 改写"，是 RAG 检索和记忆召回共用的套路**——用户的自然语言和数据库的存储格式之间需要一个翻译步骤。
> 注意：这里是 LIKE 关键词匹配，比 a01_rag 的向量检索粗糙，但够用且零依赖；记忆量大了再换 Embedding。

### 18. `src/a04_memory/t08_agent_memory_demo.py` —— 长期记忆 Agent（合体）

把提取（t01）、存储（t05_memory_crud）、检索（t07_memory_retriever）串成能对话的 Agent：

- **Memory Read 流程**：每个用户问题 → `retrieve_memories()` 找相关记忆 → 整理成 `- 记忆内容` 列表 → 作为第二条 system 消息注入 → LLM 按记忆回答
- **回答规则写进 System Prompt**：可参考记忆、不编造记忆里没有的、没有相关记忆就明说不知道——和 t01_rag_agent 的 RAG 规矩一脉相承
- **演示数据自举**：库空则先写入 4 条测试记忆（张三 / Java 工程师 / 学 Agent / 先原理后框架），然后交互循环提问，`exit` 退出

至此长期记忆的读路径闭环了：**问"我叫什么"→ 提取关键词"姓名/名字"→ LIKE 搜库 → 记忆注入 prompt → Agent 答出"张三"**。写路径（对话中自动提取入库）是下一步。

> 关键认知：**长期记忆的用法 = 每轮对话前先查库、把查到的塞进 system prompt**——和 RAG 同构，只是查的对象从文档换成了用户自己的事实。

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
| `MemoryStore` | SQLite 存取长期记忆，`user_id` 隔离不同用户 |
| LLM 提取检索关键词 | 用户问题 → 同义词关键词 → 查库；自然语言和存储格式之间的翻译层 |
| Memory Read | 每轮对话前检索长期记忆，注入 system prompt 供 LLM 参考 |


---
