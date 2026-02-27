"""
predictions_20260221.json と predictions_20260222.json を
Unicode ポイント直接指定でvenueを修復し、
netkeiba からは horse_name だけを再取得する
"""
import json, pathlib, time, re, requests
from bs4 import BeautifulSoup

# Venue code map using explicit Unicode characters
VENUE_CODE = {
    "01": "\u672d\u5e4c",   # 札幌
    "02": "\u51fd\u9928",   # 函館
    "03": "\u798f\u5cf6",   # 福島
    "04": "\u65b0\u6f5f",   # 新潟
    "05": "\u6771\u4eac",   # 東京
    "06": "\u4e2d\u5c71",   # 中山
    "07": "\u4e2d\u4eac",   # 中京
    "08": "\u4eac\u90fd",   # 京都
    "09": "\u962a\u795e",   # 阪神
    "10": "\u5c0f\u5009",   # 小倉
    "30": "\u9580\u5225",   # 門別
    "35": "\u5e2f\u5e83",   # 帯広
    "42": "\u76db\u5ca1",   # 盛岡
    "43": "\u6c34\u6ca2",   # 水沢
    "46": "\u4e0a\u5c71",   # 上山
    "50": "\u6d66\u548c",   # 浦和
    "51": "\u8239\u6a4b",   # 船橋
    "54": "\u5927\u4e95",   # 大井
    "55": "\u5ddd\u5d0e",   # 川崎
    "58": "\u91d1\u6ca2",   # 金沢
    "59": "\u7b20\u677e",   # 笠松
    "60": "\u540d\u53e4\u5c4b",  # 名古屋
    "62": "\u56e3\u7530",   # 園田
    "63": "\u59eb\u8def",   # 姫路
    "65": "\u798f\u5c71",   # 福山
    "66": "\u9ad8\u77e5",   # 高知
    "70": "\u4f50\u8cc0",   # 佐賀
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

def fetch_horse_names(race_id: str) -> dict:
    """出馬表から 馬番→馬名 マップを返す"""
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.encoding = 'euc-jp'
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"    [ERROR] {e}")
        return {}, ""

    # レース名
    rn_elem = soup.find('div', class_='RaceName') or soup.find('h1', class_='RaceTitle')
    race_name = rn_elem.get_text(strip=True) if rn_elem else ""

    # 馬名マップ
    names = {}
    table = soup.find('table', class_='Shutuba_Table')
    if table:
        for row in table.find_all('tr', class_='HorseList'):
            ub_td = row.find('td', class_=re.compile('Umaban'))
            nm_sp = row.find('span', class_='HorseName')
            if ub_td and nm_sp:
                try:
                    names[int(ub_td.get_text(strip=True))] = nm_sp.get_text(strip=True)
                except ValueError:
                    pass
    return names, race_name


def repair_file(fpath: pathlib.Path):
    data = json.loads(fpath.read_text(encoding='utf-8'))
    races = data.get('races', [])
    print(f"\n=== {fpath.name}: {len(races)} races ===")

    for i, race in enumerate(races):
        race_id = str(race.get('race_id', ''))
        place_code = race_id[4:6]
        venue = VENUE_CODE.get(place_code, f"\u5834\u30b3\u30fc\u30c9{place_code}")
        race['venue'] = venue

        print(f"  [{i+1}/{len(races)}] race_id={race_id} venue={venue}", end=" ", flush=True)

        names_map, race_name_fetched = fetch_horse_names(race_id)
        time.sleep(1.2)

        if race_name_fetched:
            race['race_name'] = race_name_fetched
        elif race.get('race_name', '').startswith('Race ') or not race.get('race_name'):
            race['race_name'] = f"{race.get('race_num', i+1)}R"

        fixed = 0
        for key in ('predictions', 'horses'):
            for h in race.get(key, []):
                ub = h.get('umaban')
                if ub is not None and int(ub) in names_map:
                    h['horse_name'] = names_map[int(ub)]
                    fixed += 1

        print(f"name={race['race_name']} horses_fixed={fixed}")

    fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\nSaved: {fpath}")


if __name__ == '__main__':
    HISTORY_DIR = pathlib.Path('data/history')
    for fname in ['predictions_20260221.json', 'predictions_20260222.json']:
        fp = HISTORY_DIR / fname
        if fp.exists():
            repair_file(fp)

    print("\n=== Final check ===")
    for fname in ['predictions_20260221.json', 'predictions_20260222.json']:
        fp = HISTORY_DIR / fname
        if not fp.exists():
            continue
        d = json.loads(fp.read_text(encoding='utf-8'))
        for r in d['races'][:3]:
            preds = r.get('predictions', r.get('horses', []))
            h0 = preds[0] if preds else {}
            print(f"  [{fname}] {r['race_num']}R {r['venue']} / {r['race_name']} / horse1={h0.get('horse_name','')}")
