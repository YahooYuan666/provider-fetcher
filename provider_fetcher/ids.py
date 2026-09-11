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


def normalize_model_id(model_id: str) -> str:
    text = (model_id or "").strip().lower().replace("_", "-")
    text = re.sub(r"-+", "-", text).strip("-")
    return text


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
    text = normalize_model_id(model_id)
    if not text:
        return ""
    parts = text.split("-")
    while len(parts) > 1:
        if parts[-1] in ROUTING_SUFFIXES or parts[-1] in VARIANT_SUFFIXES:
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
    stripped = strip_routing_suffixes(model_id)
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
        return False
    return True


def tokens(model_id: str) -> list[str]:
    return [part for part in _SPLIT.split(normalize_model_id(model_id)) if part]
