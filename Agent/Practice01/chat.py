import configparser
import requests
import json
import time

# 读取同目录下的 config.ini
config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")

url = config["llm"]["base_url"]
key = config["llm"]["api_key"]
model = config["llm"]["model"]

# 对话历史，支持多轮上下文
messages = []

print("=== DeepSeek 交互式聊天 ===")
print("输入内容后回车发送，按 Ctrl+C 退出\n")

while True:
    user_input = input("你: ").strip()
    if not user_input:
        continue

    messages.append({"role": "user", "content": user_input})

    # 流式请求
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": messages,
            "stream": True,
        },
        stream=True,
    )

    print("AI: ", end="", flush=True)
    assistant_text = ""
    for line in resp.iter_lines():
        if not line:
            continue
        data = line.decode("utf-8")
        if not data.startswith("data: "):
            continue
        payload = data[6:]
        if payload == "[DONE]":
            break
        text = json.loads(payload)["choices"][0]["delta"].get("content", "")
        assistant_text += text
        for ch in text:
            print(ch, end="", flush=True)
            time.sleep(0.03)
    print()

    # 把本轮回复加入历史，下一轮模型才能记得上下文
    messages.append({"role": "assistant", "content": assistant_text})
