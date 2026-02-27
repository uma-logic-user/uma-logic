import json, sys

fpath = 'data/history/predictions_20260221.json'
raw = open(fpath, 'rb').read()

for enc in ['cp932', 'shift_jis', 'utf-8', 'utf-8-sig']:
    try:
        s = raw.decode(enc)
        data = json.loads(s)
        races = data.get('races', [])
        r0 = races[0] if races else {}
        preds = r0.get('predictions', r0.get('horses', []))
        h0 = preds[0] if preds else {}
        print(f'=== {enc} ===')
        print('race_id:', r0.get('race_id'))
        print('venue:', repr(r0.get('venue','')))
        print('race_name:', repr(r0.get('race_name','')))
        print('horse_name:', repr(h0.get('horse_name','')))
        print('uma_index:', h0.get('uma_index'))
        print('rank:', h0.get('rank'))
        print()
    except Exception as e:
        print(f'{enc}: ERROR => {e}')
        print()
