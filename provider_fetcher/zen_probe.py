from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .urlutil import normalize_base_url

USER_AGENT = "provider-fetcher/0.2 (zen availability probe)"
REQUEST_TIMEOUT = 45
REQUEST_GAP_SECONDS = 3.0
MAX_PROBES = 40

# status -> (中文标签, 是否外部可直接调用)
STATUS_META = {
    "ok": ("外部可调用", True),
    "client_only": ("仅限 OpenCode 客户端", False),
    "unavailable": ("上游已下架", False),
    "auth": ("需要有效 API Key", False),
    "error": ("服务端错误", False),
    "unknown": ("结果不明", False),
}


def classify(status_code: int, message: str) -> str:
    text = (message or "").lower()
    if status_code == 200:
        return "ok"
    if "free tier can only be used" in text:
        return "client_only"
    if "model is unavailable" in text or "modelnotfound" in text or "model not found" in text:
        return "unavailable"
    if "missing api key" in text or ("invalid" in text and "key" in text):
        return "auth"
    if status_code in (401, 403):
        return "auth"
    if status_code >= 500:
        return "error"
    if status_code == 404:
        return "unavailable"
    return "unknown"


def load_report() -> dict[str, Any]:
    from .paths import zen_probe_path

    path = zen_probe_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _probe_once(base_url: str, api_key: str, model_id: str) -> tuple[str, str]:
    body = json.dumps(
        {
            "model": model_id,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            response.read()
        return "ok", ""
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        message = raw
        try:
            parsed = json.loads(raw)
            error = parsed.get("error")
            if isinstance(error, dict):
                message = str(error.get("message") or error)
            elif error:
                message = str(error)
        except json.JSONDecodeError:
            pass
        return classify(exc.code, message), message[:200]
    except Exception as exc:  # noqa: BLE001 - 单个模型探测失败不应中断整批
        return "unknown", str(exc)[:200]


def probe_models(
    base_url: str,
    api_key: str,
    models: list[str],
    delay: float = REQUEST_GAP_SECONDS,
) -> dict[str, Any]:
    """逐个发一次 1-token 请求，回答“这个模型能否在本工具/外部直接调用”。

    与免费标记无关：免费标记来自目录的 isFree + status，被动且稳定；
    实测只补充“外部能否直连”这类只有发请求才知道的信息（例如 Zen 的
    免费档限制为只能在 OpenCode 客户端内部使用）。
    """
    base_url = normalize_base_url(str(base_url or ""))
    if not base_url:
        raise ValueError("BASE_URL_REQUIRED")
    targets = [m.strip() for m in models if isinstance(m, str) and m.strip()][:MAX_PROBES]
    results: dict[str, Any] = {}
    for index, model_id in enumerate(targets, start=1):
        status, message = _probe_once(base_url, str(api_key or ""), model_id)
        label, usable = STATUS_META[status]
        results[model_id] = {"status": status, "label": label, "usable": usable, "message": message}
        if index < len(targets):
            time.sleep(delay)
    return {
        "base_url": base_url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "probed": len(results),
        "results": results,
    }
