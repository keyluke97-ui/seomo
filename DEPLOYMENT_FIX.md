# 🛠️ Notion 연동 버그 수정 및 배포 가이드

## 1. 수정 사항 확인
코드에 **상세 에러 리포팅 기능**을 추가했습니다. 
이제 Notion 저장 실패 시, 단순히 "실패"라고만 뜨지 않고 **구체적인 원인(예: 인증 오류, 데이터베이스 ID 오류 등)**을 화면에 표시합니다.

## 2. GitHub에 변경 사항 업로드
현재 로컬 폴더에 Git 커밋을 완료했습니다. 터미널을 열어 아래 명령어로 GitHub에 푸시하세요.

```bash
# 1. 새 창에서 터미널 열기 (또는 기존 터미널 사용)
cd C:\Users\keylu\.gemini\antigravity\scratch\job-dashboard

# 2. 원격 저장소 주소 등록 (기존에 했다면 생략 가능)
# 저장소 주소는 GitHub 리포지토리 페이지에서 확인하세요 (예: https://github.com/아이디/job-dashboard.git)
git remote add origin https://github.com/YOUR_USERNAME/job-dashboard.git

# 3. 브랜치 설정 및 푸시 (강제 푸시 주의)
# 만약 기존 저장소와 충돌이 난다면 --force 옵션이 필요할 수 있습니다.
git branch -M main
git push -u origin main
```

## 3. Streamlit Cloud 설정 확인 (가장 중요! ⭐️)
`Reference error`나 `Unauthorized` 에러가 뜬다면 99% 확률로 **Secrets 설정** 문제입니다.

1. [Streamlit Cloud 대시보드](https://share.streamlit.io/) 접속
2. 배포된 앱의 **Settings** (점 3개 메뉴) 클릭
3. **Secrets** 탭 클릭
4. 아래 내용이 **정확히** 들어있는지 확인 (복사 붙여넣기 추천):

```toml
NOTION_TOKEN = "secret_..."  # 여기에 실제 토큰
NOTION_DATABASE_ID = "..."   # 여기에 실제 데이터베이스 ID
```

> **주의:** `.streamlit/secrets.toml` 파일은 보안상 GitHub에 업로드되지 않습니다. 따라서 Streamlit Cloud의 Secrets 설정에 직접 입력해야만 작동합니다.

## 4. 디버깅 방법
1. 앱이 업데이트되면 다시 접속합니다.
2. "공고 찾기 & Notion 저장" 버튼을 누릅니다.
3. 만약 또 실패한다면, **"실패 상세 내용 보기"**를 클릭하세요.
4. 에러 메시지를 확인합니다:
   - `object_not_found`: 데이터베이스 ID가 틀렸거나, 봇이 데이터베이스에 초대되지 않음 (공유 > 초대)
   - `unauthorized`: 토큰이 틀렸음
   - `validation_error`: 속성 이름(공고명, 링크 등)이 Notion 데이터베이스의 컬럼명과 다름

이제 문제를 쉽게 찾을 수 있을 것입니다!
