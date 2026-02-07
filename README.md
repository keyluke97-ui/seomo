# 💼 채용 공고 자동화 대시보드

취준생을 위한 채용 공고 자동 수집 및 Notion 연동 대시보드입니다.

## ✨ 주요 기능

- 📅 **지원 마감일 기준 검색**: 원하는 기간의 채용 공고만 필터링
- 🌐 **다중 채용 사이트 지원**: 사람인, 인크루트, 잡코리아
- 💼 **직군별 키워드 관리**: 직군과 키워드를 자유롭게 추가/수정
- 📝 **Notion 자동 저장**: 수집한 공고를 Notion 데이터베이스에 자동 저장
- 🔍 **중복 제거**: 이미 저장된 공고는 자동으로 제외
- 🚀 **Streamlit Cloud 배포 가능**: 별도 서버 없이 무료로 사용

## 🛠️ 기술 스택

- **Frontend**: Streamlit
- **Scraping**: Requests + BeautifulSoup4 (메모리 최적화)
- **Database**: Notion API
- **Deployment**: Streamlit Community Cloud

## 📋 사전 준비

### 1. Notion 설정

1. [Notion Integrations](https://www.notion.so/my-integrations)에서 새 통합 생성
2. Integration Token 복사
3. Notion에서 채용 공고용 데이터베이스 생성
4. 데이터베이스에 다음 속성(Properties) 추가:
   - **공고명** (제목/Title)
   - **링크** (URL)
   - **지원기업** (Text)
   - **지원 마감일** (Date)
   - **출처** (Select)
   - **경력** (Text)
   - **학력** (Text)
   - **고용형태** (Text)
   - **근무지역** (Text)
   - **급여** (Text)
5. 데이터베이스 설정 → Connections에서 생성한 Integration 연결
6. 데이터베이스 URL에서 ID 복사 (URL 형식: `https://www.notion.so/[workspace]/[database_id]?v=...`)

## 🚀 로컬 실행

### 1. 저장소 클론

```bash
git clone https://github.com/YOUR_USERNAME/job-dashboard.git
cd job-dashboard
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. Secrets 설정

`.streamlit/secrets.toml` 파일 생성 및 설정:

```toml
NOTION_TOKEN = "your-notion-integration-token"
NOTION_DATABASE_ID = "your-notion-database-id"
```

> ⚠️ **주의**: `secrets.toml` 파일은 절대 GitHub에 업로드하지 마세요!

### 4. 앱 실행

```bash
streamlit run app.py
```

## ☁️ Streamlit Cloud 배포

### 1. GitHub에 푸시

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Streamlit Cloud 배포

1. [Streamlit Cloud](https://streamlit.io/cloud)에 로그인
2. "New app" 클릭
3. GitHub 저장소 선택
4. Main file: `app.py`
5. **Advanced settings** → **Secrets**에 아래 내용 입력:

```toml
NOTION_TOKEN = "your-notion-integration-token"
NOTION_DATABASE_ID = "your-notion-database-id"
```

6. "Deploy!" 클릭

## 📖 사용 방법

### 1️⃣ 검색 기간 설정
지원 마감일 기준으로 검색할 기간을 선택합니다.

### 2️⃣ 검색 소스 선택
사람인, 인크루트, 잡코리아 중 원하는 사이트를 선택합니다.

### 3️⃣ 직군 및 키워드 설정
- 기본 제공 직군: 대학교 행정직, 교직원, 은행, 유학
- "➕" 버튼으로 새 직군 추가 가능
- 키워드는 쉼표로 구분하여 입력

### 4️⃣ 실행
- **🔍 공고 수집만**: Notion 없이 테스트용 (결과만 화면에 표시)
- **🔍 공고 찾기 & Notion 저장**: 수집 + Notion 자동 저장

## 📁 프로젝트 구조

```
job-dashboard/
├── app.py              # Streamlit 메인 UI
├── scraper.py          # 웹 스크래핑 로직
├── notion_bot.py       # Notion API 연동
├── config.py           # 설정 관리
├── requirements.txt    # Python 의존성
├── packages.txt        # 시스템 패키지 (비어있음)
├── .gitignore
├── .streamlit/
│   └── secrets.toml    # Notion API 키 (로컬 전용)
└── user_config.json    # 사용자 키워드 설정 (자동 생성, gitignore됨)
```

## 🔧 트러블슈팅

### Notion 연결 오류
- Notion Integration Token이 올바른지 확인
- Database ID가 정확한지 확인
- Notion 데이터베이스에 Integration이 연결되어 있는지 확인

### 스크래핑 결과가 없음
- 검색 키워드가 너무 구체적이지 않은지 확인
- 마감일 범위를 넓혀보기
- 해당 기간에 실제로 공고가 있는지 채용 사이트에서 직접 확인

### Streamlit Cloud 메모리 오류
- 검색 소스를 1~2개로 제한
- 키워드 수를 줄이기
- 마감일 범위를 짧게 설정

## 📝 라이선스

MIT License

## 🙏 기여

버그 리포트, 기능 제안, Pull Request 환영합니다!

---

**⭐ 이 프로젝트가 도움이 되셨다면 Star를 눌러주세요!**
