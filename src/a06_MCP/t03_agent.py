# ============================================================
# MCP Agent：LLM + 动态发现的 MCP 工具
#
# 对比 a05 的 Agent：工具不是自己注册的，而是连接时从
# MCP Server 动态发现，再翻译成 Tool Calling 格式——
# 换个 Server 就换一套工具，Agent 代码一行不用改。
# 链路：list_tools 发现 → convert_mcp_tools 转格式 →
# Agent Loop 里 call_tool 执行（工具执行发生在 MCP 服务端）。
#
# 运行前先起服务端：uv run python src/a06_MCP/t01_server.py
# （mcp dev 起的是 stdio + Inspector，HTTP 客户端连不上）
# 运行：uv run python src/a06_MCP/t03_agent.py
# ============================================================

import os
import json
import asyncio

from openai import OpenAI
from mcp import Client


# DeepSeek 客户端
llm = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


def convert_mcp_tools(mcp_tools):
    """
    将 MCP Tool 转换为 OpenAI Tool Calling 格式
    """
    tools = []

    for tool in mcp_tools:
        tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema
            }
        })

    return tools


def extract_tool_result(result):
    """
    提取 MCP 工具返回的文本
    """
    texts = []

    for block in result.content:
        text = getattr(block, "text", None)
        if text is not None:
            texts.append(text)

    return "\n".join(texts)


async def run_agent(user_input: str):
    # 连接 MCP Server
    async with Client("http://localhost:8000/mcp") as mcp_client:

        # 1. 动态发现 MCP 工具
        result = await mcp_client.list_tools()
        mcp_tools = result.tools

        # 2. 转换为 LLM 能理解的工具格式
        llm_tools = convert_mcp_tools(mcp_tools)

        messages = [
            {
                "role": "system",
                "content": "你是一个能够调用工具的 AI 助手。需要计算时使用提供的工具。"
            },
            {
                "role": "user",
                "content": user_input
            }
        ]

        max_steps = 10

        # 3. Agent Loop
        for step in range(max_steps):

            response = llm.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=llm_tools,
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message

            # 保存 LLM 的回复
            messages.append(
                assistant_message.model_dump(exclude_none=True)
            )

            # 4. 没有工具调用，说明 LLM 已经生成最终答案
            if not assistant_message.tool_calls:
                print("\nAgent 最终回答：")
                print(assistant_message.content)
                return

            # 5. 执行 LLM 请求的工具
            for tool_call in assistant_message.tool_calls:

                tool_name = tool_call.function.name
                arguments = json.loads(
                    tool_call.function.arguments
                )

                print(f"\nAgent 调用工具：{tool_name}")
                print(f"工具参数：{arguments}")

                # 通过 MCP Client 调用 MCP Server
                tool_result = await mcp_client.call_tool(
                    tool_name,
                    arguments
                )

                # 提取执行结果
                result_text = extract_tool_result(tool_result)

                if tool_result.is_error:
                    result_text = f"工具执行失败：{result_text}"

                print(f"工具返回：{result_text}")

                # 6. 把工具结果交回 LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text
                })

        print("Agent 已达到最大执行步数。")


if __name__ == "__main__":
    asyncio.run(
        run_agent("先计算 10 加 20，然后把结果乘以 5。")
    )
