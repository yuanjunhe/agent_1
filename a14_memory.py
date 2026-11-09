# ============================================================
# 记忆存储：SQLite 持久化提取出的长期记忆
#
# MemoryStore 提供按 user_id 隔离的增查接口：add 写入一条
# 记忆，list 读出一个用户的全部记忆；表结构为
# user_id + content + 自增 id。
#
# 运行：uv run a14_test_long_term_memory.py
# ============================================================

import sqlite3
from dataclasses import dataclass


@dataclass
class Memory:
    id: int
    user_id: str
    content: str


class MemoryStore:

    def __init__(self, db_path="agent_memory.db"):
        self.conn = sqlite3.connect(db_path)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL
            )
        """)

        self.conn.commit()

    def add(self, user_id: str, content: str):

        self.conn.execute(
            """
            INSERT INTO memories (user_id, content)
            VALUES (?, ?)
            """,
            (user_id, content)
        )

        self.conn.commit()

    def list(self, user_id: str):

        cursor = self.conn.execute(
            """
            SELECT id, user_id, content
            FROM memories
            WHERE user_id = ?
            ORDER BY id
            """,
            (user_id,)
        )

        return cursor.fetchall()