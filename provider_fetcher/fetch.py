from __future__ import annotations

import ipaddress
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

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


BLOCKED_TARGET_HOSTS = frozenset({"169.254.169.254", "metadata.google.internal"})


def _private_targets_allowed() -> bool:
    """是否允许回环/内网目标。

    本工具的用途就是查询用户自填的 Base URL，本地网关（127.0.0.1:7863 之类）
    是常见且正当的场景，因此默认允许；设为 0 可收紧为只允许公网地址。
    """
    return os.environ.get("PROVIDER_FETCHER_ALLOW_PRIVATE", "1") != "0"


def safe_target(url: str) -> str:
    """出站白名单：协议、主机白名单与解析后 IP 边界校验，返回校验过的 URL。

    云元数据地址无条件拒绝；环回/私网地址取决于 _private_targets_allowed()。
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("TARGET_SCHEME_BLOCKED")
    host = (parsed.hostname or "").lower()
    if host in BLOCKED_TARGET_HOSTS:
        raise ValueError("TARGET_HOST_BLOCKED")
    if _private_targets_allowed():
        return url
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        # 解析失败交给请求阶段报错，这里不因解析问题放过未知地址
        return url
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip in ipaddress.ip_network("198.18.0.0/15"):
            continue  # 本地代理 fake-ip 占位解析，不是真实内网目标
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError("TARGET_IP_BLOCKED")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """跟随 302 可能被带到内网地址，这里直接拒绝跳转。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _get_json(url: str, api_key: str, timeout: int) -> tuple[Any, int]:
    target = safe_target(url)
    request = urllib.request.Request(
        target,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "provider-fetcher/0.2",
        },
    )
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=context))
    try:
        with opener.open(request, timeout=timeout) as response:
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
