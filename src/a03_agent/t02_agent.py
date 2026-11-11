# ============================================================
# 有状态的 Agent：多轮对话 + AgentState 外置 + 步数上限
#
# 三个增量：
# 1. AgentState 用 dataclass 外置，main() 创建长期存在的 state
#    传入 agent()，对话历史跨轮保留——这是多轮对话的基础
# 2. 工具集扩展到 4 个：三个计算函数 + 从 RAG 线合流来的
#    search_knowledge（检索知识库）
# 3. for 循环 + MAX_STEPS 限制单次任务的步数，防止 LLM
#    无限循环调工具
#
# 运行前必须先跑过入库脚本 t02_rag_ingest.py（否则 collection 不存在）。
# 运行：uv run python src/a03_agent/t02_agent.py
# ============================================================

import os
import json
import asyncio
from dataclasses import dataclass, field
from openai import AsyncOpenAI

from t01_rag_agent import search_knowledge


# 1. Agent State
# 对话历史的容器；state 由 main() 创建并长期持有，
# agent() 只使用不创建，多轮对话靠它延续上下文

@dataclass
class AgentState:

    # 保存整个对话历史
    messages: list = field(default_factory=list)

    # 当前 Agent 执行步骤（实际项目中通常针对每次任务单独计算）
    step: int = 0

    # 当前任务是否完成
    finished: bool = False


# 2. 创建异步客户端

client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# 3. 定义 Tool

def add(a: int, b: int):
    return a + b


def multiply(a: int, b: int):
    return a * b


def subtract(a: int, b: int):
    return a - b


# 4. Tool Registry
# 计算工具 + 检索工具，RAG 线和 Tool Calling 线在这里共用一张表

TOOL_REGISTRY = {
    "add": add,
    "multiply": multiply,
    "subtract": subtract,
    "search_knowledge": search_knowledge,
}


# 5. Tool Schema

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "计算两个数字的和",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "multiply",
            "description": "计算两个数字的乘积",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "subtract",
            "description": "计算两个数字的差",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "搜索知识库",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string"
                    }
                },
                "required": ["query"],
            },
        },
    },
]


# 6. Dispatcher
# 和检索 Agent 的写法一致：查表 → 执行 → 失败返回错误字符串

def dispatch_tool(tool_name: str, arguments: dict):

    print(f"\n[Tool] {tool_name}")
    print(f"[Args] {arguments}")

    tool = TOOL_REGISTRY.get(tool_name)

    if tool is None:
        return f"Tool 不存在：{tool_name}"

    try:
        result = tool(**arguments)
        print(f"[Result] {result}")
        return str(result)
    except Exception as e:
        return f"Tool 执行失败：{e}"


# 7. Agent：用 for + MAX_STEPS 替代 while True
# state 从外部传入（agent 不创建 state），单次任务最多走
# MAX_STEPS 步，到顶返回提示而不是无限循环

async def agent(state: AgentState):

    MAX_STEPS = 10

    for step in range(MAX_STEPS):

        state.step = step + 1

        print(f"\n========== Agent Step {state.step} ==========")

        # 调用 LLM
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=state.messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # 没有 tool_calls 说明本轮任务完成
        if not message.tool_calls:
            state.finished = True
            return message.content

        # assistant 的 tool_calls 消息必须先入历史
        state.messages.append(message)

        # 逐个执行工具，结果带 tool_call_id 回传
        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            result = dispatch_tool(tool_name, arguments)

            state.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    return "Agent 执行超过最大步骤限制。"


# 8. Main：创建长期 state，循环处理多轮输入

async def main():

    # 创建一个长期存在的 State，整个对话过程复用
    state = AgentState()

    # 初始化 System Prompt：定角色、列工具、定规矩
    state.messages.append(
        {
            "role": "system",
            "content": """
你是一个智能 Agent。

你可以使用：

1. add
2. multiply
3. subtract
4. search_knowledge

根据用户问题自主决定是否调用工具。

如果任务需要多个步骤，
可以连续调用多个工具。

只有任务完成后才返回最终答案。
"""
        }
    )

    # 多轮对话：每次输入都追加进同一个 state，上下文跨轮保留
    while True:

        question = input("\n用户：")

        if question.lower() == "exit":
            print("Agent 已退出。")
            break

        state.messages.append(
            {
                "role": "user",
                "content": question
            }
        )

        answer = await agent(state)

        print(f"\nAgent：{answer}")


# 9. 启动
if __name__ == "__main__":
    asyncio.run(main())
