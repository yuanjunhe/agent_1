# ============================================================
# 业务工具集：Agent 能调用的三个实际工具函数
#
# 纯函数集合，不含 Schema 和审批逻辑；Schema 定义在
# t04_tool_registry.py，审批判定在 t02_approval.py。
# 查询是只读的低风险操作，删除和转账是高风险操作。
#
# 运行：uv run python src/a07_human_in_the_loop/t05_agent.py
# ============================================================


# 查询用户：只读，低风险
def query_user(user_id: int):
    """查询用户"""
    return {
        "user_id": user_id,
        "username": "张三",
        "balance": 10000
    }


# 删除用户：高风险，t02_approval 会拦截审批
def delete_user(user_id: int):
    """删除用户"""
    print(f"[MCP Server] 正在删除用户 {user_id}")

    return {
        "success": True,
        "message": f"用户 {user_id} 删除成功"
    }


# 转账：高风险，t02_approval 会拦截审批
def transfer_money(
    from_user_id: int,
    to_user_id: int,
    amount: float
):
    """转账"""

    print("[MCP Server] 正在执行转账")

    return {
        "success": True,
        "from_user_id": from_user_id,
        "to_user_id": to_user_id,
        "amount": amount
    }


# 工具注册表：工具名 → 函数，Agent 执行时按名字查找
TOOL_FUNCTIONS = {
    "query_user": query_user,
    "delete_user": delete_user,
    "transfer_money": transfer_money,
}
