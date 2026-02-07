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
    
    col_btn1, col_btn2 = st.columns([1, 1])
    
    # 세션 상태 초기화 (검색 결과가 없으면)
    if "scraped_jobs" not in st.session_state:
        st.session_state.scraped_jobs = []
    
    with col_btn1:
        # 기존: 공고 수집만 -> 변경: 공고 검색하기 (Flow 1단계)
        search_button = st.button(
            "🔍 공고 검색하기",
            key="search_btn",
            use_container_width=True,
            help="Notion에 저장하기 전에 먼저 검색 결과를 확인합니다."
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
    
    # 1단계: 검색 실행
    if search_button:
        if not validate_inputs():
            st.stop()
        
        # 상태 메시지 컨테이너
        status_container = st.status("채용 공고를 검색하고 있습니다...", expanded=True)
        
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            # 진행 상황 콜백
            def update_status(msg):
                status_container.write(f"👉 {msg}")
            
            # 스크래핑 실행
            jobs = scrape_jobs(
                sources=selected_sources,
                keywords=new_keywords,
                deadline_start=start_datetime,
                deadline_end=end_datetime,
                progress_callback=update_status  # 문자열 콜백으로 변경
            )
            
            st.session_state.scraped_jobs = jobs
            status_container.update(label="검색 완료!", state="complete", expanded=False)
            
        except Exception as e:
            status_container.update(label="오류 발생", state="error")
            st.error(f"검색 중 오류가 발생했습니다: {e}")
            import traceback
            st.code(traceback.format_exc())

    # 2단계: 결과 미리보기 및 저장 (검색 결과가 있을 때 표시)
    if st.session_state.scraped_jobs:
        st.markdown("---")
        st.markdown(f"### 📋 검색 결과 확인 ({len(st.session_state.scraped_jobs)}건)")
        
        # DataFrame 생성을 위한 데이터 가공
        import pandas as pd
        
        # 표시할 데이터만 추출
        display_data = []
        for job in st.session_state.scraped_jobs:
            display_data.append({
                "선택": True,  # 기본값 체크
                "공고명": job.get("title"),
                "회사명": job.get("company"),
                "마감일": job.get("deadline"),
                "링크": job.get("url")
            })
            
        df = pd.DataFrame(display_data)
        
        # 데이터 에디터 (체크박스 기능)
        edited_df = st.data_editor(
            df,
            column_config={
                "선택": st.column_config.CheckboxColumn(
                    "저장",
                    help="Notion에 저장할 공고를 선택하세요",
                    default=True,
                ),
                "링크": st.column_config.LinkColumn("공고 링크"),
            },
            hide_index=True,
            use_container_width=True
        )
        
        # 선택된 공고만 필터링
        selected_indices = [
            i for i, row in edited_df.iterrows() if row["선택"]
        ]
        
        col_save, col_info = st.columns([1, 2])
        
        with col_save:
            save_button = st.button(
                f"💾 선택한 {len(selected_indices)}개 공고 Notion 저장",
                type="primary",
                use_container_width=True,
                disabled=len(selected_indices) == 0
            )

        # 3단계: 저장 실행
        if save_button:
            # 선택된 원본 데이터 가져오기
            jobs_to_save = [st.session_state.scraped_jobs[i] for i in selected_indices]
            
            # Notion 연결 확인
            try:
                notion_token = st.secrets.get("NOTION_TOKEN", "") or st.secrets.get("notion", {}).get("token", "")
                notion_db_id = st.secrets.get("NOTION_DATABASE_ID", "") or st.secrets.get("notion", {}).get("database_id", "")
                
                if not notion_token or not notion_db_id or "your-" in notion_token:
                    st.error("⚠️ Notion API 설정이 필요합니다. `.streamlit/secrets.toml` 파일을 확인해주세요.")
                    st.stop()
                
                notion_bot = NotionBot(notion_token, notion_db_id)
                
                # 저장 진행
                save_status = st.status("Notion에 저장 중입니다...", expanded=True)
                progress_bar = save_status.progress(0)
                
                def notion_progress(p):
                    progress_bar.progress(int(p * 100))
                
                result = notion_bot.batch_create_jobs(jobs_to_save, progress_callback=notion_progress)
                
                save_status.update(label="저장 완료!", state="complete", expanded=False)
                
                # 결과 리포트
                if result['failed'] == 0:
                    st.success(f"✅ **{result['saved']}개** 저장 성공! (중복 제외: {result['skipped']}개)")
                    st.balloons()
                else:
                    st.warning(f"⚠️ {result['saved']}개 성공, {result['failed']}개 실패")
                    with st.expander("실패 상세 내용 보기"):
                        for err in result.get('errors', []):
                            st.text(err)
                
                # 바로가기 링크 버튼
                db_url = f"https://www.notion.so/{notion_db_id.replace('-', '')}"
                st.markdown(f"""
                    <a href="{db_url}" target="_blank" style="text-decoration: none;">
                        <button style="
                            background-color: #4CAF50;
                            border: none;
                            color: white;
                            padding: 10px 24px;
                            text-align: center;
                            text-decoration: none;
                            display: inline-block;
                            font-size: 16px;
                            margin: 4px 2px;
                            cursor: pointer;
                            border-radius: 4px;
                            width: 100%;">
                            👉 내 Notion 페이지 바로가기
                        </button>
                    </a>
                    """, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Notion 저장 중 오류 발생: {e}")
                
    elif search_button: # 검색 버튼 눌렀는데 결과가 없는 경우
         st.markdown("---")
         st.info("오늘은 조건에 맞는 새로운 공고가 없네요! ☕\n\n잠시 쉬어가라는 뜻인가 봐요. 내일 다시 확인해보세요!")


if __name__ == "__main__":
    main()
