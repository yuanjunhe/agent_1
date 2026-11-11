# Tool Calling

## 架构总览

```
Tool Calling 演进流程（t01 → t07，每个文件在上一个基础上加一件事）：

  t01 最小闭环（没有循环）
  ─────────────────────────────────────────────
  发消息 + 工具清单（Schema）给 LLM
       │
       ▼
   LLM 返回 tool_calls       只有工具名 + 参数 JSON 字符串
       │
       ▼
   解析参数，本地执行函数
       │
       ▼
   结果包成 role="tool" 回传  tool_call_id 绑定对应哪次调用
       │
       ▼
   再调一次 LLM，生成最终回答

  t02 Agent Loop（核心骨架，后面文件都基于它）
  ─────────────────────────────────────────────
  while True：
       │
       ▼
   调 LLM（带完整历史 + 工具清单）
       │
       ▼
   没有 tool_calls？ ── 是 ──► 输出最终回答，退出
       │ 否
       ▼
   逐个执行 tool_call，失败也包成 tool 消息回传
       │
       └────► 进入下一轮（LLM 看到结果自己纠错）

  t03-t07 在骨架上加的每一层：

   t03  一次响应多个 tool_call，遍历全部执行（不能只取 [0]）
   t04  工具改 async，asyncio.gather 并行执行（串行 4 秒 → 并行 2 秒）
   t05  抽出 TOOL_REGISTRY + dispatch_tool，主循环只管调度
   t06  Dispatcher 里加参数校验，坏参数在进业务代码前拦住
   t07  执行环节加超时（wait_for）+ 重试，工具挂了不拖垮 Agent
```

## 文件清单

| 文件 | 角色 | 关键点 |
|---|---|---|
| `t01_tool_calling_0.py` | 最小闭环 | 一次调用 + 一次回传，看清 tool_calls / tool_call_id / role="tool" 三个概念 |
| `t02_tool_calling.py` | Agent Loop | while True 循环 + 遍历 tool_calls + 三种异常兜底，本目录核心 |
| `t03_multi_tool_calling.py` | 一次多个调用 | LLM 一次返回多个 tool_call，for 循环逐个执行逐个回传 |
| `t04_async_tool_calling.py` | 并行执行 | 工具改 async，asyncio.gather 同时跑，对比串行耗时 |
| `t05_tool_registry.py` | 架构化 | TOOL_REGISTRY 查表 + dispatch_tool 调度，LLM 只认工具名 |
| `t06_tool_validation.py` | 参数校验 | 缺参数 / 类型不对在进业务代码前拦住，错误回传给 LLM 重试 |
| `t07_tool_runtime.py` | 工具运行时 | asyncio.wait_for 超时 + 失败歇 1 秒重试，slow_tool 演示完整链路 |

## 一条主线

所有文件共享同一个心智模型：**LLM = 决策者（返回工具名 + 参数），Python = 执行者（查表跑函数）**。t01→t07 的一切改动，都是在让"执行者"更抗造——把错误当工具结果回传给 LLM，它就能自己纠错。
