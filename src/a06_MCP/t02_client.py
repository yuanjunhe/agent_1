# ============================================================
# MCP Client：发现工具、调用工具、读取资源
#
# 连接本地起着的 MCP Server（Streamable HTTP 端点），演示
# MCP 的三个核心动作：
# 1. list_tools        发现服务端有哪些工具（动态发现，不用写死）
# 2. call_tool         调用工具，结果在 result.content[i].text
# 3. read_resource     读资源，结果在 result.contents[i].text
#
# 运行前先起服务端：uv run python src/a06_MCP/t01_server.py
# （mcp dev 起的是 stdio + Inspector，HTTP 客户端连不上）
# 运行：uv run python src/a06_MCP/t02_client.py
# ============================================================

import asyncio
from mcp import Client


async def main():
    # 连接 MCP Server
    async with Client("http://localhost:8000/mcp") as client:

        # 1. 发现工具
        print("===== 服务端工具列表 =====")
        tools = await client.list_tools()

        for tool in tools.tools:
            print(f"工具名称：{tool.name}")
            print(f"工具描述：{tool.description}")
            print(f"参数定义：{tool.input_schema}")
            print("-" * 40)

        # 2. 调用 add 工具
        print("\n===== 调用 add =====")
        result = await client.call_tool(
            "add",
            {"a": 10, "b": 20}
        )
        print("调用结果：", result.content)

        # 3. 调用 multiply 工具
        print("\n===== 调用 multiply =====")
        result = await client.call_tool(
            "multiply",
            {"a": 8, "b": 9}
        )
        print("调用结果：", result.content)

        # 4. 发现并读取 Resource
        print("\n===== 读取 Resource =====")
        resources = await client.list_resources()

        for resource in resources.resources:
            print("资源 URI：", resource.uri)

        profile = await client.read_resource("user://profile")

        # ReadResourceResult.contents 是内容列表，每项（TextResourceContents）的内容在 .text
        for item in profile.contents:
            print("资源内容：", item.text)


if __name__ == "__main__":
    asyncio.run(main())
