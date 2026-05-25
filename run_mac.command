#!/bin/bash
# ────────────────────────────────────────────────────────────
# 네이버 플레이스 수집기 — Mac 실행 스크립트
# 더블클릭 → Streamlit 웹 대시보드 시작 + 브라우저 자동 오픈
# ────────────────────────────────────────────────────────────

cd "$(dirname "$0")" || exit 1

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  📍 네이버 플레이스 수집기 시작 중..."
echo "═══════════════════════════════════════════════════════════"
echo ""

if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ 가상환경이 없습니다.${NC}"
    echo ""
    echo "   먼저 ${YELLOW}install_mac.command${NC} 를 더블클릭해서 설치해주세요."
    echo ""
    read -p "엔터 키를 눌러 종료..."
    exit 1
fi

# 최초 실행 시 Streamlit 이메일 프롬프트 우회
mkdir -p "$HOME/.streamlit"
if [ ! -f "$HOME/.streamlit/credentials.toml" ]; then
    printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml"
fi

echo -e "${YELLOW}→${NC} 웹 대시보드를 시작합니다."
echo -e "${YELLOW}→${NC} 잠시 후 브라우저가 자동으로 열립니다 (열리지 않으면 아래 주소로 접속):"
echo ""
echo -e "   ${GREEN}http://localhost:8501${NC}"
echo ""
echo -e "${YELLOW}→${NC} 종료하려면 이 창에서 ${YELLOW}Ctrl+C${NC} 를 누르거나 창을 닫으세요."
echo ""

# 3초 후 브라우저 오픈 (Streamlit이 자동으로 열어주기도 하지만 보장 차원)
( sleep 3 && open "http://localhost:8501" ) &

.venv/bin/streamlit run app.py --server.headless=false --server.port=8501 --browser.gatherUsageStats=false
