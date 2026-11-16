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
```

## 文件清单

| 文件 | 角色 | 关键点 |
|---|---|---|
| `t01_server.py` | MCP Server | 装饰器注册 Tool / Resource；docstring 即描述，类型注解自动生成 Schema |
| `t02_client.py` | MCP Client | 三个核心动作：list_tools / call_tool / read_resource，先起服务端再跑 |
| `t03_agent.py` | MCP Agent | 工具动态发现 + 转成 Tool Calling 格式，换 Server 就换工具，Agent 代码不改 |

## 一条主线

a05 把工具执行整合成可复用模块，但工具还是**自己写、进程内注册**；MCP 把"工具"抽成独立服务——Server 提供工具，Client 按标准协议发现和调用，执行发生在服务端进程。接上 Agent 后，工具集从"代码里写死的几个函数"变成"连接哪个 Server 就有哪套工具"。

> 关键认知：**MCP 对 Agent 的意义 = 工具的动态发现 + 进程解耦**——`list_tools` 替代手工注册，`convert_mcp_tools` 那一步翻译就是 Tool Schema 和 MCP Schema 之间的桥。
> 踩坑记录：`read_resource` 返回 `ReadResourceResult`，内容在 `.contents[i].text`；`call_tool` 的结果在 `.content[i].text`。直接迭代 pydantic 模型拿到的是 `(字段名, 值)` 元组，不是内容。
