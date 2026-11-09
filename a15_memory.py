# ============================================================
# 记忆存储：SQLite 持久化长期记忆，提供完整 CRUD
#
# MemoryStore 按用户隔离记忆：add / get / list / update /
# delete / search 六个方法，表结构为 user_id + category +
# content + 时间戳，user_id 建有索引。
#
# 运行：uv run a15_test_crud.py
# ============================================================

import sqlite3


class MemoryStore:

    def __init__(self, db_path="agent_memory.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        # 创建记忆表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 为 user_id 创建索引
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_user
            ON memories(user_id)
        """)

        self.conn.commit()

    # CREATE：新增记忆
    def add(self, user_id: str, category: str, content: str) -> int:

        cursor = self.conn.execute(
            """
            INSERT INTO memories (user_id, category, content)
            VALUES (?, ?, ?)
            """,
            (user_id, category, content)
        )

        self.conn.commit()

        return cursor.lastrowid

    # READ：根据 ID 查询单条记忆
    def get(self, user_id: str, memory_id: int):

        cursor = self.conn.execute(
            """
            SELECT *
            FROM memories
            WHERE user_id = ? AND id = ?
            """,
            (user_id, memory_id)
        )

        row = cursor.fetchone()

        return dict(row) if row else None

    # READ：查询用户全部记忆
    def list(self, user_id: str):

        cursor = self.conn.execute(
            """
            SELECT *
            FROM memories
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        )

        return [dict(row) for row in cursor.fetchall()]

    # UPDATE：修改记忆
    def update(
        self,
        user_id: str,
        memory_id: int,
        category: str,
        content: str
    ) -> bool:

        cursor = self.conn.execute(
            """
            UPDATE memories
            SET category = ?,
                content = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND id = ?
            """,
            (category, content, user_id, memory_id)
        )

        self.conn.commit()

        return cursor.rowcount > 0

    # DELETE：删除记忆
    def delete(self, user_id: str, memory_id: int) -> bool:

        cursor = self.conn.execute(
            """
            DELETE FROM memories
            WHERE user_id = ? AND id = ?
            """,
            (user_id, memory_id)
        )

        self.conn.commit()

        return cursor.rowcount > 0

    # SEARCH：关键词检索记忆
    def search(
        self,
        user_id: str,
        keyword: str,
        limit: int = 5
    ):

        keyword = keyword.strip()

        if not keyword:
            return []

        cursor = self.conn.execute(
            """
            SELECT *
            FROM memories
            WHERE user_id = ?
              AND content LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, f"%{keyword}%", limit)
        )

        return [dict(row) for row in cursor.fetchall()]

    # 关闭数据库连接
    def close(self):
        self.conn.close()
