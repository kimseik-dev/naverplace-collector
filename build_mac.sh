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

# Chromium 복사 (전체 chromium + headless_shell 둘 다 필요)
# - chromium-NUMBER: headless=False 일 때 사용
# - chromium_headless_shell-NUMBER: headless=True 일 때 사용 (우리 기본값)
echo -e "${YELLOW}→${NC} Chromium 브라우저 복사 중 (chromium + headless_shell)..."
mkdir -p "dist/NaverPlace/ms-playwright"

# 가장 최신 버전 번호 찾기 (둘 다 같은 번호 가정)
LATEST_NUM=0
for dir in "$PW_CACHE"/chromium_headless_shell-[0-9]*; do
    [ -d "$dir" ] || continue
    name=$(basename "$dir")
    num=$(echo "$name" | sed 's/chromium_headless_shell-//')
    if [ "$num" -gt "$LATEST_NUM" ] 2>/dev/null; then
        LATEST_NUM=$num
    fi
done

if [ "$LATEST_NUM" -eq 0 ]; then
    echo -e "${RED}❌ chromium_headless_shell-NUMBER 폴더를 찾을 수 없습니다.${NC}"
    echo "       'playwright install chromium' 을 먼저 실행해주세요."
    exit 1
fi

echo "        선택된 버전: $LATEST_NUM"

# chromium-NUMBER (full chrome) 복사
if [ -d "$PW_CACHE/chromium-$LATEST_NUM" ]; then
    echo "        → chromium-$LATEST_NUM 복사 중..."
    cp -R "$PW_CACHE/chromium-$LATEST_NUM" "dist/NaverPlace/ms-playwright/chromium-$LATEST_NUM"
fi

# chromium_headless_shell-NUMBER (headless 모드용) 복사
echo "        → chromium_headless_shell-$LATEST_NUM 복사 중..."
cp -R "$PW_CACHE/chromium_headless_shell-$LATEST_NUM" \
      "dist/NaverPlace/ms-playwright/chromium_headless_shell-$LATEST_NUM"

# ffmpeg (옵션, 미디어 처리 시 필요할 수 있음)
for ff in "$PW_CACHE"/ffmpeg-*; do
    [ -d "$ff" ] || continue
    name=$(basename "$ff")
    cp -R "$ff" "dist/NaverPlace/ms-playwright/$name"
    break
done

# .links 메타 파일
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
