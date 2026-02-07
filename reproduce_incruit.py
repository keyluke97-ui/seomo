import requests
from bs4 import BeautifulSoup
import sys

def test_incruit(keyword="기획"):
    url = "https://search.incruit.com/list/search.asp"
    params = {
        "col": "job",
        "kw": keyword,
        "startno": 1
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"URL: {url}")
    res = requests.get(url, params=params, headers=headers, timeout=10)

    # Force UTF-8 based on the meta tag we saw
    res.encoding = 'utf-8' 
    
    soup = BeautifulSoup(res.text, 'html.parser')
    
    items = soup.select('.c_row') 
    if not items:
         items = soup.select('.clist_vv li')

    if not items:
        print("No items found.")
        return

    for i, item in enumerate(items[:1]):
        print(f"\n--- Item {i+1} HTML ---")
        print(item.prettify())
        
        print("\n--- Parsed Info ---")
        
        # Link Logic Test
        # We need to find the link that goes to 'jobdb_info/jobpost.asp' not 'company'
        
        # Try finding all links
        links = item.select('a')
        for l in links:
            print(f"Link: {l.get('href')} | Text: {l.text.strip()}")

        # Current Logic
        link = item.select_one('.cell_mid .cl_top a, span.custom a, .cl_top a')
        if link:
            print(f"Current Logic Selected: {link.get('href')}")


if __name__ == "__main__":
    test_incruit()
