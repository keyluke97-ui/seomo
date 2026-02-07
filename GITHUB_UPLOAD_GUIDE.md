# 🚀 GitHub 업로드 가이드 (Git 미설치 시)

Git이 설치되어 있지 않은 경우, GitHub 웹 인터페이스를 통해 직접 업로드할 수 있습니다.

## 📦 업로드할 파일 목록

### ✅ 반드시 업로드해야 할 파일:

#### 1. Python 소스 코드
- `app.py`
- `scraper.py`
- `notion_bot.py`
- `config.py`

#### 2. 설정 파일
- `requirements.txt`
- `packages.txt`
- `.gitignore`

#### 3. 문서 파일
- `README.md`
- `DEPLOYMENT.md`

#### 4. 예시 파일
- `user_config.json.example`
- `.streamlit/secrets.toml.example`

### ❌ 절대 업로드하면 안 되는 파일:

- `.streamlit/secrets.toml` ⚠️ **API 키 포함! 절대 업로드 금지**
- `user_config.json` (개인 설정)
- `__pycache__/` 폴더
- `*.html` 파일 (덤프)
- `test_requests.py` (개발 테스트용)

## 📋 웹에서 GitHub에 업로드하는 방법

### 방법 1: GitHub 웹 인터페이스 사용 (권장)

1. **GitHub에서 새 저장소 생성**
   - https://github.com/new 접속
   - Repository name: `job-dashboard`
   - Description: "채용 공고 자동화 대시보드"
   - Public 선택
   - **"Add a README file" 체크 해제** (이미 있음)
   - Create repository 클릭

2. **파일 업로드**
   - "uploading an existing file" 클릭
   - 위의 "업로드할 파일 목록"의 파일들을 드래그&드롭
   - 또는 "choose your files" 클릭하여 선택

3. **폴더 구조 맞추기**
   - `.streamlit/secrets.toml.example` 파일의 경우:
     - 먼저 `.streamlit` 폴더 생성 (Add file → Create new file → 파일명: `.streamlit/temp`)
     - 그 다음 `secrets.toml.example` 업로드

4. **커밋**
   - Commit message: "Initial commit: 채용 공고 자동화 대시보드"
   - "Commit changes" 클릭

### 방법 2: Git Desktop 사용

1. **Git Desktop 설치**
   - https://desktop.github.com/ 다운로드 및 설치

2. **저장소 생성**
   - File → New repository
   - Name: `job-dashboard`
   - Local path: `C:\Users\keylu\.gemini\antigravity\scratch\job-dashboard`
   - Initialize this repository with a README: 체크 해제
   - Create repository 클릭

3. **커밋 및 푸시**
   - Changes 탭에서 업로드할 파일만 선택
   - Summary: "Initial commit"
   - Commit to main
   - Publish repository 클릭

## 🌐 Streamlit Cloud 배포

### 1. Streamlit Cloud 접속
- https://streamlit.io/cloud
- GitHub 계정으로 로그인

### 2. 새 앱 배포
1. "New app" 버튼 클릭
2. **Repository**: `YOUR_USERNAME/job-dashboard` 선택
3. **Branch**: `main`
4. **Main file path**: `app.py`
5. **App URL**: 원하는 이름 (예: `my-job-dashboard`)

### 3. Secrets 설정 (매우 중요!)
1. "Advanced settings" 클릭
2. "Secrets" 섹션에 다음 내용 입력:

```toml
NOTION_TOKEN = "실제-노션-토큰-입력"
NOTION_DATABASE_ID = "실제-데이터베이스-ID-입력"
```

⚠️ **주의**: 따옴표 포함해서 정확히 입력!

### 4. 배포
- "Deploy!" 클릭
- 2~3분 대기
- 배포 완료 후 URL로 접속

## ✅ 배포 완료 체크리스트

- [ ] GitHub 저장소에 모든 필수 파일 업로드 완료
- [ ] GitHub에 `.streamlit/secrets.toml` 없는지 확인 ⚠️
- [ ] Streamlit Cloud에 배포 완료
- [ ] Streamlit Secrets에 Notion 토큰 설정
- [ ] 배포된 앱이 정상 작동하는지 테스트
- [ ] README.md에 라이브 데모 링크 추가 (선택사항)

## 🐛 문제 해결

### "Import Error: No module named 'streamlit'"
→ Streamlit Cloud가 `requirements.txt`를 읽지 못함
→ 파일 이름과 위치 확인 (루트 디렉토리에 있어야 함)

### "Notion API Error"
→ Streamlit Cloud의 Secrets 설정 확인
→ 토큰과 DB ID가 정확한지 확인

### "Memory Limit Exceeded"
→ 검색 소스 개수 줄이기 (1~2개)
→ 키워드 수 줄이기
→ 마감일 범위 단축

## 📞 추가 도움

- Streamlit 공식 문서: https://docs.streamlit.io/
- Notion API 문서: https://developers.notion.com/
- 이슈 제기: GitHub Issues 탭 사용
