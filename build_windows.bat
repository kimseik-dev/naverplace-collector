@echo off
REM ============================================================
REM Windows 단일 폴더 빌드 스크립트
REM 결과: dist\NaverPlace\ — NaverPlace.exe 더블클릭으로 실행
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"
setlocal ENABLEEXTENSIONS

if not exist ".venv\" (
    echo [오류] .venv 가 없습니다. install_windows.bat 을 먼저 실행해주세요.
    exit /b 1
)

REM PyInstaller 설치 확인
.venv\Scripts\pyinstaller --version >nul 2>nul
if errorlevel 1 (
    echo [진행] PyInstaller 설치 중...
    .venv\Scripts\pip install pyinstaller --quiet
)

REM Playwright Chromium 캐시 확인
set "PW_CACHE=%USERPROFILE%\AppData\Local\ms-playwright"
if not exist "%PW_CACHE%\" (
    echo [진행] Playwright Chromium 설치...
    .venv\Scripts\playwright install chromium
)

echo [진행] PyInstaller 빌드 시작 (5-10분 소요)...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
.venv\Scripts\pyinstaller naverplace.spec --clean --noconfirm
if errorlevel 1 (
    echo [오류] PyInstaller 빌드 실패
    exit /b 1
)

if not exist "dist\NaverPlace\" (
    echo [오류] 빌드 실패 — dist\NaverPlace 가 생성되지 않았습니다.
    exit /b 1
)

echo [진행] Chromium 브라우저 복사 중 (최신 1개만)...
if not exist "dist\NaverPlace\ms-playwright" mkdir "dist\NaverPlace\ms-playwright"

REM chromium-NUMBER 폴더 중 가장 최신 1개만 복사 (chromium_headless_shell 제외)
set "LATEST_NUM=0"
set "LATEST_NAME="
for /d %%D in ("%PW_CACHE%\chromium-*") do (
    set "DIR_NAME=%%~nxD"
    setlocal ENABLEDELAYEDEXPANSION
    REM chromium_headless_shell 제외
    echo !DIR_NAME! | findstr /B /C:"chromium_" >nul
    if errorlevel 1 (
        set "NUM=!DIR_NAME:chromium-=!"
        if !NUM! GTR !LATEST_NUM! (
            endlocal & set "LATEST_NUM=%%~nxD" & set "LATEST_NAME=%%~nxD" & set "LATEST_PATH=%%D"
        ) else (
            endlocal
        )
    ) else (
        endlocal
    )
)

if not defined LATEST_PATH (
    echo [오류] chromium-NUMBER 폴더를 찾을 수 없습니다.
    exit /b 1
)
echo         선택된 chromium: %LATEST_NAME%
xcopy /E /I /Q /Y "%LATEST_PATH%" "dist\NaverPlace\ms-playwright\%LATEST_NAME%" >nul

if exist "%PW_CACHE%\.links" xcopy /E /I /Q /Y "%PW_CACHE%\.links" "dist\NaverPlace\ms-playwright\.links" >nul

REM 사용 안내
> "dist\NaverPlace\사용법.txt" echo 📍 네이버 플레이스 수집기
>> "dist\NaverPlace\사용법.txt" echo.
>> "dist\NaverPlace\사용법.txt" echo [실행 방법]
>> "dist\NaverPlace\사용법.txt" echo 이 폴더 안의 NaverPlace.exe 를 더블클릭하세요.
>> "dist\NaverPlace\사용법.txt" echo 잠시 후 브라우저가 자동으로 열립니다.
>> "dist\NaverPlace\사용법.txt" echo.
>> "dist\NaverPlace\사용법.txt" echo [종료] 콘솔 창을 닫거나 Ctrl+C
>> "dist\NaverPlace\사용법.txt" echo [주의] 학습/연구 목적 전용

echo.
echo ===========================================================
echo   빌드 완료
echo ===========================================================
echo.
echo   결과: dist\NaverPlace\
echo   실행: dist\NaverPlace\NaverPlace.exe  (더블클릭)
echo.
echo   배포 시 dist\NaverPlace 폴더 전체를 zip 으로 압축하세요.
echo.
