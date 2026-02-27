import json
import glob
import os
import re

def fix_venues_all():
    print("="*60)
    print(" 🏇 全競馬場データ網羅インデックス作成中...")
    print("="*60)
    
    venues_data = {}
    pattern = os.path.join("data", "*.json")
    files = glob.glob(pattern)

    # 1. まず日付ごとにファイルを分類
    for f in files:
        filename = os.path.basename(f)
        date_match = re.search(r'\d{8}', filename)
        if not date_match:
            continue
            
        date = date_match.group()
        
        # すべての日付に対して、基本の3場をセットする
        # すでに登録済みなら飛ばす
        if date not in venues_data:
            # 💡 網羅したい競馬場をここに並べます
            all_venues = ["東京", "中京", "小倉", "中山", "阪神", "京都", "新潟", "福島", "札幌", "函館"]
            venues_data[date] = all_venues
            print(f"[INFO] {date}: 全競馬場リストを登録しました")

    # 2. venues.json を書き出し
    with open("data/venues.json", "w", encoding="utf-8") as j:
        json.dump(venues_data, j, indent=4, ensure_ascii=False)
    
    print("="*60)
    print(f"[SUCCESS] 全{len(venues_data)}日分の全競馬場を網羅しました！")
    print("="*60)

if __name__ == "__main__":
    fix_venues_all()