from __future__ import annotations

from urllib.parse import urlparse, urlunparse


CHAT_SUFFIXES = (
    "/chat/completions",
    "/responses",
    "/messages",
    "/completions",
)


def normalize_base_url(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError("BASE_URL_EMPTY")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("BASE_URL_INVALID")
    path = parsed.path.rstrip("/") or ""
    lower = path.lower()
    for suffix in CHAT_SUFFIXES:
        if lower.endswith(suffix):
            path = path[: -len(suffix)]
            break
    path = path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")).rstrip("/")


def models_url_candidates(raw: str) -> list[str]:
    base = normalize_base_url(raw)
    parsed = urlparse(base)
    path = parsed.path.rstrip("/")
    tail = path.rsplit("/", 1)[-1] if path else ""
    if tail.lower() in {"model", "models"}:
        return [_join(parsed, path)]

    versioned = (
        len(tail) > 1
        and tail[0] in {"v", "V"}
        and tail[1:].isdigit()
    )
    if not path:
        return [_join(parsed, "/v1/models"), _join(parsed, "/models")]
    if versioned:
        return [_join(parsed, f"{path}/models")]
    return [
        _join(parsed, f"{path}/v1/models"),
        _join(parsed, f"{path}/models"),
    ]


def _join(parsed, path: str) -> str:
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
