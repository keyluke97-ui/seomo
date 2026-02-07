"""
app.py - Streamlit 메인 UI
취준생 맞춤형 채용 공고 자동화 대시보드
"""
import streamlit as st
from datetime import datetime, timedelta
from config import (
    load_config, save_config, get_keywords,
    add_category, update_keywords, get_all_categories,
    JOB_SOURCES
)
from scraper import scrape_jobs
from notion_bot import NotionBot

# 페이지 설정
st.set_page_config(
    page_title="취준생 채용 공고 대시보드",
    page_icon="💼",
    layout="wide"
)

# CSS 스타일
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #6b7280;
        margin-bottom: 2rem;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        font-size: 1.1rem;
        font-weight: 600;
        border-radius: 0.5rem;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #5a67d8 0%, #6b46c1 100%);
    }
    .result-card {
        background: #f8fafc;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
    }
    .tag {
        display: inline-block;
        background: #e0e7ff;
        color: #4338ca;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        margin: 0.125rem;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """세션 상태 초기화"""
    if "config" not in st.session_state:
        st.session_state.config = load_config()
    if "current_keywords" not in st.session_state:
        st.session_state.current_keywords = []
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "show_add_category" not in st.session_state:
        st.session_state.show_add_category = False


def main():
    """메인 앱"""
    init_session_state()
    
    # 헤더
    st.markdown('<p class="main-header">💼 채용 공고 자동화 대시보드</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">원하는 조건으로 채용 공고를 검색하고 Notion에 자동 저장하세요</p>', unsafe_allow_html=True)
    
    # 메인 컨텐츠
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📅 Step 1: 검색 기간 설정")
        st.caption("지원 마감일 기준으로 필터링됩니다")
        
        today = datetime.now().date()
        default_end = today + timedelta(days=30)
        
        date_range = st.date_input(
            "마감일 범위 선택",
            value=(today, default_end),
            min_value=today,
            max_value=today + timedelta(days=365),
            key="date_range"
        )
        
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = date_range
        
        st.markdown("---")
        
        st.markdown("### 🌐 Step 2: 검색 소스 선택")
        
        selected_sources = []
        source_cols = st.columns(2)
        
        for i, (source_name, source_info) in enumerate(JOB_SOURCES.items()):
            with source_cols[i % 2]:
                if st.checkbox(
                    source_name,
                    value=source_info["enabled"],
                    key=f"source_{source_name}",
                    disabled=not source_info["enabled"] and source_name == "대학교 사이트"
                ):
                    if source_info["enabled"] or source_name != "대학교 사이트":
                        selected_sources.append(source_name)
        
        if "대학교 사이트" in selected_sources:
            selected_sources.remove("대학교 사이트")
            st.info("대학교 사이트는 추후 지원 예정입니다.")
    
    with col2:
        st.markdown("### 💼 Step 3: 직군 및 키워드 설정")
        
        categories = get_all_categories(st.session_state.config)
        
        # 직군 추가 버튼
        col_cat, col_add = st.columns([4, 1])
        with col_cat:
            selected_category = st.radio(
                "직군 선택",
                options=categories,
                horizontal=True,
                key="category"
            )
        with col_add:
            if st.button("➕", key="add_cat_btn", help="새 직군 추가"):
                st.session_state.show_add_category = not st.session_state.show_add_category
        
        # 새 직군 추가 폼
        if st.session_state.show_add_category:
            with st.expander("새 직군 추가", expanded=True):
                new_cat_name = st.text_input("직군 이름", key="new_cat_name")
                new_cat_keywords = st.text_input(
                    "키워드 (쉼표로 구분)",
                    placeholder="예: 마케팅, 광고, 브랜드",
                    key="new_cat_keywords"
                )
                if st.button("추가", key="save_new_cat"):
                    if new_cat_name and new_cat_keywords:
                        keywords_list = [k.strip() for k in new_cat_keywords.split(",") if k.strip()]
                        st.session_state.config = add_category(new_cat_name, keywords_list, st.session_state.config)
                        st.session_state.show_add_category = False
                        st.rerun()
        
        # 현재 직군의 키워드 표시 및 편집
        current_keywords = get_keywords(selected_category, st.session_state.config)
        
        st.markdown("**🏷️ 검색 키워드**")
        st.caption("키워드를 수정하면 자동 저장됩니다")
        
        # 키워드 태그 표시
        keyword_tags = st.text_input(
            "키워드 편집",
            value=", ".join(current_keywords),
            key="keyword_input",
            label_visibility="collapsed"
        )
        
        # 키워드 변경 감지 및 저장
        new_keywords = [k.strip() for k in keyword_tags.split(",") if k.strip()]
        if new_keywords != current_keywords:
            st.session_state.config = update_keywords(selected_category, new_keywords, st.session_state.config)
            st.success("키워드가 저장되었습니다!", icon="✅")
        
        # 현재 키워드 태그 형태로 표시
        if new_keywords:
            tags_html = " ".join([f'<span class="tag">{k}</span>' for k in new_keywords])
            st.markdown(f'<div style="margin-top: 0.5rem;">{tags_html}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Step 4: 실행 버튼
    st.markdown("### 🚀 Step 4: 실행")
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
    
    with col_btn1:
        scrape_only_button = st.button(
            "🔍 공고 수집만",
            key="scrape_only_btn",
            use_container_width=True,
            help="Notion 저장 없이 스크래핑만 실행"
        )
    
    with col_btn2:
        search_button = st.button(
            "🔍 공고 찾기 & Notion 저장",
            key="search_btn",
            use_container_width=True
        )
    
    # 공통 검증
    def validate_inputs():
        if not selected_sources:
            st.error("검색할 소스를 하나 이상 선택해주세요.")
            return False
        if not new_keywords:
            st.error("검색 키워드를 입력해주세요.")
            return False
        return True
    
    # 스크래핑만 실행
    if scrape_only_button:
        if not validate_inputs():
            st.stop()
        
        progress_container = st.container()
        
        with progress_container:
            st.markdown("#### 🔄 검색 중...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("채용 공고 수집 중...")
            
            try:
                start_datetime = datetime.combine(start_date, datetime.min.time())
                end_datetime = datetime.combine(end_date, datetime.max.time())
                
                jobs = scrape_jobs(
                    sources=selected_sources,
                    keywords=new_keywords,
                    deadline_start=start_datetime,
                    deadline_end=end_datetime,
                    progress_callback=lambda p: progress_bar.progress(int(p * 100))
                )
                
                progress_bar.progress(100)
                status_text.empty()
                
                if not jobs:
                    st.warning("검색 조건에 맞는 공고가 없습니다.")
                else:
                    st.success(f"✅ **{len(jobs)}개**의 공고를 찾았습니다!")
                    st.session_state.search_results = jobs
                    
            except Exception as e:
                st.error(f"오류 발생: {e}")
    
    # 검색 + Notion 저장 실행
    if search_button:
        if not validate_inputs():
            st.stop()
        
        # Notion 연결 확인
        try:
            notion_token = st.secrets.get("NOTION_TOKEN", "")
            notion_db_id = st.secrets.get("NOTION_DATABASE_ID", "")
            
            if not notion_token or not notion_db_id or "your-" in notion_token:
                st.error("⚠️ Notion API 설정이 필요합니다. `.streamlit/secrets.toml` 파일을 확인해주세요.")
                st.info("""
                **설정 방법:**
                1. [Notion Integrations](https://www.notion.so/my-integrations)에서 새 통합 생성
                2. 토큰 복사 후 `secrets.toml`에 입력
                3. Notion 데이터베이스에서 통합 연결
                
                **💡 Notion 없이 테스트하려면** 왼쪽의 "🔍 공고 수집만" 버튼을 사용하세요.
                """)
                st.stop()
            
            notion_bot = NotionBot(notion_token, notion_db_id)
        except Exception as e:
            st.error(f"Notion 연결 실패: {e}")
            st.stop()
        
        # 진행 상태 표시
        progress_container = st.container()
        
        with progress_container:
            st.markdown("#### 🔄 검색 중...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 1단계: 크롤링
            status_text.text("채용 공고 수집 중...")
            
            try:
                start_datetime = datetime.combine(start_date, datetime.min.time())
                end_datetime = datetime.combine(end_date, datetime.max.time())
                
                jobs = scrape_jobs(
                    sources=selected_sources,
                    keywords=new_keywords,
                    deadline_start=start_datetime,
                    deadline_end=end_datetime,
                    progress_callback=lambda p: progress_bar.progress(int(p * 50))
                )
                
                if not jobs:
                    st.warning("검색 조건에 맞는 공고가 없습니다.")
                    st.stop()
                
                status_text.text(f"{len(jobs)}개의 공고를 찾았습니다. Notion에 저장 중...")
                
                # 2단계: Notion 저장
                def notion_progress(p):
                    progress_bar.progress(50 + int(p * 50))
                
                result = notion_bot.batch_create_jobs(jobs, progress_callback=notion_progress)
                
                progress_bar.progress(100)
                status_text.empty()
                
                # 결과 표시
                st.success(f"""
                ✅ **완료!**
                - 저장됨: **{result['saved']}개**
                - 중복 제외: {result['skipped']}개
                - 실패: {result['failed']}개
                """)
                
                st.session_state.search_results = jobs
                
            except Exception as e:
                import traceback
                error_msg = traceback.format_exc()
                st.error(f"오류 발생: {e}")
                with st.expander("에러 상세 정보"):
                    st.code(error_msg, language="python")

    # 검색 결과 표시
    if st.session_state.search_results:
        st.markdown("---")
        st.markdown("### 📋 검색 결과")
        
        # 저장 결과가 있을 경우 (Notion 저장 시도 후)
        # result 변수가 로컬 범위에 존재하는지 확인 (검색 버튼을 눌렀을 때만 존재)
        if 'result' in locals() and result and result.get('failed', 0) > 0:
            st.error(f"⚠️ {result['failed']}개의 공고 저장에 실패했습니다.")
            with st.expander("실패 상세 내용 보기"):
                for err in result.get('errors', []):
                    st.text(err)
                
                st.info("""
                **Notion 저장 실패 시 확인사항:**
                1. `.streamlit/secrets.toml`에 `NOTION_TOKEN`과 `NOTION_DATABASE_ID`가 올바른지 확인하세요.
                2. Notion 데이터베이스에 통합(Integration)이 연결되어 있는지 확인하세요. (데이터베이스 우측 상단 ... > 'Add connections')
                3. 데이터베이스 속성(컬럼) 이름이 코드와 일치하는지 확인하세요. (공고명, 링크, 지원기업, 직무, 급여, 담당업무, 근무형태, 근무시간, 근무예정일, 근무기간, 지원상태, 지원 마감일)
                """)
        
        for job in st.session_state.search_results[:10]:
            with st.container():
                st.markdown(f"""
                <div class="result-card">
                    <strong>{job.get('title', '제목 없음')}</strong><br>
                    <span style="color: #6b7280;">🏢 {job.get('company', '-')} | ⏰ {job.get('deadline', '-')}</span>
                </div>
                """, unsafe_allow_html=True)
        
        if len(st.session_state.search_results) > 10:
            st.info(f"... 외 {len(st.session_state.search_results) - 10}개의 공고가 더 있습니다.")


if __name__ == "__main__":
    main()
