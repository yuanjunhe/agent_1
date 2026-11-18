# ============================================================
# 多 Server MCP Agent：同时连多个 MCP Server 的工具
#
# 对比 t03_agent（单 Server）的两个增量：
# 1. 多 Server 连接：AsyncExitStack 统一管理多个 Client 的
#    生命周期，退出时全部自动关闭
# 2. 工具路由表：发现工具时加"服务名__"前缀避免跨 Server
#    重名（math__add / user__get_user_info），LLM 工具名到
#    (Client, 原始工具名) 的映射，调用时按路由分发
#
# 运行前先起两个服务端（各占一个终端）：
#   uv run python src/a06_MCP/t01_server.py
#   uv run python src/a06_MCP/t04_user_server.py
# （mcp dev 起的是 stdio + Inspector，HTTP 客户端连不上）
# 运行：uv run python src/a06_MCP/t05_multi_server_agent.py
# ============================================================

import os
import json
import asyncio

from contextlib import AsyncExitStack
from openai import OpenAI
from mcp import Client


llm = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# 多个 MCP Server 配置
MCP_SERVERS = {
    "math": "http://localhost:8000/mcp",
    "user": "http://localhost:8001/mcp"
}


def extract_tool_result(result):
    # 提取 MCP 工具返回的文本；返回 dict 的工具拿到的是
    # structured_content（结构化结果），序列化成 JSON 字符串
    texts = []

    for block in result.content:
        text = getattr(block, "text", None)
        if text is not None:
            texts.append(text)

    if result.structured_content is not None:
        return json.dumps(
            result.structured_content,
            ensure_ascii=False
        )

    return "\n".join(texts)


async def run_agent(user_input: str):

    # 管理多个 MCP Client 的生命周期
    async with AsyncExitStack() as stack:

        llm_tools = []

        # 工具路由表：
        # LLM 工具名称 -> (MCP Client, Server 原始工具名)
        tool_routes = {}

        # 1. 连接所有 MCP Server
        for server_name, url in MCP_SERVERS.items():

            client = await stack.enter_async_context(
                Client(url)
            )

            print(f"已连接 MCP Server：{server_name}")

            # 2. 动态发现当前 Server 的工具
            response = await client.list_tools()

            for tool in response.tools:

                # 增加服务前缀，避免工具名称冲突
                llm_tool_name = f"{server_name}__{tool.name}"

                llm_tools.append({
                    "type": "function",
                    "function": {
                        "name": llm_tool_name,
                        "description": tool.description or "",
                        "parameters": tool.input_schema
                    }
                })

                # 保存工具路由
                tool_routes[llm_tool_name] = (
                    client,
                    tool.name
                )

        print("\nAgent 已发现以下工具：")
        for tool in llm_tools:
            print(tool["function"]["name"])

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个 AI 助手，可以使用用户服务和数学服务。"
                    "根据用户需求自主选择工具。"
                )
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

            messages.append(
                assistant_message.model_dump(exclude_none=True)
            )

            # 没有工具调用，说明已生成最终答案
            if not assistant_message.tool_calls:
                print("\nAgent 最终回答：")
                print(assistant_message.content)
                return

            # 4. 执行工具调用，按路由表分发到对应 Server
            for tool_call in assistant_message.tool_calls:

                tool_name = tool_call.function.name
                arguments = json.loads(
                    tool_call.function.arguments
                )

                # 从路由表找到对应的 MCP Client
                if tool_name not in tool_routes:
                    result_text = f"未知工具：{tool_name}"

                else:
                    client, original_name = tool_routes[tool_name]

                    print(f"\n调用工具：{tool_name}")
                    print(f"参数：{arguments}")

                    result = await client.call_tool(
                        original_name,
                        arguments
                    )

                    result_text = extract_tool_result(result)

                    if result.is_error:
                        result_text = f"工具执行失败：{result_text}"

                print(f"工具结果：{result_text}")

                # 5. 将结果交还 LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text
                })

        print("Agent 已达到最大执行步数。")


if __name__ == "__main__":
    asyncio.run(
        run_agent(
            "查询用户 U1001 的信息，再查询订单 O1001 的状态，"
            "最后计算订单金额乘以 3。"
        )
    )
