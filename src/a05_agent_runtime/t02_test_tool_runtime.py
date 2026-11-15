# ============================================================
# 工具运行时测试：四类工具逐项验证 dispatch 各环节
#
# 注册加法、异常、超时、需授权四个工具，七个测试分别覆盖：
# 正常执行、参数类型错误、工具不存在、异常重试、超时、
# 权限拦截、导出 Tool Schema；每个测试注释标明卡在
# dispatch 的第几步。
#
# 运行：uv run python src/a05_agent_runtime/t02_test_tool_runtime.py
# ============================================================

import asyncio
import time

from t01_tool_runtime import (
    ToolSpec,
    ToolRegistry,
    ToolRuntime
)


# 普通同步工具
def add(a: int, b: int):
    return a + b


# 故意执行失败的工具
def unstable_tool():
    raise RuntimeError("模拟工具异常")


# 故意超时的工具
def slow_tool():
    time.sleep(5)
    return "执行完成"


# 需要授权的工具
def delete_data(memory_id: int):
    return f"已删除记忆 {memory_id}"


async def main():

    # 1. 创建工具注册表
    registry = ToolRegistry()

    # 2. 注册四个测试工具
    # 注册加法工具
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
            timeout=5
        )
    )

    # 注册异常工具
    registry.register(
        ToolSpec(
            name="unstable_tool",
            description="模拟工具异常",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=unstable_tool,
            max_retries=2
        )
    )

    # 注册超时工具
    registry.register(
        ToolSpec(
            name="slow_tool",
            description="模拟慢速工具",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=slow_tool,
            timeout=1
        )
    )

    # 注册授权工具
    registry.register(
        ToolSpec(
            name="delete_data",
            description="删除数据",
            parameters={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "integer"}
                },
                "required": ["memory_id"]
            },
            handler=delete_data,
            requires_confirmation=True
        )
    )

    # 3. 创建工具运行时
    runtime = ToolRuntime(registry)

    # 测试 1：正常执行，走通 dispatch 全流程
    print("\n测试 1：正常执行")

    result = await runtime.dispatch(
        "add",
        '{"a": 10, "b": 20}'
    )

    print(result)

    # 测试 2：参数类型错误，卡在 dispatch 第 3 步参数校验
    print("\n测试 2：参数错误")

    result = await runtime.dispatch(
        "add",
        '{"a": 10, "b": "hello"}'
    )

    print(result)

    # 测试 3：工具不存在，卡在 dispatch 第 1 步查找工具
    print("\n测试 3：工具不存在")

    result = await runtime.dispatch(
        "unknown_tool",
        '{}'
    )

    print(result)

    # 测试 4：工具抛异常，dispatch 第 5 步重试 2 次后仍失败
    print("\n测试 4：工具异常和重试")

    result = await runtime.dispatch(
        "unstable_tool",
        '{}'
    )

    print(result)

    # 测试 5：工具执行超时，dispatch 第 5 步 1 秒后超时
    print("\n测试 5：工具超时")

    result = await runtime.dispatch(
        "slow_tool",
        '{}'
    )

    print(result)

    # 测试 6：需授权工具，卡在 dispatch 第 4 步权限检查
    print("\n测试 6：权限检查")

    result = await runtime.dispatch(
        "delete_data",
        '{"memory_id": 1}'
    )

    print(result)

    # 测试 7：导出发给 LLM 的工具 Schema
    print("\n测试 7：Tool Schema")

    print(registry.get_schemas())


if __name__ == "__main__":
    asyncio.run(main())
