# RAG 知识库

## 架构总览

```
RAG 实现流程：

  离线：建库（t02_rag_ingest.py，跑一次）
  ─────────────────────────────────────────────
  读取文档
       │
       ▼
   切分 Chunk
       │
       ▼
   向量化（Embedding）
       │
       ▼
   存入 ChromaDB（持久化）
  ─────────────────────────────────────────────
            ┃  ★ 入库和查询必须用同一个 Embedding 模型
            ▼
  在线：问答（t03_rag_query.py，交互循环）
  ─────────────────────────────────────────────
  用户问题
       │
       ▼
   问题向量化
       │
       ▼
   向量检索 Top-3
       │
       ▼
   拼 Prompt
       │
       ▼
   LLM 生成回答

```

## 文件清单

| 文件 | 角色 | 关键点 |
|---|---|---|
| `t01_ping_api.py` | LLM 冒烟测试 | 读 Key → 建客户端 → 发一条对话 → 打印回答和 token 用量 |
| `t02_rag_ingest.py` | 建库（写路径） | 读取 → 切分 → 向量化 → 入库 → 抽查验证，`main()` 串流水线 |
| `t03_rag_query.py` | 问答（读路径） | 向量检索 Top-3 → 拼 Prompt → 生成回答，交互循环 |

## 两个半边的共享契约

t02 写库、t03 读库，两边靠这三个约定对上，任何一边改了另一边必须跟着改：

| 契约 | 值 | 谁用 |
|---|---|---|
| Embedding 模型 | `BAAI/bge-small-zh-v1.5`（512 维） | t02 和 t03 **必须一致**，否则向量空间对不上，检索全是噪声 |
| Collection 名 | `java_knowledge` | t02 写 / t03 读 |
| Chunk 参数 | size=200，overlap=50 | 只影响 t02 建库质量，t03 无感 |

## 运行顺序

```bash
uv run python src/a01_rag/t01_ping_api.py   # 可选：先验证 API 通
uv run python src/a01_rag/t02_rag_ingest.py # 建库（换机器/换文档后重跑）
uv run python src/a01_rag/t03_rag_query.py  # 问答（依赖 t02 建好的库）
```

`data/`（原始文档）和 `chroma_db/`（向量库）都已 gitignore。
