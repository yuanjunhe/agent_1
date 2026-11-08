# ============================================================
# 一次响应，多个工具调用
#
# 对比基础 Agent Loop：那个版本讲"循环和容错"，每轮只处理一个工具调用；
# 这个版本讲"一次多个"——LLM 一次响应可以返回多个 tool_call
# （如 add(10,20) 和 multiply(8,9)），遍历全部执行后再回传。
#
# 运行：uv run a06_multi_tool_calling.py
# ============================================================

import os
import json

from openai import OpenAI


# 1. 创建客户端

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not DEEPSEEK_API_KEY:
    raise ValueError(
        "没有找到 DEEPSEEK_API_KEY 环境变量，"
        "请先运行: set DEEPSEEK_API_KEY=你的_API_KEY"
    )

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


# 2. 定义真正执行的 Python 函数
# LLM 只负责说"请调用 add，传 a=10, b=20"，真正执行的是下面的函数

def add(a, b):
    return a + b


def multiply(a, b):
    return a * b


# 3. Tool Registry（雏形）
# 工具名 → Python 函数的映射，后面会抽成正式的 Registry / Dispatcher

tools_map = {
    "add": add,
    "multiply": multiply
}


# 4. 给 LLM 描述有哪些 Tool（Schema）

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


# 5. 对话上下文
# 故意要两个独立计算，诱导 LLM 一次返回两个 tool_call

messages = [
    {
        "role": "user",
        "content": "同时计算 10 + 20，以及 8 × 9。"
    }
]


# 6. Tool Calling Loop
# 和上一版相同的循环骨架：调 LLM → 存消息 → 没有工具调用就结束

while True:

    print("\n================ 调用 DeepSeek ================\n")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    message = response.choices[0].message

    # assistant 消息必须存入历史，下一轮 LLM 靠它知道刚才要求了哪些工具
    messages.append(message)

    # 没有 tool_calls 说明 LLM 已直接回答，退出
    if not message.tool_calls:
        print("================ 最终回答 ================\n")
        print(message.content)
        break

    # 7. 处理多个 Tool Call
    # message.tool_calls 是列表（可能同时有 add 和 multiply），遍历执行；
    # 每个结果各自带 tool_call_id 回传，LLM 才能对上号
    for tool_call in message.tool_calls:

        # 工具名和参数（arguments 是 JSON 字符串，要转 dict）
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        print("LLM 请求调用 Tool:", tool_name)
        print("Tool 参数:", arguments)

        # 查表找到真正的函数并执行
        tool_function = tools_map[tool_name]
        result = tool_function(**arguments)

        print("Tool 执行结果:", result)
        print()

        # 结果以 role="tool" 回传，tool_call_id 对应刚才哪次调用
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            }
        )
