"""
scraper.py - 웹 크롤러 모듈 (Requests + BeautifulSoup)
경량화 버전 (메모리 최적화)

리팩토링 v3:
- [A] 인크루트 인코딩 cp949 강제 (apparent_encoding 오탐 수정)
- [C] 잡코리아 셀렉터 다중화 + 헤더 강화 + early exit
- [D] 네거티브 키워드 필터
- [FIX] 인크루트/잡코리아 지역 필터 적용
- [FIX] URL 없는 공고 중복제거 개선
- [FIX] 키워드-타이틀 매칭 검증 추가
- [FIX] source 필드 추가 (출처 추적)
- [FIX] D-N only 텍스트 날짜 파싱 개선
- [FIX] category 없어도 기본 네거티브 필터 적용
"""
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import re
import urllib3

# SSL 경고 숨김
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 기본 설정
DEFAULT_TIMEOUT = 15
MAX_BODY_LENGTH = 2000

# ──────────────────────────────────────
# [D] 네거티브 키워드 필터 (제외 목록)
# ──────────────────────────────────────
# 전역 기본 네거티브 (모든 직군에 공통 적용)
DEFAULT_NEGATIVE = ["미화", "조리", "경비", "시설관리", "운전", "청소", "배식", "주방",
                    "세탁", "보안", "주차", "조경", "용역"]

# 직군별 추가 네거티브 키워드 (기본 + 추가분 합산)
CATEGORY_NEGATIVE = {
    "대학교 행정직": [],  # 기본만 사용
    "교직원": [],
    "은행": [],
    "유학": [],
}


def get_default_negative(category: str) -> List[str]:
    """직군별 기본 제외 키워드 반환 (UI 초기값용)"""
    extra = CATEGORY_NEGATIVE.get(category, [])
    return DEFAULT_NEGATIVE[:] + extra


def filter_by_relevance(
    jobs: List[Dict],
    category: str = "",
    custom_negative: Optional[List[str]] = None,
    **kwargs  # 하위호환
) -> List[Dict]:
    """
    네거티브 키워드 필터:
    - 제목에 네거티브 키워드가 포함되면 제외
    - category 없어도 DEFAULT_NEGATIVE는 적용
    """
    if custom_negative is not None:
        negative = custom_negative
    else:
        negative = get_default_negative(category)

    if not negative:
        return jobs

    filtered = []
    for job in jobs:
        title = job.get("title", "")
        if any(neg in title for neg in negative):
            continue
        filtered.append(job)

    return filtered


