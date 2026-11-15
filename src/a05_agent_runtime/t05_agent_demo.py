# ============================================================
# Agent 演示：多轮对话入口，串起 t01/t03/t04
#
# main() 创建 Runtime 和消息列表，循环读用户输入；
# agent()（t04）持有 Agent Loop，工具执行走
# t01_tool_runtime 的 dispatch 全链路。
#
# 运行：uv run python src/a05_agent_runtime/t05_agent_demo.py
# ============================================================

import asyncio

from t04_agent import (
    agent,
    SYSTEM_PROMPT,
    create_runtime
)


# 1. 创建运行时和初始消息
async def main():

    runtime, registry = create_runtime()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    print("Agent 已启动，输入 exit 退出。")

    # 2. 多轮对话：每次输入追加进同一个 messages，上下文跨轮保留
    while True:

        question = input("\n用户：").strip()

        if question.lower() == "exit":
            break

        if not question:
            continue

        messages.append({
            "role": "user",
            "content": question
        })

        # 3. 调 Agent Loop 处理本轮任务
        answer = await agent(
            messages,
            runtime,
            registry
        )

        print("\nAgent：", answer)


# 4. 启动
if __name__ == "__main__":
    asyncio.run(main())
