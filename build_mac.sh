#!/bin/bash
# ────────────────────────────────────────────────────────────
# Mac 단일 폴더 빌드 스크립트
# 결과: dist/NaverPlace/ — NaverPlace 더블클릭으로 실행
# ────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ .venv 가 없습니다. install_mac.command 를 먼저 실행해주세요.${NC}"
    exit 1
fi

# pyinstaller 가 설치되어 있는지 확인
if ! .venv/bin/pyinstaller --version >/dev/null 2>&1; then
    echo -e "${YELLOW}→${NC} PyInstaller 설치 중..."
    .venv/bin/pip install pyinstaller --quiet
fi

# Playwright Chromium 캐시 확인
PW_CACHE="$HOME/Library/Caches/ms-playwright"
if [ ! -d "$PW_CACHE" ]; then
    echo -e "${YELLOW}→${NC} Playwright Chromium 설치..."
    .venv/bin/playwright install chromium
fi

echo -e "${YELLOW}→${NC} PyInstaller 빌드 시작 (5-10분 소요)..."
rm -rf build dist
.venv/bin/pyinstaller naverplace.spec --clean --noconfirm

if [ ! -d "dist/NaverPlace" ]; then
    echo -e "${RED}❌ 빌드 실패 — dist/NaverPlace 가 생성되지 않았습니다.${NC}"
    exit 1
fi

# Chromium 만 복사 (headless_shell 등은 제외, 최신 1개만 → 용량 절약)
echo -e "${YELLOW}→${NC} Chromium 브라우저 복사 중 (최신 1개만)..."
mkdir -p "dist/NaverPlace/ms-playwright"

# 최신 chromium-NUMBER 폴더 1개만 선택 (headless_shell 제외)
LATEST_CHROMIUM=""
LATEST_NUM=0
for dir in "$PW_CACHE"/chromium-[0-9]*; do
    [ -d "$dir" ] || continue
    name=$(basename "$dir")
    # chromium_headless_shell 제외 (이름이 chromium- 로 시작하므로 추가 검증)
    case "$name" in
        chromium_*) continue ;;
    esac
    num=$(echo "$name" | sed 's/chromium-//')
    if [ "$num" -gt "$LATEST_NUM" ] 2>/dev/null; then
        LATEST_NUM=$num
        LATEST_CHROMIUM=$dir
    fi
done

if [ -z "$LATEST_CHROMIUM" ]; then
    echo -e "${RED}❌ chromium-NUMBER 폴더를 찾을 수 없습니다.${NC}"
    exit 1
fi

CHROMIUM_NAME=$(basename "$LATEST_CHROMIUM")
echo "        선택된 chromium: $CHROMIUM_NAME"
cp -R "$LATEST_CHROMIUM" "dist/NaverPlace/ms-playwright/$CHROMIUM_NAME"

# .links 메타 파일도 복사 (Playwright 가 참조)
if [ -d "$PW_CACHE/.links" ]; then
    cp -R "$PW_CACHE/.links" "dist/NaverPlace/ms-playwright/.links"
fi

# 더블클릭 가능한 실행 래퍼
cat > "dist/NaverPlace/실행하기.command" <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./NaverPlace
EOF
chmod +x "dist/NaverPlace/실행하기.command"

# 사용 안내 README
cat > "dist/NaverPlace/사용법.txt" <<'EOF'
📍 네이버 플레이스 수집기

[실행 방법]
이 폴더 안의 「실행하기.command」파일을 더블클릭하세요.
잠시 후 브라우저가 자동으로 열립니다.

[종료 방법]
터미널 창을 닫거나 Ctrl+C 를 누르세요.

[주의]
• 학습/연구 목적으로만 사용해주세요
• 네이버 이용약관을 준수해주세요
• 폴더를 다른 위치로 옮겨도 동작합니다 (단, 폴더 통째로 옮겨야 함)
EOF

# 결과 크기 확인
SIZE=$(du -sh dist/NaverPlace | cut -f1)
echo ""
echo "═══════════════════════════════════════════════════════════"
echo -e "  ${GREEN}✓ 빌드 완료${NC}"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  📁 결과: dist/NaverPlace/  ($SIZE)"
echo "  🚀 실행: dist/NaverPlace/실행하기.command  (더블클릭)"
echo ""
echo "  배포 시 dist/NaverPlace 폴더를 통째로 zip 으로 압축해서 전달하세요."
echo ""
