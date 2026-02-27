"""
2/21の予測データを結果データから正しいオッズ情報で更新するスクリプト
オッズ取得失敗の問題を解決し、正しいオッズ情報を反映します
"""
import json
from pathlib import Path
from datetime import datetime

# パス設定
DATA_DIR = Path("data")
HISTORY_DIR = DATA_DIR / "history"
RESULTS_FILE = DATA_DIR / "results_20260221.json"
PREDICTIONS_FILE = HISTORY_DIR / "predictions_20260221.json"

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
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ ファイルを保存しました: {file_path}")
        return True
    except Exception as e:
        print(f"❌ ファイル保存エラー: {file_path}: {e}")
        return False

def extract_odds_from_results(results_data):
    """結果データからオッズ情報を抽出"""
    odds_map = {}
    
    if "races" not in results_data:
        print("❌ 結果データにracesフィールドがありません")
        return odds_map
    
    for race in results_data["races"]:
        race_id = race.get("race_id", "")
        if not race_id:
            continue
            
        # top3からオッズ情報を取得
        if "top3" in race:
            for horse in race["top3"]:
                umaban = str(horse.get("馬番", ""))
                odds = horse.get("オッズ")
                if umaban and odds is not None:
                    key = f"{race_id}_{umaban}"
                    odds_map[key] = odds
        
        # all_resultsからオッズ情報を取得
        if "all_results" in race:
            for horse in race["all_results"]:
                umaban = str(horse.get("馬番", ""))
                odds = horse.get("オッズ")
                if umaban and odds is not None:
                    key = f"{race_id}_{umaban}"
                    odds_map[key] = odds
    
    print(f"📊 抽出したオッズ情報: {len(odds_map)}件")
    return odds_map

def update_predictions_with_odds(predictions_data, odds_map):
    """予測データをオッズ情報で更新"""
    updated_count = 0
    
    if "races" not in predictions_data:
        print("❌ 予測データにracesフィールドがありません")
        return updated_count
    
    for race in predictions_data["races"]:
        race_id = race.get("race_id", "")
        if not race_id:
            continue
        
        # 予測データの馬情報を更新
        horses = race.get("predictions", [])
        for horse in horses:
            umaban = str(horse.get("umaban", horse.get("馬番", "")))
            if not umaban:
                continue
                
            key = f"{race_id}_{umaban}"
            if key in odds_map:
                new_odds = odds_map[key]
                old_odds = horse.get("odds", horse.get("オッズ", None))
                
                # オッズ情報を更新
                horse["odds"] = new_odds
                horse["オッズ"] = new_odds
                horse["odds_status"] = "from_results"
                horse["odds_prev"] = old_odds
                
                # expected_valueを再計算
                win_prob = horse.get("win_probability", 0)
                if win_prob and new_odds:
                    horse["expected_value"] = round(win_prob * new_odds, 2)
                
                updated_count += 1
    
    # 更新日時を設定
    predictions_data["odds_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    predictions_data["odds_source"] = "from_results_data"
    predictions_data["odds_status"] = "fixed"
    
    return updated_count

def main():
    """メイン処理"""
    print("🔄 2/21の予測データを結果データから修正します...")
    
    # ファイル読み込み
    results_data = load_json_file(RESULTS_FILE)
    predictions_data = load_json_file(PREDICTIONS_FILE)
    
    if not results_data or not predictions_data:
        return False
    
    # オッズ情報を抽出
    odds_map = extract_odds_from_results(results_data)
    if not odds_map:
        print("❌ オッズ情報の抽出に失敗しました")
        return False
    
    # デバッグ情報: 最初の10個のキーを表示
    print(f"📊 抽出したオッズキーの例: {list(odds_map.keys())[:10]}")
    
    # 予測データのrace_idを確認
    prediction_race_ids = [race.get('race_id', '') for race in predictions_data.get('races', [])]
    print(f"📊 予測データのrace_id例: {prediction_race_ids[:5]}")
    
    # 結果データのrace_idを確認
    result_race_ids = [race.get('race_id', '') for race in results_data.get('races', [])]
    print(f"📊 結果データのrace_id例: {result_race_ids[:5]}")
    
    # 予測データを更新
    updated_count = update_predictions_with_odds(predictions_data, odds_map)
    
    if updated_count > 0:
        print(f"✅ {updated_count}件のオッズ情報を更新しました")
        
        # バックアップを作成
        backup_file = PREDICTIONS_FILE.with_name(f"predictions_20260221_backup_{datetime.now().strftime('%H%M%S')}.json")
        save_json_file(backup_file, predictions_data)
        
        # 本ファイルを保存
        success = save_json_file(PREDICTIONS_FILE, predictions_data)
        if success:
            print("🎉 予測データの修正が完了しました")
            return True
        else:
            print("❌ 予測データの保存に失敗しました")
            return False
    else:
        print("⚠️ 更新対象のオッズ情報が見つかりませんでした")
        
        # 詳細なデバッグ情報
        print("🔍 デバッグ情報:")
        print(f"   - オッズマップサイズ: {len(odds_map)}")
        print(f"   - 予測データレース数: {len(predictions_data.get('races', []))}")
        
        # 最初のレースのマッチング状況を確認
        if predictions_data.get('races'):
            first_race = predictions_data['races'][0]
            race_id = first_race.get('race_id', '')
            print(f"   - 最初のレースID: {race_id}")
            
            # このレースIDに対応するオッズ情報があるか確認
            matching_keys = [key for key in odds_map.keys() if key.startswith(race_id)]
            print(f"   - マッチングするオッズキー: {matching_keys}")
        
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)