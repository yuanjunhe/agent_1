# ============================================================
# 第二个 MCP Server：用户/订单查询服务（模拟业务数据）
#
# 配合多 Server Agent（t05）演示跨服务调用：和 t01_server
# 分开起，占 8001 端口；两个工具返回 dict，t05 里会拿到
# structured_content 而不是纯文本。
#
# 运行：uv run mcp dev src/a06_MCP/t04_user_server.py
# ============================================================

from mcp.server import MCPServer

mcp = MCPServer("User Service")


@mcp.tool()
def get_user_info(user_id: str) -> dict:
    """根据用户 ID 查询用户信息"""
    users = {
        "U1001": {
            "user_id": "U1001",
            "name": "张三",
            "department": "研发部"
        },
        "U1002": {
            "user_id": "U1002",
            "name": "李四",
            "department": "产品部"
        }
    }

    return users.get(user_id, {"error": "用户不存在"})


@mcp.tool()
def get_order_status(order_id: str) -> dict:
    """根据订单 ID 查询订单状态"""
    orders = {
        "O1001": {
            "order_id": "O1001",
            "amount": 360,
            "status": "已支付"
        }
    }

    return orders.get(order_id, {"error": "订单不存在"})


if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8001)
