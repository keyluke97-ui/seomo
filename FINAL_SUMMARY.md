# 최종 디버깅 및 배포 체크리스트

## ✅ 완료된 작업

### 1. 파일 정리 및 최적화
- ✅ `packages.txt` 최적화 (불필요한 chromium 제거)
- ✅ `.gitignore`에 `user_config.json` 추가
- ✅ 모든 Python 파일 문법 검증 완료

### 2. 생성된 문서
- ✅ `README.md` - 프로젝트 소개 및 사용법
- ✅ `DEPLOYMENT.md` - 배포 체크리스트
- ✅ `GITHUB_UPLOAD_GUIDE.md` - Git 미설치 시 업로드 가이드
- ✅ `.streamlit/secrets.toml.example` - Notion 설정 예시
- ✅ `user_config.json.example` - 키워드 설정 예시
- ✅ `check_deployment.py` - 배포 전 자동 검증 스크립트

## 📋 GitHub 업로드 파일 목록

### ✅ 반드시 업로드할 파일 (12개)

#### Python 소스 코드 (4개)
```
app.py
scraper.py
notion_bot.py
config.py
```

#### 설정 파일 (3개)
```
requirements.txt
packages.txt
.gitignore
```

#### 문서 파일 (3개)
```
README.md
DEPLOYMENT.md
GITHUB_UPLOAD_GUIDE.md
```

#### 예시 파일 (2개)
```
user_config.json.example
.streamlit/secrets.toml.example
```

### ❌ 업로드하면 안 되는 파일

- `.streamlit/secrets.toml` ⚠️ **Notion API 키 포함!**
- `user_config.json` (개인 설정)
- `__pycache__/` (Python 캐시)
- `*.html` (덤프 파일들)
- `test_requests.py` (개발 테스트용)
- `check_deployment.py` (선택사항)

## 🚀 배포 방법

### 방법 1: GitHub 웹 인터페이스 (추천)

1. **GitHub 저장소 생성**
   - https://github.com/new
   - Repository name: `job-dashboard`
   - Public 선택
   - Create repository

2. **파일 업로드**
   - "uploading an existing file" 클릭
   - 위의 12개 파일 드래그 앤 드롭
   - Commit message: "Initial commit"
   - Commit changes

3. **Streamlit Cloud 배포**
   - https://streamlit.io/cloud
   - New app → GitHub 저장소 선택
   - Main file: `app.py`
   - Advanced settings → Secrets:
     ```toml
     NOTION_TOKEN = "실제-토큰"
     NOTION_DATABASE_ID = "실제-DB-ID"
     ```
   - Deploy!

### 방법 2: GitHub Desktop (Git UI 도구)

1. GitHub Desktop 설치: https://desktop.github.com/
2. File → Add local repository
3. 커밋 후 Publish repository

## 🧪 로컬 테스트

배포 전에 반드시 로컬에서 테스트:

```bash
# 1. 의존성 확인
python -c "import streamlit; import requests; import bs4; import notion_client; print('OK')"

# 2. 배포 체크
python check_deployment.py

# 3. 앱 실행
streamlit run app.py
```

### 테스트 체크리스트
- [ ] 앱이 로드되는가?
- [ ] 날짜 선택이 작동하는가?
- [ ] "공고 수집만" 버튼이 작동하는가?
- [ ] Notion 연동이 작동하는가?

## ⚠️ 중요 주의사항

### 1. API 키 보안
- `.streamlit/secrets.toml` 절대 GitHub 업로드 금지
- `.gitignore`에 이미 포함되어 있음
- Streamlit Cloud Secrets에만 입력

### 2. Notion 데이터베이스 설정
데이터베이스에 다음 속성 필요:
- 공고명 (Title)
- 링크 (URL)
- 지원기업 (Text)
- 지원 마감일 (Date)
- 출처 (Select)
- 경력 (Text)
- 학력 (Text)
- 고용형태 (Text)
- 근무지역 (Text)
- 급여 (Text)

### 3. Streamlit Cloud 메모리 제한
- 무료 플랜: 1GB RAM
- 검색 소스 1~2개 권장
- 키워드 5개 이하 권장
- 마감일 범위 30일 이하 권장

## 🐛 예상되는 문제와 해결

### 문제 1: Streamlit Cloud 메모리 오류
**원인**: 너무 많은 데이터 수집
**해결**: 
- 검색 소스 줄이기
- 키워드 수 줄이기
- 마감일 범위 단축

### 문제 2: Notion API 오류
**원인**: Secrets 설정 오류
**해결**:
- Streamlit Cloud Secrets 확인
- Notion Integration 연결 확인
- Database 속성 확인

### 문제 3: 스크래핑 결과 없음
**원인**: 조건이 너무 엄격
**해결**:
- 키워드 단순화 (예: "대학교 행정직" → "대학교")
- 마감일 범위 확대
- 실제 사이트에서 검색 테스트

## 📞 도움말

- **Streamlit 문서**: https://docs.streamlit.io/
- **Notion API 문서**: https://developers.notion.com/
- **프로젝트 가이드**: `GITHUB_UPLOAD_GUIDE.md` 참고

## ✅ 최종 체크리스트

- [ ] `check_deployment.py` 실행 → 모든 파일 확인
- [ ] 로컬에서 `streamlit run app.py` 테스트 성공
- [ ] GitHub 저장소 생성
- [ ] 12개 필수 파일 업로드
- [ ] `.streamlit/secrets.toml` GitHub에 없는지 재확인
- [ ] Streamlit Cloud 배포
- [ ] Streamlit Secrets 설정
- [ ] 배포된 앱 테스트 성공
- [ ] README.md에 라이브 URL 추가 (선택)

---

**🎉 모든 준비가 완료되었습니다!**

위의 단계를 따라하시면 성공적으로 배포할 수 있습니다.
