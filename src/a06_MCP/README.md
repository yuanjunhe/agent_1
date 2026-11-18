# MCP：让工具从"自己写"变成"别人提供"

## 架构总览

```
MCP 三层演进（t01 → t03，每个文件在上一个基础上加一件事）：

  t01 Server：工具和资源的提供方
  ─────────────────────────────────────────────
  @mcp.tool() 注册工具           @mcp.resource(URI) 注册资源
  （docstring 即描述，          （URI 定位，客户端主动读，
    类型注解自动生成 Schema）      类 GET 请求，不做动作）
       │                             │
       └──────────┬──────────────────┘
                  ▼
        mcp.run() 起服务，等客户端连接

  t02 Client：标准协议访问
  ─────────────────────────────────────────────
  Client("http://localhost:8000/mcp")
       │
       ▼
  list_tools     发现工具（动态，不用写死）
  call_tool      调用工具，结果在 result.content[i].text
  read_resource  读资源，结果在 result.contents[i].text

  t03 Agent：LLM 接上动态发现的工具
  ─────────────────────────────────────────────
  list_tools 发现 MCP 工具
       │
       ▼
  convert_mcp_tools 翻译成 Tool Calling 格式
       │
       ▼
  Agent Loop：LLM 决定调什么 → call_tool（执行发生在服务端）
  → 结果交回 LLM → 直到给出最终答案
  t04-t05 多 Server 接入
  ─────────────────────────────────────────────
  t04 第二个 Server（用户/订单服务，8001 端口）
       │
       ▼
  t05 Agent 同时连两个 Server
       │  AsyncExitStack 统一管理多个 Client 生命周期
       ▼
  发现工具时加前缀：math__add / user__get_user_info
       │  ★ 前缀避免跨 Server 工具重名
       ▼
  工具路由表：LLM 工具名 → (Client, 原始工具名)
       │
       ▼
  Agent Loop 里按路由分发：找到 Client 调原始名，
  结果（或 structured_content）交回 LLM

  t06-t08 资源/Prompt 与 STDIO 传输
  ─────────────────────────────────────────────
  t06 直接测 t04 的三类能力：
    固定 Resource（URI 写死）→ 直接 read
    Resource Template（URI 带 {参数}）→ 按实际 ID read
    Prompt → get_prompt 传参取回 messages
       │
       ▼
  t07 综合 Agent：三类能力合体——
    Resource（公司规则）+ Prompt（分析模板）拼进 system，
    工具调用走 t05 的路由表，LLM 按规则、按模板分析订单
       │
       ▼
  t08 换 STDIO 传输：Client 拿 StdioServerParameters
    自己 spawn 服务端子进程，stdin/stdout 收发 JSON-RPC，
    不占端口；上层协议动作（list_tools/call_tool）不变
```

## 两种传输怎么选

| 启动方式 | 传输 | 谁连谁 | 用途 |
|---|---|---|---|
| `mcp dev xxx.py` | stdio | Inspector 网页连子进程 | 人工调试服务端（t04 头注释的"调试"命令） |
| `uv run python t0x_server.py` | streamable-http | t02/t05/t06/t07 连 localhost 端口 | 真实运行，服务端独立起 |
| Client + `StdioServerParameters` | stdio | 客户端自己 spawn 子进程 | 桌面客户端场景，t08 演示，不用先起服务端 |

## 文件清单

| 文件 | 角色 | 关键点 |
|---|---|---|
| `t01_server.py` | MCP Server（数学服务） | 装饰器注册 Tool / Resource；docstring 即描述，类型注解自动生成 Schema |
| `t02_client.py` | MCP Client | 三个核心动作：list_tools / call_tool / read_resource，先起服务端再跑 |
| `t03_agent.py` | MCP Agent（单 Server） | 工具动态发现 + 转成 Tool Calling 格式，换 Server 就换工具，Agent 代码不改 |
| `t04_user_server.py` | MCP Server（用户/订单服务） | 第二个服务占 8001 端口；含固定 Resource、Resource Template、Prompt，返回 dict → structured_content |
| `t05_multi_server_agent.py` | 多 Server MCP Agent | AsyncExitStack 管多个连接；工具名加 `服务__` 前缀防冲突，路由表分发调用 |
| `t06_test_resources_prompts.py` | Resource / Prompt 测试 | 客户端读固定资源、模板资源（带参数 URI）、取回 Prompt 模板 |
| `t07_agent2.py` | 综合 Agent | Resource 规则 + Prompt 模板拼进 system，工具走 t05 路由表，三类能力一个 Agent 全用上 |
| `t08_test_stdio.py` | STDIO 客户端测试 | StdioServerParameters 让 Client 自己拉起服务端子进程，不占端口、不用先起服务端 |

## 一条主线

a05 把工具执行整合成可复用模块，但工具还是**自己写、进程内注册**；MCP 把"工具"抽成独立服务——Server 提供工具，Client 按标准协议发现和调用，执行发生在服务端进程。接上 Agent 后，工具集从"代码里写死的几个函数"变成"连接哪个 Server 就有哪套工具"。

> 关键认知：**MCP 对 Agent 的意义 = 工具的动态发现 + 进程解耦**——`list_tools` 替代手工注册，`convert_mcp_tools` 那一步翻译就是 Tool Schema 和 MCP Schema 之间的桥。
> 踩坑记录：`read_resource` 返回 `ReadResourceResult`，内容在 `.contents[i].text`；`call_tool` 的结果在 `.content[i].text`。直接迭代 pydantic 模型拿到的是 `(字段名, 值)` 元组，不是内容。
> 传输坑：`mcp dev` / `mcp run` 默认 stdio（挂在父进程下，不占端口），HTTP 客户端连不上——t02/t05/t06/t07 必须用 `uv run python` 直跑服务端（脚本里显式 `transport="streamable-http"`）；反过来 t08 的 stdio 客户端也连不上 HTTP 起的服务端，两边传输要对上。
