# AnythingLLM MCP Server

一个极简的 **MCP Server（Python）**，通过 **Streamable HTTP** 把本机 AnythingLLM 暴露给 MCP 客户端。
协议版本：**MCP 2026-07-28**（无状态）。当前只提供一个工具：向 AnythingLLM **第一个工作区**提问，返回基于工作区文档的 AI 回答（RAG）。

## 文件结构
```
D:\LLM\AnythingLLMMCP\
├── server.py          # MCP Server（唯一入口，约 90 行）
├── .env               # 配置（base URL / API key / 端口）
├── .mcp.json          # 项目级 MCP 配置（供 Cursor / Claude Code 等客户端读取）
├── requirements.txt   # 依赖
└── venv\              # Python 虚拟环境
```

## 环境要求
- Python 3.10+
- 本机 AnythingLLM 正在运行（默认 `http://localhost:3001`），且 API key 有效

## 安装（仅首次）
```powershell
cd "D:\LLM\AnythingLLMMCP"
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
```

## 配置（.env）
| 变量 | 说明 | 默认值 |
|---|---|---|
| `ANYTHINGLLM_BASE_URL` | AnythingLLM 地址 | `http://localhost:3001` |
| `ANYTHINGLLM_API_KEY` | AnythingLLM API key（必填） | 无 |
| `WORKSPACE_SLUG` | 工作区 slug，**留空自动取第一个工作区** | 空 |
| `MCP_HOST` | MCP 服务监听地址 | `127.0.0.1` |
| `MCP_PORT` | MCP 服务端口 | `8899` |

## 启动 / 停止 MCP Server

### 前台启动（推荐，便于看日志）
```powershell
cd "D:\LLM\AnythingLLMMCP"
venv\Scripts\python server.py
```
停止：在窗口按 `Ctrl+C`。

### 后台启动（关掉终端也不中断）
```powershell
Start-Process -FilePath "D:\LLM\AnythingLLMMCP\venv\Scripts\python.exe" `
  -ArgumentList "D:\LLM\AnythingLLMMCP\server.py" `
  -WorkingDirectory "D:\LLM\AnythingLLMMCP" -WindowStyle Hidden
```

### 停止后台服务（按端口找到进程并结束）
```powershell
$pid8899 = (Get-NetTCPConnection -LocalPort 8899 -State Listen).OwningProcess
Stop-Process -Id $pid8899
```

### 验证服务已启动
```powershell
curl.exe http://127.0.0.1:8899/mcp -i
```
能看到 HTTP 响应即服务在运行。启动日志应包含 `[anythingllm-mcp] 使用工作区: ...` 和 `Uvicorn running on http://127.0.0.1:8899`。

## 项目级 MCP 配置（.mcp.json）
`.mcp.json` 位于项目根目录，Cursor、Claude Code 等支持项目级 MCP 的客户端打开本项目时会自动读取：

```json
{
  "mcpServers": {
    "anythingllm": {
      "type": "http",
      "url": "http://127.0.0.1:8899/mcp"
    }
  }
}
```
> ⚠️ **顺序**：必须先启动 MCP Server（见上），客户端才能连上 `http://127.0.0.1:8899/mcp`。

## 工具
| 工具 | 参数 | 说明 |
|---|---|---|
| `anythingllm_ask` | `question`(必填), `mode`=`automatic` | 向第一个工作区提问；`mode`: `automatic` 检索+回答（默认）/ `query` 仅检索到相关片段才回答 / `chat` 纯 LLM+嵌入 |

## 常见问题
- **启动报连接 AnythingLLM 失败**：确认 AnythingLLM 已运行、`.env` 里 key 正确。
- **端口 8899 被占用**：改 `.env` 的 `MCP_PORT`，并同步改 `.mcp.json` 里的 `url`。
- **客户端连不上 / 返回 400**：客户端必须支持 MCP 2026-07-28 且带标准头（`MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name`）；新版本 Cursor / Claude Code 会自动处理。
- **想指定其他工作区**：在 `.env` 填 `WORKSPACE_SLUG`（在 AnythingLLM 的 API 文档里可查到 slug）。
