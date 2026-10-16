"""不用框架手写的最小 agent loop：两个工具、轮次与 token 上限、工具错误以 is_error 回传。

用法：
    python agent.py "统计 data.csv 有多少行" --workdir ./sandbox
    python agent.py "..." --yes --transcript run.transcript.json
"""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

MODEL = "claude-haiku-5-5"  # 学习用，选最便宜的当前一代模型
MAX_OUTPUT_CHARS = 10_000  # 工具结果截断长度，防止一次读入超大文件撑爆上下文

TOOLS = [
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file inside the working directory. "
        "Takes a path relative to the working directory. Output longer than "
        f"{MAX_OUTPUT_CHARS} characters is truncated.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path, e.g. data/notes.txt"}},
            "required": ["path"],
        },
    },
    {
        "name": "run_python",
        "description": "Run a Python script with the working directory as cwd and return stdout and stderr. "
        "Each call is a fresh process; nothing persists between calls except files written to disk. "
        "Times out after 30 seconds.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Complete Python source to execute"}},
            "required": ["code"],
        },
    },
]
READ_ONLY_TOOLS = {"read_file"}  # 只读工具可以并行；有副作用的工具串行执行


class ToolError(Exception):
    """工具执行失败。消息会作为 is_error 的 tool_result 回给模型，所以要写清下一步怎么做。"""


def truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n... [truncated, {len(text) - MAX_OUTPUT_CHARS} more characters]"


def read_file(workdir: Path, path: str) -> str:
    target = (workdir / path).resolve()
    if not target.is_relative_to(workdir):
        raise ToolError(f"Path {path!r} is outside the working directory. Use a relative path inside it.")
    if not target.is_file():
        raise ToolError(f"File {path!r} does not exist. Use run_python to list files, e.g. os.listdir('.').")
    try:
        return truncate(target.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        raise ToolError(f"File {path!r} is not UTF-8 text.") from None


def run_python(workdir: Path, code: str, auto_approve: bool) -> str:
    # 注意：这里没有沙箱。脚本能读写本机任何当前用户可访问的文件，所以默认每次都让人确认。
    if not auto_approve:
        print(f"\n--- run_python 将执行 ---\n{code}\n-----------------------", file=sys.stderr)
        if input("允许执行？[y/N] ").strip().lower() != "y":
            raise ToolError("The user declined to run this code. Ask what they want instead of retrying it.")
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code], cwd=workdir, capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        raise ToolError("Script timed out after 30 seconds. Make it faster or process less data.") from None
    output = f"exit code: {proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    if proc.returncode != 0:
        raise ToolError(truncate(output))
    return truncate(output)


def execute(block, workdir: Path, auto_approve: bool) -> dict:
    """执行一个 tool_use 块，任何失败都转换成 is_error 的 tool_result，而不是让 loop 崩溃。"""
    result = {"type": "tool_result", "tool_use_id": block.id}
    try:
        if block.name == "read_file":
            content = read_file(workdir, require_str(block.input, "path"))
        elif block.name == "run_python":
            content = run_python(workdir, require_str(block.input, "code"), auto_approve)
        else:
            raise ToolError(f"Unknown tool {block.name!r}. Available tools: read_file, run_python.")
        result["content"] = content
    except ToolError as e:
        result["content"] = str(e)
        result["is_error"] = True
    print(f"  <- {block.name}{' [error]' if result.get('is_error') else ''}: {result['content'][:200]!r}", file=sys.stderr)
    return result


def require_str(tool_input: dict, key: str) -> str:
    # schema 合法不等于参数可用，harness 自己再校验一次
    value = tool_input.get(key)
    if not isinstance(value, str) or not value:
        raise ToolError(f"Missing or empty string argument {key!r}.")
    return value


def run_tools(blocks: list, workdir: Path, auto_approve: bool) -> list[dict]:
    """只读工具并发执行，其余按原顺序串行；结果按 tool_use 的原顺序放进同一条 user 消息。"""
    results: dict[str, dict] = {}
    read_only = [b for b in blocks if b.name in READ_ONLY_TOOLS]
    with ThreadPoolExecutor() as pool:
        for block, result in zip(read_only, pool.map(lambda b: execute(b, workdir, auto_approve), read_only)):
            results[block.id] = result
    for block in blocks:
        if block.name not in READ_ONLY_TOOLS:
            results[block.id] = execute(block, workdir, auto_approve)
    return [results[b.id] for b in blocks]


def agent_loop(task: str, workdir: Path, max_turns: int, token_budget: int, auto_approve: bool, transcript: Path | None):
    client = anthropic.Anthropic()  # 从环境变量 ANTHROPIC_API_KEY 等读取凭据
    system = (
        f"You are a careful assistant working in the directory {workdir}. "
        "Use the tools to inspect files and run Python when that helps; answer concisely once you are done."
    )
    messages = [{"role": "user", "content": task}]
    used_tokens = 0
    stop = "max_turns"
    try:
        for turn in range(1, max_turns + 1):
            response = client.messages.create(
                model=MODEL,
                max_tokens=16_000,
                system=system,
                tools=TOOLS,
                messages=messages,
                output_config={"effort": "medium"},
            )
            used_tokens += response.usage.input_tokens + response.usage.output_tokens
            print(
                f"[turn {turn}] stop_reason={response.stop_reason} "
                f"in={response.usage.input_tokens} out={response.usage.output_tokens} total={used_tokens}",
                file=sys.stderr,
            )
            # 整个 content 原样追加：thinking 块必须原样回传给同一个模型
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                stop = response.stop_reason
                if stop == "refusal" and response.stop_details:
                    print(f"refusal: {response.stop_details.category}", file=sys.stderr)
                break
            if used_tokens >= token_budget:
                stop = "token_budget"
                break

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            for b in tool_uses:
                print(f"  -> {b.name}({json.dumps(b.input, ensure_ascii=False)[:200]})", file=sys.stderr)
            messages.append({"role": "user", "content": run_tools(tool_uses, workdir, auto_approve)})
    finally:
        if transcript:
            transcript.write_text(
                json.dumps(messages, ensure_ascii=False, indent=2, default=lambda o: o.to_dict()), encoding="utf-8"
            )

    final = messages[-1]
    text = "".join(b.text for b in final["content"] if b.type == "text") if final["role"] == "assistant" else ""
    return text, stop, turn, used_tokens


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task")
    parser.add_argument("--workdir", type=Path, default=Path.cwd())
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--token-budget", type=int, default=200_000, help="累计 input+output token 上限")
    parser.add_argument("--yes", action="store_true", help="run_python 不再逐次确认（没有沙箱，慎用）")
    parser.add_argument("--transcript", type=Path, help="把完整 messages 写成 JSON，便于复盘")
    args = parser.parse_args()

    text, stop, turns, tokens = agent_loop(
        args.task, args.workdir.resolve(), args.max_turns, args.token_budget, args.yes, args.transcript
    )
    print(text)
    print(f"\n[stop={stop} turns={turns} tokens={tokens}]", file=sys.stderr)


if __name__ == "__main__":
    main()
