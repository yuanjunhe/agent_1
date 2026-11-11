# 长期记忆：提取 → 存储 → 检索 → 注入

## 架构总览

```
长期记忆演进流程（t01 → t08，每个文件在上一个基础上加一件事）：

  写路径：把值得长期保存的信息存下来
  ─────────────────────────────────────────────
  用户消息
       │
       ▼
   t01 提取（extract_memories）
       │  LLM 判断哪些是稳定事实（姓名/职业/目标），
       │  返回 JSON 数组，解析失败降级为 []
       ▼
   t02 最简存储（MemoryStore）
       │  SQLite 一张表：id / user_id / content
       ▼
   t05 存储升级：完整 CRUD
          add / get / list / update / delete / search，
          加 category 字段 + 时间戳 + user_id 索引
  ─────────────────────────────────────────────
            ┃  ★ 隔离靠每条 SQL 强制 WHERE user_id = ?
            ▼
  读路径：把记忆找回来注入对话
  ─────────────────────────────────────────────
  用户问题
       │
       ▼
   t07 检索（retrieve_memories）
       │  LLM 先把问题改写成关键词（含同义词），
       │  逐个关键词 LIKE 查库，按记忆 id 去重
       ▼
   t08 注入（Agent 合体）
       │  记忆整理成列表，作为第二条 system 消息
       ▼
   LLM 参考记忆回答，没有就说不知道

  测试文件：
  t03 测提取（6 条消息：4 条应提取，计算/闲聊返回 []）
  t04 串完整写链路（提取 → 写库 → 打印）
  t06 测 CRUD 六个方法
```

## 文件清单

| 文件 | 角色 | 关键点 |
|---|---|---|
| `t01_memory_extractor.py` | 记忆提取 | LLM 做分类 + 结构化输出，正反例规则写进 Prompt |
| `t02_memory_store.py` | 最简存储 | SQLite 三列表，add/list 按 user_id 隔离 |
| `t03_test_memory_extractor.py` | 提取测试 | 6 条消息验证提取边界 |
| `t04_test_long_term_memory.py` | 端到端测试 | 提取 → 写库 → 打印，串起写路径 |
| `t05_memory_crud.py` | 存储升级 | 完整 CRUD + category + 时间戳 + 索引 + LIKE 搜索 |
| `t06_test_crud.py` | CRUD 测试 | 六个方法各调一遍逐步验证 |
| `t07_memory_retriever.py` | 记忆检索 | 检索前加"LLM 改写"，问题 → 关键词 → 查库 → 去重 |
| `t08_agent_memory_demo.py` | 合体演示 | 检索到的记忆注入 system prompt，读路径闭环 |

## 一条主线

长期记忆分两条路：**写路径**靠 LLM 决定"存什么"（提取 = 分类 + 结构化输出），数据库负责持久和隔离；**读路径**靠 LLM 改写"怎么查"（检索前先翻译成关键词）。摘要记忆（a03_agent/t03）记住"聊过什么"，这里存的是"用户是谁"，跨会话不丢。
