import configparser
import json
import mimetypes
import os
import platform
import shutil
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
    # --- 原有工具 ---
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
    },
    {
        "type": "function",
        "function": {
            "name": "isLeapYear",
            "description": "判断输入的年份是否为闰年",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "要判断的年份，如 2024",
                    }
                },
                "required": ["year"],
            },
        },
    },
    # --- 本地文件操作工具 ---
    {
        "type": "function",
        "function": {
            "name": "getCwd",
            "description": "获取当前工作目录",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listDir",
            "description": "列出指定目录下所有文件和子目录（仅列出一层，不递归）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要列出的目录路径，缺省为当前工作目录",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "getFileType",
            "description": "获取指定文件的文件类型（目录 / 常见扩展名分类 / MIME 类型）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要查询类型的文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "readFile",
            "description": "获取指定文件的内容（仅支持纯文本文件，自动识别 UTF-8 / GBK 编码）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "createFile",
            "description": "根据指定的目录和文件名创建新文件（空文件；若文件已存在则报错）",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "文件所在目录路径",
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名",
                    },
                },
                "required": ["directory", "filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "editFile",
            "description": "编辑指定文件的内容（仅支持纯文本格式文件）。mode 为 overwrite 时覆盖全文，为 append 时在末尾追加",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要编辑的文件路径",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入或追加的文本内容",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["overwrite", "append"],
                        "description": "编辑方式，缺省为 overwrite",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "createDir",
            "description": "创建新目录（可一次创建多级目录；目录已存在时提示）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要创建的目录路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deleteDir",
            "description": "删除目录（包括非空目录，会连同其中所有文件和子目录一并删除，不可恢复，请谨慎使用）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要删除的目录路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deleteFile",
            "description": "删除指定文件（不可恢复，请谨慎使用）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要删除的文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename",
            "description": "重命名文件或目录（old_path 为原路径，new_path 为新路径）",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_path": {
                        "type": "string",
                        "description": "原路径",
                    },
                    "new_path": {
                        "type": "string",
                        "description": "新路径",
                    },
                },
                "required": ["old_path", "new_path"],
            },
        },
    },
]


# ========== 2. 工具的真实实现 ==========

# 2.1 getDate：调用本地 date 命令获取日期时间
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


# 2.2 isLeapYear：用 Python 代码计算指定年份是否为闰年
def is_leap_year(year):
    """判断指定年份是否为闰年（纯 Python 计算）。

    闰年规则：能被 4 整除且不能被 100 整除；或能被 400 整除。
    """
    try:
        year = int(year)
    except (TypeError, ValueError):
        return f"输入的年份无效：{year!r}，请输入合法的整数年份"
    if year < 1:
        return f"输入的年份无效：{year}，年份应为正整数"
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return f"{year} 年是闰年"
    return f"{year} 年不是闰年"


# ===== 2.3 本地文件操作工具（自行开发 Python 代码实现） =====

def get_cwd():
    """获取当前工作目录。"""
    return f"当前工作目录：{os.getcwd()}"


def list_dir(path="."):
    """列出指定目录下所有文件和子目录（仅一层，不递归）。"""
    path = path or "."
    if not os.path.isdir(path):
        return f"错误：目录不存在或不是目录：{path}"
    try:
        entries = sorted(os.listdir(path))
    except PermissionError as e:
        return f"错误：没有权限访问该目录：{e}"
    except OSError as e:
        return f"错误：访问目录失败：{e}"
    if not entries:
        return f"{path} 是空目录"
    lines = [f"{path} 下共有 {len(entries)} 项："]
    for name in entries:
        full = os.path.join(path, name)
        if os.path.isdir(full):
            lines.append(f"[目录] {name}")
        else:
            try:
                size = os.path.getsize(full)
                lines.append(f"[文件] {name}（{size} 字节）")
            except OSError:
                lines.append(f"[文件] {name}")
    return "\n".join(lines)


def create_file(directory, filename):
    """根据指定的目录和文件名创建新文件（空文件）。"""
    directory = directory or "."
    full = os.path.join(directory, filename)
    if not os.path.isdir(directory):
        return f"错误：目录不存在：{directory}"
    if os.path.exists(full):
        return f"错误：文件已存在：{full}"
    try:
        with open(full, "w", encoding="utf-8"):
            pass
        return f"已创建空文件：{full}"
    except OSError as e:
        return f"错误：创建文件失败：{e}"


def read_file(path):
    """获取指定文件的内容（仅支持纯文本文件）。"""
    if not os.path.isfile(path):
        return f"错误：文件不存在或不是普通文件：{path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"文件 {path} 的内容：\n{content}"
    except UnicodeDecodeError:
        # UTF-8 解码失败，尝试 GBK（常见于中文 Windows 环境）
        try:
            with open(path, "r", encoding="gbk") as f:
                content = f.read()
            return f"文件 {path} 的内容（GBK 编码）：\n{content}"
        except (UnicodeDecodeError, OSError) as e:
            return f"错误：无法以纯文本方式读取该文件（可能是二进制文件）：{e}"
    except OSError as e:
        return f"错误：读取文件失败：{e}"


