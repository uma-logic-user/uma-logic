"""
2/21 predictions JSON 修復スクリプト
- race_id から venue を復元
- latin-1 trick で horse_name / race_name を修復
- 修復済み JSON を上書き保存
"""
import json, pathlib, re

VENUE_CODE = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉",
    # 地方競馬コード (念のため)
    "30": "門別", "31": "北見", "35": "岩見沢", "36": "帯広",
    "42": "盛岡", "43": "水沢", "46": "上山", "50": "浦和",
    "51": "船橋", "54": "大井", "55": "川崎", "58": "金沢",
    "59": "笠松", "60": "名古屋", "61": "紀三井寺", "62": "園田",
    "63": "姫路", "64": "益田", "65": "福山", "66": "高知",
    "70": "佐賀", "72": "荒尾", "74": "中津",
}

def fix_str(s: str) -> str:
    """latin-1 として再解釈し cp932 でデコードを試みる"""
    if not s:
        return s
    try:
        return s.encode('latin-1').decode('cp932')
    except Exception:
        pass
    try:
        return s.encode('latin-1').decode('shift_jis', errors='replace')
    except Exception:
        return s

def get_venue(race: dict) -> str:
    """venue フィールドがなければ race_id から復元"""
    v = race.get('venue', '')
    if v:
        fixed = fix_str(v)
        # 正常な日本語ならそのまま返す
        if all('\u3000' <= c <= '\u9fff' or '\u30A0' <= c <= '\u30FF' or ord(c) < 0x80 for c in fixed):
            return fixed
    race_id = str(race.get('race_id', ''))
    if len(race_id) >= 10:
        code = race_id[4:6]
        return VENUE_CODE.get(code, f"場コード{code}")
    return v or '不明'


def repair_file(fpath: pathlib.Path):
    raw = fpath.read_bytes()
    data = json.loads(raw.decode('utf-8'))
    races = data.get('races', [])

    for race in races:
        # venue 修復
        race['venue'] = get_venue(race)

        # race_name 修復
        rn = race.get('race_name', '')
        if rn:
            fixed_rn = fix_str(rn)
            race['race_name'] = fixed_rn

        # 各馬の horse_name 修復
        for key in ('horses', 'predictions'):
            horses = race.get(key, [])
            for h in horses:
                hn = h.get('horse_name', '')
                if hn:
                    h['horse_name'] = fix_str(hn)

    out = json.dumps(data, ensure_ascii=False, indent=2)
    fpath.write_text(out, encoding='utf-8')
    print(f"Fixed: {fpath.name}")


if __name__ == '__main__':
    base = pathlib.Path('data/history')
    for f in sorted(base.glob('predictions_*.json')):
        if '_backup' in f.name:
            continue
        repair_file(f)

    print("\n=== Sample check (predictions_20260221.json) ===")
    d = json.loads(pathlib.Path('data/history/predictions_20260221.json').read_text(encoding='utf-8'))
    races = d.get('races', [])
    for r in races[:5]:
        preds = r.get('predictions', r.get('horses', []))
        h0 = preds[0] if preds else {}
        print(f"  {r['race_num']}R venue={r['venue']} name={r['race_name']} horse={h0.get('horse_name','')}")
