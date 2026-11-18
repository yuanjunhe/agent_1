# ============================================================
# 第二个 MCP Server：用户/订单查询服务（模拟业务数据）
#
# 配合多 Server Agent（t05）/ 综合测试（t06 / t07）：和 t01_server
# 分开起，占 8001 端口；两个工具返回 dict，t05 里会拿到
# structured_content 而不是纯文本。
#
# 调试（Inspector 网页）：uv run mcp dev src/a06_MCP/t04_user_server.py
# 供 HTTP 客户端连接：  uv run python src/a06_MCP/t04_user_server.py
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


# 固定 Resource：URI 写死，内容不随参数变
@mcp.resource("company://policy")
def get_company_policy() -> str:
    """获取公司业务规则"""
    return """
    公司订单规则：
    1. 已支付订单可以申请售后。
    2. 未支付订单不能申请退款。
    3. 订单金额超过 1000 元，需要主管审批。
    """


# Resource Template：URI 带 {参数} 占位，按 user_id 动态生成内容
@mcp.resource("users://{user_id}/profile")
def get_user_profile(user_id: str) -> str:
    """根据用户 ID 获取用户档案资源"""
    profiles = {
        "U1001": "张三，研发部，Java 工程师。",
        "U1002": "李四，产品部，产品经理。"
    }

    return profiles.get(user_id, "未找到该用户档案")


# Prompt：服务端预置的提示词模板，客户端 get_prompt 传参取回
@mcp.prompt(title="订单分析")
def analyze_order(order_id: str, order_info: str) -> str:
    """生成订单分析提示词"""
    return f"""
    请分析以下订单：

    订单编号：{order_id}
    订单信息：{order_info}

    请分析：
    1. 订单当前状态
    2. 是否符合公司订单规则
    3. 是否存在需要注意的风险
    """


if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8001)
