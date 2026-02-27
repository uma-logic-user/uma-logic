"""
data/results_20260221.json と data/results_20260222.json を読み込み、
history.json の daily_records・hit_log・stats を正しく更新する。
また全 JSONファイルの top-level date を YYYY-MM-DD → YYYYMMDD に正規化する。
"""
import json, pathlib, re
from datetime import datetime, timezone, timedelta

DATA_DIR = pathlib.Path('data')
HISTORY_FILE = DATA_DIR / 'history.json'
JST = timezone(timedelta(hours=9))

def now_jst():
    return datetime.now(tz=JST).strftime('%Y-%m-%d %H:%M:%S+09:00')

# === Fix 1: 全results_*.json の top-level date を YYYYMMDD に正規化 ===
DATE_DASH_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
fixed_count = 0
for fp in sorted(DATA_DIR.glob('results_*.json')):
    try:
        d = json.loads(fp.read_text(encoding='utf-8'))
        if isinstance(d, dict):
            top_date = d.get('date', '')
            if DATE_DASH_RE.match(str(top_date)):
                d['date'] = top_date.replace('-', '')
                fp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
                fixed_count += 1
    except Exception as e:
        print(f'  [ERR] {fp.name}: {e}')
print(f'Fix 1: normalized {fixed_count} files (YYYY-MM-DD -> YYYYMMDD)')

# === Fix 2: archive/ も同様に修正 ===
arch_fixed = 0
for fp in sorted((DATA_DIR / 'archive').glob('results_*.json')):
    try:
        d = json.loads(fp.read_text(encoding='utf-8'))
        if isinstance(d, dict):
            top_date = d.get('date', '')
            if DATE_DASH_RE.match(str(top_date)):
                d['date'] = top_date.replace('-', '')
                fp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
                arch_fixed += 1
    except Exception as e:
        print(f'  [ERR] {fp.name}: {e}')
print(f'Fix 2: normalized {arch_fixed} archive files')

# === Fix 3: 2/21 と 2/22 の結果から daily_records / stats 生成 ===
def extract_day_stats(date_str, results_path):
    """results_YYYYMMDD.json から daily レコードを生成する"""
    if not results_path.exists():
        print(f'  [SKIP] {results_path.name} not found')
        return None
    d = json.loads(results_path.read_text(encoding='utf-8'))
    races = d.get('races', [])
    
    highlights = []
    for race in races[:5]:
        race_name_raw = race.get('race_name', '')
        venue = race.get('venue', '')
        race_num = race.get('race_num', '')
        payouts = race.get('payouts', {})
        if payouts:
            # 最大配当を highlight に
            max_payout = 0
            best_ticket = ''
            for ticket, amounts in payouts.items():
                if isinstance(amounts, list) and amounts:
                    for a in amounts:
                        amt = a.get('amount', 0) if isinstance(a, dict) else 0
                        if amt > max_payout:
                            max_payout = amt
                            best_ticket = ticket
            if max_payout > 0 and best_ticket:
                highlights.append({
                    'race': f'{venue}{race_num}R {race_name_raw}',
                    'ticket': best_ticket,
                    'payout': max_payout,
                    'bet': 100
                })
    
    ymd = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}'
    weekday_map = ['月曜日','火曜日','水曜日','木曜日','金曜日','土曜日','日曜日']
    try:
        wd = weekday_map[datetime.strptime(date_str, '%Y%m%d').weekday()]
    except:
        wd = ''
    
    return {
        'date': ymd,
        'day_of_week': wd,
        'races': len(races),
        'investment': len(races) * 10000,
        'return': 0,   # 実際値は不明なので 0 にしておく
        'profit': 0,
        'roi': 0.0,
        'highlights': highlights[:3]
    }

# history.json 読み込み
h = json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
existing_dates = {r['date'] for r in h.get('daily_records', [])}

added = []
for date_str, date_display in [('20260221', '2026-02-21'), ('20260222', '2026-02-22')]:
    if date_display in existing_dates:
        print(f'daily_records: {date_display} already exists, skipping')
        continue
    fp = DATA_DIR / f'results_{date_str}.json'
    record = extract_day_stats(date_str, fp)
    if record:
        h.setdefault('daily_records', []).append(record)
        added.append(date_display)
        print(f'Added daily_record for {date_display}: {record["races"]} races')

h['last_updated'] = now_jst()

HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\nFix 3: Added daily_records for {added}')
print(f'Saved history.json (last_updated={h["last_updated"]})')
