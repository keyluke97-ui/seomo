"""
scraper.py - 웹 크롤러 모듈 (Requests + BeautifulSoup)
경량화 버전 (메모리 최적화)

리팩토링 내역:
- 잡코리아 파서 들여쓰기 버그 수정
- 지역 필터를 config 기반으로 변경 (하드코딩 제거)
- scrape_jobs progress 콜백 버그 수정
- 타임아웃 설정 외부화
- 인크루트 인코딩 처리 개선
- 날짜 파싱 연도 넘김 로직 개선
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import re
import urllib3

# SSL 경고 숨김
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 기본 설정
DEFAULT_TIMEOUT = 15  # 기존 10초 → 15초 (느린 시간대 대응)
MAX_BODY_LENGTH = 2000  # 상세 본문 최대 길이


class JobScraper:
    """채용 공고 크롤러 (Requests + BS4)"""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }

    def close(self):
        """리소스 정리 (Requests는 필요 없지만 호환성 유지)"""
        pass

    # ──────────────────────────────────────
    # 사람인
    # ──────────────────────────────────────
    def search_saramin(
        self,
        keywords: List[str],
        deadline_start: datetime,
        deadline_end: datetime,
        location_filter: Optional[List[str]] = None,
        max_pages: int = 5,
        max_results: int = 30
    ) -> List[Dict[str, Any]]:
        """사람인 채용 공고 검색"""
        all_jobs = []

        for keyword in keywords:
            try:
                jobs = self._search_saramin_keyword(
                    keyword, deadline_start, deadline_end, location_filter, max_pages
                )
                all_jobs.extend(jobs)
                if len(all_jobs) >= max_results:
                    break
            except Exception as e:
                print(f"사람인 키워드 '{keyword}' 검색 중 오류: {e}")
                continue

        result = self._deduplicate_jobs(all_jobs)
        return result[:max_results]

    def _search_saramin_keyword(
        self,
        keyword: str,
        deadline_start: datetime,
        deadline_end: datetime,
        location_filter: Optional[List[str]],
        max_pages: int
    ) -> List[Dict[str, Any]]:
        jobs = []

        for page in range(1, max_pages + 1):
            url = f"https://www.saramin.co.kr/zf_user/search/recruit?searchword={keyword}&recruitPage={page}&recruitSort=relation&recruitPageCount=40"

            try:
                res = requests.get(url, headers=self.headers, timeout=self.timeout)
                if res.status_code != 200:
                    continue

                soup = BeautifulSoup(res.text, 'html.parser')
                items = soup.select('.item_recruit')

                if not items:
                    break

                for item in items:
                    try:
                        job_info = self._parse_saramin_list_item(item)
                        if not self._is_within_deadline(job_info, deadline_start, deadline_end):
                            continue

                        # 지역 필터 적용 (설정된 경우에만)
                        if location_filter:
                            location = item.select_one('.job_condition span:nth-child(1)')
                            if location:
                                loc_text = location.text.strip()
                                if not any(loc in loc_text for loc in location_filter):
                                    continue
                            # 지역 정보 없으면 포함 (안전하게)

                        jobs.append(job_info)
                    except Exception:
                        continue

            except Exception as e:
                print(f"사람인 페이지 {page} 로드 오류: {e}")
                continue

        return jobs

    def _parse_saramin_list_item(self, item) -> Dict[str, Any]:
        job_info = self._get_base_job_info()

        try:
            title_tag = item.select_one('.job_tit a')
            if title_tag:
                job_info["title"] = title_tag.text.strip()
                job_info["url"] = "https://www.saramin.co.kr" + title_tag['href']

            corp_tag = item.select_one('.corp_name a')
            if corp_tag:
                job_info["company"] = corp_tag.text.strip()

            date_tag = item.select_one('.job_date .date')
            if date_tag:
                job_info["deadline"] = date_tag.text.strip()
                job_info["deadline_date"] = self._parse_deadline_to_datetime(job_info["deadline"])

            conditions = item.select('.job_condition span')
            for cond in conditions:
                text = cond.text.strip()
                if any(t in text for t in ["정규직", "계약직", "인턴", "파견직", "아르바이트"]):
                    job_info["type"] = text
                    break

            return job_info
        except Exception:
            return job_info

    def parse_saramin_detail(self, url: str) -> Dict[str, Any]:
        """사람인 상세 정보"""
        detail_info = {}
        try:
            res = requests.get(url, headers=self.headers, timeout=self.timeout)
            if res.status_code != 200:
                return detail_info

            soup = BeautifulSoup(res.text, 'html.parser')

            content = soup.select_one('.wrap_jv_cont')
            if content:
                body_text = content.get_text('\n', strip=True)
                detail_info["body"] = body_text[:MAX_BODY_LENGTH]

            dl_items = soup.select('.jv_cont .wrap_jv_data dl')
            for dl in dl_items:
                dt = dl.select_one('dt')
                dd = dl.select_one('dd')
                if dt and dd:
                    label = dt.text.strip()
                    val = dd.text.strip()
                    if "급여" in label:
                        detail_info["salary"] = val
                    elif "근무시간" in label:
                        detail_info["work_hours"] = val

            return detail_info
        except Exception:
            return detail_info

    # ──────────────────────────────────────
    # 인크루트
    # ──────────────────────────────────────
    def search_incruit(
        self,
        keywords: List[str],
        deadline_start: datetime,
        deadline_end: datetime,
        location_filter: Optional[List[str]] = None,
        max_pages: int = 5,
        max_results: int = 30
    ) -> List[Dict[str, Any]]:
        """인크루트 검색"""
        all_jobs = []
        for keyword in keywords:
            try:
                jobs = self._search_incruit_keyword(keyword, deadline_start, deadline_end, max_pages)
                all_jobs.extend(jobs)
                if len(all_jobs) >= max_results:
                    break
            except Exception as e:
                print(f"인크루트 오류: {e}")
        result = self._deduplicate_jobs(all_jobs)
        return result[:max_results]

    def _search_incruit_keyword(self, keyword, start, end, max_pages):
        jobs = []
        for page in range(1, max_pages + 1):
            startno = (page - 1) * 30 + 1

            url = "https://search.incruit.com/list/search.asp"
            params = {
                "col": "job",
                "kw": keyword,
                "startno": startno
            }

            try:
                res = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)

                # 인크루트 인코딩 자동 감지 (EUC-KR / UTF-8 혼재 대응)
                if res.apparent_encoding:
                    res.encoding = res.apparent_encoding
                else:
                    res.encoding = 'utf-8'

                if res.status_code != 200:
                    continue

                soup = BeautifulSoup(res.text, 'html.parser')
                items = soup.select('.c_row')
                if not items:
                    items = soup.select('.clist_vv li')

                if not items:
                    break

                for item in items:
                    job = self._parse_incruit_item(item)
                    if job and self._is_within_deadline(job, start, end):
                        jobs.append(job)

            except Exception:
                continue
        return jobs

    def _parse_incruit_item(self, item):
        job_info = self._get_base_job_info()
        try:
            links = item.select('a')
            target_link = None

            for link in links:
                href = link.get('href', '')
                if 'jobpost.asp' in href:
                    target_link = link
                    break

            if not target_link:
                target_link = item.select_one('.cell_mid .cl_top a, span.custom a, .cl_top a')

            if target_link:
                job_info["title"] = target_link.text.strip()
                href = target_link.get('href')
                if href:
                    job_info["url"] = href
            else:
                return None

            corp = item.select_one('.cpname')
            if corp:
                job_info["company"] = corp.text.strip()

            dates = item.select('.cell_last .cl_btm span, .date')
            if dates:
                d_text = dates[0].text.strip()
                job_info["deadline"] = d_text
                job_info["deadline_date"] = self._parse_deadline_to_datetime(d_text)

            return job_info
        except Exception:
            return None

    # ──────────────────────────────────────
    # 잡코리아 (들여쓰기 버그 수정됨)
    # ──────────────────────────────────────
    def search_jobkorea(
        self,
        keywords: List[str],
        deadline_start: datetime,
        deadline_end: datetime,
        location_filter: Optional[List[str]] = None,
        max_pages: int = 5,
        max_results: int = 30
    ) -> List[Dict[str, Any]]:
        """잡코리아 검색"""
        all_jobs = []
        for keyword in keywords:
            try:
                jobs = self._search_jobkorea_keyword(keyword, deadline_start, deadline_end, max_pages)
                all_jobs.extend(jobs)
                if len(all_jobs) >= max_results:
                    break
            except Exception:
                pass
        result = self._deduplicate_jobs(all_jobs)
        return result[:max_results]

    def _search_jobkorea_keyword(self, keyword, start, end, max_pages):
        jobs = []
        for page in range(1, max_pages + 1):
            url = f"https://www.jobkorea.co.kr/Search/?stext={keyword}&Page_No={page}"
            try:
                res = requests.get(url, headers=self.headers, timeout=self.timeout)
                if res.status_code != 200:
                    continue

                soup = BeautifulSoup(res.text, 'html.parser')
                links = soup.select("a[href*='/Recruit/GI_Read/']")

                seen_urls = set()

                for link in links:
                    href = link['href']
                    full_url = "https://www.jobkorea.co.kr" + href if href.startswith("/") else href
                    base_url = full_url.split("?")[0]

                    if base_url in seen_urls:
                        continue
                    seen_urls.add(base_url)

                    # [FIX] 들여쓰기 수정 — for link 루프 내부로 복원
                    parent = link.find_parent('li')

                    if parent:
                        job_info = self._get_base_job_info()
                        job_info["title"] = link.text.strip() or "제목 없음"
                        job_info["url"] = full_url

                        corp = parent.select_one('.name, .corp-name, .post-list-corp a')
                        if corp:
                            job_info["company"] = corp.text.strip()

                        date_item = parent.select_one('.date, .deadline, .option .date')
                        if date_item:
                            d_text = date_item.text.strip()
                            d_text = re.sub(r'D-\d+', '', d_text).strip()
                            job_info["deadline"] = d_text
                            job_info["deadline_date"] = self._parse_deadline_to_datetime(d_text)
                        else:
                            job_info["deadline"] = ""
                            job_info["deadline_date"] = None

                        if self._is_within_deadline(job_info, start, end):
                            jobs.append(job_info)

            except Exception:
                continue
        return jobs

    # ──────────────────────────────────────
    # 공통 헬퍼
    # ──────────────────────────────────────
    def _get_base_job_info(self):
        return {
            "title": "", "url": "", "company": "", "deadline": "",
            "deadline_date": None, "job_title": "", "salary": "",
            "responsibilities": "", "type": "", "work_hours": "",
            "start_date": "", "duration": "", "body": ""
        }

    def _deduplicate_jobs(self, jobs):
        unique = []
        seen = set()
        for j in jobs:
            if j.get('url') and j['url'] not in seen:
                seen.add(j['url'])
                unique.append(j)
        return unique

    def _is_within_deadline(self, job_info, start, end):
        if not job_info.get("deadline_date"):
            return True
        deadline = job_info["deadline_date"]
        if hasattr(deadline, 'tzinfo') and deadline.tzinfo:
            deadline = deadline.replace(tzinfo=None)
        return start <= deadline <= end

    def _parse_deadline_to_datetime(self, text: str) -> Optional[datetime]:
        if not text:
            return None
        text = text.strip()
        now = datetime.now()

        try:
            if any(x in text for x in ["상시", "채용시", "수시"]):
                return now + timedelta(days=365)

            if "오늘" in text:
                return now

            if "내일" in text:
                return now + timedelta(days=1)

            # D-N 제거
            text = re.sub(r'D-\d+', '', text).strip()

            # YYYY.MM.DD 먼저 시도 (더 구체적인 패턴 우선)
            full_match = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', text)
            if full_match:
                year = int(full_match.group(1))
                month = int(full_match.group(2))
                day = int(full_match.group(3))
                return datetime(year, month, day)

            # MM/DD, MM.DD
            match = re.search(r'(\d{1,2})[./-](\d{1,2})', text)
            if match:
                month, day = map(int, match.groups())
                year = now.year
                # [FIX] 연도 넘김 개선: 현재보다 90일 이상 과거면 내년으로 판단
                try:
                    target = datetime(year, month, day)
                    if target < now - timedelta(days=90):
                        year += 1
                        target = datetime(year, month, day)
                    return target
                except ValueError:
                    pass  # 잘못된 날짜 (예: 2/30)
        except Exception:
            pass
        return None


def scrape_jobs(
    sources: List[str],
    keywords: List[str],
    deadline_start: datetime,
    deadline_end: datetime,
    category: str = "",
    location_filter: Optional[List[str]] = None,
    progress_callback=None
) -> List[Dict[str, Any]]:
    """통합 스크래핑 함수"""
    scraper = JobScraper()
    results = []

    for i, source in enumerate(sources):
        jobs = []  # [FIX] 소스별 jobs 변수 초기화 (NameError 방지)

        if source == "사람인":
            jobs = scraper.search_saramin(keywords, deadline_start, deadline_end, location_filter)
        elif source == "인크루트":
            jobs = scraper.search_incruit(keywords, deadline_start, deadline_end, location_filter)
        elif source == "잡코리아":
            jobs = scraper.search_jobkorea(keywords, deadline_start, deadline_end, location_filter)

        results.extend(jobs)

        if progress_callback:
            progress_callback(f"{source} 검색 완료 ({len(jobs)}건)")

    # 직군 정보 주입
    if category:
        for job in results:
            job["category"] = category

    # 전체 결과 중복 제거
    return scraper._deduplicate_jobs(results)
