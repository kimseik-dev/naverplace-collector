@echo on
REM ============================================================
REM Windows 단일 폴더 빌드 스크립트
REM 결과: dist\NaverPlace\
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo [STEP] 1. venv 확인
if not exist ".venv\" (
    echo [ERROR] .venv 가 없습니다.
    exit /b 1
)

echo.
echo [STEP] 2. PyInstaller 확인
.venv\Scripts\pyinstaller --version
if errorlevel 1 (
    echo [INFO] PyInstaller 설치
    .venv\Scripts\pip install pyinstaller
    if errorlevel 1 exit /b 1
)

echo.
echo [STEP] 3. Playwright Chromium 캐시 확인
set "PW_CACHE=%USERPROFILE%\AppData\Local\ms-playwright"
if not exist "%PW_CACHE%\" (
    echo [INFO] Playwright Chromium 설치
    .venv\Scripts\playwright install chromium
    if errorlevel 1 exit /b 1
)

echo.
echo [STEP] 4. PyInstaller 빌드
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
.venv\Scripts\pyinstaller naverplace.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller 빌드 실패
    exit /b 1
)

echo.
echo [STEP] 5. 빌드 결과 확인
if not exist "dist\NaverPlace\" (
    echo [ERROR] dist\NaverPlace 가 생성되지 않았습니다.
    dir dist /b
    exit /b 1
)

echo.
echo [STEP] 6. Chromium 복사 (Python helper)
.venv\Scripts\python scripts\copy_chromium.py dist\NaverPlace
if errorlevel 1 (
    echo [ERROR] Chromium 복사 실패
    exit /b 1
)

echo.
echo [STEP] 7. 사용 안내 생성
> "dist\NaverPlace\사용법.txt" echo NaverPlace - Naver Place Collector
>> "dist\NaverPlace\사용법.txt" echo.
>> "dist\NaverPlace\사용법.txt" echo Execute: Double-click NaverPlace.exe
>> "dist\NaverPlace\사용법.txt" echo Stop: Close console window or Ctrl+C
>> "dist\NaverPlace\사용법.txt" echo Purpose: Learning/research only

echo.
echo [DONE] 빌드 완료
dir dist\NaverPlace /b
