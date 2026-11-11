# ============================================================
# 长期记忆 Agent 演示：CRUD 存储 + 记忆检索 + LLM 回答串成闭环
#
# 先给测试用户准备几条记忆，然后进入交互循环：
# 每个问题先经 retrieve_memories() 检索相关长期记忆，
# 检索结果注入 system prompt，再让 LLM 按记忆回答。
# 输入 exit / quit 退出。
#
# 运行：uv run python src/a04_memory/t08_agent_memory_demo.py
# ============================================================

import os
import asyncio

from openai import AsyncOpenAI

from t05_memory_crud import MemoryStore
from t07_memory_retriever import retrieve_memories


client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# 用户 ID
USER_ID = "user_001"


async def ask_agent(question: str, memories: list[dict]) -> str:
    """
    将检索到的长期记忆交给 LLM，生成最终答案。
    """

    # 把记忆整理成文本
    if memories:
        memory_text = "\n".join(
            f"- {item['content']}"
            for item in memories
        )
    else:
        memory_text = "没有检索到相关的长期记忆。"

    messages = [
        {
            "role": "system",
            "content": """
你是一个具有长期记忆能力的 Agent。

回答规则：
1. 可以参考提供的长期记忆回答问题。
2. 不要编造长期记忆中不存在的信息。
3. 如果记忆中没有相关信息，明确说明不知道。
4. 对于普通知识问题，可以使用自身知识回答。
"""
        },
        {
            "role": "system",
            "content": f"""
以下是从用户长期记忆中检索到的信息：

{memory_text}
"""
        },
        {
            "role": "user",
            "content": question
        }
    ]

    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0
    )

    return response.choices[0].message.content or ""


async def main():

    # 初始化数据库
    store = MemoryStore()

    try:
        # 第一步：准备测试数据
        # 使用独立的测试用户，避免影响其他数据
        test_user_id = USER_ID

        existing_memories = store.list(test_user_id)

        if not existing_memories:
            store.add(
                test_user_id,
                "profile",
                "用户叫张三"
            )

            store.add(
                test_user_id,
                "career",
                "用户是一名 Java 工程师"
            )

            store.add(
                test_user_id,
                "interest",
                "用户正在学习 Agent 开发"
            )

            store.add(
                test_user_id,
                "preference",
                "用户喜欢先理解底层原理，再使用框架"
            )

        print("========== 当前长期记忆 ==========")

        for item in store.list(test_user_id):
            print(
                f"ID={item['id']} | "
                f"分类={item['category']} | "
                f"内容={item['content']}"
            )

        # 第二步：进入交互测试
        while True:

            question = input("\n用户：").strip()

            if question.lower() in ("exit", "quit"):
                break

            if not question:
                continue

            # 第三步：Memory Read
            memories = await retrieve_memories(
                store,
                test_user_id,
                question
            )

            print("\n========== 检索结果 ==========")

            if memories:
                for item in memories:
                    print(
                        f"ID={item['id']} | "
                        f"{item['content']}"
                    )
            else:
                print("没有检索到相关记忆")

            # 第四步：将记忆交给 LLM
            answer = await ask_agent(
                question,
                memories
            )

            print("\nAgent：", answer)

    finally:
        store.close()


if __name__ == "__main__":
    asyncio.run(main())
