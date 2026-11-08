# ============================================================
# 参数校验：缺参数、类型不对都要拦住
#
# 对比上一版：Dispatcher 直接信任 LLM 给的参数；这个版本在查表
# 和执行之间加一道 validate_arguments——参数缺失抛 ValueError、
# 类型不对抛 TypeError，校验失败时把错误作为 tool 结果回传，
# LLM 有机会修正后重试。
#
# 运行：uv run a09_tool_validation.py
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
    await asyncio.sleep(1)
    return a + b


async def multiply(a, b):
    await asyncio.sleep(1)
    return a * b


# 3. Tool Registry

TOOL_REGISTRY = {
    "add": add,
    "multiply": multiply
}


# 4. 参数校验器（本文件的新东西）
# 检查参数是否存在（ValueError）、类型是否正确（TypeError），
# 最简实现：每个工具一组手写检查

def validate_arguments(tool_name, arguments):

    if tool_name == "add":
        if "a" not in arguments:
            raise ValueError("缺少参数：a")
        if "b" not in arguments:
            raise ValueError("缺少参数：b")
        if not isinstance(arguments["a"], (int, float)):
            raise TypeError("参数 a 必须是数字")
        if not isinstance(arguments["b"], (int, float)):
            raise TypeError("参数 b 必须是数字")

    elif tool_name == "multiply":
        if "a" not in arguments:
            raise ValueError("缺少参数：a")
        if "b" not in arguments:
            raise ValueError("缺少参数：b")
        if not isinstance(arguments["a"], (int, float)):
            raise TypeError("参数 a 必须是数字")
        if not isinstance(arguments["b"], (int, float)):
            raise TypeError("参数 b 必须是数字")

    else:
        raise ValueError(f"未知 Tool：{tool_name}")


# 5. Dispatcher：在上一版基础上多了一道校验
# 完整流水线：解析 JSON → 查表 → 校验参数 → 执行，每步失败都回传错误

async def dispatch_tool(tool_call):

    tool_name = tool_call.function.name

    # 解析 JSON 参数，不合法就回传错误
    try:
        arguments = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": "Tool 参数不是合法 JSON"
        }

    print(f"\nDispatcher 收到请求：{tool_name}")
    print(f"Tool 参数：{arguments}")

    # 检查 Tool 是否存在
    tool_function = TOOL_REGISTRY.get(tool_name)
    if tool_function is None:
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"Tool 不存在：{tool_name}"
        }

    # 参数校验：缺参数 / 类型不对都会被拦在这里
    try:
        validate_arguments(tool_name, arguments)
    except (ValueError, TypeError) as e:
        print(f"参数校验失败：{e}")
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"参数错误：{e}"
        }

    # 执行 Tool；执行期异常同样兜底
    try:
        result = await tool_function(**arguments)
        print(f"Tool 执行成功：{tool_name} → {result}")

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result)
        }

    except Exception as e:
        print(f"Tool 执行异常：{e}")
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"Tool 执行失败：{e}"
        }


# 6. Tool Schema
# 注意 multiply 的参数故意没写 description——模拟描述不全的真实场景

tools = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "计算两个数字的和",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {
                        "type": "number",
                        "description": "第一个数字"
                    },
                    "b": {
                        "type": "number",
                        "description": "第二个数字"
                    }
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


# 7. Agent Loop
# 骨架和上一版相同，健壮性全部在 Dispatcher 里

async def main():

    messages = [
        {
            "role": "user",
            "content": (
                "同时计算 "
                "10 + 20，"
                "以及 8 × 9。"
            )
        }
    ]

    while True:

        print("\n================ 调用 DeepSeek ================")

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
            print("\n================ 最终回答 ================")
            print(message.content)
            break

        # 并行执行所有 tool_call，结果批量回传
        tasks = [
            dispatch_tool(tool_call)
            for tool_call in message.tool_calls
        ]

        results = await asyncio.gather(*tasks)

        messages.extend(results)


# 8. 启动
if __name__ == "__main__":
    asyncio.run(main())
