# ============================================================
# 调通 DeepSeek API
#
# 用 OpenAI SDK 调用 DeepSeek 的 OpenAI 兼容接口，
# 发送一句最简单的对话，验证 API Key、网络、SDK 都没问题。
#
# 运行：uv run a01_ping_api.py
# ============================================================

import os

from openai import OpenAI


# 1. 读取 API Key
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise RuntimeError(
        "没有找到 DEEPSEEK_API_KEY 环境变量"
    )


# 2. 创建客户端（DeepSeek 提供 OpenAI 兼容接口）
client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)


# 3. 发起对话请求
response = client.chat.completions.create(
    model="deepseek-v4-flash",

    messages=[
        {
            "role": "system",
            "content": "你是一个简洁的知识问答助手。"
        },
        {
            "role": "user",
            "content": "什么是 RAG？"
        }
    ],

    # 第一次测试先关闭思考模式，
    # 让调用链路尽可能简单。
    # OpenAI SDK 未内置 thinking 参数，需通过 extra_body 透传给 DeepSeek
    extra_body={
        "thinking": {
            "type": "disabled"
        }
    },

    stream=False
)


# 4. 提取回答并打印
answer = response.choices[0].message.content

print("========== DeepSeek ==========")
print(answer)

print("\n========== Token 使用情况 ==========")
print(response.usage)