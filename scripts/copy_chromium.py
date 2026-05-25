"""
Playwright Chromium 폴더를 dist 결과 옆으로 복사하는 헬퍼.

cmd batch / bash 양쪽 OS 에서 동일한 로직을 안정적으로 실행하기 위함.
가장 최신 버전의 chromium-XXXX + chromium_headless_shell-XXXX 둘 다 복사합니다.

사용:
    python scripts/copy_chromium.py <DIST_DIR>

예:
    python scripts/copy_chromium.py dist/NaverPlace
"""

import os
import re
import shutil
import sys
from pathlib import Path

# Windows 콘솔 인코딩 (cp1252)에서 한글 출력 시 UnicodeEncodeError 방지
if sys.platform.startswith("win") and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def find_cache_dir() -> Path:
    """OS별 Playwright 브라우저 캐시 위치."""
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env:
        p = Path(env)
        if p.exists():
            return p

    home = Path.home()
    if sys.platform == "darwin":
        candidates = [home / "Library/Caches/ms-playwright"]
    elif sys.platform.startswith("win"):
        candidates = [home / "AppData/Local/ms-playwright"]
    else:
        candidates = [home / ".cache/ms-playwright"]

    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"Playwright 캐시를 찾을 수 없습니다. 후보: {candidates}\n"
        f"'playwright install chromium' 을 먼저 실행해주세요."
    )


def latest_version(cache_dir: Path, prefix: str) -> tuple[int, Path] | None:
    """캐시에서 prefix-NUMBER 패턴 중 가장 높은 NUMBER 폴더 찾기."""
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    best: tuple[int, Path] | None = None
    for entry in cache_dir.iterdir():
        if not entry.is_dir():
            continue
        m = pattern.match(entry.name)
        if not m:
            continue
        num = int(m.group(1))
        if best is None or num > best[0]:
            best = (num, entry)
    return best


def copy_tree(src: Path, dst: Path) -> None:
    """폴더 통째 복사 (덮어쓰기)."""
    if dst.exists():
        shutil.rmtree(dst)
    print(f"  → {src.name}  →  {dst}")
    shutil.copytree(src, dst, symlinks=False)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python copy_chromium.py <DIST_DIR>")
        return 2

    dist_dir = Path(sys.argv[1]).resolve()
    if not dist_dir.exists():
        print(f"[ERROR] {dist_dir} 가 존재하지 않습니다.")
        return 1

    cache = find_cache_dir()
    print(f"[INFO] Playwright 캐시: {cache}")
    print(f"[INFO] 대상 폴더    : {dist_dir}")

    target_dir = dist_dir / "ms-playwright"
    target_dir.mkdir(exist_ok=True)

    # 1) chromium_headless_shell (필수 — headless=True 모드용)
    hs = latest_version(cache, "chromium_headless_shell")
    if hs is None:
        print("[ERROR] chromium_headless_shell-NUMBER 폴더 없음. "
              "'playwright install chromium' 먼저 실행하세요.")
        return 1
    hs_num, hs_path = hs
    print(f"[INFO] 선택된 버전: {hs_num}")
    copy_tree(hs_path, target_dir / hs_path.name)

    # 2) chromium (full Chrome — headless=False 디버깅용)
    #    크기 절약을 위해 INCLUDE_FULL_CHROMIUM=1 환경변수가 있을 때만 포함.
    if os.environ.get("INCLUDE_FULL_CHROMIUM"):
        chromium_dir = cache / f"chromium-{hs_num}"
        if chromium_dir.exists():
            copy_tree(chromium_dir, target_dir / chromium_dir.name)

    # 3) ffmpeg 는 비디오 처리 시에만 필요. 기본 생략 (크기 절약).
    if os.environ.get("INCLUDE_FFMPEG"):
        ff = latest_version(cache, "ffmpeg")
        if ff:
            copy_tree(ff[1], target_dir / ff[1].name)

    # 4) .links 메타 파일
    links = cache / ".links"
    if links.exists():
        dst_links = target_dir / ".links"
        if dst_links.exists():
            shutil.rmtree(dst_links)
        shutil.copytree(links, dst_links)
        print(f"  → .links  →  {dst_links}")

    # 결과 표시
    total = sum(
        f.stat().st_size
        for f in target_dir.rglob("*")
        if f.is_file()
    )
    print(f"[DONE] 총 {total / 1024 / 1024:.0f} MB 복사됨")
    print(f"[DONE] 구성:")
    for entry in sorted(target_dir.iterdir()):
        print(f"   - {entry.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
