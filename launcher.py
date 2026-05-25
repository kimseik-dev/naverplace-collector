"""
PyInstaller 단일 실행파일용 진입점.

이 파일은 PyInstaller로 .exe / .app 으로 컴파일됩니다.
실행 시:
  1. Playwright 브라우저 경로 환경변수 설정 (번들된 chromium 사용)
  2. Streamlit 서버를 서브프로세스가 아닌 같은 프로세스 안에서 부팅
  3. 기본 브라우저로 자동 오픈
"""

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _resource_dir() -> Path:
    """PyInstaller 번들 안에서는 sys._MEIPASS, 개발 환경에서는 현재 폴더."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return Path(__file__).resolve().parent


def _setup_playwright_env() -> None:
    """번들된 Playwright Chromium 경로를 환경변수로 지정."""
    base = _resource_dir()
    exe_dir = Path(sys.executable).resolve().parent
    # 빌드 후처리 스크립트가 ms-playwright 를 어디에 두느냐에 따라 후보가 달라짐
    candidates = [
        base / "ms-playwright",
        exe_dir / "ms-playwright",
        exe_dir.parent / "ms-playwright",
        exe_dir.parent / "Resources" / "ms-playwright",     # Mac .app
        exe_dir.parent / "_internal" / "ms-playwright",     # Win onedir 의 _internal
        base.parent / "ms-playwright",
    ]
    for c in candidates:
        if c.exists() and any(c.iterdir()):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(c)
            print(f"[launcher] PLAYWRIGHT_BROWSERS_PATH={c}")
            return
    print("[launcher] ⚠️  ms-playwright 폴더를 찾지 못했습니다. "
          "기본 캐시 위치를 사용합니다.")


def _setup_streamlit_env() -> None:
    """Streamlit 첫 실행 이메일 프롬프트 우회."""
    home = Path.home()
    cred_dir = home / ".streamlit"
    cred_dir.mkdir(parents=True, exist_ok=True)
    cred_file = cred_dir / "credentials.toml"
    if not cred_file.exists():
        cred_file.write_text('[general]\nemail = ""\n', encoding="utf-8")


def _open_browser_when_ready(url: str, timeout: float = 30.0) -> None:
    """서버가 준비되면 브라우저를 자동으로 엽니다."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1).read()
            break
        except Exception:
            time.sleep(0.5)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main() -> None:
    _setup_playwright_env()
    _setup_streamlit_env()

    base = _resource_dir()
    app_file = str(base / "app.py")
    port = "8501"
    url = f"http://localhost:{port}"

    print("═" * 60)
    print("  📍 네이버 플레이스 수집기")
    print("═" * 60)
    print(f"  브라우저: {url}")
    print(f"  종료: 이 창을 닫거나 Ctrl+C")
    print("═" * 60)
    print()

    # 백그라운드에서 서버 준비를 기다렸다가 브라우저 오픈
    threading.Thread(
        target=_open_browser_when_ready,
        args=(url,),
        daemon=True,
    ).start()

    # Streamlit CLI 를 같은 프로세스에서 실행
    sys.argv = [
        "streamlit", "run", app_file,
        "--global.developmentMode=false",
        "--server.headless=true",          # CLI 가 브라우저 열려고 시도하지 않게
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]
    from streamlit.web import cli as stcli
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
