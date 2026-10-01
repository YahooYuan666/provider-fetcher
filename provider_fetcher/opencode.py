from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from .urlutil import normalize_base_url

OPENCODE_PATHS = {
    "items": [
        {
            "label": "Windows",
            "value": "%USERPROFILE%\\.config\\opencode\\opencode.json",
            "note": "即 C:\\Users\\<用户名>\\.config\\opencode\\opencode.json；设了 XDG_CONFIG_HOME 则以它为准",
        },
        {
            "label": "WSL",
            "value": "~/.config/opencode/opencode.json",
            "note": "WSL 内部路径；Windows 侧访问：\\\\wsl.localhost\\<发行版>\\home\\<用户名>\\.config\\opencode\\opencode.json，发行版名用 wsl -l 查看",
        },
        {
            "label": "macOS",
            "value": "~/.config/opencode/opencode.json",
            "note": "即 /Users/<用户名>/.config/opencode/opencode.json",
        },
    ],
    "tips": [
        "放在项目根目录的 opencode.json 会合并覆盖全局配置，只想给单个项目用时可以放那儿",
        "不想把密钥写进配置文件，可以改用 opencode auth login 存进 auth.json，然后把 options.apiKey 删掉",
    ],
}


def provider_slug(base_url: str) -> str:
    host = urlparse(base_url).netloc or base_url
    slug = re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")
    return slug or "custom-provider"


def _model_entry(row: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    model_id = str(row.get("id") or "").strip()
    if not model_id:
        return None
    entry: dict[str, Any] = {"name": str(row.get("display_name") or model_id)}
    context = row.get("context")
    output = row.get("max_output")
    # opencode schema 里 limit.context 和 limit.output 都是必填，缺一个就整体不写
    if isinstance(context, int) and isinstance(output, int) and context > 0 and output > 0:
        entry["limit"] = {"context": context, "output": output}
    if isinstance(row.get("reasoning_capable"), bool):
        entry["reasoning"] = row["reasoning_capable"]
    if isinstance(row.get("tool_call"), bool):
        entry["tool_call"] = row["tool_call"]
    field = row.get("interleaved_field")
    if isinstance(field, str) and field:
        entry["interleaved"] = {"field": field}
    # 推理强度档位：目录声明了 effort 档位才生成 variants。
    # 注意：OpenCode 2.0.20 只接受对象格式（数组格式会导致整个供应商被静默丢弃），
    # 且该版本尚不消费档位——升级到支持 variants 的版本后自动生效。
    levels = row.get("reasoning_levels")
    if isinstance(levels, list) and levels:
        entry["variants"] = {
            str(level): {"reasoningEffort": str(level)}
            for level in levels
            if isinstance(level, str) and level
        }
    return model_id, entry


def build_opencode_config(base_url: str, api_key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    base_url = normalize_base_url(str(base_url or ""))
    if not base_url:
        raise ValueError("BASE_URL_REQUIRED")
    slug = provider_slug(base_url)
    models: dict[str, Any] = {}
    first_chat: str | None = None
    for row in rows or []:
        if not isinstance(row, dict) or (row.get("kind") or "chat") != "chat":
            continue
        entry = _model_entry(row)
        if entry is None:
            continue
        model_id, entry_body = entry
        if model_id not in models:
            models[model_id] = entry_body
        if first_chat is None:
            first_chat = model_id

    options: dict[str, Any] = {"baseURL": base_url}
    key = str(api_key or "").strip()
    if key:
        options["apiKey"] = key
    else:
        options["apiKey"] = "{env:" + slug.upper().replace("-", "_") + "_API_KEY}"

    config: dict[str, Any] = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            slug: {
                "npm": "@ai-sdk/openai-compatible",
                "name": urlparse(base_url).netloc or slug,
                "options": options,
                "models": models,
            }
        },
    }
    if first_chat:
        config["model"] = f"{slug}/{first_chat}"
    return config
