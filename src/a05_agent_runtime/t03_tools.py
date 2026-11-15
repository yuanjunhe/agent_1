# ============================================================
# 定义业务工具集：Agent 用的三个实际工具函数
#
# 纯函数集合，不含 Schema 和注册逻辑；Schema 定义在
# t04_agent.py 的 create_runtime() 里，和 handler 分开。
# get_weather 返回模拟数据，不调用真实天气服务。
#
# 运行：uv run python src/a05_agent_runtime/t05_agent_demo.py
# ============================================================


# 加法工具
def add(a: int, b: int):
    return a + b


# 乘法工具
def multiply(a: int, b: int):
    return a * b


# 天气查询工具（模拟数据）
def get_weather(city: str):
    weather_data = {
        "北京": "晴天，25℃",
        "上海": "多云，28℃",
        "深圳": "小雨，30℃"
    }

    return weather_data.get(city, "暂无天气数据")
