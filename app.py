"""
app.py - Streamlit 메인 UI
취준생 맞춤형 채용 공고 자동화 대시보드

리팩토링 내역:
- 검색 결과 없음 분기 로직 수정
- 지역 필터 UI 추가
- scrape_jobs에 location_filter 전달
"""
import streamlit as st
from datetime import datetime, timedelta
from config import (
    load_config, save_config, get_keywords,
    add_category, update_keywords, get_all_categories,
    JOB_SOURCES, LOCATION_OPTIONS
)
from scraper import scrape_jobs, get_default_negative, enrich_jobs
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
    if "scraped_jobs" not in st.session_state:
        st.session_state.scraped_jobs = []
    if "search_executed" not in st.session_state:
        st.session_state.search_executed = False


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

        st.markdown("---")

        # [B] 지역 필터 — 기본값 서울/경기
        st.markdown("### 📍 Step 2.5: 지역 필터")
        st.caption("기본: 서울/경기 | 전국 검색하려면 선택 해제하세요")
        selected_locations = st.multiselect(
            "지역 선택",
            options=LOCATION_OPTIONS,
            default=["서울", "경기"],
            key="location_filter",
            label_visibility="collapsed"
        )

    with col2:
        st.header("Step 3: 직군 및 키워드 설정")

        categories = get_all_categories(st.session_state.config)

        if "selected_category" not in st.session_state:
            st.session_state.selected_category = categories[0] if categories else "기본"

        st.write("직군 선택")

        cols = st.columns(len(categories) + 1 if categories else 1)

        def set_category(cat):
            st.session_state.selected_category = cat
            st.rerun()

        for i, cat in enumerate(categories):
            with cols[i]:
                btn_type = "primary" if st.session_state.selected_category == cat else "secondary"
                if st.button(cat, key=f"cat_{i}", type=btn_type, use_container_width=True):
                    set_category(cat)

        with cols[len(categories) if categories else 0]:
            with st.popover("➕", use_container_width=True):
                new_cat_name = st.text_input("새 직군 이름")
                new_cat_keywords = st.text_input("키워드 (쉼표 구분)")
                if st.button("추가"):
                    if new_cat_name and new_cat_keywords:
                        k_list = [k.strip() for k in new_cat_keywords.split(",") if k.strip()]
                        st.session_state.config = add_category(new_cat_name, k_list, st.session_state.config)
                        st.success(f"'{new_cat_name}' 추가됨!")
                        st.rerun()

        selected_category = st.session_state.selected_category
        current_keywords = get_keywords(selected_category, st.session_state.config)

        st.subheader(f"🏷️ '{selected_category}' 검색 키워드")
        st.caption("키워드를 수정하면 자동 저장됩니다")

        keyword_tags = st.text_input(
            "키워드 편집",
            value=", ".join(current_keywords),
            key="keyword_input",
            label_visibility="collapsed"
        )

        new_keywords = [k.strip() for k in keyword_tags.split(",") if k.strip()]
        if new_keywords != current_keywords:
            st.session_state.config = update_keywords(selected_category, new_keywords, st.session_state.config)
            st.success("키워드가 저장되었습니다!", icon="✅")

        if new_keywords:
            tags_html = " ".join([f'<span class="tag">{k}</span>' for k in new_keywords])
            st.markdown(f'<div style="margin-top: 0.5rem;">{tags_html}</div>', unsafe_allow_html=True)

    # ──────────────────────────────────────
    # Step 3.5: 제외 키워드 설정 (네거티브 필터)
    # ──────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🚫 Step 3.5: 제외 키워드")
    st.caption("제목에 아래 키워드가 포함된 공고는 자동으로 제외됩니다. 쉼표로 구분하여 자유롭게 편집하세요.")

    # 선택된 직군의 기본 네거티브 로드
    default_neg = get_default_negative(selected_category)

    # 세션 초기화 (직군 변경 시 리셋)
    if st.session_state.get("_last_filter_cat") != selected_category:
        st.session_state["_last_filter_cat"] = selected_category
        st.session_state[f"neg_{selected_category}"] = ", ".join(default_neg)

    neg_input = st.text_area(
        "제외 키워드",
        value=st.session_state.get(f"neg_{selected_category}", ", ".join(default_neg)),
        key=f"neg_input_{selected_category}",
        height=80,
        label_visibility="collapsed",
        placeholder="미화, 조리, 경비, 청소 ..."
    )
    neg_keywords = [k.strip() for k in neg_input.split(",") if k.strip()]
    st.session_state[f"neg_{selected_category}"] = neg_input

    if neg_keywords:
        neg_tags = " ".join([f'<span style="display:inline-block;background:#fee2e2;color:#dc2626;padding:0.15rem 0.5rem;border-radius:9999px;font-size:0.8rem;margin:0.1rem;">{k}</span>' for k in neg_keywords])
        st.markdown(neg_tags, unsafe_allow_html=True)

    st.markdown("---")

    # Step 4: 실행 버튼
    st.markdown("### 🚀 Step 4: 실행")

    # 공통 검증
    def validate_inputs():
        if not selected_sources:
            st.error("검색할 소스를 하나 이상 선택해주세요.")
            return False
        if not new_keywords:
            st.error("검색 키워드를 입력해주세요.")
            return False
        return True

    search_button = st.button(
        "🔍 공고 검색하기",
        key="search_btn",
        use_container_width=True,
        help="Notion에 저장하기 전에 먼저 검색 결과를 확인합니다."
    )

    # 1단계: 검색 실행
    if search_button:
        if not validate_inputs():
            st.stop()

        # [FIX] 재검색 시 이전 상태 리셋
        st.session_state.scraped_jobs = []
        st.session_state.search_executed = False

        status_container = st.status("채용 공고를 검색하고 있습니다...", expanded=True)

        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            def update_status(msg):
                status_container.write(f"👉 {msg}")

            # 지역 필터 전달 (비어있으면 None → 전국)
            loc_filter = selected_locations if selected_locations else None

            # 제외 키워드 (UI에서 편집한 값 실시간 반영)
            user_neg = [k.strip() for k in st.session_state.get(f"neg_{selected_category}", "").split(",") if k.strip()] or None

            jobs = scrape_jobs(
                sources=selected_sources,
                keywords=new_keywords,
                deadline_start=start_datetime,
                deadline_end=end_datetime,
                category=selected_category,
                location_filter=loc_filter,
                custom_negative=user_neg,
                progress_callback=update_status
            )

            st.session_state.scraped_jobs = jobs
            st.session_state.search_executed = True
            status_container.update(label="검색 완료!", state="complete", expanded=False)

        except Exception as e:
            status_container.update(label="오류 발생", state="error")
            st.error(f"검색 중 오류가 발생했습니다: {e}")
            import traceback
            st.code(traceback.format_exc())

    # 2단계: 결과 표시
    if st.session_state.scraped_jobs:
        st.markdown("---")
        st.markdown(f"### 📋 검색 결과 확인 ({len(st.session_state.scraped_jobs)}건)")

        import pandas as pd

        # [FIX] 소스별 건수 요약 표시
        source_counts = {}
        for job in st.session_state.scraped_jobs:
            src = job.get("source", "기타")
            source_counts[src] = source_counts.get(src, 0) + 1
        summary_parts = [f"{src} {cnt}건" for src, cnt in source_counts.items()]
        if summary_parts:
            st.caption(f"📊 소스별: {' / '.join(summary_parts)}")

        # [FIX-JK] 잡코리아가 선택됐는데 결과 0건이면 경고
        if "잡코리아" in selected_sources and source_counts.get("잡코리아", 0) == 0:
            st.warning("⚠️ 잡코리아에서 결과를 가져오지 못했습니다. 배포 서버 IP가 차단된 것으로 보입니다. 로컬 환경에서 실행하면 정상 작동할 수 있습니다.")

        display_data = []
        for job in st.session_state.scraped_jobs:
            display_data.append({
                "선택": True,
                "소스": job.get("source", ""),
                "공고명": job.get("title"),
                "회사명": job.get("company"),
                "급여": job.get("salary", ""),
                "마감일": job.get("deadline"),
                "링크": job.get("url")
            })

        df = pd.DataFrame(display_data)

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

        selected_indices = [
            i for i, row in edited_df.iterrows() if row["선택"]
        ]

        col_enrich, col_save, col_info = st.columns([1, 1, 1])

        with col_enrich:
            # [Phase2] 상세 보강 버튼
            salary_empty = sum(1 for j in st.session_state.scraped_jobs if not j.get("salary", "").strip())
            enrich_button = st.button(
                f"🔍 급여정보 보강 ({salary_empty}건 미확인)",
                use_container_width=True,
                disabled=salary_empty == 0,
                help="급여 정보가 없는 공고의 상세 페이지를 방문하여 급여 정보를 가져옵니다."
            )

        with col_save:
            save_button = st.button(
                f"💾 선택한 {len(selected_indices)}개 공고 Notion 저장",
                type="primary",
                use_container_width=True,
                disabled=len(selected_indices) == 0
            )

        # 2.5단계: 상세 보강 실행
        if enrich_button:
            enrich_status = st.status("상세 페이지에서 급여 정보를 가져오고 있습니다...", expanded=True)

            def enrich_progress(msg):
                enrich_status.write(f"👉 {msg}")

            try:
                st.session_state.scraped_jobs = enrich_jobs(
                    st.session_state.scraped_jobs,
                    progress_callback=enrich_progress
                )
                enrich_status.update(label="급여 보강 완료!", state="complete", expanded=False)
                st.rerun()
            except Exception as e:
                enrich_status.update(label="보강 중 오류", state="error")
                st.error(f"상세 보강 중 오류: {e}")

        # 3단계: 저장 실행
        if save_button:
            jobs_to_save = [st.session_state.scraped_jobs[i] for i in selected_indices]

            try:
                notion_token = st.secrets.get("NOTION_TOKEN", "") or st.secrets.get("notion", {}).get("token", "")
                notion_db_id = st.secrets.get("NOTION_DATABASE_ID", "") or st.secrets.get("notion", {}).get("database_id", "")

                if not notion_token or not notion_db_id or "your-" in notion_token:
                    st.error("⚠️ Notion API 설정이 필요합니다. `.streamlit/secrets.toml` 파일을 확인해주세요.")
                    st.stop()

                notion_bot = NotionBot(notion_token, notion_db_id)

                save_status = st.status("Notion에 저장 중입니다...", expanded=True)
                progress_bar = save_status.progress(0)

                def notion_progress(p):
                    progress_bar.progress(int(p * 100))

                result = notion_bot.batch_create_jobs(jobs_to_save, progress_callback=notion_progress)

                save_status.update(label="저장 완료!", state="complete", expanded=False)

                if result['failed'] == 0:
                    st.success(f"✅ **{result['saved']}개** 저장 성공! (중복 제외: {result['skipped']}개)")
                    st.balloons()
                else:
                    st.warning(f"⚠️ {result['saved']}개 성공, {result['failed']}개 실패")
                    with st.expander("실패 상세 내용 보기"):
                        for err in result.get('errors', []):
                            st.text(err)

                db_url = f"https://www.notion.so/{notion_db_id.replace('-', '')}"
                st.link_button("👉 내 Notion 페이지 바로가기", db_url, use_container_width=True)

            except Exception as e:
                st.error(f"Notion 저장 중 오류 발생: {e}")

    # [FIX] 검색 실행했는데 결과가 없는 경우 — session_state 기반으로 판단
    elif st.session_state.get("search_executed", False) and not st.session_state.scraped_jobs:
        st.markdown("---")
        st.info("오늘은 조건에 맞는 새로운 공고가 없네요! ☕\n\n검색 키워드나 기간을 조정해보세요.")


if __name__ == "__main__":
    main()
