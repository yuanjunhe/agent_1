# ============================================================
# 记忆提取器测试：用一组典型消息验证 t01_memory_extractor
#
# 覆盖两类输入：值得记忆的（姓名、职业、兴趣、偏好）
# 和不值得记忆的（计算任务、闲聊），检查提取结果是否符合预期。
#
# 运行：uv run python src/a04_memory/t03_test_memory_extractor.py
# ============================================================

import asyncio

from t01_memory_extractor import extract_memories


async def main():

    test_cases = [
        "我叫张三",
        "我是 Java 工程师",
        "我正在学习 Agent 开发",
        "我喜欢先理解底层原理，再使用框架",
        "帮我计算 123 * 456",
        "今天天气怎么样？",
    ]

    # 1. 逐条调用记忆提取器并打印结果
    for text in test_cases:

        memories = await extract_memories(text)

        print("\n用户：", text)
        print("Memory：", memories)


if __name__ == "__main__":
    asyncio.run(main())
