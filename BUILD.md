# 📦 빌드 및 배포 가이드

개발자/배포자용 문서입니다. 일반 사용자는 [README.md](README.md) 를 참고하세요.

---

## 빌드 결과물

| OS | 결과 폴더 | 실행 파일 | 더블클릭용 래퍼 | 압축 크기 |
|----|----------|----------|----------------|----------|
| Mac (Apple Silicon/Intel) | `dist/NaverPlace/` | `NaverPlace` | `실행하기.command` | ~250 MB |
| Windows | `dist\NaverPlace\` | `NaverPlace.exe` | (직접 더블클릭) | ~280 MB |

내부 구조:
```
NaverPlace/
├── NaverPlace          ← 실행 파일 (PyInstaller)
├── _internal/          ← Python 런타임 + 라이브러리
├── ms-playwright/      ← 번들된 Chromium 브라우저
├── 실행하기.command       ← 더블클릭용 래퍼 (Mac만)
└── 사용법.txt           ← 사용자용 간단 안내
```

---

## 빌드 방법

### 방법 A — 로컬에서 직접 빌드

해당 OS의 머신에서 한 번만 빌드하면 됩니다.

#### Mac

```bash
# 0. 가상환경/의존성 설치 (최초 1회)
bash install_mac.command

# 1. PyInstaller 설치 + 빌드
bash build_mac.sh
```

소요 시간: 5-10분.

#### Windows

```cmd
:: 0. 가상환경/의존성 설치 (최초 1회)
install_windows.bat

:: 1. PyInstaller 설치 + 빌드
build_windows.bat
```

### 방법 B — GitHub Actions (자동 빌드, Mac + Windows 동시)

1. 이 프로젝트를 GitHub 저장소에 푸시
2. GitHub 저장소 페이지 → **Actions** 탭
3. 두 가지 트리거:

   **수동 빌드**: `Build executables` 워크플로 선택 → **Run workflow** 클릭

   **태그 기반 자동 빌드 + Release 업로드**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
   → GitHub Release 페이지에 `NaverPlace-mac.zip`, `NaverPlace-win.zip` 자동 첨부

4. 빌드 완료 후 Artifacts 또는 Release 에서 zip 다운로드

GitHub Actions 빌드 환경:
- macOS: `macos-latest` (Intel/Apple Silicon 자동)
- Windows: `windows-latest`
- Python: 3.12

---

## 배포

### 단순 배포 (1-5명)

1. 로컬에서 빌드 → `dist/NaverPlace/` 생성
2. 폴더를 zip 으로 압축:
   - Mac: `cd dist && zip -r NaverPlace-mac.zip NaverPlace`
   - Win: PowerShell `Compress-Archive -Path dist\NaverPlace -DestinationPath NaverPlace-win.zip`
3. zip 파일을 메신저/이메일/드라이브로 전달
4. 사용자는 압축 풀고 더블클릭

### GitHub Release 배포 (추천)

`git tag v1.0.0 && git push --tags` 한 번으로 Mac + Windows 빌드 + 압축 + Release 업로드까지 자동.

사용자는 Release 페이지에서 OS에 맞는 zip 다운로드.

---

## 알아둘 점

### 파일 크기
- 약 250~280MB (Chromium 포함). 압축 해제 후 600~700MB.
- 더 줄이려면: Chromium 빼고 첫 실행 시 다운로드하게 변경 가능 (사용자 인터넷 필요)

### Mac 코드사이닝
- 현재 ad-hoc 사인 상태. 정식 Apple Developer 인증서 없음.
- 사용자가 처음 실행 시 **"확인되지 않은 개발자"** 경고가 뜸 → 우클릭 → 열기 로 우회 가능.
- 정식 사인 + 공증 (notarization) 을 원하면 Apple Developer 계정 필요 (연 $99).

### Windows 안티바이러스
- PyInstaller .exe 는 종종 오탐됨 (특히 Defender SmartScreen).
- 해결: Microsoft 코드사이닝 인증서 구매 또는 사용자에게 "추가 정보 → 실행"으로 우회 안내.
- 1-5명 규모면 신뢰 기반 전달이면 충분.

### Chromium 버전
- 빌드 시점의 Playwright 가 가진 최신 Chromium 1개만 포함합니다.
- Playwright 가 업데이트되면 재빌드 필요.

---

## 트러블슈팅

| 증상 | 원인 / 해결 |
|------|------------|
| 빌드 시 codesign 실패 | `chromium-*` 폴더가 datas 에 포함됨. spec 의 `playwright_data = []` 확인 |
| 실행 시 `ms-playwright not found` | 빌드 후처리 단계가 안 돌아간 것. `build_mac.sh` / `build_windows.bat` 가 끝까지 실행됐는지 확인 |
| 실행은 되는데 수집이 안 됨 | `ms-playwright/chromium-XXX/` 가 결과 폴더에 있는지 확인 |
| Streamlit "이메일 입력" 프롬프트 | `~/.streamlit/credentials.toml` 생성 (launcher 가 자동 처리) |
| 빌드 시 메모리 부족 | PyInstaller 는 메모리를 많이 씁니다. 8GB+ 권장 |

---

## 버전 업데이트 워크플로

1. 코드 수정
2. `requirements.txt` 의 라이브러리 버전 확인
3. 변경 사항 commit
4. 새 태그 푸시: `git tag v1.0.1 && git push --tags`
5. GitHub Actions 가 자동으로 빌드 → Release 업데이트
6. 사용자에게 새 Release 링크 공유
