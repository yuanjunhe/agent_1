# ============================================================
# 工具运行时（整合版）：ToolSpec + Registry + 校验 + 调度
#
# 把 Tool Calling 线的工具定义、注册表、参数校验、运行时保护
# 整合成一个独立模块：dispatch 是唯一入口，按
# 查找 → JSON 解析 → 参数校验 → 授权检查 → 执行（超时 + 重试）
# 的顺序跑完整条链路，任何一步失败都返回 JSON 错误而不是抛异常。
#
# 运行：uv run python src/a05_agent_runtime/t02_test_tool_runtime.py
# ============================================================

from dataclasses import dataclass
from typing import Callable, Any


# 工具规格：一个工具的完整定义
@dataclass
class ToolSpec:

    # 工具名称
    name: str

    # 工具描述
    description: str

    # OpenAI Function Calling 参数 Schema
    parameters: dict

    # 实际执行的 Python 函数
    handler: Callable

    # 超时时间，单位秒
    timeout: int = 10

    # 最大重试次数
    max_retries: int = 0

    # 是否需要额外授权
    requires_confirmation: bool = False



# 工具注册表：按名称存放 ToolSpec，支持注册、查找和导出 Schema
class ToolRegistry:

    def __init__(self):
        self.tools = {}

    # 注册工具，重名直接报错
    def register(self, tool: ToolSpec):

        if tool.name in self.tools:
            raise ValueError(
                f"工具已经注册：{tool.name}"
            )

        self.tools[tool.name] = tool

    def get(self, name: str):

        return self.tools.get(name)

    def list_tools(self):

        return list(self.tools.values())

    # 导出成 OpenAI Function Calling 的 tools 参数格式
    def get_schemas(self):

        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in self.tools.values()
        ]




# 参数校验失败异常
class ToolValidationError(Exception):
    pass


def validate_arguments(schema: dict, arguments: dict):

    if not isinstance(arguments, dict):
        raise ToolValidationError("工具参数必须是 JSON 对象")

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # 1. 检查必填参数
    for name in required:
        if name not in arguments:
            raise ToolValidationError(
                f"缺少必填参数：{name}"
            )

    # 2. 检查未知参数
    if schema.get("additionalProperties") is False:
        for name in arguments:
            if name not in properties:
                raise ToolValidationError(
                    f"不允许的参数：{name}"
                )

    # 3. 检查参数类型
    for name, value in arguments.items():

        if name not in properties:
            continue

        expected_type = properties[name].get("type")

        valid = True

        if expected_type == "integer":
            valid = type(value) is int

        elif expected_type == "number":
            valid = type(value) in (int, float)

        elif expected_type == "string":
            valid = isinstance(value, str)

        elif expected_type == "boolean":
            valid = isinstance(value, bool)

        elif expected_type == "array":
            valid = isinstance(value, list)

        elif expected_type == "object":
            valid = isinstance(value, dict)

        if not valid:
            raise ToolValidationError(
                f"参数 {name} 类型错误，期望 {expected_type}"
            )




import json
import asyncio
import inspect


# 工具运行时：dispatch 是唯一入口，串起查找 → 解析 → 校验 → 授权 → 执行
class ToolRuntime:

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def dispatch(
        self,
        tool_name: str,
        arguments: str
    ) -> str:

        # 1. 查找工具
        tool = self.registry.get(tool_name)

        if tool is None:
            return json.dumps({
                "success": False,
                "error": f"工具不存在：{tool_name}"
            }, ensure_ascii=False)

        # 2. 解析 JSON
        try:
            args = json.loads(arguments)

        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"JSON 参数解析失败：{e}"
            }, ensure_ascii=False)

        # 3. 参数校验
        try:
            validate_arguments(
                tool.parameters,
                args
            )

        except ToolValidationError as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)

        # 4. 权限检查
        if tool.requires_confirmation:
            return json.dumps({
                "success": False,
                "error": "该工具需要用户确认，当前尚未获得授权"
            }, ensure_ascii=False)

        # 5. 执行工具，失败后按 max_retries 重试
        for attempt in range(tool.max_retries + 1):

            try:

                # 协程工具直接 await；同步工具丢进线程池，避免阻塞事件循环
                if inspect.iscoroutinefunction(tool.handler):

                    result = await asyncio.wait_for(
                        tool.handler(**args),
                        timeout=tool.timeout
                    )

                else:

                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            tool.handler,
                            **args
                        ),
                        timeout=tool.timeout
                    )

                # default=str 兜底：返回值不可 JSON 序列化时转成字符串
                return json.dumps({
                    "success": True,
                    "data": result
                }, ensure_ascii=False, default=str)

            except asyncio.TimeoutError:

                error = "工具执行超时"

            except Exception as e:

                error = f"工具执行异常：{str(e)}"

            # 判断是否还有重试机会
            if attempt < tool.max_retries:
                await asyncio.sleep(0.5)

        return json.dumps({
            "success": False,
            "error": error
        }, ensure_ascii=False)
