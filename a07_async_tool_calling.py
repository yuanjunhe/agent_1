# ============================================================
# 并行执行工具：asyncio.gather
#
# 对比串行执行：上一版多个工具是逐个执行的；这个版本把工具
# 改成 async，用 asyncio.gather 同时执行——两个各耗时 2 秒的
# 工具，串行 4 秒、并行约 2 秒。
#
# 运行：uv run a07_async_tool_calling.py
# ============================================================

import os
import json
import asyncio

from openai import AsyncOpenAI


# 1. 创建异步客户端

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not DEEPSEEK_API_KEY:
    raise ValueError(
        "没有找到 DEEPSEEK_API_KEY 环境变量，"
        "请先运行: set DEEPSEEK_API_KEY=你的_API_KEY"
    )

client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


# 2. 定义 Tool（async 版）
# 用 asyncio.sleep(2) 模拟耗时操作（如网络请求），方便对比串行/并行的耗时

async def add(a, b):
    await asyncio.sleep(2)
    return a + b


async def multiply(a, b):
    await asyncio.sleep(2)
    return a * b


# 3. Tool Registry
# 工具名 → Python 函数

tools_map = {
    "add": add,
    "multiply": multiply
}


# 4. 告诉 LLM 有哪些 Tool（Schema）

tools = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "计算两个数字的和",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "multiply",
            "description": "计算两个数字的乘积",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        }
    }
]


# 5. 执行单个 Tool
# 封装一条链：tool_call → 查表找函数 → await 执行 → 打包成 tool 消息
# 返回值直接是可以塞进 messages 的 dict，gather 收集后批量 extend

async def execute_tool(tool_call):
    tool_name = tool_call.function.name

    # arguments 是 JSON 字符串，转成 dict
    arguments = json.loads(tool_call.function.arguments)

    print(f"开始执行 Tool: {tool_name}, 参数: {arguments}")

    tool_function = tools_map[tool_name]
    result = await tool_function(**arguments)

    print(f"Tool 执行完成: {tool_name}, 结果: {result}")

    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": str(result)
    }


# 6. Agent Loop（async 版）
# 骨架和上一版相同，区别只在工具执行那段：并行而不是逐个执行

async def main():

    messages = [
        {
            "role": "user",
            "content": "同时计算 10 + 20，以及 8 × 9。"
        }
    ]

    while True:

        print("\n================ 调用 DeepSeek ================\n")

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        message = response.choices[0].message

        # assistant 消息必须存入历史
        messages.append(message)

        # 没有 tool_calls 说明 LLM 已直接回答，退出
        if not message.tool_calls:
            print("\n================ 最终回答 ================\n")
            print(message.content)
            break

        # 7. 并行执行所有 Tool Call
        # 先为每个 tool_call 建协程任务，asyncio.gather 让它们同时跑
        # （add 和 multiply 同时开始，约 2 秒后一起完成）
        tasks = [
            execute_tool(tool_call)
            for tool_call in message.tool_calls
        ]

        results = await asyncio.gather(*tasks)

        # 所有工具结果批量加入历史，交给 LLM 组织最终回答
        messages.extend(results)


# 8. 启动程序
if __name__ == "__main__":
    asyncio.run(main())
