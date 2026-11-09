# ============================================================
# 长期记忆端到端测试：提取 + 存储串成完整链路
#
# 5 条用户消息逐条交给 extract_memories() 提取，
# 提取结果写入 MemoryStore，最后打印该用户的全部记忆；
# 跑完会在当前目录生成 agent_memory.db。
#
# 运行：uv run a14_test_long_term_memory.py
# ============================================================

import asyncio

from a14_memory import MemoryStore
from a14_memory_extractor import extract_memories


async def main():

    user_id = "user_001"

    store = MemoryStore()

    messages = [
        "我叫张三",
        "我是 Java 工程师",
        "我正在学习 Agent 开发",
        "我喜欢先理解底层原理，再使用框架",
        "帮我计算 123 * 456",
    ]

    for message in messages:

        print(f"\n用户：{message}")

        memories = await extract_memories(message)

        print("提取出的 Memory：", memories)

        for memory in memories:
            store.add(
                user_id,
                memory
            )

    print("\n========== 数据库中的 Memory ==========")

    memories = store.list(user_id)

    for memory in memories:
        print(memory)


if __name__ == "__main__":
    asyncio.run(main())