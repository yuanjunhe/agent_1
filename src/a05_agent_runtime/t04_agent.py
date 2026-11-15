# ============================================================
# Agent 核心：Agent Loop + 工具注册，执行交给 ToolRuntime
#
# 对比 a03_agent/t02_agent.py 的三个变化：
# 1. 工具注册进 t01 的 ToolRegistry，Schema 由
#    get_schemas() 自动生成，不再手写 TOOLS 列表
# 2. 工具执行统一交给 t01 的 ToolRuntime.dispatch()，
#    校验 / 超时 / 重试都在模块内部兜底，agent() 不用管
# 3. 工具函数拆到 t03_tools.py，定义和注册分离
#
# 运行：uv run python src/a05_agent_runtime/t05_agent_demo.py
# ============================================================

import os

from openai import AsyncOpenAI

from t01_tool_runtime import (
    ToolSpec,
    ToolRegistry,
    ToolRuntime
)

from t03_tools import add, multiply, get_weather


# 1. 创建异步客户端

client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# 2. System Prompt：定角色、列工具、定规矩

SYSTEM_PROMPT = """
你是一个能够使用工具的智能 Agent。

你可以使用：
1. add：计算加法
2. multiply：计算乘法
3. get_weather：查询模拟天气

规则：
1. 根据用户任务选择合适的工具。
2. 如果任务需要多个步骤，可以连续调用多个工具。
3. 工具返回结果后，结合结果继续思考。
4. 不要编造工具执行结果。
5. 完成任务后给出最终答案。
"""


# 3. 创建工具运行时
# 把三个工具注册进 Registry，Schema 不用再手写，
# agent() 里由 get_schemas() 自动导出

def create_runtime():

    registry = ToolRegistry()

    registry.register(
        ToolSpec(
            name="add",
            description="计算两个整数的和",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                "required": ["a", "b"],
                "additionalProperties": False
            },
            handler=add,
            timeout=5,
            max_retries=0
        )
    )

    registry.register(
        ToolSpec(
            name="multiply",
            description="计算两个整数的乘积",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                "required": ["a", "b"],
                "additionalProperties": False
            },
            handler=multiply,
            timeout=5
        )
    )

    registry.register(
        ToolSpec(
            name="get_weather",
            description="查询指定城市的模拟天气",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"],
                "additionalProperties": False
            },
            handler=get_weather,
            timeout=5
        )
    )

    return ToolRuntime(registry), registry


# 4. Agent Loop：和 t02_agent.py 同构，执行换成 runtime.dispatch
# 每步调 LLM → 无 tool_calls 返回最终答案；有则逐个交给
# dispatch（校验 / 超时 / 重试在模块内部兜底），结果带
# tool_call_id 回传，最多 MAX_STEPS 步

async def agent(messages, runtime, registry):

    max_steps = 10

    # 从 Registry 自动生成 Schema
    tools_schema = registry.get_schemas()

    for step in range(max_steps):

        print(f"\n========== Agent Step {step + 1} ==========")

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools_schema,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message

        # 没有 Tool Call，返回最终答案
        if not assistant_message.tool_calls:

            answer = assistant_message.content or ""

            messages.append({
                "role": "assistant",
                "content": answer
            })

            return answer

        # 保留完整 Assistant Tool Call 消息
        messages.append(
            assistant_message.model_dump(exclude_none=True)
        )

        # 逐个执行 Tool Calls
        for tool_call in assistant_message.tool_calls:

            tool_name = tool_call.function.name
            arguments = tool_call.function.arguments

            print(f"\n调用工具：{tool_name}")
            print(f"工具参数：{arguments}")

            # 关键变化：统一交给 Runtime
            result = await runtime.dispatch(
                tool_name,
                arguments
            )

            print(f"工具结果：{result}")

            # 将结果带 tool_call_id 回传 LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })

    return "Agent 执行超过最大步骤限制。"
