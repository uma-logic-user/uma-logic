"""
レース番号の不一致を修正するスクリプト
予測データのレース番号を結果データと一致させる（01→02）
"""
import json
from pathlib import Path
from datetime import datetime

# パス設定
DATA_DIR = Path("data")
HISTORY_DIR = DATA_DIR / "history"
PREDICTIONS_FILE = HISTORY_DIR / "predictions_20260221.json"
BACKUP_FILE = HISTORY_DIR / "predictions_20260221_backup2.json"

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

def save_json_file(file_path, data):
    """JSONファイルを保存する"""
    try:
        # バックアップを作成
        if file_path.exists():
            backup_path = file_path.parent / f"{file_path.stem}_backup2{file_path.suffix}"
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(load_json_file(file_path), f, ensure_ascii=False, indent=2)
            print(f"✅ バックアップを作成: {backup_path}")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ ファイルを保存しました: {file_path}")
        return True
    except Exception as e:
        print(f"❌ ファイル保存エラー: {file_path}: {e}")
        return False

def fix_race_number_mismatch(predictions_data):
    """レース番号の不一致を修正（01→02）"""
    updated_count = 0
    
    if "races" not in predictions_data:
        print("❌ 予測データにracesフィールドがありません")
        return updated_count
    
    for race in predictions_data["races"]:
        race_id = race.get("race_id", "")
        if not race_id:
            continue
            
        # レース番号を01（第1回）から02（第2回）に変更
        if "20265501" in race_id:
            new_race_id = race_id.replace("20265501", "20265502")
            race["race_id"] = new_race_id
            
            print(f"  🔄 レース番号更新: {race_id} -> {new_race_id}")
            updated_count += 1
    
    predictions_data["race_number_fixed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return updated_count

def main():
    print("🔄 レース番号の不一致を修正します（01→02）...")
    
    # 予測データを読み込み
    predictions_data = load_json_file(PREDICTIONS_FILE)
    if not predictions_data:
        return
    
    print(f"📊 処理前のレース数: {len(predictions_data.get('races', []))}")
    
    # レース番号を修正
    updated_count = fix_race_number_mismatch(predictions_data)
    
    if updated_count > 0:
        print(f"✅ レース番号を {updated_count} 件更新しました")
        
        # 修正したデータを保存
        if save_json_file(PREDICTIONS_FILE, predictions_data):
            print("🎉 レース番号の修正が完了しました！")
            print("📝 次のステップ: scripts/fix_odds_from_results.py を実行してオッズ情報を更新してください")
        else:
            print("❌ ファイルの保存に失敗しました")
    else:
        print("ℹ️ 更新対象のレース番号は見つかりませんでした")

if __name__ == "__main__":
    main()