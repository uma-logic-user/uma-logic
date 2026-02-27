import json
from pathlib import Path

data = json.loads(Path('data/predictions_20260220.json').read_text(encoding='utf-8'))
races = data.get('races', [])
print(f'本日の予想データ: {len(races)}レース')
venues = list(set(r['venue'] for r in races))
print(f'競馬場: {sorted(venues)}')
for v in sorted(venues):
    cnt = len([r for r in races if r['venue'] == v])
    print(f'  {v}: {cnt}レース')
top_races = [r for r in races if r.get('rank', '') in ['S+', 'S']]
print(f'S+/Sランク: {len(top_races)}レース')
for r in top_races:
    honmei = r.get('honmei', {})
    print(f'  {r["venue"]} {r["race_num"]}R {r["race_name"]} [{r["rank"]}] 本命: {honmei.get("horse_name","")} (指数{honmei.get("uma_index",0)})')
print('データ確認OK')
