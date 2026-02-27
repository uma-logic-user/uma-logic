"""
2/21の race_name を結果ページから補完する
地方競馬はnetkeibaではなくrace.netkeiba.comの結果ページを使う
"""
import json, pathlib, time, re, requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

def fetch_race_name(race_id: str) -> str:
    """出走馬ページか結果ページからレース名を取得する"""
    # Try results page first
    for url_template in [
        f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}",
        f"https://db.netkeiba.com/race/{race_id}",
    ]:
        try:
            r = requests.get(url_template, headers=HEADERS, timeout=10)
            for enc in ['euc-jp', 'utf-8', 'shift_jis']:
                try:
                    r.encoding = enc
                    soup = BeautifulSoup(r.text, 'html.parser')
                    # Try various selectors
                    for sel in [
                        ('div', 'RaceName'),
                        ('h1', 'RaceTitle'),
                        ('div', 'RaceList_Item02'),
                        ('span', 'RaceName'),
                    ]:
                        elem = soup.find(sel[0], class_=sel[1])
                        if elem:
                            name = elem.get_text(strip=True)
                            if name and not name.startswith('Race '):
                                return name
                except Exception:
                    pass
        except Exception as e:
            print(f"  Error {url_template}: {e}")
        time.sleep(0.5)
    return ""


# Check race_id 202655022101 specifically  
race_id = "202655022101"
print(f"Testing race_id: {race_id}")

# Fetch and show raw HTML snippet
url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
r = requests.get(url, headers=HEADERS, timeout=12)
r.encoding = 'euc-jp'
soup = BeautifulSoup(r.text, 'html.parser')
print(f"Status: {r.status_code}")
print(f"Title tag: {soup.title.get_text() if soup.title else '(none)'}")

# Find any element with "Race" info
for tag in ['div', 'h1', 'h2', 'h3', 'span']:
    elems = soup.find_all(tag)
    for e in elems[:30]:
        classes = ' '.join(e.get('class', []))
        txt = e.get_text(strip=True)[:50]
        if txt and ('Race' in classes or 'race' in classes.lower() or 
                    any(kw in classes for kw in ['Name', 'Title', 'Header'])):
            print(f"  <{tag} class='{classes}'> {txt}")
