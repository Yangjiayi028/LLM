import configparser
import json
import platform
import subprocess
import time

import requests

# 读取同目录下的 config.ini
config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")

url = config["llm"]["base_url"]
key = config["llm"]["api_key"]
model = config["llm"]["model"]

# ========== 1. 定义 function call 工具 ==========
tools = [
    {
        "type": "function",
        "function": {
            "name": "getDate",
            "description": "获取当前电脑的日期和时间",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    }
]


# ========== 2. 工具的真实实现：调用本地 date 命令获取日期时间 ==========
def get_date():
    """通过调用操作系统本地的 date 命令获取当前日期和时间（不编写 Python 日期代码）。"""
    if platform.system() == "Windows":
        # Windows 下 date /t 输出当前日期、time /t 输出当前时间（date 是 cmd 内置命令，必须加 /t，否则会进入修改日期交互）
        date_out = subprocess.run(
            ["cmd", "/c", "date", "/t"], capture_output=True, text=True
        ).stdout.strip()
        time_out = subprocess.run(
            ["cmd", "/c", "time", "/t"], capture_output=True, text=True
        ).stdout.strip()
        return f"当前电脑日期：{date_out}；时间：{time_out}"
    # Linux / macOS 下 date 命令直接输出完整的日期和时间
    out = subprocess.run(["date"], capture_output=True, text=True).stdout.strip()
    return f"当前电脑日期时间：{out}"


# 工具名 -> 实现函数的映射表
TOOL_IMPL = {"getDate": get_date}


# 对话历史，支持多轮上下文
messages = []


def stream_chat(messages, tools=None):
    """向模型发起流式请求，返回 (模型输出的完整文本, 累积的 tool_calls 字典)。

    tool_calls 结构：{index: {"id": ..., "function": {"name": ..., "arguments": ...}}}
    """
    body = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if tools:
        body["tools"] = tools

    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}"},
        json=body,
        stream=True,
    )

    assistant_text = ""
    tool_calls = {}
    for line in resp.iter_lines():
        if not line:
            continue
        data = line.decode("utf-8")
        if not data.startswith("data: "):
            continue
        payload = data[6:]
        if payload == "[DONE]":
            break
        delta = json.loads(payload)["choices"][0].get("delta", {})

        # 普通文本增量
        content = delta.get("content")
        if content:
            assistant_text += content
            for ch in content:
                print(ch, end="", flush=True)
                time.sleep(0.03)

        # function call 增量（流式下按 index 分段累积）
        if delta.get("tool_calls"):
            for tc in delta["tool_calls"]:
                idx = tc.get("index", 0)
                call = tool_calls.setdefault(
                    idx, {"id": "", "function": {"name": "", "arguments": ""}}
                )
                if tc.get("id"):
                    call["id"] = tc["id"]
                if tc.get("function"):
                    call["function"]["name"] += tc["function"].get("name", "")
                    call["function"]["arguments"] += tc["function"].get("arguments", "")
    print()
    return assistant_text, tool_calls


print("=== DeepSeek 交互式聊天（支持 getDate function call）===")
print("输入内容后回车发送，按 Ctrl+C 退出\n")

while True:
    user_input = input("你: ").strip()
    if not user_input:
        continue

    messages.append({"role": "user", "content": user_input})

    # 循环执行：模型可能先请求调用工具，工具结果回传后再继续，直到模型给出最终回答
    while True:
        assistant_text, tool_calls = stream_chat(messages, tools)

        # 没有工具调用：本轮对话结束
        if not tool_calls:
            messages.append({"role": "assistant", "content": assistant_text})
            break

        # 模型请求调用工具：先把 assistant 的 tool_calls 记入历史
        calls = []
        for idx in sorted(tool_calls):
            call = tool_calls[idx]
            calls.append(
                {
                    "id": call["id"] or f"call_{idx}",
                    "type": "function",
                    "function": {
                        "name": call["function"]["name"],
                        "arguments": call["function"]["arguments"],
                    },
                }
            )
        messages.append(
            {"role": "assistant", "content": assistant_text, "tool_calls": calls}
        )

        # 逐个执行工具，并把结果以 role=tool 回传给模型
        for call in calls:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"] or "{}")
            print(f"  [调用工具] {name}({json.dumps(args, ensure_ascii=False)})")
            result = TOOL_IMPL[name](**args)
            print(f"  [工具返回] {result}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                }
            )
