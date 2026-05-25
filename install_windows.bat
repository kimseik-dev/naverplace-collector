@echo off
REM ============================================================
REM 네이버 플레이스 수집기 — Windows 설치 스크립트
REM 더블클릭 → Python 환경 + 의존성 자동 설치
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ===========================================================
echo   네이버 플레이스 수집기 — 설치 시작
echo ===========================================================
echo.

REM Python 찾기 (3.10 이상)
set PYTHON_BIN=
for %%P in (python python3.12 python3.11 python3.10 python3) do (
    where %%P >nul 2>nul
    if not errorlevel 1 (
        for /f "tokens=*" %%V in ('%%P -c "import sys; print(sys.version_info.major*10+sys.version_info.minor)" 2^>nul') do (
            if %%V GEQ 310 (
                set PYTHON_BIN=%%P
                goto :found_python
            )
        )
    )
)

:not_found
echo [오류] Python 3.10 이상이 설치되어 있지 않습니다.
echo.
echo   1. https://www.python.org/downloads/ 에서 설치 파일 다운로드
echo   2. 설치 시 "Add Python to PATH" 옵션을 반드시 체크
echo   3. 설치 후 이 스크립트를 다시 실행
echo.
pause
exit /b 1

:found_python
echo [확인] Python 발견: %PYTHON_BIN%
%PYTHON_BIN% --version
echo.

REM 가상환경
if not exist ".venv\" (
    echo [진행] 가상환경 생성 중...
    %PYTHON_BIN% -m venv .venv
    if errorlevel 1 (
        echo [오류] venv 생성 실패
        pause
        exit /b 1
    )
    echo [완료] 가상환경 생성 완료
) else (
    echo [확인] 가상환경 이미 존재
)
echo.

REM 의존성 설치
echo [진행] pip 업그레이드 중...
.venv\Scripts\python -m pip install --upgrade pip --quiet

echo [진행] Python 패키지 설치 중 (1-2분 소요)...
.venv\Scripts\pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [오류] 패키지 설치 실패
    pause
    exit /b 1
)
echo [완료] 패키지 설치 완료
echo.

REM Playwright Chromium
echo [진행] Chromium 브라우저 설치 중 (2-3분 소요, 최초 1회)...
.venv\Scripts\playwright install chromium
echo [완료] 브라우저 설치 완료
echo.

echo ===========================================================
echo   🎉 설치 완료!
echo ===========================================================
echo.
echo   앱을 실행하려면 run_windows.bat 파일을 더블클릭하세요.
echo.
pause
