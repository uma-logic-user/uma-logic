"""
全JSONファイルの日付フォーマット異常を検出するスクリプト
"""
import json, pathlib, re

DATA_DIR = pathlib.Path('data')
VALID_DATE_RE = re.compile(r'^\d{8}$')

def check_file(fp):
    try:
        d = json.loads(fp.read_text(encoding='utf-8'))
    except Exception as e:
        return f"PARSE_ERROR: {e}"
    
    issues = []
    # トップレベルの date フィールド
    top_date = d.get('date', '')
    if top_date and not VALID_DATE_RE.match(str(top_date)):
        issues.append(f"top-level date={repr(top_date)}")
    
    # races の中
    for i, race in enumerate(d.get('races', [])):
        for field in ['date', 'processed_at', 'generated_at']:
            v = race.get(field, '')
            if v and not isinstance(v, str):
                issues.append(f"races[{i}].{field}={repr(v)} (non-str)")
    
    # generated_at / updated_at
    for field in ['generated_at', 'updated_at', 'saved_at']:
        v = d.get(field, '')
        if v and not isinstance(v, str):
            issues.append(f"top.{field}={repr(v)} (non-str)")
    
    return issues if issues else None


print("=== Scanning data/ for bad dates ===")
bad = []
for fp in sorted(DATA_DIR.rglob('*.json')):
    if 'backup' in fp.name or '.venv' in str(fp):
        continue
    result = check_file(fp)
    if result and result != []:
        bad.append((str(fp.relative_to(DATA_DIR)), result))
        print(f"  BAD: {fp.relative_to(DATA_DIR)} => {result}")

print(f"\nTotal bad files: {len(bad)}")

# history.json の確認
print("\n=== history.json entries ===")
h = json.loads(pathlib.Path('data/history.json').read_text(encoding='utf-8'))
entries = h.get('bets', h.get('entries', h.get('results', [])))
if isinstance(entries, list):
    for e in entries[:10]:
        print(f"  date={e.get('date','')} venue={e.get('venue','')} result={e.get('result','')}")
elif isinstance(entries, dict):
    print("  (dict) keys:", list(entries.keys())[:10])
else:
    print("  Unknown type:", type(entries))
    print("  top keys:", list(h.keys()))
