# ============================================================
# Resource 与 Prompt 客户端测试：验证 t04 新增的三种能力
#
# MCP 不只有工具，还有两类数据和一类模板：
# 1. 固定 Resource：URI 写死（company://policy），客户端直接读
# 2. Resource Template：URI 带参数占位（users://{user_id}/profile），
#    list_resource_templates 发现，按实际 ID 读
# 3. Prompt：服务端预置的提示词模板（analyze_order），get_prompt
#    传参取回 messages，可直接当 LLM 的输入
#
# 运行前先起服务端：uv run python src/a06_MCP/t04_user_server.py
# （mcp dev 起的是 stdio + Inspector，HTTP 客户端连不上）
# 运行：uv run python src/a06_MCP/t06_test_resources_prompts.py
# ============================================================

import asyncio

from mcp import Client
from mcp.types import TextResourceContents, TextContent


async def main():

    async with Client("http://localhost:8001/mcp") as client:

        # =========================
        # 一、读取固定 Resource
        # =========================
        print("\n===== 固定 Resource =====")

        resources = await client.list_resources()

        for resource in resources.resources:
            print("资源 URI：", resource.uri)

        result = await client.read_resource("company://policy")

        for item in result.contents:
            if isinstance(item, TextResourceContents):
                print(item.text)

        # =========================
        # 二、读取 Resource Template
        # =========================
        print("\n===== Resource Template =====")

        templates = await client.list_resource_templates()

        for template in templates.resource_templates:
            print("模板 URI：", template.uri_template)

        result = await client.read_resource(
            "users://U1001/profile"
        )

        for item in result.contents:
            if isinstance(item, TextResourceContents):
                print(item.text)

        # =========================
        # 三、获取 Prompt
        # =========================
        print("\n===== Prompt =====")

        prompts = await client.list_prompts()

        for prompt in prompts.prompts:
            print("Prompt 名称：", prompt.name)
            print("Prompt 描述：", prompt.description)

        prompt_result = await client.get_prompt(
            "analyze_order",
            {
                "order_id": "O1001",
                "order_info": "金额 360 元，状态已支付"
            }
        )

        for message in prompt_result.messages:
            print("角色：", message.role)

            if isinstance(message.content, TextContent):
                print("提示词内容：", message.content.text)


if __name__ == "__main__":
    asyncio.run(main())
