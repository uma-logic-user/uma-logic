"""
データ不整合を解決するためのスクリプト
予測データと結果データの整合性を確保する
"""
import json
from pathlib import Path
from datetime import datetime

# パス設定
DATA_DIR = Path("data")
HISTORY_DIR = DATA_DIR / "history"
PREDICTIONS_FILE = HISTORY_DIR / "predictions_20260221.json"
RESULTS_FILE = DATA_DIR / "results_20260221.json"

def load_json_file(file_path):
    """JSONファイルを読み込む"""
    if not file_path.exists():
        print(f"❌ ファイルが見つかりません: {file_path}")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ ファイル読み込みエラー: {file_path}: {e}")
        return None

def analyze_data_inconsistency():
    """データ不整合を分析"""
    print("🔍 データ不整合の分析を開始します...")
    
    # ファイル読み込み
    predictions_data = load_json_file(PREDICTIONS_FILE)
    results_data = load_json_file(RESULTS_FILE)
    
    if not predictions_data or not results_data:
        return
    
    print("📊 データ分析結果:")
    print(f"   - 予測データ日付: {predictions_data.get('date', '不明')}")
    print(f"   - 結果データ日付: {results_data.get('date', '不明')}")
    print(f"   - 予測データレース数: {len(predictions_data.get('races', []))}")
    print(f"   - 結果データレース数: {len(results_data.get('races', []))}")
    
    # 競馬場コードの分析
    pred_race_ids = [race.get('race_id', '') for race in predictions_data.get('races', [])]
    result_race_ids = [race.get('race_id', '') for race in results_data.get('races', [])]
    
    if pred_race_ids:
        print(f"   - 予測データ競馬場コード: {pred_race_ids[0][4:6]}")
        print(f"   - 予測データレース番号: {pred_race_ids[0][6:10]}")
    
    if result_race_ids:
        print(f"   - 結果データ競馬場コード: {result_race_ids[0][4:6]}")
        print(f"   - 結果データレース番号: {result_race_ids[0][6:10]}")
    
    # 不一致の特定
    if pred_race_ids and result_race_ids:
        pred_prefix = pred_race_ids[0][:6]  # 最初の6文字（年月+競馬場コード）
        result_prefix = result_race_ids[0][:6]
        
        if pred_prefix != result_prefix:
            print(f"❌ 深刻な不一致: 競馬場コードが異なります")
            print(f"   - 予測: {pred_prefix}")
            print(f"   - 結果: {result_prefix}")
            return False
        
        # レース番号の不一致チェック
        pred_race_num = pred_race_ids[0][6:8]  # レース番号部分
        result_race_num = result_race_ids[0][6:8]
        
        if pred_race_num != result_race_num:
            print(f"❌ レース番号不一致: {pred_race_num} vs {result_race_num}")
            return False
    
    print("✅ データに重大な不一致は見つかりませんでした")
    return True

def restore_from_backup():
    """バックアップからデータを復元"""
    print("🔄 バックアップからデータを復元します...")
    
    backup_file = HISTORY_DIR / "predictions_20260221_backup.json"
    if not backup_file.exists():
        print("❌ バックアップファイルが見つかりません")
        return False
    
    try:
        # バックアップから復元
        backup_data = load_json_file(backup_file)
        if not backup_data:
            return False
        
        with open(PREDICTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        print("✅ バックアップからデータを復元しました")
        return True
    except Exception as e:
        print(f"❌ 復元中にエラー: {e}")
        return False

def main():
    """メイン処理"""
    print("=" * 60)
    print("🏇 UMA-Logic Pro - データ不整合解決ツール")
    print("=" * 60)
    
    # データ分析
    if not analyze_data_inconsistency():
        print("\n🔄 データ不整合を検出したため、修復を試みます...")
        
        # バックアップから復元
        if restore_from_backup():
            print("\n✅ 修復が完了しました！")
            print("📝 次のステップ:")
            print("   1. データ再取得スクリプトを実行: scripts/fetch_recent_results_official.py")
            print("   2. オッズ更新スクリプトを実行: scripts/fix_odds_from_results.py")
        else:
            print("❌ 修復に失敗しました")
    else:
        print("\nℹ️ データ不整合は見つかりませんでした")

if __name__ == "__main__":
    main()