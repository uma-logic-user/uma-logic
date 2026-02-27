"""
全 data/results_*.json の空 venue フィールドを race_id から補完する
"""
import json, pathlib

DATA_DIR = pathlib.Path('data')

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
    "61": "\u5712\u7530",   # 園田
    "62": "\u5712\u7530",   # 園田
    "63": "\u59eb\u8def",   # 姫路
    "65": "\u798f\u5c71",   # 福山
    "66": "\u9ad8\u77e5",   # 高知
    "70": "\u4f50\u8cc0",   # 佐賀
    "72": "\u8377\u539f",   # 荒尾
}

def get_venue_from_race_id(race_id: str) -> str:
    s = str(race_id)
    if len(s) >= 10:
        code = s[4:6]
        return VENUE_CODE.get(code, f"\u4e0d\u660e({code})")
    return ""

total_files = 0
total_fixed = 0

for fp in sorted(DATA_DIR.glob("results_*.json")):
    try:
        d = json.loads(fp.read_text(encoding='utf-8'))
        if not isinstance(d, dict):
            continue
        races = d.get('races', [])
        fixed = 0
        for r in races:
            if not r.get('venue'):
                rid = r.get('race_id', '')
                v = get_venue_from_race_id(str(rid))
                if v:
                    r['venue'] = v
                    fixed += 1
        if fixed > 0:
            fp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
            total_fixed += fixed
            total_files += 1
            print(f"  Fixed {fixed} venues in {fp.name}")
    except Exception as e:
        print(f"  ERROR {fp.name}: {e}")

print(f"\nDone: Fixed {total_fixed} venues across {total_files} files")

# 確認
fp221 = DATA_DIR / 'results_20260221.json'
fp222 = DATA_DIR / 'results_20260222.json'
for fp in [fp221, fp222]:
    if fp.exists():
        d = json.loads(fp.read_text(encoding='utf-8'))
        venues = list(set(r.get('venue','') for r in d['races']))
        print(f"{fp.name}: venues = {venues}")
