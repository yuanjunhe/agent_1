# ============================================================
# RAG 问答：问题 → 向量检索 → 拼 Prompt → LLM 生成答案
#
# 连接前面建好的 ChromaDB，把用户问题转成向量
# 检索 Top-K 相关 Chunk，拼进 Prompt 交给 DeepSeek 生成回答。
#
# 运行：uv run python src/a01_rag/t03_rag_query.py
# ============================================================

from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI

import os


# 1. 基础配置

# 项目根 / ChromaDB 数据目录
# chroma_db/ 在项目根目录，不在本文件所在目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CHROMA_DIR = BASE_DIR / "chroma_db"

# 必须和 t02_rag_ingest.py（RAG 建库脚本，在 src/a01_rag/ 下）使用相同的 Collection
COLLECTION_NAME = "java_knowledge"

# 必须使用和入库时相同的 Embedding 模型
EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"

# 每次检索返回多少条结果
TOP_K = 3

# DeepSeek 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise RuntimeError(
        "没有找到 DEEPSEEK_API_KEY 环境变量"
    )

llm = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

LLM_MODEL = "deepseek-v4-flash"


# 2. 初始化 Embedding 模型

print("正在加载 Embedding 模型...")

model = SentenceTransformer(EMBEDDING_MODEL_NAME)

print(f"Embedding 维度：{model.get_embedding_dimension()}")


# 3. 连接 ChromaDB

print("\n正在连接 ChromaDB...")

client = chromadb.PersistentClient(path=str(CHROMA_DIR))

collection = client.get_collection(name=COLLECTION_NAME)

print(f"知识库名称：{COLLECTION_NAME}")
print(f"知识库数据量：{collection.count()}")


# 4. 向量检索

def search(query: str, top_k: int = TOP_K):
    """把问题转成向量，在 ChromaDB 里检索最相关的 top_k 条 Chunk"""
    # 问题 → 向量
    query_embedding = model.encode(query)
    print(f"\n问题：{query}")
    print(f"问题向量维度：{query_embedding.shape}")

    # 用问题向量查询 ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k
    )

    return results


# 5. 打印检索结果

def print_results(results):
    """格式化打印 ChromaDB 返回的检索结果"""
    documents = results["documents"][0]
    distances = results["distances"][0]
    ids = results["ids"][0]
    metadatas = results["metadatas"][0]

    print("\n================================")
    print("          检索结果")
    print("================================")

    for i in range(len(documents)):
        print(f"\n----------- Top {i + 1} -----------")
        print(f"ID：{ids[i]}")
        print(f"Distance：{distances[i]:.4f}")
        print(f"Metadata：{metadatas[i]}")
        print(f"Document：\n{documents[i]}")


# 6. 拼 Prompt

def build_prompt(query, results):
    """把用户问题和检索到的知识片段拼装成发送给大模型的 Prompt"""
    # 取出检索到的文本和元数据
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    # 拼装知识上下文
    context_parts = []
    for i in range(len(documents)):
        source = metadatas[i].get("source", "未知来源")
        context_parts.append(
            f"[知识片段 {i + 1}]（来源：{source}）\n"
            f"{documents[i]}"
        )

    context = "\n\n".join(context_parts)

    # 构造完整 Prompt
    prompt = (
        f"用户问题：{query}\n\n"
        f"请根据以下知识库内容回答问题：\n\n"
        f"{context}\n\n"
        f"如果知识库中没有相关内容，请如实说明。"
    )

    return prompt


# 7. 调用 LLM 生成回答

def generate_answer(prompt):
    """把 RAG Prompt 发送给 DeepSeek，返回最终回答"""
    response = llm.chat.completions.create(
        model=LLM_MODEL,

        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个专业的知识库问答助手。"
                    "必须优先根据用户提供的知识库内容回答问题。"
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        # 第一次实验先关闭思考模式
        # OpenAI SDK 未内置 thinking 参数，需通过 extra_body 透传
        extra_body={
            "thinking": {
                "type": "disabled"
            }
        },

        stream=False
    )

    return response.choices[0].message.content


# 8. 主程序

def main():
    print("================================")
    print("          RAG 查询系统")
    print("================================")
    print(f"知识库数据量：{collection.count()}")

    while True:
        query = input("\n请输入问题（输入 q 退出）：")

        if query.lower() == "q":
            print("程序结束")
            break

        if not query.strip():
            continue

        # 4. 向量检索
        results = search(query)

        # 5. 打印检索结果
        print_results(results)

        # 6. 拼 Prompt
        prompt = build_prompt(query, results)

        # 7. 调用 DeepSeek
        print("\n================================")
        print("          DeepSeek 回答")
        print("================================")

        answer = generate_answer(prompt)
        print(answer)


# Python 程序入口
if __name__ == "__main__":
    main()
