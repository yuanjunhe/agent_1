# ============================================================
# 人工审批最小机制：高风险工具执行前先问人
#
# Human in the Loop 的出发点：Agent 拿到工具不是立刻执行，
# 高风险动作（删数据、转账、发邮件）先停下来，把工具名和参数
# 摆到人面前——人批准才执行，拒绝就返回拒绝信息。
# 本文件不接 LLM，先把手动的"拦截 → 审批 → 执行"链路跑通。
#
# 运行：uv run python src/a07_human_in_the_loop/t01_human_approval.py
# ============================================================

from dataclasses import dataclass


# 1. 定义工具：一个低风险（只读）、一个高风险（删数据）

def get_user_info(user_id: int):
    return {"user_id": user_id, "name": "张三", "department": "研发部"}


def delete_user(user_id: int):
    print(f"正在删除用户：{user_id}")
    return f"用户 {user_id} 删除成功"


# 2. 工具注册表 + 风险分级
# 审批策略是配置不是散落的 if：新增高风险工具只改 HIGH_RISK_TOOLS

TOOL_REGISTRY = {
    "get_user_info": get_user_info,
    "delete_user": delete_user,
}

HIGH_RISK_TOOLS = {"delete_user"}


# 3. 审批请求：一张待审批的"工单"，status 留痕
# pending → approved / rejected

@dataclass
class ApprovalRequest:
    tool_name: str
    arguments: dict
    status: str = "pending"


# 4. 审批机制：展示工具名和参数，人输入 yes/no 裁决
# 裁决结果写回 request.status（审批留痕）并返回

def request_approval(request: ApprovalRequest):
    print("\n===== 人工审批 =====")
    print(f"工具：{request.tool_name}")
    print(f"参数：{request.arguments}")

    decision = input("是否批准？(yes/no)：")

    request.status = "approved" if decision.lower() == "yes" else "rejected"

    return request.status


# 5. Agent 执行入口：高风险先审批，批准才执行

def execute_tool(tool_name: str, arguments: dict):

    # 未知工具直接返回错误
    if tool_name not in TOOL_REGISTRY:
        return f"未知工具：{tool_name}"

    # 高风险工具：生成审批请求，走人工审批
    if tool_name in HIGH_RISK_TOOLS:
        request = ApprovalRequest(
            tool_name=tool_name,
            arguments=arguments
        )

        if request_approval(request) != "approved":
            return f"操作已被人工拒绝，未执行（工具 {tool_name}）"

    # 低风险工具 / 审批通过：正常执行
    return TOOL_REGISTRY[tool_name](**arguments)


# 6. 演示：同一个入口，低风险直接过，高风险卡审批
if __name__ == "__main__":

    print(">>> 低风险：查询用户信息（不触发审批）")
    print(execute_tool("get_user_info", {"user_id": 10086}))

    print("\n>>> 高风险：删除用户（触发审批，输入 no 拒绝 / yes 批准）")
    print(execute_tool("delete_user", {"user_id": 10086}))
