@echo off
REM ============================================================
REM 네이버 플레이스 수집기 — Windows 실행 스크립트
REM 더블클릭 → Streamlit 웹 대시보드 시작 + 브라우저 자동 오픈
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ===========================================================
echo   네이버 플레이스 수집기 시작 중...
echo ===========================================================
echo.

if not exist ".venv\" (
    echo [오류] 가상환경이 없습니다.
    echo.
    echo   먼저 install_windows.bat 을 더블클릭해서 설치해주세요.
    echo.
    pause
    exit /b 1
)

REM 최초 실행 시 Streamlit 이메일 프롬프트 우회
if not exist "%USERPROFILE%\.streamlit\" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

echo [진행] 웹 대시보드를 시작합니다.
echo [진행] 잠시 후 브라우저가 자동으로 열립니다 (열리지 않으면 아래 주소로 접속):
echo.
echo    http://localhost:8501
echo.
echo [안내] 종료하려면 이 창에서 Ctrl+C 를 누르거나 창을 닫으세요.
echo.

REM 3초 후 브라우저 열기
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8501"

.venv\Scripts\streamlit run app.py --server.headless=false --server.port=8501 --browser.gatherUsageStats=false
