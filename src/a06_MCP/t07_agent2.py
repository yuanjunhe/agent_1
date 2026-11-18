# ============================================================
# 综合 Agent：Tools + Resources + Prompts 三类能力合体
#
# 对比 t05 多 Server Agent 的增量：不只用工具，还把服务端的
# Resource（公司规则）和 Prompt（分析模板）取回来拼进 system
# 提示词，让 LLM 按规则、按模板做订单风险分析。
#
# 运行前先起两个服务端（各占一个终端）：
#   uv run python src/a06_MCP/t01_server.py
#   uv run python src/a06_MCP/t04_user_server.py
# （mcp dev 起的是 stdio + Inspector，HTTP 客户端连不上）
# 运行：uv run python src/a06_MCP/t07_agent2.py
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

# 服务端路由表：LLM 工具名前缀 -> 服务端地址
MCP_SERVERS = {
    "math": "http://localhost:8000/mcp",
    "user": "http://localhost:8001/mcp"
}


def extract_text(contents):
    """提取 Resource 或 Tool 返回的文本：逐项取 .text，有才收"""
    texts = []

    for item in contents:
        text = getattr(item, "text", None)
        if text is not None:
            texts.append(text)

    return "\n".join(texts)


def extract_tool_result(result):
    """提取 Tool 返回结果：优先 structured_content（dict 转 JSON），退回纯文本"""
    if result.structured_content is not None:
        return json.dumps(
            result.structured_content,
            ensure_ascii=False
        )

    return extract_text(result.content)


async def run_agent(user_input: str):
    """Agent 主流程：发现工具 -> 取 Resource/Prompt -> 拼 system -> Agent Loop"""

    async with AsyncExitStack() as stack:

        clients = {}      # 服务名 -> Client
        llm_tools = []    # 喂给 LLM 的工具定义（带前缀名）
        tool_routes = {}  # LLM 工具名 -> (Client, 原始工具名)

        # =================================
        # 1. 连接多个 MCP Server，发现 Tools
        # =================================

        for server_name, url in MCP_SERVERS.items():

            client = await stack.enter_async_context(
                Client(url)
            )

            clients[server_name] = client

            response = await client.list_tools()

            for tool in response.tools:

                # 加"服务名__"前缀，避免跨 Server 重名
                llm_name = f"{server_name}__{tool.name}"

                llm_tools.append({
                    "type": "function",
                    "function": {
                        "name": llm_name,
                        "description": tool.description or "",
                        "parameters": tool.input_schema
                    }
                })

                tool_routes[llm_name] = (
                    client,    # 调用时按路由分发到对应 Server
                    tool.name
                )

        # =================================
        # 2. 读取 Resource：拿公司业务规则
        # =================================

        user_client = clients["user"]

        resource_result = await user_client.read_resource(
            "company://policy"
        )

        # Resource 内容作为背景知识，后面拼进 system
        company_policy = extract_text(
            resource_result.contents
        )

        print("===== 公司业务规则 =====")
        print(company_policy)

        # =================================
        # 3. 获取 Prompt：拿订单分析模板
        # =================================

        prompt_result = await user_client.get_prompt(
            "analyze_order",
            {
                "order_id": "O1001",
                "order_info": "等待查询"   # 订单信息待工具查询，先占位
            }
        )

        # messages 里逐条取 content，拼回纯文本模板
        prompt_text = extract_text([
            message.content
            for message in prompt_result.messages
        ])

        print("\n===== 订单分析模板 =====")
        print(prompt_text)

        # =================================
        # 4. 构建 LLM 上下文：规则 + 模板进 system
        # =================================

        messages = [
            {
                "role": "system",
                "content": f"""
你是一个企业订单分析助手。

请遵守以下公司业务规则：
{company_policy}

请参考以下订单分析模板：
{prompt_text}

需要查询订单时，使用提供的订单查询工具。
根据查询结果和公司规则进行分析。
"""
            },
            {
                "role": "user",
                "content": user_input
            }
        ]

        # =================================
        # 5. Agent Loop：调 LLM -> 有工具调用就执行 -> 回填结果
        # =================================

        max_steps = 10   # 防止无限循环的最大步数

        for step in range(max_steps):

            response = llm.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=llm_tools,
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message

            # 助手消息原样回填历史，保持上下文完整
            messages.append(
                assistant_message.model_dump(exclude_none=True)
            )

            # 没有工具调用，返回最终答案
            if not assistant_message.tool_calls:

                print("\n===== 最终分析结果 =====")
                print(assistant_message.content)
                return

            # =================================
            # 6. 执行 MCP Tool：按路由表分发到对应 Server
            # =================================

            for tool_call in assistant_message.tool_calls:

                tool_name = tool_call.function.name

                # LLM 给的参数是 JSON 字符串，解析成 dict
                arguments = json.loads(
                    tool_call.function.arguments
                )

                print(f"\n调用工具：{tool_name}")
                print(f"参数：{arguments}")

                if tool_name not in tool_routes:

                    result_text = f"未知工具：{tool_name}"

                else:

                    # 路由：查表拿到对应 Client 和原始工具名
                    client, original_name = tool_routes[tool_name]

                    result = await client.call_tool(
                        original_name,
                        arguments
                    )

                    result_text = extract_tool_result(result)

                    # 服务端报错时标记出来，让 LLM 知道工具失败了
                    if result.is_error:
                        result_text = f"工具执行失败：{result_text}"

                print(f"工具结果：{result_text}")

                # 将工具结果交给 LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text
                })

        print("Agent 已达到最大执行步数。")


if __name__ == "__main__":

    # 两个服务端起着时直接跑（t04 占 8001，我这边已后台拉起）
    asyncio.run(
        run_agent(
            "请查询订单 O1001，结合公司的业务规则，"
            "分析订单是否存在风险。"
        )
    )
