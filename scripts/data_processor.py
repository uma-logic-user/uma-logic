import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# --- ログ設定 ---
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "uma_logic.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("UMA_Logic")

class DataProcessor:
    """レースデータの処理、検証、ログ出力を担当するクラス"""

    def __init__(self):
        self.abnormal_status = [
            "中止", "延期", "除外", "取消", "競走除外", "出走取消", "発走除外"
        ]

    def log(self, level: str, message: str, context: dict = None):
        """構造化ログを出力"""
        log_msg = f"{message}"
        if context:
            log_msg += f" | context={json.dumps(context, ensure_ascii=False)}"
        
        if level == "INFO":
            logger.info(log_msg)
        elif level == "WARN":
            logger.warning(log_msg)
        elif level == "ERROR":
            logger.error(log_msg)
        elif level == "DEBUG":
            logger.debug(log_msg)

    def check_cancellation(self, race_data: Dict) -> Tuple[bool, str]:
        """レースが中止・延期されたか判定"""
        # レース名や着順データから異常を検知
        race_name = race_data.get("race_name", "")
        
        # 1. レース名に含まれるキーワードチェック
        if "中止" in race_name:
            return True, "CANCELLED_BY_NAME"
        
        # 2. 結果データのチェック
        all_results = race_data.get("all_results", [])
        if not all_results:
            return True, "NO_RESULTS"
        
        # 3. 全頭除外などのケース（稀だが雪で開催中止になった場合など）
        # 特定の着順文字列チェック
        abnormal_count = 0
        for horse in all_results:
            rank = str(horse.get("着順", ""))
            if rank in self.abnormal_status:
                abnormal_count += 1
        
        if abnormal_count > 0 and abnormal_count == len(all_results):
             return True, "ALL_HORSES_EXCLUDED"

        return False, ""

    def process_race_data(self, race_data: Dict) -> Dict:
        """レースデータを処理し、メタデータを付与"""
        is_cancelled, reason = self.check_cancellation(race_data)
        
        processed_data = race_data.copy()
        processed_data["is_cancelled"] = is_cancelled
        processed_data["cancellation_reason"] = reason
        processed_data["processed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 代替開催の検知（レースIDや日付から推測）
        # 通常、代替開催は曜日が月曜や火曜になることが多い
        # ここでは簡易的に日付文字列を含むかチェック
        race_date_str = race_data.get("date", "") # YYYY-MM-DD
        if race_date_str:
            try:
                dt = datetime.strptime(race_date_str, "%Y-%m-%d")
                weekday = dt.weekday() # 0:月, 1:火 ... 5:土, 6:日
                if weekday in [0, 1, 4]: # 月・火・金（祝日除く平日開催の可能性）
                     processed_data["is_alternative"] = True
                     self.log("INFO", f"代替開催または平日開催を検知: {race_date_str}", {"race_id": race_data.get("race_id")})
                else:
                    processed_data["is_alternative"] = False
            except ValueError:
                pass
        
        if is_cancelled:
            self.log("WARN", f"レース中止検知: {reason}", {"race_id": race_data.get("race_id"), "race_name": race_data.get("race_name")})
        
        return processed_data

    def validate_data(self, race_data: Dict) -> bool:
        """必須フィールドの検証"""
        required_fields = ["race_id", "race_name", "venue"]
        for field in required_fields:
            if field not in race_data:
                self.log("ERROR", f"必須フィールド欠損: {field}", {"data": str(race_data)[:100]})
                return False
        return True

if __name__ == "__main__":
    # テスト実行
    processor = DataProcessor()
    test_data = {
        "race_id": "202602010101",
        "race_name": "3歳未勝利 (中止)",
        "venue": "東京",
        "all_results": [],
        "date": "2026-02-02" # 月曜日（代替開催想定）
    }
    processed = processor.process_race_data(test_data)
    print(json.dumps(processed, indent=2, ensure_ascii=False))
