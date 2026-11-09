# ============================================================
# 记忆提取器：从用户消息里提取值得长期记忆的信息
#
# 这是长期记忆管线的第一步：把一条用户消息交给 LLM，
# 按 prompt 里的规则判断哪些信息值得长期保存（姓名、职业、
# 长期目标等），以 JSON 数组形式返回；解析失败时降级为空列表。
#
# 运行：uv run a14_test_memory_extractor.py
# ============================================================

import os
import json

from openai import AsyncOpenAI


# 1. 读取 API Key
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise RuntimeError(
        "没有找到 DEEPSEEK_API_KEY 环境变量"
    )


# 2. 创建异步客户端（DeepSeek 提供 OpenAI 兼容接口）
client = AsyncOpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)


# 3. 记忆提取：组装 prompt，让 LLM 从用户消息中提取长期记忆
async def extract_memories(user_message: str) -> list[str]:

    prompt = f"""
请从下面的用户消息中提取值得长期记忆的信息。

应该记忆的信息包括：

1. 用户姓名
2. 用户职业
3. 用户长期兴趣
4. 用户长期偏好
5. 用户长期目标
6. 用户正在进行的重要项目
7. 其他未来对话可能有价值的信息

不要记录：

1. 一次性的计算任务
2. 普通闲聊
3. 临时问题
4. 没有长期价值的信息

用户消息：

{user_message}

如果存在值得记忆的信息，请输出 JSON 数组：

["记忆1", "记忆2"]

如果没有值得记忆的信息，请输出：

[]

只输出 JSON，不要输出其他内容。
"""

    # 4. 调用 LLM 提取记忆
    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "你是一个负责提取长期用户记忆的组件。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    content = response.choices[0].message.content

    # 5. 解析 LLM 输出的 JSON，解析失败或不是数组就返回空列表
    try:
        memories = json.loads(content)

        if not isinstance(memories, list):
            return []

        return memories

    except json.JSONDecodeError:
        return []
