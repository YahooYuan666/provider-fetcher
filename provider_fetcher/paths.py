from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "provider-fetcher"


def user_data_dir() -> Path:
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(root) / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        root = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def catalog_cache_path() -> Path:
    return user_data_dir() / "models-dev-api.json"


def favorites_path() -> Path:
    return user_data_dir() / "favorites.json"


def last_fetch_path() -> Path:
    return user_data_dir() / "last-fetch.json"
