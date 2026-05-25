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
echo [STEP] 3. Playwright Chromium 확인
set "PW_CACHE=%USERPROFILE%\AppData\Local\ms-playwright"
if not exist "%PW_CACHE%\" (
    echo [INFO] Playwright Chromium 설치
    .venv\Scripts\playwright install chromium
    if errorlevel 1 exit /b 1
)
dir "%PW_CACHE%" /b

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
echo [STEP] 5. dist 폴더 확인
dir dist /b
if not exist "dist\NaverPlace\" (
    echo [ERROR] dist\NaverPlace 가 생성되지 않았습니다.
    exit /b 1
)

echo.
echo [STEP] 6. Chromium 브라우저 복사
if not exist "dist\NaverPlace\ms-playwright" mkdir "dist\NaverPlace\ms-playwright"

REM 가장 최신 chromium-NUMBER 폴더 찾기 (chromium_headless_shell 제외)
REM "chromium-*" 글로브는 'chromium_' 로 시작하는 것은 매칭하지 않음 (literal "chromium-" 일치 필요)
set "LATEST_NUM=0"
set "LATEST_PATH="
set "LATEST_NAME="
for /d %%D in ("%PW_CACHE%\chromium-*") do (
    setlocal ENABLEDELAYEDEXPANSION
    set "FULL=%%D"
    set "BASE=%%~nxD"
    set "NUM=!BASE:chromium-=!"
    REM 숫자 검증: 비숫자 문자가 들어 있으면 건너뜀
    set "NUM_CHECK="
    for /f "delims=0123456789" %%X in ("!NUM!") do set "NUM_CHECK=NOT_NUMERIC"
    if defined NUM_CHECK (
        endlocal
    ) else (
        if !NUM! GTR %LATEST_NUM% (
            endlocal & set "LATEST_NUM=%%~nxD" & set "LATEST_PATH=%%D" & set "LATEST_NAME=%%~nxD"
        ) else (
            endlocal
        )
    )
)

if not defined LATEST_PATH (
    echo [ERROR] chromium-NUMBER 폴더를 찾을 수 없습니다.
    echo [DEBUG] PW_CACHE 내용:
    dir "%PW_CACHE%" /b
    exit /b 1
)

echo [INFO] 선택된 chromium: %LATEST_NAME%
echo [INFO] 경로: %LATEST_PATH%
xcopy /E /I /Q /Y "%LATEST_PATH%" "dist\NaverPlace\ms-playwright\%LATEST_NAME%" >nul
if errorlevel 1 (
    echo [ERROR] Chromium 복사 실패
    exit /b 1
)

if exist "%PW_CACHE%\.links" xcopy /E /I /Q /Y "%PW_CACHE%\.links" "dist\NaverPlace\ms-playwright\.links" >nul

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
