"""
2/21(土)・2/22(日) の中央競馬(JRA)結果のみを
db.netkeiba.com から再取得して results_YYYYMMDD.json を上書きする
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json, time, pathlib, re, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

DATA_DIR = pathlib.Path('data')
JST = timezone(timedelta(hours=9))
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

JRA_CODES = {"01","02","03","04","05","06","07","08","09","10"}
# 01=札幌 02=函館 03=福島 04=新潟 05=東京 06=中山 07=中京 08=京都 09=阪神 10=小倉
JRA_VENUE_NAMES = {
    "01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京",
    "06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"
}

def fetch(url, enc='euc-jp'):
    for _ in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.encoding = enc
            return r.text
        except Exception as e:
            print(f"  [RETRY] {e}")
            time.sleep(2)
    return None

def is_jra(race_id):
    s = str(race_id)
    return len(s) >= 10 and s[4:6] in JRA_CODES

def get_jra_race_ids(date_str):
    url = f"https://db.netkeiba.com/race/list/{date_str}/"
    html = fetch(url, 'euc-jp')
    if not html:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    ids = []
    for a in soup.select('a[href*="/race/"]'):
        m = re.search(r'/race/(\d{12})/', a.get('href',''))
        if m:
            rid = m.group(1)
            if rid not in ids and is_jra(rid):
                ids.append(rid)
    print(f"  {date_str}: found {len(ids)} JRA race_ids")
    return sorted(ids)

def parse_number(text):
    if not text: return 0
    nums = re.findall(r'\d+', text.replace(',',''))
    return int(nums[0]) if nums else 0

def parse_float(text):
    if not text: return 0.0
    nums = re.findall(r'[\d.]+', text)
    return float(nums[0]) if nums else 0.0

def fetch_race_result(race_id):
    url = f"https://db.netkeiba.com/race/{race_id}/"
    html = fetch(url, 'euc-jp')
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')

    code = str(race_id)[4:6]
    venue = JRA_VENUE_NAMES.get(code, f"場{code}")

    race_data = {
        "race_id": race_id,
        "race_num": int(str(race_id)[-2:]),
        "race_name": "",
        "venue": venue,
        "top3": [], "all_results": [], "payouts": {},
        "processed_at": datetime.now(tz=JST).strftime("%Y-%m-%d %H:%M:%S+09:00")
    }

    # レース名
    for sel in ['.racedata h1', '.data_intro h1', 'h1']:
        el = soup.select_one(sel)
        if el:
            race_data['race_name'] = el.get_text(strip=True)
            break

    # 距離・トラック
    for sel in ['.racedata p', '.data_intro p', '.RaceData01']:
        el = soup.select_one(sel)
        if el:
            txt = el.get_text()
            if '芝' in txt:   race_data['track_type'] = '芝'
            elif 'ダ' in txt: race_data['track_type'] = 'ダート'
            m = re.search(r'(\d{3,4})m', txt)
            if m: race_data['distance'] = int(m.group(1))
            break

    # 着順テーブル
    tbl = soup.select_one('table.race_table_01')
    if tbl:
        for row in tbl.select('tr')[1:]:
            cells = row.select('td')
            if len(cells) < 10: continue
            try:
                rank = parse_number(cells[0].get_text(strip=True))
                if rank == 0: continue
                horse_el = cells[3].select_one('a')
                horse_name = horse_el.get_text(strip=True) if horse_el else cells[3].get_text(strip=True)
                jockey_el = cells[6].select_one('a') if len(cells)>6 else None
                h = {
                    "着順": rank,
                    "馬番": parse_number(cells[2].get_text(strip=True)),
                    "馬名": horse_name,
                    "騎手": jockey_el.get_text(strip=True) if jockey_el else "",
                    "タイム": cells[7].get_text(strip=True) if len(cells)>7 else "",
                    "上がり3F": cells[11].get_text(strip=True) if len(cells)>11 else "",
                    "オッズ": parse_float(cells[12].get_text(strip=True)) if len(cells)>12 else 0.0
                }
                race_data['all_results'].append(h)
                if rank <= 3:
                    race_data['top3'].append(h)
            except: continue

    if not race_data['all_results']:
        return None

    # 払戻金
    for tbl in soup.select('table.pay_table_01'):
        for row in tbl.select('tr'):
            th = row.select_one('th')
            tds = row.select('td')
            if th and len(tds) >= 2:
                bt = th.get_text(strip=True)
                payout = parse_number(tds[1].get_text(strip=True))
                for key in ["単勝","複勝","枠連","馬連","馬単","ワイド","三連複","三連単"]:
                    if key in bt:
                        race_data['payouts'][key] = payout
                        break

    return race_data


def scrape_date(date_str):
    race_ids = get_jra_race_ids(date_str)
    if not race_ids:
        print(f"  [SKIP] JRAレースなし: {date_str}")
        return

    results = []
    for i, rid in enumerate(race_ids):
        print(f"  [{i+1}/{len(race_ids)}] {rid} ...", end=' ')
        r = fetch_race_result(rid)
        if r:
            results.append(r)
            print(f"OK ({r['venue']} {r['race_num']}R {r['race_name'][:15]})")
        else:
            print("SKIP")
        time.sleep(1.5)

    if results:
        out = {
            "date": date_str,
            "updated_at": datetime.now(tz=JST).strftime("%Y-%m-%d %H:%M:%S+09:00"),
            "races": results
        }
        fp = DATA_DIR / f"results_{date_str}.json"
        fp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        venues = list(set(r['venue'] for r in results))
        print(f"\n  Saved: {fp.name} ({len(results)} JRA races, venues={venues})\n")
    else:
        print(f"  [WARN] 結果データなし: {date_str}")


if __name__ == '__main__':
    for date in ['20260221', '20260222']:
        print(f"\n===== {date} =====")
        scrape_date(date)
    print("\nDone.")
