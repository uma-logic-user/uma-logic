"""
全 data/results_*.json を検査して地方競馬が混入しているファイルを列挙し、
JRAのみ再取得して上書きする。
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json, time, re, pathlib, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

DATA_DIR = pathlib.Path('data')
JST = timezone(timedelta(hours=9))
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

JRA_CODES = {"01","02","03","04","05","06","07","08","09","10"}
JRA_NAMES  = {"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京",
               "06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}

def is_jra(rid):
    s = str(rid)
    return len(s) >= 10 and s[4:6] in JRA_CODES

def venue_of(rid):
    s = str(rid)
    code = s[4:6] if len(s) >= 10 else "??"
    return JRA_NAMES.get(code, f"地方({code})")

# ============================================================
# Step1: どのファイルに地方競馬が混入しているか調べる
# ============================================================
print("=== Scanning for non-JRA contamination ===\n")
need_fix = []   # (date_str, local_count, total_count)

for fp in sorted(DATA_DIR.glob("results_*.json"), reverse=True)[:60]:
    try:
        d = json.loads(fp.read_text(encoding='utf-8'))
        if not isinstance(d, dict):
            continue
        date_str = fp.stem.replace("results_", "")
        if not (len(date_str) == 8 and date_str.isdigit()):
            continue
        races = d.get('races', [])
        local = sum(1 for r in races if not is_jra(str(r.get('race_id',''))))
        jra   = len(races) - local
        if local > 0 or jra == 0:
            need_fix.append((date_str, local, len(races)))
            print(f"  NEEDS FIX: {date_str} (JRA={jra}, 地方={local}, total={len(races)})")
        else:
            print(f"  OK:        {date_str} (JRA={jra})")
    except Exception as e:
        print(f"  ERROR: {fp.name}: {e}")

print(f"\n修正必要ファイル数: {len(need_fix)}")

# ============================================================
# Step2: 必要な日付のみ JRA 再取得
# ============================================================

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

def parse_number(text):
    if not text: return 0
    nums = re.findall(r'\d+', text.replace(',',''))
    return int(nums[0]) if nums else 0

def parse_float(text):
    if not text: return 0.0
    nums = re.findall(r'[\d.]+', text)
    return float(nums[0]) if nums else 0.0

def get_jra_ids(date_str):
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
    return sorted(ids)

def fetch_race_result(race_id):
    url = f"https://db.netkeiba.com/race/{race_id}/"
    html = fetch(url, 'euc-jp')
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    code = str(race_id)[4:6]
    race_data = {
        "race_id": race_id,
        "race_num": int(str(race_id)[-2:]),
        "race_name": "",
        "venue": JRA_NAMES.get(code, ""),
        "top3": [], "all_results": [], "payouts": {},
        "processed_at": datetime.now(tz=JST).strftime("%Y-%m-%d %H:%M:%S+09:00")
    }
    for sel in ['.racedata h1', '.data_intro h1', 'h1']:
        el = soup.select_one(sel)
        if el:
            race_data['race_name'] = el.get_text(strip=True)
            break
    for sel in ['.racedata p', '.data_intro p']:
        el = soup.select_one(sel)
        if el:
            txt = el.get_text()
            if '芝' in txt:   race_data['track_type'] = '芝'
            elif 'ダ' in txt: race_data['track_type'] = 'ダート'
            m = re.search(r'(\d{3,4})m', txt)
            if m: race_data['distance'] = int(m.group(1))
            break
    tbl = soup.select_one('table.race_table_01')
    if tbl:
        for row in tbl.select('tr')[1:]:
            cells = row.select('td')
            if len(cells) < 10: continue
            try:
                rank = parse_number(cells[0].get_text(strip=True))
                if rank == 0: continue
                horse_el = cells[3].select_one('a')
                jockey_el = cells[6].select_one('a') if len(cells) > 6 else None
                h = {
                    "着順": rank,
                    "馬番": parse_number(cells[2].get_text(strip=True)),
                    "馬名": horse_el.get_text(strip=True) if horse_el else cells[3].get_text(strip=True),
                    "騎手": jockey_el.get_text(strip=True) if jockey_el else "",
                    "タイム": cells[7].get_text(strip=True) if len(cells) > 7 else "",
                    "上がり3F": cells[11].get_text(strip=True) if len(cells) > 11 else "",
                    "オッズ": parse_float(cells[12].get_text(strip=True)) if len(cells) > 12 else 0.0
                }
                race_data['all_results'].append(h)
                if rank <= 3:
                    race_data['top3'].append(h)
            except: continue
    if not race_data['all_results']:
        return None
    for tbl in soup.select('table.pay_table_01'):
        for row in tbl.select('tr'):
            th = row.select_one('th')
            tds = row.select('td')
            if th and len(tds) >= 2:
                bt = th.get_text(strip=True)
                pv = parse_number(tds[1].get_text(strip=True))
                for key in ["単勝","複勝","枠連","馬連","馬単","ワイド","三連複","三連単"]:
                    if key in bt:
                        race_data['payouts'][key] = pv
                        break
    return race_data

def scrape_and_save(date_str):
    ids = get_jra_ids(date_str)
    if not ids:
        print(f"  [SKIP] JRAレースなし: {date_str}")
        return False
    print(f"  {date_str}: {len(ids)} JRA races")
    results = []
    for i, rid in enumerate(ids):
        r = fetch_race_result(rid)
        if r:
            results.append(r)
            print(f"    [{i+1}/{len(ids)}] {r['venue']} {r['race_num']}R {r['race_name'][:20]}")
        time.sleep(1.5)
    if results:
        out = {
            "date": date_str,
            "updated_at": datetime.now(tz=JST).strftime("%Y-%m-%d %H:%M:%S+09:00"),
            "races": results
        }
        fp = DATA_DIR / f"results_{date_str}.json"
        fp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        venues = sorted(set(r['venue'] for r in results))
        print(f"  -> Saved {fp.name}: {len(results)} races, venues={venues}\n")
        return True
    return False

# 修正が必要なのは土日のみ（平日は競馬なし）且つ2016年以降
print("\n=== Starting JRA re-fetch for contaminated files ===\n")
fixed = 0
for date_str, local_cnt, total in need_fix:
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        # 土(5)・日(6)のみ
        if dt.weekday() not in (5, 6):
            print(f"  SKIP (weekday): {date_str}")
            continue
        # 未来はスキップ
        if dt.date() > datetime.now(tz=JST).date():
            print(f"  SKIP (future): {date_str}")
            continue
        ok = scrape_and_save(date_str)
        if ok:
            fixed += 1
        time.sleep(1)
    except Exception as e:
        print(f"  ERROR {date_str}: {e}")

print(f"\n=== Done: {fixed} dates fixed ===")
