import json, pathlib

VENUE_CODE = {
    "01": "札幌(JRA)", "02": "函館(JRA)", "03": "福島(JRA)", "04": "新潟(JRA)",
    "05": "東京(JRA)", "06": "中山(JRA)", "07": "中京(JRA)", "08": "京都(JRA)",
    "09": "阪神(JRA)", "10": "小倉(JRA)",
    # 地方競馬
    "30": "門別(地)", "35": "帯広(地)", "42": "盛岡(地)", "43": "水沢(地)",
    "46": "上山(地)", "50": "浦和(地)", "51": "船橋(地)", "54": "大井(地)",
    "55": "川崎(地)", "58": "金沢(地)", "59": "笠松(地)", "60": "名古屋(地)",
    "62": "園田(地)", "63": "姫路(地)", "65": "福山(地)", "66": "高知(地)",
    "70": "佐賀(地)", "72": "荒尾(地)",
}

DATA_DIR = pathlib.Path('data')
for fname in sorted(DATA_DIR.glob('results_*.json'), reverse=True)[:5]:
    d = json.loads(fname.read_text(encoding='utf-8'))
    races = d.get('races', [])
    venue_breakdown = {}
    for r in races:
        rid = str(r.get('race_id', ''))
        code = rid[4:6] if len(rid) >= 10 else '??'
        label = VENUE_CODE.get(code, f"不明({code})")
        venue_breakdown[label] = venue_breakdown.get(label, 0) + 1
    jra = sum(v for k, v in venue_breakdown.items() if 'JRA' in k)
    local = sum(v for k, v in venue_breakdown.items() if '地' in k)
    print(f"\n{fname.name} ({len(races)} races): JRA={jra}, 地方={local}")
    for k, v in sorted(venue_breakdown.items()):
        print(f"  {k}: {v}レース")
