"""
notion_bot.py - Notion API 연동 모듈

리팩토링 내역:
- dead code (return result) 제거
- 중복 체크 기능 복원 (주석 해제)
- 근무형태 중복 속성 설정 제거
- 날짜 파싱 연도 넘김 로직 개선
- 코드가 사용하는 Notion DB 속성 목록 명시
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dateutil import parser as date_parser
from notion_client import Client
import streamlit as st


# 코드에서 사용하는 Notion DB 속성 목록 (새 DB 만들 때 참고)
REQUIRED_PROPERTIES = {
    "공고명": "title",        # 필수 (Title)
    "링크": "url",            # URL
    "지원기업": "rich_text",   # Text
    "지원 마감일": "date",     # Date
    "직군": "select",         # Select (대학교 행정직, 교직원, 은행, 유학 등)
    "직무": "rich_text",      # Text
    "근무형태": "select",     # Select (정규직, 계약직, 인턴 등)
    "급여": "rich_text",      # Text
    "담당업무": "rich_text",   # Text
    "근무시간": "rich_text",   # Text
    "근무예정일": "rich_text",  # Text
    "근무기간": "rich_text",   # Text
    "지원상태": "select",     # Select (접수 전, 서류접수, 면접 등)
}


class NotionBot:
    """Notion 데이터베이스와 연동하여 채용 공고를 저장하는 클래스"""

    def __init__(self, token: str = None, database_id: str = None):
        self.token = token or st.secrets.get("NOTION_TOKEN", "")
        self.database_id = database_id or st.secrets.get("NOTION_DATABASE_ID", "")

        if not self.token or not self.database_id:
            raise ValueError("Notion token과 database_id가 필요합니다.")

        self.client = Client(auth=self.token)

    def check_duplicate(self, url: str) -> bool:
        """URL이 이미 데이터베이스에 존재하는지 확인"""
        if not url:
            return False
        try:
            response = self.client.databases.query(
                **{
                    "database_id": self.database_id,
                    "filter": {
                        "property": "링크",
                        "url": {
                            "equals": url
                        }
                    }
                }
            )
            return len(response.get("results", [])) > 0
        except Exception as e:
            print(f"중복 확인 중 오류: {e}")
            return False

    def create_job_page(self, job_data: Dict[str, Any]) -> Optional[str]:
        """채용 공고 페이지 생성 (중복 체크 포함)"""
        # [FIX] 중복 체크 복원
        url = job_data.get("url", "")
        if url and self.check_duplicate(url):
            return None  # 중복 → 스킵

        properties = self._build_properties(job_data)
        children = self._build_content_blocks(job_data.get("body", ""))

        try:
            response = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
                children=children
            )
            return response.get("id")
        except Exception as e:
            print(f"페이지 생성 중 오류: {e}")
            print(f"  - 제목: {job_data.get('title', 'N/A')}")
            print(f"  - URL: {job_data.get('url', 'N/A')}")
            print(f"  - 설정된 속성 키: {list(properties.keys())}")
            return None

    def _build_properties(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Notion 페이지 속성 구성 (한글 속성명 사용)"""
        properties = {}

        # 공고명 (제목) - 필수
        title = job_data.get("title", "제목 없음")
        properties["공고명"] = {
            "title": [{"text": {"content": title[:2000]}}]
        }

        # 링크 (URL)
        url = job_data.get("url", "")
        if url:
            properties["링크"] = {"url": url}

        # 지원기업
        company = job_data.get("company", "")
        if company:
            properties["지원기업"] = {
                "rich_text": [{"text": {"content": company[:2000]}}]
            }

        # 지원 마감일 (날짜 형식)
        deadline = job_data.get("deadline", "")
        deadline_date = None

        if job_data.get("deadline_date"):
            d_date = job_data["deadline_date"]
            if isinstance(d_date, datetime):
                deadline_date = d_date.strftime("%Y-%m-%d")

        if not deadline_date:
            deadline_date = self._parse_deadline(deadline)

        if deadline_date:
            properties["지원 마감일"] = {"date": {"start": deadline_date}}

        # 직군 (사용자가 선택한 카테고리)
        category = job_data.get("category", "")
        if category:
            properties["직군"] = {"select": {"name": category}}

        # 직무 (공고 내용상 모집직무)
        job_title_text = job_data.get("job_title", "")
        if job_title_text:
            properties["직무"] = {
                "rich_text": [{"text": {"content": job_title_text[:2000]}}]
            }

        # 근무형태 (Select)
        job_type = job_data.get("type", "")
        if job_type:
            properties["근무형태"] = {"select": {"name": job_type}}

        # 급여
        salary = job_data.get("salary", "")
        if salary:
            properties["급여"] = {
                "rich_text": [{"text": {"content": salary[:2000]}}]
            }

        # 담당업무
        responsibilities = job_data.get("responsibilities", "")
        if responsibilities:
            properties["담당업무"] = {
                "rich_text": [{"text": {"content": responsibilities[:2000]}}]
            }

        # 근무시간
        work_hours = job_data.get("work_hours", "")
        if work_hours:
            properties["근무시간"] = {
                "rich_text": [{"text": {"content": work_hours[:2000]}}]
            }

        # 근무예정일
        start_date = job_data.get("start_date", "")
        if start_date:
            properties["근무예정일"] = {
                "rich_text": [{"text": {"content": start_date[:2000]}}]
            }

        # 근무기간
        duration = job_data.get("duration", "")
        if duration:
            properties["근무기간"] = {
                "rich_text": [{"text": {"content": duration[:2000]}}]
            }

        # 지원상태 - 기본값: 접수 전
        properties["지원상태"] = {"select": {"name": "접수 전"}}

        return properties

    def _parse_deadline(self, deadline_str: str) -> Optional[str]:
        """다양한 날짜 형식을 ISO 8601로 변환"""
        if not deadline_str:
            return None

        deadline_str = deadline_str.strip()
        today = datetime.now()

        if "오늘" in deadline_str:
            return today.strftime("%Y-%m-%d")
        if "내일" in deadline_str:
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")

        # D-N 형식
        d_match = re.match(r'D-(\d+)', deadline_str, re.IGNORECASE)
        if d_match:
            days = int(d_match.group(1))
            result_date = today + timedelta(days=days)
            return result_date.strftime("%Y-%m-%d")

        if any(keyword in deadline_str for keyword in ["채용시", "상시", "수시", "마감시"]):
            return None

        try:
            # YYYY.MM.DD 또는 YYYY-MM-DD (구체적 패턴 우선)
            full_date_match = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', deadline_str)
            if full_date_match:
                year = int(full_date_match.group(1))
                month = int(full_date_match.group(2))
                day = int(full_date_match.group(3))
                return datetime(year, month, day).strftime("%Y-%m-%d")

            # MM/DD, MM.DD
            date_pattern = re.search(r'(\d{1,2})[./-](\d{1,2})', deadline_str)
            if date_pattern:
                month = int(date_pattern.group(1))
                day = int(date_pattern.group(2))
                year = today.year

                # [FIX] 연도 넘김: 90일 이상 과거면 내년으로
                try:
                    target = datetime(year, month, day)
                    if target < today - timedelta(days=90):
                        year += 1
                    return datetime(year, month, day).strftime("%Y-%m-%d")
                except ValueError:
                    pass

        except Exception:
            pass

        # dateutil 파서로 시도
        try:
            parsed = date_parser.parse(deadline_str, fuzzy=True)
            return parsed.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

        return None

    def _build_content_blocks(self, body: str) -> List[Dict[str, Any]]:
        """페이지 본문 블록 구성"""
        if not body:
            return []

        blocks = []
        paragraphs = body.split("\n\n")

        for para in paragraphs:
            if not para.strip():
                continue

            text = para.strip()[:2000]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": text}}]
                }
            })

        # Notion API 블록 수 제한
        return blocks[:100]

    def batch_create_jobs(self, jobs: List[Dict[str, Any]], progress_callback=None) -> Dict[str, Any]:
        """여러 채용 공고를 일괄 저장"""
        result = {"saved": 0, "skipped": 0, "failed": 0, "errors": []}
        total = len(jobs)

        for i, job in enumerate(jobs):
            try:
                page_id = self.create_job_page(job)
                if page_id:
                    result["saved"] += 1
                else:
                    result["skipped"] += 1  # 중복
            except Exception as e:
                error_msg = f"공고 '{job.get('title')}' 저장 실패: {str(e)}"
                print(error_msg)
                result["failed"] += 1
                result["errors"].append(error_msg)

            if progress_callback:
                progress_callback((i + 1) / total)

        return result
