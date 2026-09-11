from __future__ import annotations

import json
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .catalog import Catalog
from .favorites import (
    get_favorite,
    public_favorite,
    public_favorites,
    remove_favorite,
    touch_favorite,
    upsert_credential,
)
from .service import bootstrap_state, fetch_and_enrich

WEB_DIR = Path(__file__).resolve().parent / "web"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self._json(200, bootstrap_state())
            return
        if parsed.path == "/api/favorites":
            self._json(200, {"items": public_favorites()})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        body = self._read_json()
        try:
            if parsed.path == "/api/fetch":
                result = fetch_and_enrich(str(body.get("base_url") or ""), str(body.get("api_key") or ""))
                self._json(200, result)
                return
            if parsed.path == "/api/catalog/refresh":
                Catalog.refresh()
                catalog = Catalog.load()
                self._json(200, {"ok": True, "catalog_fetched_at": catalog.fetched_at})
                return
            if parsed.path == "/api/favorites":
                items = upsert_credential(
                    str(body.get("base_url") or ""),
                    str(body.get("api_key") or ""),
                    str(body.get("label") or ""),
                    body.get("last_counts") if isinstance(body.get("last_counts"), dict) else None,
                )
                self._json(200, {"items": [public_favorite(item) for item in items]})
                return
            if parsed.path == "/api/favorites/refetch":
                favorite = get_favorite(str(body.get("id") or ""))
                result = fetch_and_enrich(str(favorite.get("base_url") or ""), str(favorite.get("api_key") or ""))
                items = touch_favorite(str(favorite.get("id") or ""), result.get("counts"))
                result["favorites"] = [public_favorite(item) for item in items]
                result["active_favorite_id"] = favorite.get("id")
                self._json(200, result)
                return
            if parsed.path == "/api/favorites/remove":
                items = remove_favorite(str(body.get("id") or ""))
                self._json(200, {"items": [public_favorite(item) for item in items]})
                return
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"ok": False, "error": str(exc)})
            return
        self._json(404, {"ok": False, "error": "NOT_FOUND"})

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


def _warm_catalog() -> None:
    if Catalog.load().fetched_at:
        return
    try:
        Catalog.refresh()
        print("知识库已在后台缓存完成。")
    except Exception as exc:  # noqa: BLE001
        print(f"知识库后台更新失败，可稍后在页面点击更新：{exc}")


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    if not WEB_DIR.exists():
        raise SystemExit(f"web assets missing: {WEB_DIR}")
    httpd = ThreadingHTTPServer((host, port), partial(Handler))
    url = f"http://{host}:{port}/"
    print(f"provider-fetcher {__version__}")
    print("请在浏览器里查询模型。如果浏览器没有自动打开，请访问：")
    print(f"  {url}")
    print("收藏和知识库缓存在本机用户目录，不会上传。按 Ctrl+C 结束。")
    threading.Thread(target=_warm_catalog, daemon=True).start()
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
