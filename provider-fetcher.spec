# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)
hidden = collect_submodules("provider_fetcher")

a = Analysis(
    [str(ROOT / "provider_fetcher" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "provider_fetcher" / "web"), "provider_fetcher/web")],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ProviderFetcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="provider-fetcher-portable",
)
