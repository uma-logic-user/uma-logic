import json
d = json.load(open('data/history/predictions_20260221.json', 'r', encoding='utf-8'))
races = d['races']
for r in races[:6]:
    preds = r.get('predictions', r.get('horses', []))
    h0 = preds[0] if preds else {}
    print(f"{r['race_num']}R venue={r['venue']} name={r['race_name']} h1={h0.get('horse_name','')}")

print()
print("=== 2/22 ===")
d2 = json.load(open('data/history/predictions_20260222.json', 'r', encoding='utf-8'))
for r in d2['races'][:4]:
    preds = r.get('predictions', r.get('horses', []))
    h0 = preds[0] if preds else {}
    print(f"{r['race_num']}R venue={r['venue']} name={r['race_name']} h1={h0.get('horse_name','')}")
