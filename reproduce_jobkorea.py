import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

def test_jobkorea(keyword="국민은행"):
    url = f"https://www.jobkorea.co.kr/Search/?stext={keyword}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"Testing URL: {url}")
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {res.status_code}")
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. 공고 리스트 컨테이너 찾기
        # .list-default .list-post 또는 .post-list-info
        posts = soup.select(".list-post, .post-list, .post")
        print(f"Found {len(posts)} potential post elements")
        
        # 2. 링크 찾기 테스트 (기존 로직)
        links = soup.select("a[href*='/Recruit/GI_Read/']")
        print(f"Found {len(links)} links with '/Recruit/GI_Read/'")
        
        if not links:
            print("No links found with GI_Read. Dumping some HTML...")
            print(soup.prettify()[:500])
            
            # 다른 패턴의 링크가 있는지 확인
            all_links = soup.select(".post-list-info a.title")
            print(f"Alternative selector found: {len(all_links)}")
            for l in all_links[:3]:
                 print(f" - Alt Link: {l.get('href')}")
            
        for i, link in enumerate(links[:3]):
            print(f"\n--- Item {i+1} ---")
            print(f"Title: {link.text.strip()}")
            print(f"Link: {link.get('href')}")
            
            # 날짜 파싱 테스트
            parent = link.find_parent('div', class_=lambda x: x and ('post' in x or 'list' in x))
            if parent:
                date_item = parent.select_one('.date, .deadline')
                if date_item:
                    print(f"Date Text: {date_item.text.strip()}")
                else:
                     print("Date element not found")
            else:
                 print("Parent not found")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_jobkorea()
