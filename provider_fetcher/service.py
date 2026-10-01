from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .catalog import Catalog, CatalogHit
from .favorites import find_credential, load_last_fetch, public_favorites, save_last_fetch
from .fetch import fetch_model_ids
from .urlutil import normalize_base_url
from .zen_probe import load_report

API_FORMAT_HINT = "建议先尝试 Responses（/responses）；不通再改 Chat Completions 或 Anthropic Messages"


def _provider_hint(base_url: str) -> str | None:
    host = urlparse(base_url).netloc.lower()
    return "opencode" if "opencode.ai" in host else None


def _context_points(context: Any) -> int:
    if not isinstance(context, int) or context <= 0:
        return 0
    for threshold, points in ((1_000_000, 40), (400_000, 34), (200_000, 28), (128_000, 22), (32_000, 12)):
        if context >= threshold:
            return points
    return 6


def _output_points(output: Any) -> int:
    if not isinstance(output, int) or output <= 0:
        return 0
    for threshold, points in ((256_000, 20), (128_000, 16), (64_000, 12), (32_000, 8)):
        if output >= threshold:
            return points
    return 4


def _reasoning_points(hit: CatalogHit) -> int:
    if hit.reasoning_capable is not True:
        return 0
    levels = hit.reasoning_levels or []
    if any(level in ("max", "xhigh") for level in levels):
        return 15
    if len(levels) >= 3:
        return 10
    return 5


SCORE_MAX = 100


def _spec_breakdown(hit: CatalogHit) -> dict[str, int]:
    """规格参考分的逐项明细。

    这不是模型能力评分——没有任何社区榜单或实测基准支撑，只把目录里
    已经写明的参数规格（窗口大小、输出上限、推理档位等）按固定权重折算，
    方便横向对照"纸面配置"。权重是本工具自行设定的，不是行业标准。
    """
    return {
        "context": _context_points(hit.context),
        "output": _output_points(hit.max_output),
        "reasoning": _reasoning_points(hit),
        "tool_call": 15 if hit.tool_call is True else 0,
        "modalities": min(6, 2 * max(0, len(hit.inputs) - 1)),
        "structured": 4 if hit.structured_output is True else 0,
    }


def _model_score(hit: CatalogHit) -> int:
    return sum(_spec_breakdown(hit).values())


def _is_free(hit: CatalogHit, model_id: str) -> bool:
    """与 OpenCode 桌面版一致：opencode 供应商 + （无 cost 或 cost.input 为 0），且目录未标记废弃。

    - isFree 规则逐字取自 opencode 源码 packages/app/src/components/dialog-select-model.tsx：
      `provider === "opencode" && (!cost || cost.input === 0)`。
    - 再排除 `status == "deprecated"`：Zen 已下架的条目仍留在 models.dev 与公开 /models 里，
      但桌面版不会列出（实测该过滤后与桌面版当前免费名单完全一致）。
    """
    if hit.catalog_provider != "opencode":
        return False
    if hit.status == "deprecated":
        return False
    cost = hit.cost
    return not cost or cost.get("input") == 0


def enrich_models(base_url: str, models: list[dict[str, str]], catalog: Catalog) -> list[dict[str, Any]]:
    hint = _provider_hint(base_url)
    rows: list[dict[str, Any]] = []
    for model in models:
        model_id = model["id"]
        hit = catalog.lookup(model_id, provider_hint=hint)
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
                "structured_output": hit.structured_output,
                "reasoning_capable": hit.reasoning_capable,
                "reasoning_levels": hit.reasoning_levels,
                "reasoning_budget_min": hit.reasoning_budget_min,
                "interleaved_field": hit.interleaved_field,
                "tool_call": hit.tool_call,
                "free": _is_free(hit, model_id),
                "spec_score": _model_score(hit),
                "spec_breakdown": _spec_breakdown(hit),
                "catalog_provider": hit.catalog_provider,
                "catalog_id": hit.catalog_id,
                "base_url": base_url,
            }
        )
    kind_rank = {"chat": 0, "image": 1, "video": 2}
    rows.sort(
        key=lambda row: (
            kind_rank.get(row["kind"], 9),
            not row["free"],
            -row["spec_score"],
            row["id"].lower(),
        )
    )
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
        "zen_probe": load_report(),
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
