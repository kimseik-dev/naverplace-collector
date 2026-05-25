# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — 네이버 플레이스 수집기 단일 실행파일 빌드

빌드:
    Mac:     .venv/bin/pyinstaller naverplace.spec --clean --noconfirm
    Windows: .venv\\Scripts\\pyinstaller naverplace.spec --clean --noconfirm

결과:
    dist/NaverPlace        (Mac/Linux 실행파일)
    dist/NaverPlace.app    (Mac 번들)
    dist/NaverPlace.exe    (Windows)
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

block_cipher = None

# ── 경로 설정 ─────────────────────────────────────────────────
PROJECT_ROOT = Path(SPECPATH).resolve()
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"


# ── Streamlit 정적 파일 수집 ──────────────────────────────────
streamlit_datas = collect_data_files("streamlit")
streamlit_metadata = copy_metadata("streamlit")

# Streamlit 의존 패키지의 메타데이터 (importlib.metadata 필요)
extra_metadata = []
for pkg in ("streamlit", "altair", "click", "pandas", "playwright", "beautifulsoup4", "lxml", "openpyxl"):
    try:
        extra_metadata += copy_metadata(pkg)
    except Exception:
        pass


# ── Playwright 브라우저 번들 ──────────────────────────────────
# 주의: Mac에서 PyInstaller 가 Chromium.app 내부 바이너리를 자동 코드사이닝하다 실패함.
# 따라서 spec 에서는 포함하지 않고, 빌드 후 build_mac.sh / build_windows.bat 에서
# ms-playwright 폴더를 dist 결과 옆으로 직접 복사합니다.
playwright_data = []


# ── 앱 자체 데이터 (app.py 와 src 폴더) ────────────────────────
app_datas = [
    (str(PROJECT_ROOT / "app.py"), "."),
    (str(PROJECT_ROOT / "src"), "src"),
]


# ── Analysis ──────────────────────────────────────────────────
a = Analysis(
    ["launcher.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=streamlit_datas + extra_metadata + playwright_data + app_datas,
    hiddenimports=[
        # Streamlit 동적 import
        "streamlit",
        "streamlit.web.cli",
        "streamlit.runtime.scriptrunner.magic_funcs",
        # 우리 모듈
        "src.scraper",
        "src.parser",
        "src.exporter",
        # 자주 누락되는 의존
        "importlib_metadata",
        "pkg_resources",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",       # 안 씀
        "matplotlib",    # 안 씀
        "PIL.ImageTk",
        "test", "tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


# ── EXE ───────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NaverPlace",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,             # UPX는 안티바이러스 오탐을 유발하니 사용 안 함
    console=True,          # 콘솔 창 표시 (진행 로그 보기 위함)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)


coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="NaverPlace",
)


# Mac .app 번들은 의도적으로 빼두었습니다.
# Chromium.app 내부 바이너리들의 코드사이닝이 PyInstaller 의 BUNDLE 단계와 충돌해서
# 단순 폴더 형태(dist/NaverPlace/)로 배포합니다.
# 사용자는 dist/NaverPlace/NaverPlace (실행파일) 을 더블클릭하거나 터미널에서 실행합니다.