class JobScraper:
    """채용 공고 크롤러 (Requests + BS4)"""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
        }

    def close(self):
        """리소스 정리 (Requests는 필요 없지만 호환성 유지)"""
        pass

    # ──────────────────────────────────────
    # 공통 헬퍼
    # ──────────────────────────────────────
    def _get_base_job_info(self):
        return {
            "title": "", "url": "", "company": "", "deadline": "",
            "deadline_date": None, "job_title": "", "salary": "",
            "responsibilities": "", "type": "", "work_hours": "",
            "start_date": "", "duration": "", "body": "",
            "location": "", "source": ""
        }

    def _check_location(self, item, location_filter: Optional[List[str]]) -> bool:
        """[FIX] BS4 아이템 전체 텍스트에서 지역 필터 확인 (3개 소스 공통)"""
        if not location_filter:
            return True
        text = item.get_text() if hasattr(item, 'get_text') else str(item)
        return any(loc in text for loc in location_filter)

    def _keyword_in_title(self, title: str, keyword: str) -> bool:
        """[FIX] 검색 키워드가 제목에 실제 포함되는지 검증
        복합 키워드(공백 포함)는 각 단어 중 하나라도 매칭되면 통과"""
        if not title or not keyword:
            return True
        parts = keyword.split()
        return any(part in title for part in parts)

    def _deduplicate_jobs(self, jobs):
        """[FIX] URL 없는 공고도 title+company 키로 중복 제거"""
        unique = []
        seen = set()
        for j in jobs:
            # URL이 있으면 쿼리파라미터 제거 후 키로, 없으면 title+company
            url = j.get('url', '')
            if url:
                key = url.split("?")[0]
            else:
                key = f"{j.get('title', '')}|{j.get('company', '')}"
            if not key or key in seen:
                continue
            seen.add(key)
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

            # [FIX] D-N 패턴 먼저 처리 ("D-5" 만 있는 경우도 대응)
            d_match = re.search(r'D-(\d+)', text, re.IGNORECASE)
            if d_match:
                days_left = int(d_match.group(1))
                return now + timedelta(days=days_left)

            # D-N 텍스트 제거 후 날짜 파싱
            text = re.sub(r'D-\d+', '', text).strip()
            if not text:
                return None  # D-N만 있었던 경우

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
                try:
                    target = datetime(year, month, day)
                    if target < now - timedelta(days=90):
                        year += 1
                        target = datetime(year, month, day)
                    return target
                except ValueError:
                    pass
        except Exception:
            pass
        return None

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
                        job_info["source"] = "사람인"

                        if not self._is_within_deadline(job_info, deadline_start, deadline_end):
                            continue

                        # [FIX] 지역 필터 (공통 메서드 사용)
                        if not self._check_location(item, location_filter):
                            continue

                        # 지역 정보 저장
                        loc_el = item.select_one('.job_condition span:nth-child(1)')
                        if loc_el:
                            job_info["location"] = loc_el.text.strip()

                        # [FIX] 키워드-타이틀 매칭 검증
                        if not self._keyword_in_title(job_info["title"], keyword):
                            continue

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
                # [Phase1] 급여 추출 (목록 페이지)
                if any(s in text for s in ["만원", "연봉", "월급", "시급", "회사내규", "면접후", "협의", "급여"]):
                    if not job_info["salary"]:
                        job_info["salary"] = text

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
    # [A] 인크루트 — 인코딩 cp949 강제 지정
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
                jobs = self._search_incruit_keyword(
                    keyword, deadline_start, deadline_end, location_filter, max_pages
                )
                all_jobs.extend(jobs)
                if len(all_jobs) >= max_results:
                    break
            except Exception as e:
                print(f"인크루트 오류: {e}")
        result = self._deduplicate_jobs(all_jobs)
        return result[:max_results]

    def _search_incruit_keyword(self, keyword, start, end, location_filter, max_pages):
        """[FIX] location_filter 파라미터 추가"""
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

                # [FIX-A] 인크루트는 EUC-KR 계열 — cp949 강제 지정
                res.encoding = 'cp949'

                if res.status_code != 200:
                    continue

                soup = BeautifulSoup(res.text, 'html.parser')
                items = soup.select('.c_row')
                if not items:
                    items = soup.select('.clist_vv li')

                if not items:
                    break

                for item in items:
                    # [FIX] 지역 필터 적용 (사람인과 동일한 공통 메서드)
                    if not self._check_location(item, location_filter):
                        continue

                    job = self._parse_incruit_item(item)
                    if job:
                        job["source"] = "인크루트"
                        # [FIX] 키워드-타이틀 매칭 검증
                        if not self._keyword_in_title(job["title"], keyword):
                            continue
                        if self._is_within_deadline(job, start, end):
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

            # [Phase1] 급여 추출 (목록 페이지)
            salary_candidates = item.select('.cell_mid .cl_btm span, .cl_md span, span')
            for sc in salary_candidates:
                sc_text = sc.text.strip()
                if any(s in sc_text for s in ["만원", "연봉", "월급", "시급", "회사내규", "면접후", "협의", "급여"]):
                    job_info["salary"] = sc_text
                    break

            return job_info
        except Exception:
            return None

    # ──────────────────────────────────────
    # [C] 잡코리아 — 셀렉터 다중화 + 헤더 강화 + early exit
    # ──────────────────────────────────────
    def search_jobkorea(
        self,
        keywords: List[str],
        deadline_start: datetime,
        deadline_end: datetime,
        location_filter: Optional[List[str]] = None,
        max_pages: int = 3,
        max_results: int = 30
    ) -> List[Dict[str, Any]]:
        """잡코리아 검색"""
        all_jobs = []
        for keyword in keywords:
            try:
                jobs = self._search_jobkorea_keyword(
                    keyword, deadline_start, deadline_end, location_filter, max_pages
                )
                all_jobs.extend(jobs)
                if len(all_jobs) >= max_results:
                    break
            except Exception as e:
                print(f"잡코리아 키워드 '{keyword}' 오류: {e}")
        result = self._deduplicate_jobs(all_jobs)
        return result[:max_results]

    def _search_jobkorea_keyword(self, keyword, start, end, location_filter, max_pages):
        """[FIX] location_filter 파라미터 추가"""
        jobs = []

        # [FIX-C] 잡코리아 전용 헤더 (봇 탐지 우회 강화)
        jk_headers = {
            **self.headers,
            "Referer": "https://www.jobkorea.co.kr/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

        for page in range(1, max_pages + 1):
            url = f"https://www.jobkorea.co.kr/Search/?stext={keyword}&Page_No={page}"
            try:
                res = requests.get(url, headers=jk_headers, timeout=self.timeout)
                if res.status_code != 200:
                    print(f"잡코리아 HTTP {res.status_code} (page {page})")
                    continue

                soup = BeautifulSoup(res.text, 'html.parser')

                # [FIX-C] 셀렉터 다중화 — 잡코리아 구조 변경 대응
                links = soup.select("a[href*='/Recruit/GI_Read/']")
                if not links:
                    links = soup.select(".post-list-info a[href*='Recruit']")
                if not links:
                    links = soup.select("a[data-gno]")
                if not links:
                    links = soup.select(".list-default a[href*='jobkorea.co.kr']")

                # [FIX-C] early exit
                if not links:
                    print(f"잡코리아 page {page}: 결과 없음 → 중단")
                    break

                seen_urls = set()

                for link in links:
                    href = link.get('href', '')
                    if not href:
                        continue

                    full_url = "https://www.jobkorea.co.kr" + href if href.startswith("/") else href
                    base_url = full_url.split("?")[0]

                    if base_url in seen_urls:
                        continue
                    seen_urls.add(base_url)

                    parent = link.find_parent('li') or link.find_parent('div', class_=re.compile(r'list|item|post'))

                    if parent:
                        # [FIX] 지역 필터 적용
                        if not self._check_location(parent, location_filter):
                            continue

                        job_info = self._get_base_job_info()
                        job_info["title"] = link.text.strip() or "제목 없음"
                        job_info["url"] = full_url
                        job_info["source"] = "잡코리아"

                        # [FIX] 키워드-타이틀 매칭 검증
                        if not self._keyword_in_title(job_info["title"], keyword):
                            continue

                        # 회사명 셀렉터 다중화
                        corp = parent.select_one(
                            '.name, .corp-name, .post-list-corp a, '
                            '.company-name, [class*="corp"] a, [class*="company"]'
                        )
                        if corp:
                            job_info["company"] = corp.text.strip()

                        # [Phase1] 급여 추출 (목록 페이지)
                        salary_el = parent.select_one(
                            '[class*="salary"], [class*="pay"], .option span'
                        )
                        if salary_el:
                            s_text = salary_el.text.strip()
                            if any(s in s_text for s in ["만원", "연봉", "월급", "시급", "회사내규", "면접후", "협의", "급여"]):
                                job_info["salary"] = s_text

                        # 마감일 셀렉터 다중화
                        date_item = parent.select_one(
                            '.date, .deadline, .option .date, '
                            '[class*="date"], [class*="deadline"]'
                        )
                        if date_item:
                            d_text = date_item.text.strip()
                            job_info["deadline"] = d_text
                            job_info["deadline_date"] = self._parse_deadline_to_datetime(d_text)
                        else:
                            job_info["deadline"] = ""
                            job_info["deadline_date"] = None

                        if self._is_within_deadline(job_info, start, end):
                            jobs.append(job_info)

            except Exception as e:
                print(f"잡코리아 page {page} 오류: {e}")
                continue
        return jobs


    # ──────────────────────────────────────
    # [Phase2] 상세 페이지 파서 (급여 보강용)
    # ──────────────────────────────────────
    def parse_incruit_detail(self, url: str) -> Dict[str, Any]:
        """인크루트 상세 정보 (급여, 본문)"""
        detail_info = {}
        try:
            res = requests.get(url, headers=self.headers, timeout=self.timeout)
            res.encoding = 'cp949'
            if res.status_code != 200:
                return detail_info

            soup = BeautifulSoup(res.text, 'html.parser')

            # 급여 — dt/th 라벨 기반 탐색
            for el in soup.select('dt, th, .tit, .label'):
                if el and any(k in el.text for k in ["급여", "연봉", "월급", "임금", "급료"]):
                    sibling = el.find_next_sibling('dd') or el.find_next_sibling('td') or el.find_next()
                    if sibling:
                        detail_info["salary"] = sibling.text.strip()[:200]
                        break

            # 본문
            content = soup.select_one('.job_detail, .detail_cont, #content, .jobCont')
            if content:
                detail_info["body"] = content.get_text('\n', strip=True)[:MAX_BODY_LENGTH]

            return detail_info
        except Exception:
            return detail_info

    def parse_jobkorea_detail(self, url: str) -> Dict[str, Any]:
        """잡코리아 상세 정보 (급여, 본문)"""
        detail_info = {}
        try:
            jk_headers = {
                **self.headers,
                "Referer": "https://www.jobkorea.co.kr/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
            }
            res = requests.get(url, headers=jk_headers, timeout=self.timeout)
            if res.status_code != 200:
                return detail_info

            soup = BeautifulSoup(res.text, 'html.parser')

            # 급여 — dt/th 라벨 기반 탐색
            for el in soup.select('dt, th, .tit'):
                if el and any(k in el.text for k in ["급여", "연봉", "월급", "임금", "급료"]):
                    sibling = el.find_next_sibling('dd') or el.find_next_sibling('td') or el.find_next()
                    if sibling:
                        detail_info["salary"] = sibling.text.strip()[:200]
                        break

            # 본문
            content = soup.select_one('.artReadComp, .viewJobCont, .cont, .tbRow')
            if content:
                detail_info["body"] = content.get_text('\n', strip=True)[:MAX_BODY_LENGTH]

            return detail_info
        except Exception:
            return detail_info

    def enrich_job_detail(self, job: Dict) -> Dict:
        """단일 공고 상세 정보 보강 (급여 없을 때만)"""
        url = job.get("url", "")
        if not url:
            return job

        source = job.get("source", "")
        detail = {}

        if source == "사람인":
            detail = self.parse_saramin_detail(url)
        elif source == "인크루트":
            detail = self.parse_incruit_detail(url)
        elif source == "잡코리아":
            detail = self.parse_jobkorea_detail(url)

        # 기존 값이 비어있는 필드만 보강
        for key, val in detail.items():
            if val and not job.get(key):
                job[key] = val

        return job


# ──────────────────────────────────────
# 상세 보강 standalone 함수 (app.py에서 호출)
# ──────────────────────────────────────
SALARY_SKIP_KEYWORDS = ["회사내규", "면접후 결정", "면접후결정", "협의", "추후협의", "추후 협의"]


def enrich_jobs(
    jobs: List[Dict],
    progress_callback=None
) -> List[Dict]:
    """[Phase2] 급여 없는/무의미한 공고만 상세 페이지에서 보강"""
    scraper = JobScraper()

    needs_detail = []
    for i, job in enumerate(jobs):
        salary = job.get("salary", "").strip()
        if not salary or any(skip in salary for skip in SALARY_SKIP_KEYWORDS):
            needs_detail.append(i)

    enriched_count = 0
    for idx, i in enumerate(needs_detail):
        job = jobs[i]
        jobs[i] = scraper.enrich_job_detail(job)
        enriched_count += 1

        if progress_callback:
            progress_callback(f"상세 보강 중... ({idx + 1}/{len(needs_detail)})")

        # 봇 탐지 방지 딜레이
        time.sleep(0.5)

    print(f"[보강] {len(jobs)}건 중 {len(needs_detail)}건 상세 조회 → {enriched_count}건 보강 완료")
    return jobs


def scrape_jobs(
    sources: List[str],
    keywords: List[str],
    deadline_start: datetime,
    deadline_end: datetime,
    category: str = "",
    location_filter: Optional[List[str]] = None,
    custom_negative: Optional[List[str]] = None,
    progress_callback=None
) -> List[Dict[str, Any]]:
    """통합 스크래핑 함수"""
    scraper = JobScraper()
    results = []

    for i, source in enumerate(sources):
        jobs = []

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
    deduped = scraper._deduplicate_jobs(results)

    # [FIX] 네거티브 필터: category 없어도 기본 필터 적용
    filtered = filter_by_relevance(
        deduped, category,
        custom_negative=custom_negative
    )
    print(f"[필터] {len(deduped)}건 → {len(filtered)}건 (제거: {len(deduped) - len(filtered)}건)")
    return filtered
