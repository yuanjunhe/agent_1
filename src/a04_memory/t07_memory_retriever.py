# ============================================================
# 记忆检索器：根据用户问题，从长期记忆库里找回相关记忆
#
# 链路：用户问题 → LLM 提取检索关键词（考虑同义词，
# JSON 数组输出）→ 逐个关键词查 SQLite → 按 ID 去重
# → 限制条数返回。关键词提取失败时降级为空列表。
#
# 运行：uv run python src/a04_memory/t08_agent_memory_demo.py
# ============================================================

import os
import json

from openai import AsyncOpenAI

from t05_memory_crud import MemoryStore


client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


async def extract_search_keywords(question: str) -> list[str]:
    """
    使用 LLM 从用户问题中提取记忆检索关键词。
    """

    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": """
你负责从用户问题中提取长期记忆检索关键词。

要求：
1. 提取能够用于数据库检索的关键词。
2. 考虑同义词和相关表达。
3. 尽量提取多个关键词。
4. 不要提取无意义的语气词。

例如：

问题：我现在的职业是什么？
输出：["职业", "工作", "工程师", "程序员"]

问题：我叫什么名字？
输出：["姓名", "名字", "叫"]

问题：我最近在学习什么？
输出：["学习", "正在学习", "研究"]

只输出 JSON 数组，不要输出其他内容。
"""
            },
            {
                "role": "user",
                "content": question
            }
        ],
        temperature=0
    )

    content = response.choices[0].message.content or ""

    try:
        keywords = json.loads(content)

        if not isinstance(keywords, list):
            return []

        return [
            str(item).strip()
            for item in keywords
            if str(item).strip()
        ]

    except json.JSONDecodeError:
        print("关键词解析失败：", content)
        return []


async def retrieve_memories(
    store: MemoryStore,
    user_id: str,
    question: str,
    limit: int = 5
) -> list[dict]:
    """
    根据用户问题检索相关长期记忆。
    """

    # 第一步：LLM 提取关键词
    keywords = await extract_search_keywords(question)

    print("\n提取的检索关键词：", keywords)

    # 第二步：根据关键词查询 SQLite
    results = {}

    for keyword in keywords:

        memories = store.search(
            user_id,
            keyword,
            limit=limit
        )

        for memory in memories:
            # 使用记忆 ID 去重
            results[memory["id"]] = memory

    # 第三步：限制最终返回数量
    return list(results.values())[:limit]
