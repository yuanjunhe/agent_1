# ============================================================
# 工具 Schema 注册表：发给 LLM 的 Tool Calling 工具定义
#
# 这里只写 LLM 看的 Schema（名字、描述、参数结构），不含
# 实际函数——handler 在 t03_tools.py，两份清单靠工具名对上。
# LLM 按描述决定调什么工具，所以 description 写得越清楚，
# 工具被正确选中的概率越高。
#
# 运行：uv run python src/a07_human_in_the_loop/t05_agent.py
# ============================================================


# 1. 三个工具的 Schema：query_user / delete_user / transfer_money
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_user",
            "description": "根据用户ID查询用户信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "用户ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_user",
            "description": "删除指定用户账户",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_money",
            "description": "将资金从一个账户转到另一个账户",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_user_id": {
                        "type": "integer"
                    },
                    "to_user_id": {
                        "type": "integer"
                    },
                    "amount": {
                        "type": "number"
                    }
                },
                "required": [
                    "from_user_id",
                    "to_user_id",
                    "amount"
                ]
            }
        }
    }
]
