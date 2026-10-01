from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .ids import (
    CAPABILITY_TOKENS,
    collapse_minor_version,
    id_aliases,
    lookup_candidates,
    normalize_model_id,
    remainder_tokens_are_soft,
    strip_routing_suffixes,
)
from .paths import catalog_cache_path

CATALOG_URL = "https://models.dev/api.json"
OFFICIAL_PROVIDERS = (
    "xai",
    "openai",
    "anthropic",
    "google",
    "deepseek",
    "mistral",
    "groq",
    "meta",
    "cohere",
)
INPUT_MODALITIES = ("text", "image", "pdf", "video", "audio")
IMAGE_HINTS = ("image", "imagine-image", "dall-e", "gpt-image", "flux", "sdxl", "imagen")
VIDEO_HINTS = ("video", "imagine-video", "sora", "kling", "runway", "luma", "veo")


@dataclass
class CatalogHit:
    context: int | None
    max_output: int | None
    inputs: list[str]
    source: str
    catalog_id: str
    catalog_provider: str
    catalog_name: str
    kind: str
    matched: bool
    notes: list[str]
    structured_output: bool | None = None
    reasoning_capable: bool | None = None
    reasoning_levels: list[str] | None = None
    reasoning_budget_min: int | None = None
    interleaved_field: str | None = None
    tool_call: bool | None = None
    cost: dict[str, Any] | None = None
    status: str | None = None


class Catalog:
    def __init__(self, payload: dict[str, Any] | None = None, fetched_at: str | None = None):
        self.payload = payload or {}
        self.fetched_at = fetched_at
        self._index: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
        self._build_index()

    def _build_index(self) -> None:
        index: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
        for provider_id, provider in self.payload.items():
            if not isinstance(provider, dict):
                continue
            models = provider.get("models") or {}
            if not isinstance(models, dict):
                continue
            for model_id, model in models.items():
                if not isinstance(model, dict):
                    continue
                record = (provider_id, model_id, model)
                for alias in id_aliases(model_id) + id_aliases(str(model.get("id") or "")):
                    index.setdefault(alias, []).append(record)
        self._index = index

    @classmethod
    def load(cls, refresh: bool = False) -> "Catalog":
        cache = catalog_cache_path()
        if refresh:
            cls.refresh()
        if not cache.exists():
            return cls({}, None)
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return cls({}, None)
        payload = data.get("providers") if isinstance(data, dict) and "providers" in data else data
        fetched_at = data.get("fetched_at") if isinstance(data, dict) else None
        if not isinstance(payload, dict):
            payload = {}
        return cls(payload, fetched_at)

    @staticmethod
    def refresh() -> dict[str, Any]:
        request = urllib.request.Request(
            CATALOG_URL,
            headers={"User-Agent": "provider-fetcher/0.2"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("CATALOG_INVALID")
        envelope = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "providers": payload,
        }
        cache = catalog_cache_path()
        # 启动即刷新意味着查询可能与写缓存并发：先写临时文件再原子替换，
        # 避免别的线程读到写了一半的缓存。
        tmp = cache.with_name(cache.name + ".tmp")
        tmp.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, cache)
        return envelope

    def lookup(self, model_id: str, provider_hint: str | None = None) -> CatalogHit:
        notes: list[str] = []
        records = self._collect(model_id)
        chosen = _prefer(records, model_id, provider_hint)
        if not chosen:
            kind = infer_kind(model_id, [], [])
            return CatalogHit(
                context=None,
                max_output=None,
                inputs=["text"] if kind == "chat" else [],
                source="现场 ID，目录未收录",
                catalog_id="",
                catalog_provider="",
                catalog_name="",
                kind=kind,
                matched=False,
                notes=["目录未命中，上下文和最大输出请手填"],
                structured_output=None,
                reasoning_capable=None,
                reasoning_levels=[],
                reasoning_budget_min=None,
                interleaved_field=None,
                tool_call=None,
                cost=None,
                status=None,
            )

        provider_id, catalog_id, model = chosen
        if provider_id not in OFFICIAL_PROVIDERS and provider_id != provider_hint:
            notes.append("无官方实验室条目，使用中转副本")
        live_norm = normalize_model_id(model_id)
        catalog_norm = normalize_model_id(catalog_id)
        if live_norm != catalog_norm:
            notes.append(f"按 {catalog_id} 铰链")

        limits = model.get("limit") or {}
        context = _positive_int(limits.get("context"))
        max_output = _positive_int(limits.get("output"))
        modalities = model.get("modalities") or {}
        inputs = _clean_inputs(modalities.get("input") or [])
        outputs = _clean_inputs(modalities.get("output") or [])
        kind = infer_kind(model_id, inputs, outputs)
        if kind == "chat" and not inputs:
            inputs = ["text"]
        capable, levels, budget_min, inter_field = _reasoning_info(model)
        source = f"现场 ID + models.dev/{provider_id}"
        return CatalogHit(
            context=context,
            max_output=max_output,
            inputs=inputs,
            source=source,
            catalog_id=catalog_id,
            catalog_provider=provider_id,
            catalog_name=str(model.get("name") or catalog_id),
            kind=kind,
            matched=True,
            notes=notes,
            structured_output=_bool_or_none(model.get("structured_output")),
            reasoning_capable=capable,
            reasoning_levels=levels,
            reasoning_budget_min=budget_min,
            interleaved_field=inter_field,
            tool_call=_bool_or_none(model.get("tool_call")),
            cost=model.get("cost") if isinstance(model.get("cost"), dict) else None,
            status=str(model.get("status")) if model.get("status") else None,
        )

    def _collect(self, model_id: str) -> list[tuple[str, str, dict[str, Any]]]:
        seen: set[tuple[str, str]] = set()
        out: list[tuple[str, str, dict[str, Any]]] = []
        for alias in lookup_candidates(model_id):
            for record in self._index.get(alias, []):
                key = (record[0], record[1])
                if key not in seen:
                    seen.add(key)
                    out.append(record)
        return out


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _reasoning_info(model: dict[str, Any]) -> tuple[bool | None, list[str], int | None, str | None]:
    reasoning = model.get("reasoning")
    capable = reasoning if isinstance(reasoning, bool) else None
    levels: list[str] = []
    budget_min: int | None = None
    for option in model.get("reasoning_options") or []:
        if not isinstance(option, dict):
            continue
        if option.get("type") == "effort" and isinstance(option.get("values"), list):
            levels = [str(item) for item in option["values"] if isinstance(item, str)]
        elif option.get("type") == "budget_tokens":
            budget_min = _positive_int(option.get("min"))
    interleaved = model.get("interleaved")
    inter_field = None
    if isinstance(interleaved, dict):
        inter_field = str(interleaved.get("field") or "") or None
    return capable, levels, budget_min, inter_field


