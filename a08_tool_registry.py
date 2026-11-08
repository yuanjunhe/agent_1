# ============================================================
# 抽出 Tool Registry + Dispatcher
#
# 对比内联写法：之前工具查表和执行逻辑都写在主循环里；这个
# 版本把"按名字找函数 + 执行 + 兜底"封装成 dispatch_tool，
# 主循环只管调用它。新增 subtract 工具演示第三个工具如何接入。
#
# 运行：uv run a08_tool_registry.py
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


# 2. 定义 Tool

async def add(a, b):
    await asyncio.sleep(2)
    return a + b


async def multiply(a, b):
    await asyncio.sleep(2)
    return a * b


async def subtract(a, b):
    await asyncio.sleep(2)
    return a - b


# 3. Tool Registry
# 工具名 → Python 函数。Agent 不需要知道函数定义在哪里，
# 只凭名字查表。LLM 只认名字，这是架构解耦的关键。

TOOL_REGISTRY = {
    "add": add,
    "multiply": multiply,
    "subtract": subtract
}


# 4. Dispatcher：Agent 的"工具调度中心"
# 职责：查 Registry → 解析参数 → 执行 → 打包 tool 消息返回；
# 工具不存在、执行异常都不崩溃，把错误作为结果回传给 LLM

async def dispatch_tool(tool_call):

    tool_name = tool_call.function.name

    # arguments 是 JSON 字符串，如 '{"a": 10, "b": 20}'，转成 dict
    arguments = json.loads(tool_call.function.arguments)

    print(f"Dispatcher 收到请求：{tool_name}({arguments})")

    # 从 Registry 查找；找不到不崩溃，返回错误消息
    tool_function = TOOL_REGISTRY.get(tool_name)
    if tool_function is None:
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"错误：Tool '{tool_name}' 不存在"
        }

    # 执行 Tool；异常也作为 tool 结果回传（参数校验、超时留到后面阶段）
    try:
        result = await tool_function(**arguments)
        print(f"Tool 执行完成：{tool_name} → {result}")

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result)
        }

    except Exception as e:
        print(f"Tool 执行失败：{tool_name} → {e}")

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"Tool 执行失败：{str(e)}"
        }


# 5. Tool Schema
# TOOL_REGISTRY 是给 Python 查表用的，tools 是给 LLM "看"的，两者别混淆

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
    },
    {
        "type": "function",
        "function": {
            "name": "subtract",
            "description": "计算两个数字的差",
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


# 6. Agent Loop
# 和上一版的骨架相同，区别：主循环不再自己找工具，全部交给 Dispatcher

async def main():

    messages = [
        {
            "role": "user",
            "content": (
                "同时计算："
                "10 + 20，"
                "8 × 9，"
                "100 - 30。"
            )
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

        # 为每个 tool_call 建协程任务（查找和执行全在 Dispatcher 里），
        # asyncio.gather 并行执行，结果批量回传
        print(f"LLM 请求调用 {len(message.tool_calls)} 个 Tool")

        tasks = [
            dispatch_tool(tool_call)
            for tool_call in message.tool_calls
        ]

        results = await asyncio.gather(*tasks)

        messages.extend(results)


# 7. 启动 Agent
if __name__ == "__main__":
    asyncio.run(main())
