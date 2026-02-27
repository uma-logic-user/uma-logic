import sys
import io
import time
import json
from datetime import datetime
from pathlib import Path
from typing import List

# Windows環境での文字化け防止
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# パス設定 & モジュールインポート
sys.path.append(str(Path(__file__).parent))
try:
    from fetch_historical_data import get_race_dates_from_calendar, get_race_ids_for_date, fetch_race_result
    from data_processor import DataProcessor
except ImportError as e:
    print(f"Module Import Error: {e}")
    sys.exit(1)

processor = DataProcessor()
DATA_DIR = Path("data")
TARGET_MONTHS = [(2026, 1), (2026, 2)]

def main():
    print("=" * 60)
    print("🏇 UMA-Logic Pro - 公式結果データ再取得 (曜日固定撤廃版)")
    print("=" * 60)

    # 1. 異常データ・ダミーデータのクリア
    suspicious_dates = ["20260131", "20260201", "20260202", "20260207", "20260208"]
    print("\n[INFO] 異常データのクリーニングを開始...")
    for date_str in suspicious_dates:
        fpath = DATA_DIR / f"results_{date_str}.json"
        if fpath.exists():
            fpath.unlink()
            print(f"  🗑️ 削除: {fpath.name}")
            processor.log("INFO", f"異常データ削除: {fpath.name}")
    
    # 2. カレンダーベースでのデータ取得
    total_saved = 0
    
    for year, month in TARGET_MONTHS:
        print(f"\n📅 {year}年{month}月の開催日をカレンダーから取得中...")
        try:
            dates = get_race_dates_from_calendar(year, month)
        except Exception as e:
            print(f"  [ERROR] カレンダー取得失敗: {e}")
            continue
        
        if not dates:
            print("  開催日が見つかりませんでした")
            continue
            
        print(f"  開催日リスト: {dates}")
        
        for date_str in dates:
            # 未来の日付はスキップ
            try:
                target_date = datetime.strptime(date_str, "%Y%m%d")
                if target_date > datetime.now():
                    continue
            except ValueError:
                continue

            print(f"\n  Processing {date_str}...")
            
            fpath = DATA_DIR / f"results_{date_str}.json"
            
            # 既存データチェック (サイズが十分ならスキップ、ただし異常データリストにあったものは削除済みなので再取得される)
            if fpath.exists():
                if fpath.stat().st_size > 15000: # 15KB以上ならまともなデータとみなす
                    print(f"    [SKIP] 既存データあり (サイズOK: {fpath.stat().st_size} bytes)")
                    continue
                else:
                    print(f"    [RETRY] 既存データが小さいまたは空のため再取得")
            
            # レースID取得
            try:
                race_ids = get_race_ids_for_date(date_str)
            except Exception as e:
                print(f"    [ERROR] レースID取得失敗: {e}")
                continue

            if not race_ids:
                print(f"    [WARN] レースIDなし (開催中止の可能性)")
                processor.log("WARN", f"レースIDなし: {date_str}")
                continue
            
            print(f"    {len(race_ids)}レースを取得中...")
            results = []
            for race_id in race_ids:
                race_data = fetch_race_result(race_id)
                if race_data:
                    # DataProcessorで処理（中止判定・メタデータ付与）
                    processed = processor.process_race_data(race_data)
                    results.append(processed)
                time.sleep(1.0) # サーバー負荷軽減
            
            if results:
                # 保存
                output = {
                    "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "races": results
                }
                
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)
                
                print(f"    ✅ 保存完了: {len(results)}レース -> {fpath.name}")
                processor.log("INFO", f"データ保存完了: {date_str}", {"count": len(results)})
                total_saved += 1
            else:
                print(f"    [WARN] 有効なレース結果が取得できませんでした")

    print("\n" + "=" * 60)
    print(f"✅ 全処理完了 (新規・更新: {total_saved}日分)")
    print("=" * 60)

if __name__ == "__main__":
    main()
