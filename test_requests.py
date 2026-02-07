
import requests
from bs4 import BeautifulSoup
import time

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

def check_saramin():
    url = "https://www.saramin.co.kr/zf_user/search/recruit?searchword=python&recruitPage=1"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Saramin StatusCode: {res.status_code}")
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select('.item_recruit')
            print(f"Saramin Items: {len(items)}")
            if items:
                print(f"First item title: {items[0].select_one('.job_tit a').text.strip()}")
            with open('saramin_dump.html', 'w', encoding='utf-8') as f:
                f.write(res.text)
        else:
            print("Saramin failed or redirected")
    except Exception as e:
        print(f"Saramin Error: {e}")

def check_jobkorea():
    url = "https://www.jobkorea.co.kr/Search/?stext=python"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Jobkorea StatusCode: {res.status_code}")
        if res.status_code == 200:
            with open('jobkorea_dump.html', 'w', encoding='utf-8') as f:
                f.write(res.text)
            print("Jobkorea dumped.")
    except Exception as e:
        print(f"Jobkorea Error: {e}")

def check_incruit():
    url = "https://search.incruit.com/list/search.asp"
    params = {'col': 'job', 'kw': 'python'}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        res.encoding = 'euc-kr' # Incruit often uses euc-kr
        print(f"Incruit StatusCode: {res.status_code}")
        if res.status_code == 200:
            with open('incruit_dump.html', 'w', encoding='utf-8') as f: # Save as utf-8 but decoded from euc-kr
                f.write(res.text)
            print("Incruit dumped.")
    except Exception as e:
        print(f"Incruit Error: {e}")

if __name__ == "__main__":
    check_saramin()
    check_jobkorea()
    check_incruit()
