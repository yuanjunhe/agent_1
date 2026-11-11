# ============================================================
# 工具运行时：超时 + 重试 + 异常处理
#
# 对比上一版：参数校验能拦住坏参数，但工具本身挂了（比如慢接口卡死）
# 还是会拖垮 Agent。这个版本给执行环节加运行时保护：
# execute_tool 用 asyncio.wait_for 限时、失败自动重试，
# slow_tool（睡 10 秒，超时 3 秒）专门演示超时重试路径。
#
# 运行：uv run python src/a02_tool_calling/t07_tool_runtime.py
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


# 慢工具：实际项目中对应 HTTP 请求 / 数据库查询 / 第三方 API
# 故意睡 10 秒，用来触发下面的超时重试逻辑

async def slow_tool():
    print("slow_tool 开始执行")
    await asyncio.sleep(10)
    return "slow tool success"


# 3. Tool Registry

TOOL_REGISTRY = {
    "add": add,
    "multiply": multiply,
    "slow_tool": slow_tool
}


# 4. 参数校验（和上一版相同）

def validate_arguments(tool_name, arguments):

    if tool_name in ["add", "multiply"]:

        if "a" not in arguments:
            raise ValueError("缺少参数：a")
        if "b" not in arguments:
            raise ValueError("缺少参数：b")
        if not isinstance(arguments["a"], (int, float)):
            raise TypeError("参数 a 必须是数字")
        if not isinstance(arguments["b"], (int, float)):
            raise TypeError("参数 b 必须是数字")


# 5. 执行 Tool：超时 + 重试（本文件的新东西）
# wait_for 限时 timeout 秒，超时或异常都重试，最多 max_retries 次，
# 每次重试前歇 1 秒；重试耗尽抛 RuntimeError 交给 Dispatcher 兜底

async def execute_tool(
    tool_function,
    arguments,
    timeout=3,
    max_retries=3
):

    for attempt in range(1, max_retries + 1):

        try:
            print(f"Tool 第 {attempt} 次执行")

            # wait_for：最多等 timeout 秒，超时抛 TimeoutError
            result = await asyncio.wait_for(
                tool_function(**arguments),
                timeout=timeout
            )

            # 执行成功，直接返回
            return result

        except asyncio.TimeoutError:
            print(f"Tool 执行超时：{timeout} 秒")

            # 没到重试上限就歇 1 秒再试，否则抛错
            if attempt < max_retries:
                print("准备重试...")
                await asyncio.sleep(1)
            else:
                raise RuntimeError(
                    f"Tool 执行超时，已经重试 {max_retries} 次"
                )

        except Exception as e:
            print(f"Tool 执行异常：{e}")

            if attempt < max_retries:
                print("准备重试...")
                await asyncio.sleep(1)
            else:
                raise RuntimeError(f"Tool 执行失败：{e}")


# 6. Dispatcher
# 流水线：解析 JSON → 查表 → 校验 → 带运行时保护的执行，每步失败都回传

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

    print(f"\nDispatcher 收到：{tool_name}")
    print(f"参数：{arguments}")

    # 查找 Tool
    tool_function = TOOL_REGISTRY.get(tool_name)
    if tool_function is None:
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"Tool 不存在：{tool_name}"
        }

    # 参数校验
    try:
        validate_arguments(tool_name, arguments)
    except (ValueError, TypeError) as e:
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"参数错误：{e}"
        }

    # 执行 Tool：超时 3 秒、最多重试 3 次
    try:
        result = await execute_tool(
            tool_function,
            arguments,
            timeout=3,
            max_retries=3
        )
        print(f"Tool 执行成功：{tool_name} → {result}")

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result)
        }

    # 最终失败（重试耗尽）：错误作为 tool 结果回传，不拖垮 Agent
    except Exception as e:
        print(f"Tool 最终执行失败：{e}")
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"Tool 执行失败：{e}"
        }


# 7. Tool Schema

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
            "name": "slow_tool",
            "description": "一个执行时间很长的测试工具",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


# 8. Agent Loop
# 骨架和上一版相同，用户消息里故意要求调用 slow_tool 触发超时重试

async def main():

    messages = [
        {
            "role": "user",
            "content": (
                "同时计算 10 + 20，"
                "8 × 9，"
                "并测试一下 slow_tool。"
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


# 9. 启动
if __name__ == "__main__":
    asyncio.run(main())