# 常见扩展名 -> 文件类型描述
EXT_TYPES = {
    ".txt": "纯文本文件",
    ".md": "Markdown 文档",
    ".json": "JSON 数据文件",
    ".csv": "CSV 表格文件",
    ".ini": "配置文件",
    ".log": "日志文件",
    ".py": "Python 源代码",
    ".c": "C 源代码",
    ".cpp": "C++ 源代码",
    ".java": "Java 源代码",
    ".js": "JavaScript 源代码",
    ".ts": "TypeScript 源代码",
    ".css": "CSS 样式表",
    ".html": "HTML 网页文件",
    ".xml": "XML 文档",
    ".sql": "SQL 脚本",
    ".bat": "Windows 批处理脚本",
    ".cmd": "Windows 批处理脚本",
    ".ps1": "PowerShell 脚本",
    ".exe": "Windows 可执行程序",
    ".dll": "动态链接库文件",
    ".jpg": "JPEG 图片",
    ".jpeg": "JPEG 图片",
    ".png": "PNG 图片",
    ".gif": "GIF 图片",
    ".bmp": "BMP 位图",
    ".svg": "SVG 矢量图",
    ".pdf": "PDF 文档",
    ".doc": "Word 文档",
    ".docx": "Word 文档",
    ".xls": "Excel 表格",
    ".xlsx": "Excel 表格",
    ".ppt": "PowerPoint 演示文稿",
    ".pptx": "PowerPoint 演示文稿",
    ".zip": "ZIP 压缩包",
    ".rar": "RAR 压缩包",
    ".7z": "7z 压缩包",
    ".mp3": "MP3 音频",
    ".wav": "WAV 音频",
    ".mp4": "MP4 视频",
    ".avi": "AVI 视频",
    ".tmp": "临时文件",
}


def get_file_type(path):
    """获取指定文件的文件类型（目录 / 常见扩展名分类 / MIME 类型）。"""
    if not os.path.exists(path):
        return f"错误：路径不存在：{path}"
    if os.path.isdir(path):
        return f"{path} 的类型：目录"
    if not os.path.isfile(path):
        return f"{path} 的类型：特殊文件（既不是普通文件也不是目录）"
    ext = os.path.splitext(path)[1].lower()
    desc = EXT_TYPES.get(ext)
    mime, _ = mimetypes.guess_type(path)
    if desc and mime:
        return f"{path} 的类型：{desc}（MIME：{mime}）"
    if desc:
        return f"{path} 的类型：{desc}"
    if mime:
        return f"{path} 的类型：{mime}"
    return f"{path} 的类型：未知（扩展名：{ext or '无扩展名'}）"


def edit_file(path, content, mode="overwrite"):
    """编辑指定文件的内容（仅支持纯文本格式文件）。"""
    if not os.path.isfile(path):
        return f"错误：文件不存在或不是普通文件：{path}"
    try:
        if mode == "append":
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
            return f"已追加内容到文件：{path}（新增 {len(content)} 个字符）"
        # 默认 overwrite：覆盖全文
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"已覆盖写入文件：{path}（共 {len(content)} 个字符）"
    except OSError as e:
        return f"错误：编辑文件失败：{e}"


def create_dir(path):
    """创建新目录（可创建多级）。"""
    if not path:
        return "错误：目录路径不能为空"
    if os.path.exists(path):
        return f"目录已存在：{path}"
    try:
        os.makedirs(path)
        return f"已创建目录：{path}"
    except OSError as e:
        return f"错误：创建目录失败：{e}"


def delete_dir(path):
    """删除目录（非空也会连同其中所有内容一并删除，不可恢复）。"""
    if not os.path.isdir(path):
        return f"错误：目录不存在或不是目录：{path}"
    try:
        shutil.rmtree(path)
        return f"已删除目录（含其中所有内容）：{path}"
    except OSError as e:
        return f"错误：删除目录失败：{e}"


def delete_file(path):
    """删除指定文件（不可恢复）。"""
    if not os.path.isfile(path):
        return f"错误：文件不存在或不是普通文件：{path}"
    try:
        os.remove(path)
        return f"已删除文件：{path}"
    except OSError as e:
        return f"错误：删除文件失败：{e}"


def rename(old_path, new_path):
    """重命名文件或目录。"""
    if not os.path.exists(old_path):
        return f"错误：原路径不存在：{old_path}"
    if os.path.exists(new_path):
        return f"错误：目标路径已存在：{new_path}"
    try:
        os.rename(old_path, new_path)
        return f"已重命名：{old_path} -> {new_path}"
    except OSError as e:
        return f"错误：重命名失败：{e}"


# 工具名 -> 实现函数的映射表
TOOL_IMPL = {
    "getDate": get_date,
    "isLeapYear": is_leap_year,
    "getCwd": get_cwd,
    "listDir": list_dir,
    "getFileType": get_file_type,
    "readFile": read_file,
    "createFile": create_file,
    "editFile": edit_file,
    "createDir": create_dir,
    "deleteDir": delete_dir,
    "deleteFile": delete_file,
    "rename": rename,
}


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


def main():
    print("=== DeepSeek 交互式聊天（支持 getDate / isLeapYear / 本地文件操作 function call）===")
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


if __name__ == "__main__":
    main()
