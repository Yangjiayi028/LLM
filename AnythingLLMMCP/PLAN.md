# AnythingLLM MCP Server — MVP 开发计划

## 1. 目标
用 Python 写一个 MCP Server，走 **HTTP 传输（Streamable HTTP）**，对外只暴露**一个工具**：向 AnythingLLM 第一个工作区提问，返回 AI 基于工作区文档的回答（RAG）。不做多余功能。

## 2. 已探查确认的事实
- AnythingLLM 运行在本机 `http://localhost:3001`，API key 已验证有效。
- 当前有 1 个工作区：「我的工作区」，slug = `1a5e11e2-0b48-42ca-b2b9-29997206dfe2`。
- 聊天接口：`POST /api/v1/workspace/{slug}/chat`
  - 请求体：`{"message": "...", "mode": "automatic|query|chat", "sessionId": "可选"}`
  - 响应：`{textResponse, sources[{title, chunk}], error, ...}`
  - 流式接口 `.../stream-chat` 本期不用。
- MCP 协议 **2026-07-28**（当前最新版，2026-07-28 发布）：
  - **无状态核心**：没有 initialize 握手，协议版本/客户端能力放在每次请求体的 `_meta` 中。
  - Streamable HTTP：**单个 MCP 端点，只收 POST**；必须带头 `MCP-Protocol-Version`、`Mcp-Method`（tools/call 时还需 `Mcp-Name`）。
  - 官方 Python SDK 为 Tier 1 SDK，已支持该版本。

## 3. 架构（最小）
```
MCP Client ──HTTP(JSON-RPC)──> MCP Server (Python, 端口 8899) ──REST──> AnythingLLM (localhost:3001)
```

## 4. 技术选型
- 官方 `mcp` Python SDK（2026-07-28 兼容版本）+ FastMCP `transport="http"`（或 StreamableHTTPServer），uvicorn 启动。
- `httpx` 调 AnythingLLM；`python-dotenv` 读配置。

## 5. MVP 功能：一个工具
**`anythingllm_ask(question: str, mode: str = "automatic")`**
1. 启动时 `GET /api/v1/workspaces` 取**第一个**工作区 slug（写死也行，用 .env 覆盖）。
2. 调 `POST /api/v1/workspace/{slug}/chat`，`mode` 默认 `automatic`（检索+LLM 回答）。
3. 返回 `textResponse` 文本 + `sources` 的标题列表；AnythingLLM 报错则原样透传为工具错误。

## 6. 目录结构（单文件起步，不拆模块）
```
D:\LLM\AnythingLLMMCP\
  server.py        # MCP server + 唯一工具（约 100 行）
  .env             # ANYTHINGLLM_BASE_URL / ANYTHINGLLM_API_KEY / WORKSPACE_SLUG / MCP_PORT
  requirements.txt # mcp, httpx, python-dotenv
  PLAN.md
```

## 7. 实施步骤
1. 创建 venv，安装 `mcp`（确认其 Streamable HTTP 在 2026-07-28 下的用法）、`httpx`、`python-dotenv`。
2. 写 `server.py`：配置读取 → 启动时探测第一个工作区 → 注册 `anythingllm_ask`。
3. 启动服务，用 curl 模拟 MCP 客户端验证：
   - `POST /mcp`，头含 `MCP-Protocol-Version: 2026-07-28`、`Mcp-Method: tools/list` → 应返回 1 个工具。
   - `Mcp-Method: tools/call` + `Mcp-Name: anythingllm_ask` → 真实提问，应返回回答+来源。
4. 用真实问题联调 AnythingLLM，核对回答内容来自工作区文档。

## 8. 验证标准
- tools/list 返回且仅返回 1 个工具。
- tools/call 真实提问返回非空 `textResponse` 与 sources。
- 错误路径：AnythingLLM 未启动 / key 无效 / 无工作区时返回明确错误，不崩溃。

## 9. 明确不做（避免过度设计）
- 多工作区选择、会话历史（sessionId/多轮）、流式输出（SSE）、resources/prompts、OAuth 鉴权、Docker、配置文件界面、测试套件。

## 10. 参考
- AnythingLLM API 文档：http://localhost:3001/api/docs/
- MCP 2026-07-28 规范：https://modelcontextprotocol.io/specification/2026-07-28/
- Streamable HTTP 传输：https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
