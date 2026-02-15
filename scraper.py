"""
scraper.py - 웹 크롤러 모듈 (Requests + BeautifulSoup)
경량화 버전 (메모리 최적화)

리팩토링 v4:
- [A] 인크루트 인코딩 cp949 강제 (apparent_encoding 오탐 수정)
- [C] 잡코리아 셀렉터 다중화 + 헤더 강화 + early exit
- [D] 네거티브 키워드 필터
- [FIX] 인크루트/잡코리아 지역 필터 적용
- [FIX] URL 없는 공고 중복제거 개선
- [FIX] 키워드-타이틀 매칭 검증 추가
- [FIX] source 필드 추가 (출처 추적)
- [FIX] D-N only 텍스트 날짜 파싱 개선
- [FIX] category 없어도 기본 네거티브 필터 적용
- [FIX-JK] 잡코리아 cloudscraper + Session 쿠키 + Circuit Breaker
"""
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import re
import urllib3

# cloudscraper: TLS 핑거프린트 위장 (잡코리아 WAF 우회)
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False
    print("[WARN] cloudscraper 미설치 — pip install cloudscraper")

# SSL 경고 숨김
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 기본 설정
DEFAULT_TIMEOUT = 15
JK_CONNECT_TIMEOUT = 8   # 잡코리아 connect timeout (빠른 실패)
JK_READ_TIMEOUT = 15     # 잡코리아 read timeout
MAX_BODY_LENGTH = 2000
JK_MAX_CONSECUTIVE_FAILS = 3  # Circuit Breaker 임계값

# ──────────────────────────────────────
# 사이트 내장 지역 필터 코드 매핑
# ──────────────────────────────────────
SARAMIN_LOC_CODES = {
    "서울": "101000", "경기": "102000", "광주": "103000",
    "대구": "104000", "대전": "105000", "부산": "106000",
    "울산": "107000", "인천": "108000", "강원": "109000",
    "경남": "110000", "경북": "111000", "전남": "112000",
    "전북": "113000", "충북": "114000", "충남": "115000",
    "제주": "116000", "세종": "118000",
}

# 사람인 통합검색 company_cd (전체 기업형태)
SARAMIN_COMPANY_ALL = "0,1,2,3,4,5,6,7,9,10"

