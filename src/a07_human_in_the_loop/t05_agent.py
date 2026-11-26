# ============================================================
# Human in the Loop Agent：LLM + 高风险工具人工审批
#
# 对比 a02_tool_calling 的 Agent：多了统一工具执行入口
# execute_tool()，所有工具必须经过它；入口里先做风险检查，
# 高风险工具（删除、转账）停下来问人，批准才执行、拒绝就把
# 拒绝信息交回 LLM。链路：Agent Loop → execute_tool →
# 审批（t02_approval）→ 真正执行（t03_tools）。
#
# 运行：uv run python src/a07_human_in_the_loop/t05_agent.py
# ============================================================

import json
import os

from openai import OpenAI

from t02_approval import requires_approval, request_approval
from t03_tools import TOOL_FUNCTIONS
from t04_tool_registry import TOOLS


# 1. 创建 DeepSeek 客户端
client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)


# 2. 统一工具执行入口：所有工具必须经过这里
# 低风险直接执行，高风险先走人工审批

def execute_tool(tool_name: str, arguments: dict):
    """
    统一工具执行入口

    所有工具必须经过这里。
    """

    # 2.1 检查工具是否存在
    tool = TOOL_FUNCTIONS.get(tool_name)

    if tool is None:
        return {
            "success": False,
            "message": f"未知工具：{tool_name}"
        }

    # 2.2 风险检查：命中审批清单就停下来问人
    if requires_approval(tool_name):

        # 2.3 人工审批：拒绝则不执行，把拒绝信息交回 LLM
        approved = request_approval(
            tool_name,
            arguments
        )

        if not approved:
            return {
                "success": False,
                "message": "人工审批拒绝，工具未执行"
            }

    # 2.4 执行工具：低风险 / 审批通过才走到这里
    try:
        result = tool(**arguments)

        return {
            "success": True,
            "data": result
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


# 3. Agent Loop：请求 LLM → 执行工具 → 结果交回，直到给出最终答案

def run_agent(user_input: str):

    messages = [
        {
            "role": "system",
            "content": "你是一个企业助手，可以查询用户、删除用户和执行转账。"
        },
        {
            "role": "user",
            "content": user_input
        }
    ]

    while True:

        # 3.1 请求 LLM，带上工具 Schema
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )

        message = response.choices[0].message

        # 3.2 没有工具调用，说明 LLM 已生成最终答案
        if not message.tool_calls:
            return message.content

        # 3.3 保存 Assistant 的工具调用消息
        messages.append(
            message.model_dump(exclude_none=True)
        )

        # 3.4 逐个执行 LLM 请求的工具，统一走 execute_tool 触发审批
        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name

            arguments = json.loads(
                tool_call.function.arguments
            )

            print(f"\n[Agent] 请求调用工具：{tool_name}")
            print(f"[Agent] 参数：{arguments}")

            result = execute_tool(
                tool_name,
                arguments
            )

            print(f"[Tool Result] {result}")

            # 3.5 把工具执行结果交回 LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(
                    result,
                    ensure_ascii=False
                )
            })


# 4. 命令行交互：输入指令让 Agent 干活，exit 退出
if __name__ == "__main__":

    while True:

        user_input = input("\n用户：")

        if user_input.lower() == "exit":
            break

        answer = run_agent(user_input)

        print("\nAgent：", answer)
