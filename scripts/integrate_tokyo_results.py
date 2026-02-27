"""
東京競馬場の結果データをメインの結果ファイルに統合するスクリプト
"""
import json
from pathlib import Path
from datetime import datetime

# パス設定
DATA_DIR = Path("data")
TOKYO_RESULTS_FILE = DATA_DIR / "results_tokyo_20260221.json"
MAIN_RESULTS_FILE = DATA_DIR / "results_20260221.json"
BACKUP_DIR = DATA_DIR / "backup"

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

def integrate_tokyo_results():
    """東京競馬場データをメイン結果ファイルに統合"""
    print("🔄 東京競馬場データをメイン結果ファイルに統合します...")
    
    # バックアップディレクトリ作成
    BACKUP_DIR.mkdir(exist_ok=True)
    
    # ファイル読み込み
    tokyo_data = load_json_file(TOKYO_RESULTS_FILE)
    main_data = load_json_file(MAIN_RESULTS_FILE)
    
    if not tokyo_data:
        print("❌ 東京競馬場データの読み込みに失敗")
        return False
    
    # メインデータが存在しない場合は新規作成
    if not main_data:
        print("ℹ️ メイン結果ファイルが存在しないため、新規作成します")
        main_data = {
            "date": "2026-02-21",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "races": []
        }
    
    # バックアップ作成
    backup_file = BACKUP_DIR / f"results_20260221_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(main_data, f, ensure_ascii=False, indent=2)
    print(f"✅ バックアップ作成: {backup_file}")
    
    # 東京競馬場データを統合
    tokyo_races = tokyo_data.get("races", [])
    main_races = main_data.get("races", [])
    
    # 既存の東京競馬場データを削除（重複防止）
    main_races = [race for race in main_races if not race.get("race_id", "").startswith("202605")]
    
    # 東京競馬場データを追加
    main_races.extend(tokyo_races)
    main_data["races"] = main_races
    main_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 保存
    with open(MAIN_RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(main_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 東京競馬場データを統合しました: {MAIN_RESULTS_FILE}")
    print(f"📊 総レース数: {len(main_races)}レース")
    print(f"📊 東京競馬場レース数: {len(tokyo_races)}レース")
    
    return True

def verify_integration():
    """統合結果を検証"""
    print("\n🔍 統合結果を検証します...")
    
    main_data = load_json_file(MAIN_RESULTS_FILE)
    if not main_data:
        print("❌ 検証失敗: メインファイルが読み込めません")
        return False
    
    races = main_data.get("races", [])
    tokyo_races = [race for race in races if race.get("race_id", "").startswith("202605")]
    kokura_races = [race for race in races if race.get("race_id", "").startswith("202655")]
    
    print(f"📊 メインデータ総レース数: {len(races)}レース")
    print(f"📊 東京競馬場レース数: {len(tokyo_races)}レース")
    print(f"📊 小倉競馬場レース数: {len(kokura_races)}レース")
    
    if len(tokyo_races) == 12:
        print("✅ 東京競馬場データの統合が成功しました！")
        return True
    else:
        print("❌ 東京競馬場データの統合に問題があります")
        return False

def main():
    """メイン処理"""
    print("=" * 60)
    print("🏇 UMA-Logic Pro - 東京競馬場データ統合作業")
    print("=" * 60)
    
    # データ統合
    if integrate_tokyo_results():
        # 統合検証
        if verify_integration():
            print("\n🎉 データ統合が完了しました！")
            print("📝 次のステップ:")
            print("   1. オッズ更新スクリプトを実行: python scripts/fix_odds_from_results.py")
            print("   2. 的中実績の確認")
        else:
            print("\n❌ 統合検証に失敗しました")
    else:
        print("\n❌ データ統合に失敗しました")

if __name__ == "__main__":
    main()