# 인크루트 지역코드 (rgn2 파라미터용)
INCRUIT_REGION_CODES = {
    "서울": "11", "부산": "12", "대구": "13", "인천": "14",
    "광주": "15", "대전": "16", "울산": "17", "세종": "18",
    "경기": "19", "강원": "20", "충북": "21", "충남": "22",
    "전남": "23", "전북": "24", "경북": "25", "경남": "26",
    "제주": "27",
}

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
    filter_log: Optional[List[Dict]] = None,
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
        matched_neg = [neg for neg in negative if neg in title]
        if matched_neg:
            if filter_log is not None:
                filter_log.append({
                    "title": title,
                    "company": job.get("company", ""),
                    "source": job.get("source", ""),
                    "deadline": job.get("deadline", ""),
                    "reason": f"제외 키워드: {', '.join(matched_neg)}"
                })
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

        # [Phase2] 잡코리아 전용 Session (cloudscraper or requests.Session)
        self._jk_session = None
        self._jk_session_ready = False

        # [Phase3] Circuit Breaker 상태
        self._jk_consecutive_fails = 0
        self._jk_circuit_open = False

    def close(self):
        """리소스 정리"""
        if self._jk_session and hasattr(self._jk_session, 'close'):
            self._jk_session.close()

    def _get_jk_session(self):
        """[Phase1+2] 잡코리아 전용 세션 생성 + 홈페이지 warm-up"""
        if self._jk_session is not None:
            return self._jk_session

        # Phase1: cloudscraper로 TLS 핑거프린트 위장
        if HAS_CLOUDSCRAPER:
            try:
                self._jk_session = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'desktop': True,
                    }
                )
                print("[잡코리아] cloudscraper 세션 생성")
            except Exception as e:
                print(f"[잡코리아] cloudscraper 생성 실패: {e}, requests.Session fallback")
                self._jk_session = requests.Session()
        else:
            self._jk_session = requests.Session()

        # Phase2: 홈페이지 방문으로 쿠키 확보
        jk_headers = {
            **self.headers,
            "Referer": "https://www.google.com/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        try:
            warmup = self._jk_session.get(
                "https://www.jobkorea.co.kr/",
                headers=jk_headers,
                timeout=(JK_CONNECT_TIMEOUT, JK_READ_TIMEOUT),
                allow_redirects=True,
            )
            if warmup.status_code == 200:
                self._jk_session_ready = True
                print(f"[잡코리아] 세션 warm-up 성공 (쿠키 {len(self._jk_session.cookies)}개)")
            else:
                print(f"[잡코리아] warm-up HTTP {warmup.status_code}")
        except Exception as e:
            print(f"[잡코리아] warm-up 실패: {e}")

        return self._jk_session

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

    def _any_keyword_in_title(self, title: str, keywords: List[str],
                               company: str = "") -> bool:
        """검색 키워드 중 하나라도 제목 OR 회사명에 포함되는지 검증
        (회사명 매칭 추가: '대학교' 키워드 → 회사명 'OO대학교'도 통과)"""
        if not title or not keywords:
            return True
        text = f"{title} {company}" if company else title
        return any(self._keyword_in_title(text, kw) for kw in keywords)

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
        """마감일 필터: 아직 마감되지 않은 공고만 통과 (deadline >= start)
        상한(end)은 적용하지 않음 — 마감이 먼 공고도 지원 가능하므로 포함"""
        if not job_info.get("deadline_date"):
            return True  # 상시채용 등 마감일 없으면 통과
        deadline = job_info["deadline_date"]
        if hasattr(deadline, 'tzinfo') and deadline.tzinfo:
            deadline = deadline.replace(tzinfo=None)
        # 마감일이 검색 시작일 이후면 통과 (아직 열려있는 공고)
        return deadline >= start

    def _parse_deadline_to_datetime(self, text: str) -> Optional[datetime]:
        if not text:
            return None
        text = text.strip()
        now = datetime.now()

        try:
            if any(x in text for x in ["상시", "채용시", "수시"]):
                return None  # 상시채용은 마감일 없음 → _is_within_deadline에서 무조건 통과

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
        max_pages: int = 10,
        filter_log: Optional[List[Dict]] = None,
    ) -> List[Dict[str, Any]]:
        """사람인 채용 공고 검색 — 모든 키워드 반드시 검색"""
        all_jobs = []

        for keyword in keywords:
            try:
                jobs = self._search_saramin_keyword(
                    keyword, deadline_start, deadline_end, location_filter, max_pages,
                    filter_log=filter_log,
                )
                all_jobs.extend(jobs)
                print(f"  사람인 '{keyword}': {len(jobs)}건")
            except Exception as e:
                print(f"사람인 키워드 '{keyword}' 검색 중 오류: {e}")
                continue

        result = self._deduplicate_jobs(all_jobs)
        print(f"[사람인] 전체 {len(all_jobs)}건 → 중복제거 {len(result)}건")
        return result

    def _build_saramin_url(
        self, keyword: str, page: int,
        location_filter: Optional[List[str]] = None,
    ) -> str:
        """사람인 검색 URL 생성 — /zf_user/search 통합검색 엔드포인트
        (서버사이드 지역 + 기업형태 필터 적용)"""
        from urllib.parse import quote

        base = (
            f"https://www.saramin.co.kr/zf_user/search"
            f"?searchType=search"
            f"&searchword={quote(keyword)}"
            f"&company_cd={SARAMIN_COMPANY_ALL}"
            f"&search_optional_item=y"
            f"&search_done=y"
            f"&panel_count=y"
            f"&preview=y"
            f"&recruitPage={page}"
            f"&recruitSort=relation"
            f"&recruitPageCount=40"
        )

        # 지역 필터 (서버사이드)
        if location_filter:
            loc_codes = []
            for loc in location_filter:
                code = SARAMIN_LOC_CODES.get(loc)
                if code:
                    loc_codes.append(code)
            if loc_codes:
                base += "&loc_mcd=" + ",".join(loc_codes)

        return base

    def _search_saramin_keyword(
        self,
        keyword: str,
        deadline_start: datetime,
        deadline_end: datetime,
        location_filter: Optional[List[str]],
        max_pages: int,
        filter_log: Optional[List[Dict]] = None,
    ) -> List[Dict[str, Any]]:
        jobs = []

        for page in range(1, max_pages + 1):
            url = self._build_saramin_url(keyword, page, location_filter)

            # 첫 페이지 URL을 filter_log에 기록 (디버그용)
            if page == 1 and filter_log is not None:
                filter_log.append({
                    "title": f"[검색URL] 사람인 '{keyword}'",
                    "company": "",
                    "source": "사람인",
                    "deadline": "",
                    "reason": f"🔗 {url}"
                })

            try:
                res = requests.get(url, headers=self.headers, timeout=self.timeout)
                if res.status_code != 200:
                    print(f"사람인 HTTP {res.status_code} (page {page})")
                    continue

                soup = BeautifulSoup(res.text, 'html.parser')

                # ── 멀티 셀렉터: 순차 시도 ──
                items, selector_used = self._find_saramin_items(soup)

                if page == 1:
                    print(f"  사람인 셀렉터: {selector_used} → {len(items)}개 아이템")
                    if filter_log is not None:
                        # HTML 구조 자동 탐지 (디버그)
                        debug_info = f"셀렉터: {selector_used} → {len(items)}개 (HTML크기: {len(res.text)})"
                        if not items:
                            # 0건이면 HTML 클래스 목록 + 채용링크 수 로그
                            all_classes = set()
                            for tag in soup.find_all(True, class_=True):
                                for cls in tag.get('class', []):
                                    if any(k in cls.lower() for k in ['recruit', 'job', 'item', 'list', 'search', 'result', 'content']):
                                        all_classes.add(f"{tag.name}.{cls}")
                            recruit_links = soup.select('a[href*="recruit"], a[href*="rec_idx"], a[href*="jobs/relay"]')
                            debug_info += f" | 관련클래스: {sorted(all_classes)[:20]} | 채용링크: {len(recruit_links)}개"
                            if recruit_links:
                                sample = recruit_links[0]
                                parent = sample.find_parent()
                                if parent:
                                    p_classes = ' '.join(parent.get('class', []))
                                    debug_info += f" | 첫링크부모: <{parent.name} class='{p_classes}'>"
                        filter_log.append({
                            "title": f"[디버그] 사람인 셀렉터",
                            "company": "", "source": "사람인", "deadline": "",
                            "reason": debug_info
                        })

                if not items:
                    break

                for item in items:
                    try:
                        job_info = self._parse_saramin_list_item(item)
                        job_info["source"] = "사람인"

                        if not job_info.get("title"):
                            continue

                        if not self._is_within_deadline(job_info, deadline_start, deadline_end):
                            if filter_log is not None:
                                parsed = job_info.get("deadline_date")
                                parsed_str = parsed.strftime("%Y-%m-%d") if parsed else "파싱실패"
                                range_str = f"{deadline_start.strftime('%Y-%m-%d')}~{deadline_end.strftime('%Y-%m-%d')}"
                                filter_log.append({
                                    "title": job_info.get("title", ""),
                                    "company": job_info.get("company", ""),
                                    "source": "사람인",
                                    "deadline": job_info.get("deadline", ""),
                                    "reason": f"마감일 범위 밖 (원문: {job_info.get('deadline', '?')} → 파싱: {parsed_str} / 범위: {range_str})"
                                })
                            continue

                        # 지역 정보 저장 (서버사이드 필터가 이미 적용됨)
                        loc_el = item.select_one('.job_condition span:nth-child(1)')
                        if loc_el:
                            job_info["location"] = loc_el.text.strip()

                        jobs.append(job_info)
                    except Exception:
                        continue

            except Exception as e:
                print(f"사람인 페이지 {page} 로드 오류: {e}")
                continue

        return jobs

    def _find_saramin_items(self, soup):
        """사람인 검색 결과 아이템을 멀티 셀렉터로 탐색"""
        # 1) 표준 셀렉터 (.item_recruit — /search/recruit 및 /search 공용 가능)
        items = soup.select('.item_recruit')
        if items:
            return items, '.item_recruit'

        # 2) 통합검색 #recruit_info_list 컨테이너 내부
        container = soup.select_one('#recruit_info_list')
        if container:
            items = container.select('[class*="item"]')
            if items:
                return items, '#recruit_info_list [class*=item]'
            # 링크 있는 div
            items = [div for div in container.select('div')
                     if div.select_one('a[href*="recruit"]') or div.select_one('h2 a')]
            if items:
                return items, '#recruit_info_list div(link)'

        # 3) .common_recruilt 폴백
        items = soup.select('.common_recruilt')
        if items:
            return items, '.common_recruilt'

        # 4) 최종 폴백: 채용 상세 링크의 부모 블록 자동 탐지
        recruit_links = soup.select('a[href*="jobs/relay/view"], a[href*="rec_idx="]')
        if recruit_links:
            seen_parents = []
            seen_set = set()
            for link in recruit_links:
                # 공고별 블록을 감싸는 부모 요소 찾기
                parent = link.find_parent('div', class_=True) or link.find_parent('li', class_=True)
                if parent and id(parent) not in seen_set:
                    seen_set.add(id(parent))
                    seen_parents.append(parent)
            if seen_parents:
                return seen_parents, f'auto-detect(link→parent, {len(seen_parents)})'

        return [], 'none(0건)'

    def _parse_saramin_list_item(self, item) -> Dict[str, Any]:
        job_info = self._get_base_job_info()

        try:
            # 제목: .job_tit a → h2 a → 첫번째 링크 폴백
            title_tag = item.select_one('.job_tit a')
            if not title_tag:
                title_tag = item.select_one('h2 a')
            if not title_tag:
                title_tag = item.select_one('a[href*="/recruit/"]')
            if not title_tag:
                title_tag = item.select_one('a[href*="rec_idx"]')

            if title_tag:
                job_info["title"] = title_tag.text.strip()
                href = title_tag.get('href', '')
                if href:
                    if href.startswith('/'):
                        job_info["url"] = "https://www.saramin.co.kr" + href
                    elif href.startswith('http'):
                        job_info["url"] = href

            # 회사명: .corp_name a → .company_nm → 폴백
            corp_tag = item.select_one('.corp_name a')
            if not corp_tag:
                corp_tag = item.select_one('.company_nm a, .company_nm')
            if not corp_tag:
                corp_tag = item.select_one('[class*="corp"] a, [class*="company"]')
            if corp_tag:
                job_info["company"] = corp_tag.text.strip()

            # 마감일: .job_date .date → .date → [class*=date]
            date_tag = item.select_one('.job_date .date')
            if not date_tag:
                date_tag = item.select_one('.date')
            if not date_tag:
                date_tag = item.select_one('[class*="date"]')
            if date_tag:
                job_info["deadline"] = date_tag.text.strip()
                job_info["deadline_date"] = self._parse_deadline_to_datetime(job_info["deadline"])

            # 조건 (고용형태, 급여)
            conditions = item.select('.job_condition span')
            if not conditions:
                conditions = item.select('[class*="condition"] span, .job_meta span')
            for cond in conditions:
                text = cond.text.strip()
                if any(t in text for t in ["정규직", "계약직", "인턴", "파견직", "아르바이트"]):
                    job_info["type"] = text
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
        max_pages: int = 10,
        filter_log: Optional[List[Dict]] = None,
    ) -> List[Dict[str, Any]]:
        """인크루트 검색 — 모든 키워드 반드시 검색"""
        all_jobs = []
        for keyword in keywords:
            try:
                jobs = self._search_incruit_keyword(
                    keyword, deadline_start, deadline_end, location_filter, max_pages,
                    filter_log=filter_log,
                )
                all_jobs.extend(jobs)
                print(f"  인크루트 '{keyword}': {len(jobs)}건")
            except Exception as e:
                print(f"인크루트 오류: {e}")
        result = self._deduplicate_jobs(all_jobs)
        print(f"[인크루트] 전체 {len(all_jobs)}건 → 중복제거 {len(result)}건")
        return result

    def _build_incruit_url(self, keyword, page, location_filter=None):
        """인크루트 검색 URL 생성 — searchjob.asp 엔드포인트 (서버사이드 지역필터)"""
        from urllib.parse import quote

        startno = (page - 1) * 30 + 1

        # 지역필터가 있으면 searchjob.asp (rgn2 지원), 없으면 기존 search.asp
        if location_filter:
            rgn_codes = []
            for loc in location_filter:
                code = INCRUIT_REGION_CODES.get(loc)
                if code:
                    rgn_codes.append(code)

            if rgn_codes:
                rgn_param = ",".join(rgn_codes)
                url = (
                    f"https://job.incruit.com/jobdb_list/searchjob.asp"
                    f"?kw={quote(keyword, encoding='euc-kr')}"
                    f"&rgn2={rgn_param}"
                    f"&startno={startno}"
                )
                return url, "searchjob"

        # 폴백: 기존 search.asp (지역필터 없음)
        url = (
            f"https://search.incruit.com/list/search.asp"
            f"?col=job&kw={quote(keyword, encoding='euc-kr')}"
            f"&startno={startno}"
        )
        return url, "search"

    def _search_incruit_keyword(self, keyword, start, end, location_filter, max_pages, filter_log=None):
        """인크루트 검색 — 서버사이드 지역필터(rgn2) 우선 사용"""
        jobs = []
        endpoint_type = None

        for page in range(1, max_pages + 1):
            url, endpoint_type = self._build_incruit_url(keyword, page, location_filter)

            # 첫 페이지 URL을 filter_log에 기록 (디버그용)
            if page == 1 and filter_log is not None:
                filter_log.append({
                    "title": f"[검색URL] 인크루트 '{keyword}'",
                    "company": "",
                    "source": "인크루트",
                    "deadline": "",
                    "reason": f"🔗 {url} (엔드포인트: {endpoint_type})"
                })

            try:
                res = requests.get(url, headers=self.headers, timeout=self.timeout)

                # [FIX-A] 인크루트는 EUC-KR 계열 — cp949 강제 지정
                res.encoding = 'cp949'

                if res.status_code != 200:
                    print(f"인크루트 HTTP {res.status_code} (page {page})")
                    continue

                soup = BeautifulSoup(res.text, 'html.parser')

                # searchjob.asp와 search.asp의 셀렉터가 다를 수 있음
                items = soup.select('.c_row')
                if not items:
                    items = soup.select('.clist_vv li')
                if not items:
                    # searchjob.asp 전용 셀렉터 시도
                    items = soup.select('.n_job_list li, .list_item, .recruit_list li')

                if page == 1:
                    print(f"  인크루트 '{keyword}' 엔드포인트={endpoint_type}: {len(items)}개 아이템")
                    if filter_log is not None:
                        filter_log.append({
                            "title": f"[디버그] 인크루트 셀렉터",
                            "company": "", "source": "인크루트", "deadline": "",
                            "reason": f"아이템: {len(items)}개 (HTML크기: {len(res.text)}, 엔드포인트: {endpoint_type})"
                        })

                if not items:
                    break

                for item in items:
                    # searchjob.asp는 서버사이드 지역필터 적용됨 → 클라이언트 필터 스킵
                    # search.asp는 서버사이드 지역필터 없음 → 클라이언트 폴백
                    if endpoint_type == "search" and location_filter:
                        if not self._check_location(item, location_filter):
                            if filter_log is not None:
                                _link = item.select_one('a')
                                _title = _link.text.strip() if _link else "?"
                                filter_log.append({
                                    "title": _title, "company": "", "source": "인크루트",
                                    "deadline": "", "reason": "지역 불일치 (텍스트 매칭 폴백)"
                                })
                            continue

                    job = self._parse_incruit_item(item)
                    if job:
                        job["source"] = "인크루트"

                        if self._is_within_deadline(job, start, end):
                            jobs.append(job)
                        elif filter_log is not None:
                            parsed = job.get("deadline_date")
                            parsed_str = parsed.strftime("%Y-%m-%d") if parsed else "파싱실패"
                            range_str = f"{start.strftime('%Y-%m-%d')}~{end.strftime('%Y-%m-%d')}"
                            filter_log.append({
                                "title": job.get("title", ""),
                                "company": job.get("company", ""),
                                "source": "인크루트",
                                "deadline": job.get("deadline", ""),
                                "reason": f"마감일 범위 밖 (원문: {job.get('deadline', '?')} → 파싱: {parsed_str} / 범위: {range_str})"
                            })

            except Exception as e:
                print(f"인크루트 page {page} 오류: {e}")
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
        max_pages: int = 5,
    ) -> List[Dict[str, Any]]:
        """잡코리아 검색 — 모든 키워드 반드시 검색 (Circuit Breaker 제외)"""
        all_jobs = []
        for keyword in keywords:
            try:
                jobs = self._search_jobkorea_keyword(
                    keyword, deadline_start, deadline_end, location_filter, max_pages
                )
                all_jobs.extend(jobs)
                print(f"  잡코리아 '{keyword}': {len(jobs)}건")
            except Exception as e:
                print(f"잡코리아 키워드 '{keyword}' 오류: {e}")
        result = self._deduplicate_jobs(all_jobs)
        print(f"[잡코리아] 전체 {len(all_jobs)}건 → 중복제거 {len(result)}건")
        return result

    def _search_jobkorea_keyword(self, keyword, start, end, location_filter, max_pages):
        """[FIX-JK] cloudscraper + Session 쿠키 + Circuit Breaker"""
        jobs = []

        # [Phase3] Circuit Breaker — 연속 실패 시 즉시 스킵
        if self._jk_circuit_open:
            print(f"[잡코리아] Circuit OPEN — '{keyword}' 스킵")
            return jobs

        # [Phase1+2] 세션 기반 요청
        session = self._get_jk_session()

        jk_headers = {
            **self.headers,
            "Referer": "https://www.jobkorea.co.kr/Search/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

        for page in range(1, max_pages + 1):
            # Circuit Breaker 중간 체크
            if self._jk_circuit_open:
                break

            url = f"https://www.jobkorea.co.kr/Search/?stext={keyword}&Page_No={page}"
            try:
                res = session.get(
                    url,
                    headers=jk_headers,
                    timeout=(JK_CONNECT_TIMEOUT, JK_READ_TIMEOUT),
                    allow_redirects=True,
                )

                # 성공 → Circuit Breaker 리셋
                self._jk_consecutive_fails = 0

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
                        # 지역 필터 (잡코리아는 사이트 내장 필터 없음 → 텍스트 매칭 유지)
                        if not self._check_location(parent, location_filter):
                            continue

                        job_info = self._get_base_job_info()
                        job_info["title"] = link.text.strip() or "제목 없음"
                        job_info["url"] = full_url
                        job_info["source"] = "잡코리아"

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

                # 페이지 간 딜레이 (봇 탐지 방지)
                if page < max_pages:
                    time.sleep(0.8)

            except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
                # [Phase3] 연결 실패 → Circuit Breaker 카운트
                self._jk_consecutive_fails += 1
                print(f"잡코리아 page {page} 연결 실패 ({self._jk_consecutive_fails}/{JK_MAX_CONSECUTIVE_FAILS}): {type(e).__name__}")

                if self._jk_consecutive_fails >= JK_MAX_CONSECUTIVE_FAILS:
                    self._jk_circuit_open = True
                    print(f"[잡코리아] ⚠️ Circuit Breaker OPEN — 연속 {JK_MAX_CONSECUTIVE_FAILS}회 실패, 나머지 키워드 스킵")
                    break
                continue

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
        """잡코리아 상세 정보 (급여, 본문) — Session 기반"""
        detail_info = {}
        try:
            session = self._get_jk_session()
            jk_headers = {
                **self.headers,
                "Referer": "https://www.jobkorea.co.kr/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
            }
            res = session.get(url, headers=jk_headers, timeout=(JK_CONNECT_TIMEOUT, JK_READ_TIMEOUT))
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
) -> tuple:
    """통합 스크래핑 함수 — (결과 리스트, 필터 로그) 튜플 반환"""
    scraper = JobScraper()
    results = []
    filter_log = []  # 제외된 공고 추적

    for i, source in enumerate(sources):
        jobs = []

        if source == "사람인":
            jobs = scraper.search_saramin(keywords, deadline_start, deadline_end, location_filter, filter_log=filter_log)
        elif source == "인크루트":
            jobs = scraper.search_incruit(keywords, deadline_start, deadline_end, location_filter, filter_log=filter_log)
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
        custom_negative=custom_negative,
        filter_log=filter_log
    )
    print(f"[필터] {len(deduped)}건 → {len(filtered)}건 (제거: {len(deduped) - len(filtered)}건)")
    print(f"[필터 로그] 총 {len(filter_log)}건 제외됨")
    return filtered, filter_log