def infer_kind(model_id: str, inputs: list[str], outputs: list[str]) -> str:
    blob = normalize_model_id(model_id)
    out = set(outputs)
    if any(hint in blob for hint in VIDEO_HINTS) or "video" in out:
        return "video"
    if any(hint in blob for hint in IMAGE_HINTS) or "image" in out:
        return "image"
    return "chat"


def _prefer(
    records: list[tuple[str, str, dict[str, Any]]],
    model_id: str,
    provider_hint: str | None = None,
) -> tuple[str, str, dict[str, Any]] | None:
    scored = [(_score(record, model_id), record) for record in records]
    scored = [item for item in scored if item[0] > 0]
    if provider_hint:
        # 供应商提示（如 opencode.ai/zen 对应目录里的 opencode 官方镜像）压过一切副本
        scored = [
            (score + (200 if record[0] == provider_hint else 0), record)
            for score, record in scored
        ]
    if not scored:
        return None
    scored.sort(
        key=lambda item: (
            -item[0],
            0 if _has_limits(item[1][2]) else 1,
            0 if item[1][0] in OFFICIAL_PROVIDERS else 1,
            item[1][0],
            item[1][1],
        )
    )
    return scored[0][1]


def _short_id(model_id: str) -> str:
    text = normalize_model_id(model_id)
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def _score(record: tuple[str, str, dict[str, Any]], model_id: str) -> int:
    provider_id, catalog_id, _model = record
    live = _short_id(model_id)
    stripped = strip_routing_suffixes(live)
    collapsed = collapse_minor_version(stripped) or collapse_minor_version(live)
    catalog = _short_id(catalog_id)
    if not catalog:
        return 0

    live_tokens = set(stripped.split("-"))
    catalog_tokens = set(catalog.split("-"))
    extra_capabilities = (catalog_tokens - live_tokens) & CAPABILITY_TOKENS
    if extra_capabilities:
        return 0

    score = 0
    if provider_id in OFFICIAL_PROVIDERS:
        score += 100
    if catalog == live:
        score += 80
    elif catalog == stripped:
        score += 45
    elif collapsed and catalog == collapsed:
        score += 42
    elif catalog == f"{stripped}-preview":
        score += 40
    elif remainder_tokens_are_soft(stripped, catalog) or remainder_tokens_are_soft(live, catalog):
        score += 28
    elif collapsed and remainder_tokens_are_soft(collapsed, catalog):
        score += 24
    else:
        return 0
    if _has_limits(_model):
        score += 5
    score -= len(catalog)
    return score


def _has_limits(model: dict[str, Any]) -> bool:
    limits = model.get("limit") or {}
    return _positive_int(limits.get("context")) is not None or _positive_int(limits.get("output")) is not None


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _clean_inputs(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item).strip().lower()
        if text in INPUT_MODALITIES and text not in out:
            out.append(text)
    return out
