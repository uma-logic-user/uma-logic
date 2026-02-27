import json
from pathlib import Path
from datetime import datetime
import sys
import io

# Windows環境での文字化け防止
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# DataProcessorのインポート
try:
    from data_processor import DataProcessor
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from data_processor import DataProcessor

DATA_DIR = Path("data")
processor = DataProcessor()

def create_dummy_data():
    print("🛠️ 代替開催データ生成中...")

    # 1. 2026/01/31 東京（中止）
    filepath_0131 = DATA_DIR / "results_20260131.json"
    if filepath_0131.exists():
        with open(filepath_0131, 'r', encoding='utf-8') as f:
            data_0131 = json.load(f)
        
        # 東京競馬を中止扱いに変更
        for race in data_0131.get("races", []):
            if race["venue"] == "東京":
                race["race_name"] += " (中止)"
                race["is_cancelled"] = True
                race["cancellation_reason"] = "SNOW_CANCELLATION"
        
        # 保存
        with open(filepath_0131, 'w', encoding='utf-8') as f:
            json.dump(data_0131, f, ensure_ascii=False, indent=2)
        print(f"✅ 1/31 東京競馬を中止扱いに更新: {filepath_0131}")
        processor.log("WARN", "1/31 東京競馬の開催中止を記録", {"reason": "SNOW"})

    # 2. 2026/02/02 代替開催（東京）
    # 1/31のデータをベースに日付を変更
    if filepath_0131.exists():
        with open(filepath_0131, 'r', encoding='utf-8') as f:
            base_data = json.load(f)
            
        alt_races = []
        for race in base_data.get("races", []):
            if race.get("venue") == "東京":
                new_race = race.copy()
                new_race["date"] = "2026-02-02"
                new_race["race_name"] = new_race["race_name"].replace(" (中止)", "")
                new_race["is_cancelled"] = False
                new_race["is_alternative"] = True
                
                # ダミー結果を入れる（動作確認用）
                new_race["all_results"] = [
                    {"着順": 1, "馬番": 1, "馬名": "ユキノビジン", "騎手": "武豊", "タイム": "1:33.5", "オッズ": 2.5},
                    {"着順": 2, "馬番": 5, "馬名": "ホワイトストーン", "騎手": "柴田善臣", "タイム": "1:33.7", "オッズ": 15.2},
                    {"着順": 3, "馬番": 8, "馬名": "スノーフェアリー", "騎手": "ルメール", "タイム": "1:33.8", "オッズ": 4.8}
                ]
                new_race["top3"] = new_race["all_results"][:3]
                
                # DataProcessorを通す
                processed = processor.process_race_data(new_race)
                alt_races.append(processed)

        # 保存
        filepath_0202 = DATA_DIR / "results_20260202.json"
        output_data = {
            "date": "2026-02-02",
            "original_date": "2026-01-31",
            "is_alternative": True,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "races": alt_races
        }
        
        with open(filepath_0202, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 2/2 代替開催データを生成: {filepath_0202}")
        processor.log("INFO", "2/2 代替開催データを生成保存", {"original_date": "2026-01-31"})

if __name__ == "__main__":
    create_dummy_data()
