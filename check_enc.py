import json

fpath = 'data/history/predictions_20260222.json'
raw = open(fpath, 'rb').read()

for enc in ['utf-8', 'cp932', 'shift_jis', 'utf-8-sig']:
    try:
        data = json.loads(raw.decode(enc))
        races = data.get('races', [])
        r0 = races[0] if races else {}
        preds = r0.get('predictions', [])
        h0 = preds[0] if preds else {}
        print(f'=== {enc} ===')
        print('venue:', r0.get('venue'))
        print('race_name:', r0.get('race_name'))
        print('horse_name:', h0.get('horse_name'))
        break
    except Exception as e:
        print(f'{enc}: ERROR {e}')
