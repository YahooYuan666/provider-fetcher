from __future__ import annotations

import re

_SPLIT = re.compile(r"[^a-z0-9]+")
ROUTING_SUFFIXES = {
    "high",
    "low",
    "medium",
    "min",
    "max",
    "xhigh",
    "tiered",
    "thinking",
    "think",
    "reasoning",
    "nonreasoning",
    "fast",
    "preview",
    "latest",
    "turbo",
    "experimental",
}
ROUTING_COMPOUND_SUFFIXES = {
    "non-reasoning",
}
VARIANT_SUFFIXES = {
    "flare",
    "sunburst",
    "quality",
    "spark",
}
CAPABILITY_TOKENS = {
    "image",
    "video",
    "tts",
    "lite",
    "live",
    "audio",
    "embedding",
}
PRODUCT_TOKENS = {
    "image",
    "imagine",
    "flash",
    "codex",
    "video",
    "audio",
    "composer",
    "tts",
}

# 中转网关常见的命名空间前缀（路由/线路/供应商），匹配目录前可尝试剥掉。
# 保守做法：只作为额外候选交给评分机制裁决，匹配不上仍保留原始 ID。
PREFIX_MARKERS = ("global", "cn", "auto", "zai", "tdpsk", "zaicoding", "openclaw", "default")


def normalize_model_id(model_id: str) -> str:
    text = (model_id or "").strip().lower().replace("_", "-")
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def strip_namespace_prefix(model_id: str) -> str:
    """剥掉中转网关的命名空间前缀，返回可尝试匹配的裸模型名。

    处理三类写法：
    - `cn:glm-5.3`（冒号路由命名空间）
    - `global/zai_auto`（斜杠命名空间，取最后一段后再剥供应商前缀）
    - `tdpsk_deepseek-v4-pro-202606`（下划线供应商前缀）

    无法判定时返回空字符串，调用方据此跳过。
    """
    text = (model_id or "").strip()
    if not text:
        return ""
    # 冒号命名空间：cn:xxx
    if ":" in text:
        head, _, tail = text.partition(":")
        if head.strip().lower() in PREFIX_MARKERS and tail.strip():
            return tail.strip()
        return ""
    # 斜杠命名空间：取最后一段
    if "/" in text:
        text = text.rsplit("/", 1)[-1].strip()
        if not text:
            return ""
    # 下划线供应商前缀：只剥一次，且剥完必须还像模型名（含产品词或版本号）
    if "_" in text:
        head, _, tail = text.partition("_")
        if head.strip().lower() in PREFIX_MARKERS and tail.strip():
            text = tail.strip()
    normalized = normalize_model_id(text)
    if not normalized or normalized == normalize_model_id(model_id):
        return ""
    parts = normalized.split("-")
    if not any(part in PRODUCT_TOKENS for part in parts) and not any(
        re.fullmatch(r"\d+(\.\d+)?", part) for part in parts
    ):
        # 剥完不像模型名（如 auto），不冒险
        return ""
    return normalized


def id_aliases(model_id: str) -> list[str]:
    raw = (model_id or "").strip()
    if not raw:
        return []
    aliases = [raw, raw.lower(), normalize_model_id(raw)]
    if "/" in raw:
        tail = raw.rsplit("/", 1)[-1]
        aliases.extend([tail, tail.lower(), normalize_model_id(tail)])
    seen: set[str] = set()
    out: list[str] = []
    for item in aliases:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def strip_routing_suffixes(model_id: str) -> str:
    text = (model_id or "").strip().lower()
    if not text:
        return ""
    parts = text.split("-")
    while len(parts) > 1:
        if parts[-1] in ROUTING_SUFFIXES or parts[-1] in VARIANT_SUFFIXES:
            parts.pop()
            continue
        # 网关线路日期戳（-202605 / -202606）
        if re.fullmatch(r"20\d{4}", parts[-1]):
            parts.pop()
            continue
        if len(parts) >= 2 and f"{parts[-2]}-{parts[-1]}" in ROUTING_COMPOUND_SUFFIXES:
            parts = parts[:-2]
            continue
        break
    return "-".join(parts)


def collapse_minor_version(model_id: str) -> str:
    text = normalize_model_id(model_id)
    parts = text.split("-")
    if not any(part in PRODUCT_TOKENS for part in parts):
        return ""
    changed = False
    collapsed: list[str] = []
    seen_product = False
    for part in parts:
        if part in PRODUCT_TOKENS:
            seen_product = True
        if seen_product and re.fullmatch(r"\d+\.\d+", part):
            collapsed.append(part.split(".", 1)[0])
            changed = True
        else:
            collapsed.append(part)
    if not changed:
        return ""
    return "-".join(collapsed)


def lookup_candidates(model_id: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def add(value: str) -> None:
        text = (value or "").strip()
        if not text:
            return
        for alias in id_aliases(text):
            if alias not in seen:
                seen.add(alias)
                out.append(alias)

    add(model_id)
    # 中转命名空间前缀（cn: / global/ / vendor_）剥掉后的裸名
    bare = strip_namespace_prefix(model_id)
    if bare:
        add(bare)
    stripped = strip_routing_suffixes(bare or model_id)
    add(stripped)
    if stripped and not stripped.endswith("-preview"):
        add(f"{stripped}-preview")
    collapsed = collapse_minor_version(stripped or model_id)
    add(collapsed)
    add(strip_routing_suffixes(collapsed))
    return out


def remainder_tokens_are_soft(live_id: str, catalog_id: str) -> bool:
    live = normalize_model_id(live_id)
    catalog = normalize_model_id(catalog_id)
    if not catalog or live == catalog:
        return True
    if not live.startswith(f"{catalog}-"):
        return False
    remainder = live[len(catalog) + 1 :]
    if not remainder:
        return True
    parts = remainder.split("-")
    soft = ROUTING_SUFFIXES | VARIANT_SUFFIXES
    for part in parts:
        if part in soft:
            continue
        if re.fullmatch(r"\d+(\.\d+)?", part):
            continue
        if re.fullmatch(r"20\d{4}", part):  # 网关线路日期戳
            continue
        return False
    return True


def tokens(model_id: str) -> list[str]:
    return [part for part in _SPLIT.split(normalize_model_id(model_id)) if part]
