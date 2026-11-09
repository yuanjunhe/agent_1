# ============================================================
# MemoryStore CRUD 测试：逐个验证记忆存储的增删改查
#
# 依次执行新增 → 查询 → 更新 → 关键词搜索 → 删除，
# 每步打印结果，验证 a15_memory 各方法的返回值。
#
# 运行：uv run a15_test_crud.py
# ============================================================

from a15_memory import MemoryStore


def main():

    store = MemoryStore()

    user_id = "crud_test_user"

    try:
        # 1. 新增
        memory_id = store.add(
            user_id,
            "career",
            "用户是一名 Java 工程师"
        )

        print("新增记忆：", memory_id)

        # 2. 查询
        print("\n查询记忆：")
        print(store.get(user_id, memory_id))

        # 3. 查询全部
        print("\n全部记忆：")
        for item in store.list(user_id):
            print(item)

        # 4. 更新
        success = store.update(
            user_id,
            memory_id,
            "career",
            "用户是一名 Python 工程师"
        )

        print("\n更新成功：", success)
        print(store.get(user_id, memory_id))

        # 5. 关键词搜索
        print("\n搜索 Python：")
        print(store.search(user_id, "Python"))

        # 6. 删除
        success = store.delete(user_id, memory_id)

        print("\n删除成功：", success)
        print("删除后查询：", store.get(user_id, memory_id))

    finally:
        store.close()


if __name__ == "__main__":
    main()
