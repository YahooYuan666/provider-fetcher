"""定位本机的 OpenCode 配置并安全写入（备份 + 原子替换 + 保留用户其它内容）。"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

CONFIG_DIR_NAME = "opencode"
CONFIG_FILE_NAMES = ("opencode.jsonc", "opencode.json")


def candidate_dirs() -> list[Path]:
    """按优先级列出候选配置目录：显式环境变量 > 用户主目录。"""
    home = Path.home()
    override = os.environ.get("OPENCODE_CONFIG_DIR")
    dirs: list[Path] = []
    if override:
        dirs.append(Path(override).expanduser())
    dirs.append(home / ".config" / CONFIG_DIR_NAME)
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            dirs.append(Path(appdata) / CONFIG_DIR_NAME)
        dirs.append(Path(os.environ.get("USERPROFILE", str(home))) / ".config" / CONFIG_DIR_NAME)
    return dirs


def resolve_config_path() -> tuple[Path, str]:
    """返回 (目标文件路径, 判定依据)。找不到就回退到主目录下的标准位置。"""
    override = os.environ.get("OPENCODE_CONFIG_DIR")
    for directory in candidate_dirs():
        if not directory.is_dir():
            continue
        for name in CONFIG_FILE_NAMES:
            candidate = directory / name
            if candidate.exists():
                basis = "OPENCODE_CONFIG_DIR 环境变量" if override and directory == Path(override).expanduser() else "已有配置目录"
                return candidate, basis
    target_dir = candidate_dirs()[0] if override else Path.home() / ".config" / CONFIG_DIR_NAME
    return target_dir / CONFIG_FILE_NAMES[0], "按标准位置新建（目录不存在时会创建）"


def _strip_jsonc(text: str) -> str:
    """去掉 // 行注释与 /* */ 块注释，保留字符串内容。"""
    out: list[str] = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def load_jsonc(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(_strip_jsonc(text) or "{}")
    return data if isinstance(data, dict) else {}


def _skip_trivia(text: str, i: int) -> int:
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in " \t\r\n,":
            i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
        else:
            break
    return i


def _value_end(text: str, start: int) -> int:
    """返回从 start 开始的 JSON 值结束位置（不含其后分隔符）。

    标量（字符串/数字/布尔/null）就地结束；对象/数组按括号配平。
    """
    n = len(text)
    i = start
    while i < n and text[i] in " \t\r\n":
        i += 1
    if i >= n:
        return n
    ch = text[i]
    if ch == '"':
        i += 1
        while i < n:
            if text[i] == "\\":
                i += 2
                continue
            if text[i] == '"':
                return i + 1
            i += 1
        return n
    if ch not in "{[":
        # 数字 / true / false / null：到分隔符为止
        while i < n and text[i] not in ",}]\n\r":
            i += 1
        return i
    depth = 0
    while i < n:
        ch = text[i]
        if ch == '"':
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
            i += 1
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def provider_span(text: str) -> tuple[int, int] | None:
    """定位顶层 "provider" 键的取值区间 [start, end)，跳过注释与字符串。"""
    n = len(text)
    i = 0
    depth = 0
    while i < n:
        ch = text[i]
        # 注释先判
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        if ch == '"':
            key_start = i
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
            key = text[key_start + 1 : i]
            i += 1
            if depth == 1:
                j = _skip_trivia(text, i)
                if j < n and text[j] == ":":
                    vs = _skip_trivia(text, j + 1)
                    ve = _value_end(text, vs)
                    if key == "provider":
                        return (vs, ve)
                    i = ve
                    continue
                i = j
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return None
        i += 1
    return None


def _render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def splice_provider(text: str, providers: dict[str, Any]) -> str:
    """只替换顶层 provider 段，其余内容（含注释）逐字节保留。"""
    block = json.dumps(providers, ensure_ascii=False, indent=2)
    block = "\n".join("  " + line for line in block.splitlines())
    span = provider_span(text)
    if span:
        start, end = span
        return text[:start] + block + text[end:]
    # 没有 provider 段：定位根对象收尾的 "}"（最后一个让 depth 归零的位置）
    close = _root_close_index(text)
    if close < 0:
        return text
    head = text[:close].rstrip()
    tail = text[close:]
    separator = "\n" if not head.endswith("\n") else ""
    return f"{head}{separator},\n  \"provider\": {block}\n{tail}"


def _root_close_index(text: str) -> int:
    """根对象最后一个 "}" 的下标（跳过注释与字符串）。"""
    n = len(text)
    i = 0
    depth = 0
    last = -1
    while i < n:
        ch = text[i]
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        if ch == '"':
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
            i += 1
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0 and ch == "}":
                last = i
        i += 1
    return last


def write_config(
    config: dict[str, Any],
    path: Path | None = None,
    provider_id: str | None = None,
) -> dict[str, Any]:
    """把导出的 provider 合并进本机 OpenCode 配置。

    - 已存在：文本级替换 provider 段，用户其它内容与注释逐字节保留
    - 写入前按时间戳备份，随后用「同目录临时文件 + rename」原子替换
    """
    resolved, basis = resolve_config_path() if path is None else (path, "指定路径")
    providers = config.get("provider") or {}
    if provider_id is None:
        provider_id = next(iter(providers), None)
    if not provider_id or provider_id not in providers:
        raise ValueError("CONFIG_PROVIDER_ID_MISSING")

    if resolved.exists():
        original = resolved.read_text(encoding="utf-8")
        doc = load_jsonc(resolved)
        existing = doc.get("provider") if isinstance(doc.get("provider"), dict) else {}
        existed = provider_id in existing
        # 同名 provider 整体替换（不与旧内容合并），其余 provider 原样保留
        merged = {pid: item for pid, item in existing.items() if pid != provider_id}
        merged[provider_id] = providers[provider_id]
        action = "替换同名 provider" if existed else "并入已有 provider 段"
        text = splice_provider(original, merged)
        existed = True
    else:
        doc = dict(config)
        doc.setdefault("$schema", "https://opencode.ai/config.json")
        action = "新建配置文件"
        text = _render(doc)
        existed = False

    resolved.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if existed:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = resolved.with_name(f"{resolved.name}.bak-{stamp}")
        backup.write_text(original, encoding="utf-8")

    tmp = resolved.with_name(f"{resolved.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, resolved)
    return {
        "path": str(resolved),
        "basis": basis,
        "action": action,
        "backup": str(backup) if backup else "",
        "provider_id": provider_id,
        "existed": existed,
    }


def preview(config: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """写入前预览：目标路径、依据、将执行的动作，不落盘。"""
    resolved, basis = resolve_config_path() if path is None else (path, "指定路径")
    exists = resolved.exists()
    return {
        "path": str(resolved),
        "basis": basis,
        "existed": exists,
        "action": "替换/并入 provider 段" if exists else "新建配置文件",
        "backup": "写入前会在同目录留一份 .bak-时间戳" if exists else "",
    }