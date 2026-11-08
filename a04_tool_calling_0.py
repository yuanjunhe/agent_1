# ============================================================
# Tool Calling 起步：最小闭环
#
# 不带循环的最简工具调用：LLM 决定调用 multiply，本地执行后
# 把结果回传，再拿到最终回答。
# 理解 tool_calls、tool_call_id、role="tool" 三个关键概念，是后续 Agent Loop 的基础。
# 
# 运行：uv run a04_tool_calling_0.py
# ============================================================

import os
import json

from openai import OpenAI


# 1. 创建客户端

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# 2. 定义工具：本地函数 + JSON Schema

def multiply(a, b):
    return a * b


# Schema 告诉 LLM 有什么工具、参数长什么样。
# LLM 自己不执行函数，只返回"想调用谁、传什么参数"
tools = [
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


# 3. 第一次调用：LLM 返回工具调用请求

messages = [
    {
        "role": "user",
        "content": "帮我计算 12 * 30"
    }
]

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=tools
)

message = response.choices[0].message
print(message)


# 4. 解析并在本地执行工具

tool_call = message.tool_calls[0]

tool_name = tool_call.function.name
arguments = json.loads(tool_call.function.arguments)

print("工具名称:", tool_name)
print("参数:", arguments)

result = multiply(
    arguments["a"],
    arguments["b"]
)

print("工具执行结果:", result)


# 5. 把结果回传给 LLM，生成最终回答

# 追加带 tool_calls 的 assistant 消息到历史
messages.append(message)

# 追加 tool 角色消息：tool_call_id 绑定对应哪次调用，
# content 放工具真实执行的结果
messages.append(
    {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": str(result)
    }
)

# 带着工具结果再次调用，LLM 基于结果生成最终回答
second_response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=tools
)

final_message = second_response.choices[0].message

print("\n========== DeepSeek 回答 ==========")
print(final_message.content)
