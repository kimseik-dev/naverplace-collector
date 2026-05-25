#!/bin/bash
# ────────────────────────────────────────────────────────────
# 네이버 플레이스 수집기 — Mac 설치 스크립트
# 더블클릭 → Python 환경 + 의존성 자동 설치
# ────────────────────────────────────────────────────────────

# 스크립트가 있는 폴더로 이동
cd "$(dirname "$0")" || exit 1

# 색상
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  📍 네이버 플레이스 수집기 — 설치 시작"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── Python 확인 ─────────────────────────────────────────────
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        VERSION=$("$candidate" -c "import sys; print(sys.version_info.major*10+sys.version_info.minor)" 2>/dev/null)
        if [ -n "$VERSION" ] && [ "$VERSION" -ge 310 ]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}❌ Python 3.10 이상이 설치되어 있지 않습니다.${NC}"
    echo ""
    echo "   다음 중 하나의 방법으로 Python 을 먼저 설치해주세요:"
    echo "   1. https://www.python.org/downloads/ 에서 설치 파일 다운로드"
    echo "   2. 또는 Homebrew: brew install python@3.12"
    echo ""
    echo "   설치 후 이 스크립트를 다시 실행해주세요."
    read -p "엔터 키를 눌러 종료..."
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 발견: $PYTHON_BIN ($("$PYTHON_BIN" --version))"

# ── 가상환경 ────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}→${NC} 가상환경 생성 중..."
    "$PYTHON_BIN" -m venv .venv || { echo -e "${RED}venv 생성 실패${NC}"; read -p "엔터..."; exit 1; }
    echo -e "${GREEN}✓${NC} 가상환경 생성 완료"
else
    echo -e "${GREEN}✓${NC} 가상환경 이미 존재"
fi

# ── 의존성 설치 ─────────────────────────────────────────────
echo -e "${YELLOW}→${NC} pip 업그레이드 중..."
.venv/bin/pip install --upgrade pip --quiet

echo -e "${YELLOW}→${NC} Python 패키지 설치 중 (1-2분 소요)..."
.venv/bin/pip install -r requirements.txt --quiet || { echo -e "${RED}패키지 설치 실패${NC}"; read -p "엔터..."; exit 1; }
echo -e "${GREEN}✓${NC} 패키지 설치 완료"

# ── Playwright 브라우저 ────────────────────────────────────
echo -e "${YELLOW}→${NC} Chromium 브라우저 설치 중 (2-3분 소요, 최초 1회)..."
.venv/bin/playwright install chromium --with-deps 2>/dev/null || .venv/bin/playwright install chromium
echo -e "${GREEN}✓${NC} 브라우저 설치 완료"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo -e "  ${GREEN}🎉 설치 완료!${NC}"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  앱을 실행하려면 ${YELLOW}run_mac.command${NC} 파일을 더블클릭하세요."
echo ""
read -p "엔터 키를 눌러 창을 닫기..."
