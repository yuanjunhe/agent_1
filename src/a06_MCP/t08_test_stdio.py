# ============================================================
# STDIO 客户端测试：客户端自己把 Server 拉起为子进程
#
# 前几个文件都是 HTTP 客户端，连一个"已经起着"的服务端；
# stdio 传输换了一种模式：Client 拿 StdioServerParameters
# 自己 spawn 服务端子进程，通过它的 stdin/stdout 收发 JSON-RPC，
# 不占任何端口（桌面客户端连本地 MCP Server 就是这种）。
#
# 关键差异：mcp.run() 不传 transport 默认就是 stdio，所以
# 这里用 `uv run mcp run t01_server.py` 拉起 t01；HTTP 实例
# （python 直跑）和 stdio 实例可以同时存在，互不冲突。
#
# 运行：uv run python src/a06_MCP/t08_test_stdio.py
# （不需要先起任何服务端，Client 会自己拉起）
# ============================================================

import asyncio

from mcp import Client, StdioServerParameters


async def main():

    # 1. 配置如何启动 MCP Server 子进程
    #    （相对路径以运行目录为基准，从项目根运行才能找到文件）
    server = StdioServerParameters(
        command="uv",
        args=["run", "mcp", "run", "src/a06_MCP/t01_server.py"]
    )

    # 2. Client 自动启动子进程并建立 STDIO 通信
    #    （对比 HTTP 写法：Client("http://localhost:8000/mcp")）
    async with Client(server) as client:

        # 3. 发现工具（和服务端是用 HTTP 还是 stdio 无关，
        #    上层协议动作完全一样）
        tools = await client.list_tools()

        print("===== 发现的工具 =====")

        for tool in tools.tools:
            print(tool.name)

        # 4. 调用工具：int 返回值自动带 structured_content
        #    （{'result': 30}），纯文本在 result.content[0].text
        result = await client.call_tool(
            "add",
            {"a": 10, "b": 20}
        )

        print("\n===== 调用结果 =====")
        print(result.structured_content)


if __name__ == "__main__":
    asyncio.run(main())
