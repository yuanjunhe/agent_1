
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
