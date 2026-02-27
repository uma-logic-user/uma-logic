import json, pathlib

# results_20260222.json の構造確認
for fname in ['results_20260222.json', 'results_20260221.json']:
    fp = pathlib.Path('data') / fname
    if not fp.exists():
        print(f"{fname}: NOT FOUND")
        continue
    d = json.loads(fp.read_text(encoding='utf-8'))
    print(f"\n=== {fname} ===")
    print(f"  type: {type(d)}")
    if isinstance(d, dict):
        print(f"  top-level keys: {list(d.keys())}")
        print(f"  date: {d.get('date')}")
        races = d.get('races', [])
        print(f"  races count: {len(races)}")
        if races:
            r0 = races[0]
            print(f"  races[0] keys: {list(r0.keys())}")
            print(f"  races[0] venue: {repr(r0.get('venue',''))}")
            print(f"  races[0] race_id: {r0.get('race_id','')}")
            print(f"  races[0] race_num: {r0.get('race_num','')}")
            # check each unique venue
            venues = []
            for r in races:
                v = r.get('venue', '')
                if v not in venues:
                    venues.append(v)
            print(f"  unique venues: {venues}")
    elif isinstance(d, list):
        print(f"  list length: {len(d)}")
        if d:
            print(f"  d[0] keys: {list(d[0].keys()) if isinstance(d[0], dict) else type(d[0])}")
