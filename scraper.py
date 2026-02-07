"""
scraper.py - 웹 크롤러 모듈 (Requests + BeautifulSoup)
Selenium 제거 및 경량화 버전 (메모리 최적화)
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import re
import urllib3

# SSL 경고 숨김
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class JobScraper:
    """채용 공고 크롤러 (Requests + BS4)"""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
    
    def close(self):
        """리소스 정리 (Requests는 필요 없지만 호환성 유지)"""
        pass
    
    def search_saramin(
        self,
        keywords: List[str],
        deadline_start: datetime,
        deadline_end: datetime,
        max_pages: int = 5,
        max_results: int = 30
    ) -> List[Dict[str, Any]]:
        """사람인 채용 공고 검색"""
        all_jobs = []
        
        for keyword in keywords:
            try:
                jobs = self._search_saramin_keyword(
                    keyword, deadline_start, deadline_end, max_pages
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
        max_pages: int
    ) -> List[Dict[str, Any]]:
        jobs = []
        
        for page in range(1, max_pages + 1):
            url = f"https://www.saramin.co.kr/zf_user/search/recruit?searchword={keyword}&recruitPage={page}&recruitSort=relation&recruitPageCount=40"
            
            try:
                res = requests.get(url, headers=self.headers, timeout=10)
                if res.status_code != 200:
                    continue
                
                soup = BeautifulSoup(res.text, 'html.parser')
                items = soup.select('.item_recruit')
                
                if not items:
                    break
                
                for item in items:
                    try:
                        job_info = self._parse_saramin_list_item(item)
                        if self._is_within_deadline(job_info, deadline_start, deadline_end):
                            # 지역 필터: 서울, 경기 지역만
                            location = item.select_one('.job_condition span:nth-child(1)')
                            if location:
                                loc_text = location.text.strip()
                                if '서울' in loc_text or '경기' in loc_text:
                                    jobs.append(job_info)
                            else:
                                jobs.append(job_info)  # 지역 정보 없으면 포함
                    except Exception:
                        continue
                        
            except Exception as e:
                print(f"사람인 페이지 로드 오류: {e}")
                continue
                
        return jobs

    def _parse_saramin_list_item(self, item) -> Dict[str, Any]:
        job_info = self._get_base_job_info()
        
        try:
            # 제목 및 URL
            title_tag = item.select_one('.job_tit a')
            if title_tag:
                job_info["title"] = title_tag.text.strip()
                job_info["url"] = "https://www.saramin.co.kr" + title_tag['href']
            
            # 회사명
            corp_tag = item.select_one('.corp_name a')
            if corp_tag:
                job_info["company"] = corp_tag.text.strip()
            
            # 마감일
            date_tag = item.select_one('.job_date .date')
            if date_tag:
                job_info["deadline"] = date_tag.text.strip()
                job_info["deadline_date"] = self._parse_deadline_to_datetime(job_info["deadline"])
            
            # 조건 (근무형태 등)
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
        """사람인 상세 정보 (Requests)"""
        detail_info = {}
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code != 200:
                return detail_info
            
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 상세 내용 (간단히 가져오기)
            content = soup.select_one('.wrap_jv_cont')
            if content:
                # 텍스트만 추출하고, 너무 길면 자름 (메모리 절약)
                body_text = content.get_text('\n', strip=True)
                detail_info["body"] = body_text[:2000] 
            
            # 테이블 정보 (급여 등)
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

    def search_incruit(
        self,
        keywords: List[str],
        deadline_start: datetime,
        deadline_end: datetime,
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
                res = requests.get(url, params=params, headers=self.headers, timeout=10)
                # 인코딩 보정
                res.encoding = res.apparent_encoding if res.apparent_encoding else 'utf-8'
                
                if res.status_code != 200:
                    continue
                
                soup = BeautifulSoup(res.text, 'html.parser')
                # 리스트 아이템 선택자 (.clist_vv 또는 .c_row)
                items = soup.select('.c_row, .clist_vv li')
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
            # 제목/링크
            # .cl_top a 또는 .cell_mid .cl_top a, .custom a (구버전)
            link = item.select_one('.cell_mid .cl_top a, span.custom a, .cl_top a')
            
            if link:
                job_info["title"] = link.text.strip()
                href = link.get('href')
                if href:
                    job_info["url"] = href
            
            # 회사 (cpname)
            corp = item.select_one('.cpname')
            if corp:
                job_info["company"] = corp.text.strip()
            
            # 마감일 (cell_last .cl_btm span:first-child)
            # 인크루트는 구조가 다양하므로 여러 시도
            dates = item.select('.cell_last .cl_btm span, .date')
            if dates:
                d_text = dates[0].text.strip() # ~03.01 (일)
                job_info["deadline"] = d_text
                job_info["deadline_date"] = self._parse_deadline_to_datetime(d_text)
                
            return job_info
        except:
            return None

    def search_jobkorea(
        self,
        keywords: List[str],
        deadline_start: datetime,
        deadline_end: datetime,
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
                res = requests.get(url, headers=self.headers, timeout=10)
                if res.status_code != 200:
                    continue
                
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # 잡코리아는 리스트 항목이 post, list-post 등으로 나옴
                # 링크로 찾는게 가장 확실 (Recruit/GI_Read)
                links = soup.select("a[href*='/Recruit/GI_Read/']")
                
                seen_urls = set()
                
                for link in links:
                    href = link['href']
                    full_url = "https://www.jobkorea.co.kr" + href if href.startswith("/") else href
                    # 파라미터 제외하고 기본 URL만 (중복방지)
                    base_url = full_url.split("?")[0]
                    
                    if base_url in seen_urls:
                        continue
                    seen_urls.add(base_url)
                    
                    # 링크의 부모/조상에서 정보 추출
                    # 보통 div.post-list-info 또는 유사
                    parent = link.find_parent('div', class_=lambda x: x and ('post' in x or 'list' in x))
                    
                    if parent:
                        job_info = self._get_base_job_info()
                        job_info["title"] = link.text.strip() or "제목 없음"
                        job_info["url"] = full_url
                        
                        # 회사명
                        corp = parent.select_one('.name, .corp-name')
                        if corp:
                            job_info["company"] = corp.text.strip()
                        
                        # 마감일 (보통 .date)
                        date_item = parent.select_one('.date, .deadline')
                        if date_item:
                            d_text = date_item.text.strip()
                            # D-N 제거
                            d_text = re.sub(r'D-\d+', '', d_text).strip()
                            job_info["deadline"] = d_text
                            job_info["deadline_date"] = self._parse_deadline_to_datetime(d_text)
                        
                        # 데드라인 체크
                        if self._is_within_deadline(job_info, start, end):
                            jobs.append(job_info)
            except Exception:
                continue
        return jobs

    # 헬퍼 함수들
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
        # 마감일 파싱 실패 시 True (안전하게 포함)
        if not job_info.get("deadline_date"):
            return True
        # timezone 정보 제거 (naive datetime 비교)
        deadline = job_info["deadline_date"]
        if deadline.tzinfo:
             deadline = deadline.replace(tzinfo=None)
        return start <= deadline <= end

    def _parse_deadline_to_datetime(self, text: str) -> Optional[datetime]:
        if not text: return None
        text = text.strip()
        now = datetime.now()
        
        try:
            # 상시, 채용시
            if any(x in text for x in ["상시", "채용시", "수시"]):
                return now + timedelta(days=365)
            
            # 오늘마감
            if "오늘" in text:
                return now
            
            # 내일마감
            if "내일" in text:
                return now + timedelta(days=1)
            
            # 날짜 패턴 (MM/DD, MM.DD)
            # D-N 제거
            text = re.sub(r'D-\d+', '', text).strip()
            
            match = re.search(r'(\d{1,2})[./-](\d{1,2})', text)
            if match:
                month, day = map(int, match.groups())
                year = now.year
                # 과거 날짜면 내년으로 (예: 12월에 1월 마감 공고)
                if month < now.month:
                    year += 1
                return datetime(year, month, day)
        except:
            pass
        return None

def scrape_jobs(
    sources: List[str],
    keywords: List[str],
    deadline_start: datetime,
    deadline_end: datetime,
    progress_callback=None
) -> List[Dict[str, Any]]:
    """통합 스크래핑 함수"""
    scraper = JobScraper()
    results = []
    
    # 0~100 사이 값
    # 소스별로 n분의 1
    
    total_sources = len(sources)
    
    for i, source in enumerate(sources):
        base_progress = i / total_sources
        
        if source == "사람인":
            jobs = scraper.search_saramin(keywords, deadline_start, deadline_end)
            # 상세 정보 (옵션)
            for j, job in enumerate(jobs):
                if job.get('url'):
                     det = scraper.parse_saramin_detail(job['url'])
                     job.update(det)
                
                # 상세 진행률 반영
                # 0.5 (수집) + 0.5 (상세)
                # 근데 여기서 상세까지 하면 너무 느릴 수 있음.
                # 일단 진행.
            results.extend(jobs)
            
        elif source == "인크루트":
            jobs = scraper.search_incruit(keywords, deadline_start, deadline_end)
            results.extend(jobs)
            
        elif source == "잡코리아":
            jobs = scraper.search_jobkorea(keywords, deadline_start, deadline_end)
            results.extend(jobs)
        
        if progress_callback:
            progress_callback((i + 1) / total_sources)
            
    return results
