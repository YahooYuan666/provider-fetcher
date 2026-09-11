from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .paths import favorites_path, last_fetch_path
from .urlutil import normalize_base_url


def load_favorites() -> list[dict[str, Any]]:
    path = favorites_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [item for item in items if _is_credential(item)]


def save_favorites(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    envelope = {
        "updated_at": _now(),
        "items": items,
    }
    favorites_path().write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return items


def public_favorites() -> list[dict[str, Any]]:
    return [public_favorite(item) for item in load_favorites()]


def public_favorite(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry.get("id"),
        "base_url": entry.get("base_url"),
        "host": entry.get("host"),
        "label": entry.get("label") or entry.get("host") or entry.get("base_url"),
        "api_key_masked": mask_api_key(str(entry.get("api_key") or "")),
        "saved_at": entry.get("saved_at"),
        "last_fetched_at": entry.get("last_fetched_at"),
        "last_counts": entry.get("last_counts") or {},
    }


def mask_api_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return key[:1] + "…" + key[-1:]
    return key[:4] + "…" + key[-4:]


def upsert_credential(
    base_url: str,
    api_key: str,
    label: str = "",
    last_counts: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    normalized = normalize_base_url(base_url)
    key = (api_key or "").strip()
    if not key:
        raise ValueError("API_KEY_EMPTY")
    items = load_favorites()
    existing = next((item for item in items if _same_credential(item, normalized, key)), None)
    now = _now()
    if existing:
        existing["label"] = (label or existing.get("label") or urlparse(normalized).netloc).strip()
        existing["last_fetched_at"] = now
        if last_counts is not None:
            existing["last_counts"] = last_counts
        items = [existing] + [item for item in items if item.get("id") != existing.get("id")]
        return save_favorites(items)

    entry = {
        "id": str(uuid.uuid4()),
        "base_url": normalized,
        "host": urlparse(normalized).netloc,
        "label": (label or urlparse(normalized).netloc).strip(),
        "api_key": key,
        "saved_at": now,
        "last_fetched_at": now,
        "last_counts": last_counts or {},
    }
    items.insert(0, entry)
    return save_favorites(items)


def touch_favorite(favorite_id: str, last_counts: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    items = load_favorites()
    now = _now()
    for item in items:
        if item.get("id") == favorite_id:
            item["last_fetched_at"] = now
            if last_counts is not None:
                item["last_counts"] = last_counts
            break
    return save_favorites(items)


def find_credential(base_url: str, api_key: str) -> dict[str, Any] | None:
    normalized = normalize_base_url(base_url)
    key = (api_key or "").strip()
    if not key:
        return None
    return next((item for item in load_favorites() if _same_credential(item, normalized, key)), None)


def get_favorite(favorite_id: str) -> dict[str, Any]:
    for item in load_favorites():
        if item.get("id") == favorite_id:
            return item
    raise ValueError("FAVORITE_NOT_FOUND")


def remove_favorite(favorite_id: str) -> list[dict[str, Any]]:
    items = [item for item in load_favorites() if item.get("id") != favorite_id]
    return save_favorites(items)


def save_last_fetch(payload: dict[str, Any]) -> None:
    last_fetch_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_last_fetch() -> dict[str, Any] | None:
    path = last_fetch_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _is_credential(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and bool(str(item.get("base_url") or "").strip())
        and bool(str(item.get("api_key") or "").strip())
    )


def _same_credential(item: dict[str, Any], base_url: str, api_key: str) -> bool:
    return item.get("base_url") == base_url and item.get("api_key") == api_key


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
