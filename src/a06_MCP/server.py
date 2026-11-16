# ============================================================
# MCP Server：用装饰器注册 Tool 和 Resource
#
# 最小 MCP 服务端：@mcp.tool() 把普通函数暴露成 LLM 可调用的
# 工具（docstring 即描述，类型注解自动生成参数 Schema）；
# @mcp.resource(URI) 把函数暴露成可读取的资源。
# 工具和资源的区别：工具 = LLM 主动调用做动作，资源 = 客户端
# 主动读取拿数据（类 GET 请求）。
#
# 运行：uv run mcp dev src/a06_MCP/server.py   （带 Inspector 调试）
# 或：uv run python src/a06_MCP/server.py     （配 HTTP 传输时）
# ============================================================

from mcp.server import MCPServer

# 创建 MCP Server
mcp = MCPServer("My First MCP Server")


# 注册一个 Tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """
    计算两个整数的和
    """
    return a + b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """
    计算两个整数的乘积
    """
    return a * b


# 注册一个 Resource
@mcp.resource("user://profile")
def get_user_profile() -> str:
    """
    获取用户基本信息
    """
    return """
    姓名：张三
    职业：Java 工程师
    兴趣：Agent 开发
    """


if __name__ == "__main__":
    mcp.run()
