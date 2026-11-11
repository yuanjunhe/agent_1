# ============================================================
# 合流：RAG 检索封装成工具，交给 Agent 自己决定何时查库
#
# 前面两条线在这里汇合：把 RAG 的向量检索封装成 search_knowledge
# 工具（RAG 线提供"知识"），套上 Tool Calling 线的 Agent Loop
# （提供"手脚"）。LLM 自己判断要不要查库、查什么。
#
# 运行前必须先跑过入库脚本 t02_rag_ingest.py（否则 collection 不存在）。
# 运行：uv run python src/a03_agent/t01_rag_agent.py
# ============================================================

import os
import json
import asyncio

import chromadb
from openai import AsyncOpenAI
from sentence_transformers import SentenceTransformer


# 1. 创建异步客户端

client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# 2. 加载 Embedding 模型
# 必须和 t02_rag_ingest.py 入库时用的是同一个模型

embedding_model = SentenceTransformer("BAAI/bge-small-zh-v1.5")


# 3. 连接 ChromaDB 并获取知识库
# 路径和 Collection 名都要与 t02_rag_ingest.py 一致

chroma_client = chromadb.PersistentClient(path="./chroma_db")

collection = chroma_client.get_collection(name="java_knowledge")


# 4. RAG 检索工具：把向量检索的查询逻辑封装成一个 Tool

def search_knowledge(query: str) -> str:
    """根据问题检索知识库，返回拼接好的知识片段文本"""
    print(f"\n[RAG] 查询知识库：{query}")

    # 问题 → 向量
    query_embedding = embedding_model.encode(query).tolist()

    # 检索最相关的 3 个文档
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )

    documents = results.get("documents", [[]])[0]
    if not documents:
        return "知识库中没有找到相关内容。"

    # 多个片段拼成一个字符串，作为 tool 结果交给 LLM
    knowledge = "\n\n".join(
        f"[知识片段 {i + 1}]\n{doc}"
        for i, doc in enumerate(documents)
    )

    print("[RAG] 检索完成")

    return knowledge


# 5. Tool Registry
# 和计算类工具的 Registry 写法完全一致，只是工具换成了检索函数

TOOL_REGISTRY = {
    "search_knowledge": search_knowledge
}


# 6. Tool Schema
# description 写清"什么时候该用"——它直接决定 LLM 会不会查库

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "搜索内部知识库。当用户的问题需要查询知识库中的"
                "技术文档、项目资料或内部知识时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "需要查询知识库的问题"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# 7. Dispatcher
# LLM 给工具名和参数，这里负责查表执行，出错返回错误字符串

def dispatch_tool(tool_name: str, arguments: dict):
    """根据 Tool 名称找到对应 Python 函数并执行"""
    print(f"\n[Dispatcher] Tool: {tool_name}")
    print(f"[Dispatcher] 参数: {arguments}")

    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return f"错误：不存在 Tool {tool_name}"

    try:
        result = tool(**arguments)
        print("[Dispatcher] Tool 执行完成")
        return result
    except Exception as e:
        return f"Tool 执行失败：{str(e)}"


# 8. Agent：System Prompt + Agent Loop
# System Prompt 定角色和规矩（先查库、按库回答、查不到别编），
# 循环体就是之前学过的 Tool Calling Loop

async def agent(user_question: str):

    messages = [
        {
            "role": "system",
            "content": """
你是一个知识库问答助手。

当用户的问题需要查询知识库时，
请调用 search_knowledge。

获得知识库结果后，
请严格根据知识库内容回答。

如果知识库中没有相关信息，
请明确告诉用户没有找到相关知识，
不要编造答案。
"""
        },
        {
            "role": "user",
            "content": user_question
        }
    ]

    while True:

        print("\n================ 调用 LLM ================")

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )

        message = response.choices[0].message

        # 不需要工具：直接返回最终答案
        if not message.tool_calls:
            return message.content

        # 需要工具：assistant 消息必须先入历史
        messages.append(message)

        # 逐个执行 tool_call，结果带 tool_call_id 回传
        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            result = dispatch_tool(tool_name, arguments)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                }
            )


# 9. 主程序

async def main():

    question = input("请输入问题：")

    answer = await agent(question)

    print("\n================ 最终答案 ================")
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())
