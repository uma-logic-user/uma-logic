"""
東京競馬場の結果データを手動で取得するスクリプト
2026年2月21日の東京競馬場データを取得
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# パス設定
sys.path.append(str(Path(__file__).parent))
DATA_DIR = Path("data")

def fetch_tokyo_race_results():
    """東京競馬場のレース結果を取得"""
    print("🏇 東京競馬場の結果データを手動で取得します...")
    
    # 東京競馬場のレースIDリスト（2026年2月21日）
    # 実際のレースIDはネットけいばのサイト構造に基づく
    tokyo_race_ids = [
        "202605010101", "202605010102", "202605010103", "202605010104", "202605010105",
        "202605010106", "202605010107", "202605010108", "202605010109", "202605010110",
        "202605010111", "202605010112"
    ]
    
    results = []
    
    try:
        from fetch_historical_data import fetch_race_result
        from data_processor import DataProcessor
        
        processor = DataProcessor()
        
        print(f"📊 {len(tokyo_race_ids)}レースを取得中...")
        
        for i, race_id in enumerate(tokyo_race_ids, 1):
            print(f"  レース {i}/{len(tokyo_race_ids)}: {race_id}")
            
            try:
                race_data = fetch_race_result(race_id)
                if race_data:
                    processed = processor.process_race_data(race_data)
                    results.append(processed)
                    print(f"    ✅ 取得成功")
                else:
                    print(f"    ❌ 取得失敗")
                
                time.sleep(1.0)  # サーバー負荷軽減
                
            except Exception as e:
                print(f"    ❌ エラー: {e}")
                continue
        
    except ImportError as e:
        print(f"❌ モジュールインポートエラー: {e}")
        return False
    
    # 結果を保存
    if results:
        output = {
            "date": "2026-02-21",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "races": results
        }
        
        output_file = DATA_DIR / "results_tokyo_20260221.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 東京競馬場データを保存しました: {output_file}")
        print(f"📊 取得レース数: {len(results)}レース")
        return True
    else:
        print("❌ 有効なレース結果が取得できませんでした")
        return False

def main():
    """メイン処理"""
    print("=" * 60)
    print("🏇 UMA-Logic Pro - 東京競馬場データ手動取得")
    print("=" * 60)
    
    success = fetch_tokyo_race_results()
    
    if success:
        print("\n✅ 東京競馬場データの取得が完了しました！")
        print("📝 次のステップ:")
        print("   1. 取得したデータをメインの結果ファイルに統合")
        print("   2. オッズ更新スクリプトを実行")
    else:
        print("\n❌ データ取得に失敗しました")

if __name__ == "__main__":
    main()