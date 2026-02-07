"""
Notion 연결 디버깅 스크립트
이 스크립트를 실행하면 어디서 문제가 발생하는지 정확히 알 수 있습니다.
"""

from notion_client import Client
import json

# ===== 설정 =====
import streamlit as st
import os

# Streamlit secrets 또는 환경변수에서 로드
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    NOTION_DATABASE_ID = st.secrets["NOTION_DATABASE_ID"]
except Exception:
    NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
    NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")

if not NOTION_TOKEN or not NOTION_DATABASE_ID:
    print("⚠️ 경고: NOTION_TOKEN 또는 NOTION_DATABASE_ID가 설정되지 않았습니다.")
    print("Streamlit secrets.toml 파일이나 환경변수를 확인해주세요.")
# ======================================

def test_connection():
    """1단계: Notion API 연결 테스트"""
    print("=" * 50)
    print("[1단계] Notion API 연결 테스트")
    print("=" * 50)
    
    try:
        client = Client(auth=NOTION_TOKEN)
        user = client.users.me()
        print(f"  [OK] 연결 성공!")
        print(f"  - 봇 이름: {user.get('name', 'N/A')}")
        print(f"  - 봇 타입: {user.get('type', 'N/A')}")
        return client
    except Exception as e:
        print(f"  [ERROR] 연결 실패: {e}")
        return None

def search_database(client):
    """1.5단계: 데이터베이스 검색 (올바른 ID 찾기)"""
    print("\n" + "=" * 50)
    print("[1.5단계] 데이터베이스 검색")
    print("=" * 50)
    
    try:
        # 필터 없이 검색 (모든 객체 검색)
        response = client.search(
            query="채용 공고 관리"
        )
        results = response.get("results", [])
        print(f"  [INFO] 검색된 항목: {len(results)}개")
        import json
        print(f"Raw Results: {json.dumps(results, indent=2)}")
        
        for item in results:
            obj_type = item.get("object")
            item_id = item.get("id").replace("-", "")
            
            # 제목 추출 (DB인지 페이지인지에 따라 다름)
            title = "제목없음"
            if obj_type == "database":
                title_list = item.get("title", [])
                if title_list:
                    title = title_list[0].get("plain_text", "제목없음")
            elif obj_type == "page":
                props = item.get("properties", {})
                # 페이지 제목 찾기 (Title 속성)
                for prop in props.values():
                    if prop.get("id") == "title":
                        title_list = prop.get("title", [])
                        if title_list:
                            title = title_list[0].get("plain_text", "제목없음")
                        break
            
            print(f"  - [{obj_type}] ID: {item_id} | 제목: {title}")
            
            if obj_type == "database" and "채용 공고" in title:
                print(f"    -> ✨ 진짜 데이터베이스 찾음! ID: {item_id}")
                return item_id
            
        print("  [WARN] '채용 공고 관리' 데이터베이스를 찾을 수 없습니다.")
        return None
    except Exception as e:
        print(f"  [ERROR] 검색 실패: {e}")
        return None

def test_database_access(client):
    """2단계: 데이터베이스 접근 테스트"""
    print("\n" + "=" * 50)
    print("[2단계] 데이터베이스 접근 테스트")
    print("=" * 50)
    
    try:
        db = client.databases.retrieve(database_id=NOTION_DATABASE_ID)
        print(f"  [OK] 데이터베이스 접근 성공!")
        # print(f"  [DEBUG] 전체 응답: {json.dumps(db, indent=2, ensure_ascii=False)}")
        
        title_list = db.get('title', [])
        if title_list:
            print(f"  - DB 제목: {title_list[0].get('plain_text', 'N/A')}")
            
        # 혹시 페이지인지 확인
        try:
            page = client.pages.retrieve(page_id=NOTION_DATABASE_ID)
            print(f"\n  [CHECK] 페이지 조회 성공 (ID가 페이지일 수도 있음)")
            print(f"  - 페이지 제목: {page.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', 'N/A')}")
            print(f"  - Parent: {page.get('parent')}")
            print(f"  - Url: {page.get('url')}")
        except Exception as e:
            print(f"  [CHECK] 페이지 조회 실패 (순수 DB일 가능성): {e}")
        
        # 속성 목록 출력
        properties = db.get("properties", {})
        print(f"\n  [INFO] 데이터베이스 속성 목록 ({len(properties)}개):")
        print("-" * 40)
        
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "unknown")
            print(f"    - '{prop_name}' ({prop_type})")
        
        if not properties:
            print("  [WARN] 속성이 없습니다! 테스트를 위해 '공고명' 속성을 강제로 추가합니다.")
            properties["공고명"] = {"type": "title"}
            
        return properties
    except Exception as e:
        print(f"  [ERROR] 데이터베이스 접근 실패: {e}")
        return None

def test_create_page(client, db_properties):
    """3단계: 페이지 생성 테스트"""
    print("\n" + "=" * 50)
    print("[3단계] 테스트 페이지 생성 (최소 속성)")
    print("=" * 50)
    
    # Title 속성 찾기
    title_prop = None
    for prop_name, prop_info in db_properties.items():
        if prop_info.get("type") == "title":
            title_prop = prop_name
            break
    
    if not title_prop:
        print("  [ERROR] Title 속성을 찾을 수 없습니다!")
        return False
    
    print(f"  - Title 속성명: '{title_prop}'")
    
    # 최소한의 속성으로 테스트
    test_properties = {
        title_prop: {
            "title": [{"text": {"content": "[TEST] 디버깅 테스트 - 삭제해도 됨"}}]
        }
    }
    
    print(f"\n  테스트 페이지 생성 중...")
    
    try:
        response = client.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=test_properties
        )
        page_id = response.get("id")
        print(f"  [OK] 페이지 생성 성공!")
        print(f"  - 페이지 ID: {page_id}")
        return True
    except Exception as e:
        print(f"  [ERROR] 페이지 생성 실패!")
        print(f"  - 오류: {e}")
        return False

