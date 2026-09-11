from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from typing import Any

from .urlutil import models_url_candidates


def fetch_model_ids(base_url: str, api_key: str, timeout: int = 20) -> dict[str, Any]:
    key = (api_key or "").strip()
    if not key:
        raise ValueError("API_KEY_EMPTY")
    last_error = "MODELS_UNAVAILABLE"
    started = time.perf_counter()
    for url in models_url_candidates(base_url):
        try:
            body, status = _get_json(url, key, timeout)
        except Exception as exc:  # noqa: BLE001 - surface provider errors
            last_error = str(exc)
            continue
        if status == 401 or status == 403:
            raise ValueError(f"AUTH_FAILED:{status}")
        if not (200 <= status < 300):
            last_error = f"HTTP_{status}"
            continue
        models = parse_model_list(body)
        if models:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "url": url,
                "models": models,
                "latency_ms": latency_ms,
            }
        last_error = "MODELS_EMPTY"
    raise ValueError(last_error)


def parse_model_list(body: Any) -> list[dict[str, str]]:
    items: list[Any]
    if isinstance(body, list):
        items = body
    elif isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, list):
            items = data
        elif isinstance(body.get("models"), list):
            items = body["models"]
        else:
            items = []
    else:
        items = []

    seen: set[str] = set()
    models: list[dict[str, str]] = []
    for item in items:
        model_id = ""
        display_name = ""
        if isinstance(item, str):
            model_id = item.strip()
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("name") or "").strip()
            display_name = str(
                item.get("display_name") or item.get("displayName") or item.get("name") or ""
            ).strip()
            if display_name == model_id:
                display_name = ""
        if not model_id:
            continue
        key = model_id.lower()
        if key in seen:
            continue
        seen.add(key)
        models.append({"id": model_id, "display_name": display_name})
    return models


def _get_json(url: str, api_key: str, timeout: int) -> tuple[Any, int]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "provider-fetcher/0.1",
        },
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"error": raw[:300]}
        return body, status
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"MODELS_PARSE_FAILED:{exc}") from exc
    return body, status
