from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .catalog import Catalog
from .favorites import find_credential, load_last_fetch, public_favorites, save_last_fetch
from .fetch import fetch_model_ids
from .urlutil import normalize_base_url

API_FORMAT_HINT = "建议先尝试 Responses（/responses）；不通再改 Chat Completions 或 Anthropic Messages"


def enrich_models(base_url: str, models: list[dict[str, str]], catalog: Catalog) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in models:
        model_id = model["id"]
        hit = catalog.lookup(model_id)
        rows.append(
            {
                "id": model_id,
                "display_name": model.get("display_name") or hit.catalog_name or model_id,
                "context": hit.context,
                "max_output": hit.max_output,
                "inputs": hit.inputs,
                "source": hit.source,
                "kind": hit.kind,
                "matched": hit.matched,
                "notes": hit.notes,
                "catalog_provider": hit.catalog_provider,
                "catalog_id": hit.catalog_id,
                "base_url": base_url,
            }
        )
    kind_rank = {"chat": 0, "image": 1, "video": 2}
    rows.sort(key=lambda row: (kind_rank.get(row["kind"], 9), row["id"].lower()))
    return rows


def fetch_and_enrich(base_url: str, api_key: str, catalog: Catalog | None = None) -> dict[str, Any]:
    normalized = normalize_base_url(base_url)
    catalog = catalog or Catalog.load()
    fetched = fetch_model_ids(normalized, api_key)
    rows = enrich_models(normalized, fetched["models"], catalog)
    already_saved = find_credential(normalized, api_key) is not None
    result = {
        "ok": True,
        "base_url": normalized,
        "host": urlparse(normalized).netloc,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "models_url": fetched["url"],
        "latency_ms": fetched["latency_ms"],
        "api_format_hint": API_FORMAT_HINT,
        "catalog_fetched_at": catalog.fetched_at,
        "counts": _counts(rows),
        "models": rows,
        "already_saved": already_saved,
        "suggest_save": not already_saved,
    }
    save_last_fetch(
        {
            "base_url": normalized,
            "fetched_at": result["fetched_at"],
            "models_url": fetched["url"],
            "counts": result["counts"],
            "models": rows,
        }
    )
    return result


def bootstrap_state() -> dict[str, Any]:
    catalog = Catalog.load()
    last = load_last_fetch()
    return {
        "api_format_hint": API_FORMAT_HINT,
        "catalog_fetched_at": catalog.fetched_at,
        "favorites": public_favorites(),
        "last_fetch": last,
    }


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"all": len(rows), "chat": 0, "image": 0, "video": 0, "matched": 0}
    for row in rows:
        kind = row.get("kind") or "chat"
        if kind in counts:
            counts[kind] += 1
        if row.get("matched"):
            counts["matched"] += 1
    return counts