def test_each_property(client, db_properties):
    """4단계: 개별 속성 테스트"""
    print("\n" + "=" * 50)
    print("[4단계] 개별 속성 테스트")
    print("=" * 50)
    
    # Title 속성 찾기
    title_prop = None
    for prop_name, prop_info in db_properties.items():
        if prop_info.get("type") == "title":
            title_prop = prop_name
            break
    
    # 코드에서 사용하는 속성들
    test_cases = [
        ("링크", {"url": "https://example.com/test"}),
        ("지원기업", {"rich_text": [{"text": {"content": "테스트 회사"}}]}),
        ("지원 마감일", {"date": {"start": "2026-03-01"}}),
        ("직무", {"rich_text": [{"text": {"content": "테스트 직무"}}]}),
        ("급여", {"rich_text": [{"text": {"content": "회사 내규"}}]}),
        ("담당업무", {"rich_text": [{"text": {"content": "테스트 업무"}}]}),
        ("근무형태", {"select": {"name": "정규직"}}),
        ("근무시간", {"rich_text": [{"text": {"content": "09:00-18:00"}}]}),
        ("근무예정일", {"rich_text": [{"text": {"content": "협의"}}]}),
        ("근무기간", {"rich_text": [{"text": {"content": "정규직"}}]}),
        ("지원상태", {"select": {"name": "접수 전"}}),
        ("상태", {"select": {"name": "접수 전"}}),  # 이전 코드 호환성 테스트
    ]
    
    available_props = set(db_properties.keys())
    
    print(f"\n  DB에 있는 속성: {available_props}")
    print("\n  속성별 테스트:")
    print("-" * 40)
    
    for prop_name, prop_value in test_cases:
        if prop_name not in available_props:
            print(f"    [INFO] '{prop_name}' - DB 스키마에는 안 보이지만 강제 시도")
            # continue  <-- Commented out to force try
        
        # 테스트용 속성 구성
        test_props = {
            title_prop: {
                "title": [{"text": {"content": f"[TEST] {prop_name} 테스트"}}]
            },
            prop_name: prop_value
        }
        
        try:
            response = client.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties=test_props
            )
            print(f"    [OK] '{prop_name}' - 성공")
            # 테스트 페이지 삭제
            client.pages.update(page_id=response["id"], archived=True)
        except Exception as e:
            error_str = str(e)
            # 에러 메시지에서 핵심 부분만 추출
            if "validation_error" in error_str:
                print(f"    [ERROR] '{prop_name}' - 유효성 오류")
            else:
                print(f"    [ERROR] '{prop_name}' - {error_str[:80]}")

def main():
    global NOTION_DATABASE_ID
    print("\n" + "=" * 50)
    print("     Notion 연결 디버깅 시작")
    print("=" * 50 + "\n")
    
    print(f"설정된 값:")
    print(f"  - Token: {NOTION_TOKEN[:20]}...{NOTION_TOKEN[-10:]}")
    print(f"  - Database ID: {NOTION_DATABASE_ID}")
    
    # 1단계: 연결 테스트
    client = test_connection()
    if not client:
        print("\n[FAIL] Notion 연결에 실패했습니다. 토큰을 확인하세요.")
        return
    
    # 1.5단계: 데이터베이스 검색 (올바른 ID 찾기)
    searched_id = search_database(client)
    if searched_id and searched_id != NOTION_DATABASE_ID:
        print(f"\n[WARN] 설정된 ID({NOTION_DATABASE_ID})와 검색된 ID({searched_id})가 다릅니다!")
        print(f"       -> 검색된 ID로 테스트를 진행합니다.")
        # 전역 변수는 아니지만, 일단 다음 단계 함수들에 검색된 ID를 전달해야 함
        # 하지만 test_database_access 등은 전역변수를 쓰고 있음.
        # 따라서 여기서 globals()를 수정하거나 함수 인자를 바꿔야 함.
        # 간단하게 전역 변수에 할당 (이 스크립트에서만)
        # global NOTION_DATABASE_ID (이미 상단에 선언됨)
        NOTION_DATABASE_ID = searched_id
    
    # 2단계: DB 접근 테스트
    db_properties = test_database_access(client)
    if not db_properties:
        print("\n[FAIL] 데이터베이스 접근에 실패했습니다.")
        print("   - Database ID가 올바른지 확인하세요")
        print("   - Integration이 해당 DB에 연결되어 있는지 확인하세요")
        return
    
    # 3단계: 간단한 페이지 생성 테스트
    success = test_create_page(client, db_properties)
    if not success:
        print("\n[FAIL] 기본 페이지 생성도 실패했습니다.")
        return
    
    # 4단계: 개별 속성 테스트
    test_each_property(client, db_properties)
    
    print("\n" + "=" * 50)
    print("디버깅 완료!")
    print("=" * 50)
    print("\n위 결과를 복사해서 저에게 보여주세요.")

if __name__ == "__main__":
    main()
