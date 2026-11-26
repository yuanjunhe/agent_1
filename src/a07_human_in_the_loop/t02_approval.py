# ============================================================
# 审批策略模块：定义哪些工具需要人工审批、如何向人请求审批
#
# 审批策略（哪些工具要审）和审批交互（怎么问人）收拢在这个
# 独立模块里，Agent 侧只调 requires_approval / request_approval
# 两个函数，不关心具体实现；新增高风险工具只改清单。
#
# 运行：uv run python src/a07_human_in_the_loop/t05_agent.py
# ============================================================


# 1. 需要人工审批的工具清单：高风险动作集中在这里
APPROVAL_REQUIRED_TOOLS = {
    "delete_user",
    "transfer_money",
}


# 2. 判断工具是否需要人工审批
def requires_approval(tool_name: str) -> bool:
    """判断工具是否需要人工审批"""
    return tool_name in APPROVAL_REQUIRED_TOOLS


# 3. 审批交互：把工具名和参数摆到人面前，人输入 yes/no 裁决
def request_approval(tool_name: str, arguments: dict) -> bool:
    """请求人工审批，返回 True 表示批准"""

    print("\n" + "=" * 40)
    print("          人工审批请求")
    print("=" * 40)

    print(f"工具名称：{tool_name}")
    print(f"执行参数：{arguments}")

    decision = input("是否批准执行？(yes/no)：")

    return decision.strip().lower() == "yes"
