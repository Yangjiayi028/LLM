"""AnythingLLM MCP Server (MVP) — 单个工具：向 AnythingLLM 第一个工作区提问。

MCP 协议 2026-07-28，Streamable HTTP 传输（无状态）。
"""
import os
from pathlib import Path

import anyio
import httpx
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

# 无论从哪个目录启动，都读取 server.py 所在目录的 .env
load_dotenv(Path(__file__).resolve().parent / ".env")

BASE_URL = os.getenv("ANYTHINGLLM_BASE_URL", "http://localhost:3001").rstrip("/")
API_KEY = os.getenv("ANYTHINGLLM_API_KEY", "")
SLUG = os.getenv("WORKSPACE_SLUG", "")
HOST = os.getenv("MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("MCP_PORT", "8899"))
_HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def first_workspace_slug() -> str:
    r = httpx.get(f"{BASE_URL}/api/v1/workspaces", headers=_HEADERS, timeout=10)
    r.raise_for_status()
    workspaces = r.json().get("workspaces", [])
    if not workspaces:
        raise RuntimeError("AnythingLLM 没有可用工作区")
    return workspaces[0]["slug"]


SLUG = SLUG or first_workspace_slug()
print(f"[anythingllm-mcp] 使用工作区: {SLUG}")

server = MCPServer("anythingllm")


@server.tool()
def anythingllm_ask(question: str, mode: str = "automatic") -> str:
    """向 AnythingLLM 第一个工作区提问，返回基于工作区文档的 AI 回答及来源标题。

    mode: automatic=检索+LLM回答（默认），query=仅检索到相关片段才用LLM，chat=纯LLM+自定义嵌入。
    """
    body = {"message": question, "mode": mode}
    r = httpx.post(
        f"{BASE_URL}/api/v1/workspace/{SLUG}/chat",
        json=body,
        headers=_HEADERS,
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        return f"AnythingLLM 错误: {data['error']}"
    text = data.get("textResponse") or ""
    titles = [s.get("title", "") for s in (data.get("sources") or [])]
    return text + ("\n\n来源: " + ", ".join(titles) if titles else "")


async def main() -> None:
    await server.run_streamable_http_async(
        host=HOST, port=PORT, stateless_http=True
    )


if __name__ == "__main__":
    anyio.run(main)
