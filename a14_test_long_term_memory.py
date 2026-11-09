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