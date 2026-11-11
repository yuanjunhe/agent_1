# ============================================================
# Agent Loop：本仓库最核心的文件
#
# 在最小工具调用闭环的基础上加上 while True 循环，支持多轮、
# 多工具、错误兜底：LLM 要调几次工具就执行几次，直到它不再
# 要求调用工具、直接给出最终回答为止。
#
#     LLM → Tool → LLM → Tool → LLM → ... → 最终回答
#
# 运行：uv run python src/a02_tool_calling/t02_tool_calling.py
# ============================================================

import os
import json

from openai import OpenAI


# 1. 初始化客户端

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# 2. 定义真正执行的 Python 工具
# LLM = 决策者（返回工具名 + 参数），Python = 执行者（跑下面的函数）

def add(a, b):
    """计算两个数字的和"""
    return a + b


def multiply(a, b):
    """计算两个数字的积"""
    return a * b


# 3. 定义 Tool Schema
# Schema 是给 LLM "看"的（它据此决定何时调用），Python 函数是给程序
# 真正执行的，两者靠 name 对应。description 决定 LLM 什么时候用它。

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
            "description": "计算两个数字的积",
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
    }
]


# 4. 建立消息历史
# 故意给一个两步任务，测试多轮工具调用：10+20=30 → 30×5=150

messages = [
    {
        "role": "user",
        "content": "先计算 10 + 20，然后把计算结果乘以 5，告诉我最终结果。"
    }
]


# 5. 工具名 → Python 函数的映射
# LLM 只返回字符串 "add"，程序靠这张表找到真正要执行的函数

tool_functions = {
    "add": add,
    "multiply": multiply
}


# 6. Tool Calling Loop
# 每轮：调 LLM → 存 assistant 消息 → 没有工具调用就结束 →
# 有就逐个执行、把结果以 role="tool" 追加回历史，进入下一轮

while True:

    print("\n================ 调用 DeepSeek ================\n")

    # 6.1 调用 LLM（带上完整历史和工具清单）
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=tools
    )

    message = response.choices[0].message

    # 6.2 assistant 消息必须存入历史
    # 无论是直接回答还是要求调工具，下次调用 LLM 都要靠它知道之前发生了什么
    messages.append(message)

    # 6.3 没有 tool_calls 说明 LLM 已给出最终回答，退出循环
    tool_calls = message.tool_calls
    if not tool_calls:
        print("\n================ 最终回答 ================\n")
        print(message.content)
        break

    # 6.4 一次响应可能返回多个 tool_call，必须遍历而不是取 [0]
    for tool_call in tool_calls:

        # 6.4.1 获取工具名
        tool_name = tool_call.function.name
        print("LLM 请求调用 Tool:", tool_name)

        # 6.4.2 解析参数：arguments 是 JSON 字符串，如 '{"a": 10, "b": 20}'
        # 解析失败不崩溃，把错误作为 tool 结果回传，让 LLM 有机会重新处理
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            print("Tool 参数 JSON 解析失败:", e)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f"Tool 参数解析失败：{e}"
            })
            continue

        print("Tool 参数:", arguments)

        # 6.4.3 查映射表：LLM 报了一个没注册的工具名时同样兜底
        tool_function = tool_functions.get(tool_name)
        if tool_function is None:
            print("不存在的 Tool:", tool_name)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f"不存在名为 {tool_name} 的 Tool"
            })
            continue

        # 6.4.4 真正执行 Python 函数；执行失败也把错误信息回传而不是崩溃
        try:
            result = tool_function(**arguments)
            print("Tool 执行结果:", result)
        except Exception as e:
            result = f"Tool 执行失败：{e}"
            print(result)

        # 6.4.5 把结果回传给 LLM：role="tool" + tool_call_id 绑定
        # "这个结果对应你刚才发出的哪一次调用"，content 是真实结果
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result)
        })
