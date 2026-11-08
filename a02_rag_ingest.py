# ============================================================
# RAG 入库：文档 → 切分 → Embedding → 存入 ChromaDB
#
# 读取文档，切成 Chunk，用 Embedding 模型
# 转成向量后存入 ChromaDB（持久化），供后续检索。
#
# 运行：uv run a02_rag_ingest.py
# ============================================================

from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


# 1. 基础配置

# 项目目录 / 原始文档目录 / ChromaDB 持久化目录
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Collection 名称，必须和 a03_rag_query.py 一致
COLLECTION_NAME = "java_knowledge"

# Chunk 大小（字符数）和相邻 Chunk 的重叠字符数
# 例如 size=200、overlap=50：Chunk1 是 0~200，Chunk2 是 150~350，
# 重叠的 50 字符避免一个知识点刚好被切到两个 Chunk 中间
CHUNK_SIZE = 200
CHUNK_OVERLAP = 50

# Embedding 模型（中文小模型，512 维），入库和查询必须用同一个
EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"


# 2. 读取文档

def load_documents():
    """从 data 目录读取所有 txt / md 文件，返回 [{"text", "source"}, ...]"""
    documents = []

    files = sorted(
        list(DATA_DIR.glob("*.txt"))
        + list(DATA_DIR.glob("*.md"))
    )

    if not files:
        raise RuntimeError(
            f"没有找到 txt / md 文档，请检查目录：{DATA_DIR}"
        )

    for file_path in files:
        print(f"正在读取：{file_path.name}")

        text = file_path.read_text(encoding="utf-8").strip()
        if not text:
            print(f"跳过空文件：{file_path.name}")
            continue

        documents.append({
            "text": text,
            "source": file_path.name
        })

    print(f"\n共读取 {len(documents)} 个文档")

    return documents


# 3. 文本切分

def split_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    把长文本按固定窗口切成多个 Chunk，相邻 Chunk 重叠 overlap 个字符。

    例如 chunk_size=10、overlap=3：
      Chunk 1: ABCDEFGHIJ
      Chunk 2: HIJKLMNOPQ   （H I J 是重叠部分）
    """
    if overlap >= chunk_size:
        raise ValueError(
            "CHUNK_OVERLAP 必须小于 CHUNK_SIZE"
        )

    chunks = []
    start = 0

    while start < len(text):
        chunk = text[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)

        # 窗口每次前移 chunk_size - overlap
        start += chunk_size - overlap

    return chunks


def build_chunks(documents):
    """切分所有文档并打上来源标记，得到 [{"text", "source", "chunk"}, ...]"""
    all_chunks = []

    for document in documents:
        chunks = split_text(document["text"])
        print(f"{document['source']} -> {len(chunks)} 个 Chunk")

        for index, chunk in enumerate(chunks):
            all_chunks.append({
                "text": chunk,
                "source": document["source"],
                "chunk": index
            })

    print(f"\n总 Chunk 数量：{len(all_chunks)}")

    return all_chunks


# 4. 加载 Embedding 模型

def load_embedding_model():
    """加载 BAAI/bge-small-zh-v1.5，输出 512 维向量"""
    print("\n正在加载 Embedding 模型：")
    print(EMBEDDING_MODEL_NAME)

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    print(f"Embedding 维度：{model.get_embedding_dimension()}")

    return model


# 5. 生成 Embedding

def create_embeddings(model, chunks):
    """每个 Chunk 转成一个向量：Chunk → Embedding 模型 → [0.12, -0.03, ...]"""
    texts = [chunk["text"] for chunk in chunks]

    print("\n正在生成 Embedding...")

    embeddings = model.encode(texts, show_progress_bar=True)

    print(f"Embedding 数量：{len(embeddings)}")
    print(f"Embedding Shape：{embeddings.shape}")

    return embeddings


# 6. 创建 ChromaDB

def create_collection():
    """创建持久化 Collection，数据落在 chroma_db/，程序结束不丢失"""
    print("\n正在初始化 ChromaDB...")

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    print(f"Collection：{COLLECTION_NAME}")
    print(f"当前数据量：{collection.count()}")

    return collection


# 7. 保存到 ChromaDB

def save_to_chroma(collection, chunks, embeddings):
    """把文本、向量、Metadata 一起写入 ChromaDB"""
    ids = []
    documents = []
    metadatas = []

    for index, chunk in enumerate(chunks):
        # 每条数据必须有唯一 ID
        ids.append(f"{chunk['source']}_{chunk['chunk']}_{index}")
        documents.append(chunk["text"])
        metadatas.append({
            "source": chunk["source"],
            "chunk": chunk["chunk"]
        })

    print("\n正在保存到 ChromaDB...")

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings.tolist(),
        metadatas=metadatas
    )

    print(f"保存完成，当前数据库数据量：{collection.count()}")


# 8. 验证

def verify_collection(collection):
    """取出前 5 条数据，确认入库成功"""
    print("\n========== 数据库验证 ==========")

    result = collection.get(limit=5)

    for i in range(len(result["ids"])):
        print(f"\n--- 数据 {i + 1} ---")
        print("ID：")
        print(result["ids"][i])
        print("文本：")
        print(result["documents"][i])
        print("Metadata：")
        print(result["metadatas"][i])


# 9. 主程序

def main():
    print("================================")
    print("       RAG 知识库构建程序")
    print("================================")

    # 2. 读取文档
    documents = load_documents()

    # 3. 文本切分
    chunks = build_chunks(documents)

    # 4. 加载 Embedding 模型
    model = load_embedding_model()

    # 5. 生成 Embedding
    embeddings = create_embeddings(model, chunks)

    # 6. 创建 ChromaDB
    collection = create_collection()

    # 7. 保存到 ChromaDB
    save_to_chroma(collection, chunks, embeddings)

    # 8. 验证
    verify_collection(collection)

    print("\n================================")
    print("       RAG 知识库构建完成")
    print("================================")


# Python 程序入口
if __name__ == "__main__":
    main()
