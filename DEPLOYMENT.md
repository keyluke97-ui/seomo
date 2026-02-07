# 🚀 배포 체크리스트

## ✅ GitHub 업로드 전 체크리스트

### 1. 필수 파일 확인
- [x] `app.py` - 메인 앱
- [x] `scraper.py` - 스크래핑 로직
- [x] `notion_bot.py` - Notion API
- [x] `config.py` - 설정 관리
- [x] `requirements.txt` - 의존성
- [x] `packages.txt` - 시스템 패키지 (비어있음)
- [x] `.gitignore` - 중요!
- [x] `README.md` - 프로젝트 설명

### 2. 예시 파일 확인
- [x] `.streamlit/secrets.toml.example` - Notion 설정 예시
- [x] `user_config.json.example` - 키워드 설정 예시

### 3. 제외할 파일 (자동으로 gitignore됨)
- [ ] `__pycache__/` - Python 캐시
- [ ] `*.html` - 덤프 파일
- [ ] `user_config.json` - 사용자 설정
- [ ] `.streamlit/secrets.toml` - API 키

## 📋 GitHub 업로드 단계

```bash
# 1. Git 초기화 (처음만)
cd C:\Users\keylu\.gemini\antigravity\scratch\job-dashboard
git init

# 2. 파일 추가
git add .

# 3. 커밋
git commit -m "Initial commit: 채용 공고 자동화 대시보드"

# 4. GitHub 저장소 연결 (GitHub에서 저장소 생성 후)
git remote add origin https://github.com/YOUR_USERNAME/job-dashboard.git

# 5. 푸시
git branch -M main
git push -u origin main
```

## 🌐 Streamlit Cloud 배포 단계

### 1. Streamlit Cloud 설정
1. https://streamlit.io/cloud 접속
2. GitHub 계정으로 로그인
3. "New app" 클릭
4. 저장소 선택: `YOUR_USERNAME/job-dashboard`
5. Branch: `main`
6. Main file path: `app.py`

### 2. Secrets 설정 (중요!)
**Advanced settings** → **Secrets**에 아래 내용 붙여넣기:

```toml
NOTION_TOKEN = "실제-노션-토큰"
NOTION_DATABASE_ID = "실제-데이터베이스-ID"
```

### 3. 배포
- "Deploy!" 클릭
- 2~3분 대기

## 🧪 로컬 테스트

배포 전에 로컬에서 테스트하세요:

```bash
# 의존성 설치
pip install -r requirements.txt

# .streamlit/secrets.toml 설정 확인

# 앱 실행
streamlit run app.py
```

### 테스트 체크리스트
- [ ] 앱이 정상적으로 로드되는가?
- [ ] 날짜 선택이 작동하는가?
- [ ] 검색 소스 선택이 작동하는가?
- [ ] 키워드 입력/수정이 작동하는가?
- [ ] "공고 수집만" 버튼이 작동하는가? (Notion 없이)
- [ ] Notion 연동이 정상적으로 작동하는가?

## ⚠️ 주의사항

### 절대 GitHub에 올리면 안 되는 것:
- `.streamlit/secrets.toml` (API 키 포함)
- `user_config.json` (개인 설정)
- `*.html` 덤프 파일
- `__pycache__/` 폴더

### GitHub에 올려야 하는 것:
- `.streamlit/secrets.toml.example` (예시 파일)
- `user_config.json.example` (예시 파일)
- 모든 `.py` 파일
- `requirements.txt`
- `packages.txt`
- `.gitignore`
- `README.md`

## 🐛 디버깅

### 문제: Streamlit Cloud에서 메모리 오류
**해결**: 
- 검색 소스를 1~2개로 제한
- 키워드 수 줄이기
- 마감일 범위 줄이기

### 문제: Notion 연결 실패
**해결**:
- Secrets에 올바른 토큰/DB ID 입력했는지 확인
- Notion에서 Integration 연결 확인
- Database 속성이 올바른지 확인

### 문제: 스크래핑 결과 없음
**해결**:
- 실제 채용 사이트에서 해당 키워드로 검색해보기
- 마감일 범위 확대
- 키워드 변경/단순화

## ✅ 완료 후

배포가 성공하면:
1. Streamlit Cloud URL 확인 (예: `https://YOUR_APP.streamlit.app`)
2. README.md에 라이브 데모 링크 추가
3. GitHub 저장소 설명 업데이트
