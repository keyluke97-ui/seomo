"""
config.py - 직군 및 키워드 설정 관리 모듈

리팩토링: 지역 필터 옵션 추가
"""
import json
import os
from pathlib import Path

# 설정 파일 경로
CONFIG_FILE = Path(__file__).parent / "user_config.json"

# 기본 직군별 키워드 설정
DEFAULT_JOB_CATEGORIES = {
    "대학교 행정직": ["대학교", "대학 행정", "대학 교직원", "교육 행정"],
    "교직원": ["교직원", "학교", "교무", "행정실"],
    "은행": ["은행", "금융", "은행원", "텔러", "창구"],
    "유학": ["유학", "해외", "어학연수", "유학원"],
}

# 검색 소스 목록
JOB_SOURCES = {
    "사람인": {
        "enabled": True,
        "base_url": "https://www.saramin.co.kr",
        "search_url": "https://www.saramin.co.kr/zf_user/search/recruit"
    },
    "인크루트": {
        "enabled": True,
        "base_url": "https://www.incruit.com",
        "search_url": "https://search.incruit.com/list/search.asp"
    },
    "잡코리아": {
        "enabled": False,
        "base_url": "https://www.jobkorea.co.kr",
        "search_url": "https://www.jobkorea.co.kr/Search"
    },
    "대학교 사이트": {
        "enabled": False,
        "base_url": "",
        "search_url": ""
    }
}

# ──────────────────────────────────────
# 사람인 기업형태(company_cd) 코드 매핑
# 0=대기업, 1=중견기업, 2=중소기업, 3=외국계, 4=공기업/공공기관,
# 5=비영리/사회적기업, 6=병원/의료, 7=교육기관, 9=기타, 10=스타트업
# ──────────────────────────────────────
SARAMIN_COMPANY_TYPES = {
    "대기업": "0",
    "중견기업": "1",
    "중소기업": "2",
    "외국계": "3",
    "공기업/공공기관": "4",
    "비영리/사회적기업": "5",
    "병원/의료": "6",
    "교육기관": "7",
    "기타": "9",
    "스타트업": "10",
}

# 직군별 기본 기업형태 필터 (사람인 서버사이드 필터)
# None = 전체, 쉼표 구분 문자열 = 복수 선택
CATEGORY_COMPANY_FILTER = {
    "대학교 행정직": "4,5,7",   # 공기업/공공기관 + 비영리 + 교육기관
    "교직원": "4,5,7",          # 공기업/공공기관 + 비영리 + 교육기관
    "은행": "0,1,3",            # 대기업 + 중견 + 외국계
    "유학": None,               # 전체 (업종 다양)
}

# 지역 필터 옵션
LOCATION_OPTIONS = [
    "서울", "경기", "인천", "부산", "대구", "대전",
    "광주", "울산", "세종", "강원", "충북", "충남",
    "전북", "전남", "경북", "경남", "제주"
]


def load_config() -> dict:
    """JSON 파일에서 사용자 설정 로드"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    return {
        "job_categories": DEFAULT_JOB_CATEGORIES.copy(),
        "custom_categories": []
    }


def save_config(config: dict) -> bool:
    """변경된 설정을 JSON 파일에 저장"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def get_keywords(category: str, config: dict = None) -> list:
    """선택된 직군의 키워드 반환"""
    if config is None:
        config = load_config()

    categories = config.get("job_categories", DEFAULT_JOB_CATEGORIES)
    return categories.get(category, [])


def add_category(category_name: str, keywords: list, config: dict = None) -> dict:
    """새 직군 추가"""
    if config is None:
        config = load_config()

    config["job_categories"][category_name] = keywords
    if category_name not in config.get("custom_categories", []):
        config.setdefault("custom_categories", []).append(category_name)

    save_config(config)
    return config


def update_keywords(category: str, keywords: list, config: dict = None) -> dict:
    """직군의 키워드 업데이트"""
    if config is None:
        config = load_config()

    config["job_categories"][category] = keywords
    save_config(config)
    return config


def get_all_categories(config: dict = None) -> list:
    """모든 직군 목록 반환"""
    if config is None:
        config = load_config()

    return list(config.get("job_categories", DEFAULT_JOB_CATEGORIES).keys())
