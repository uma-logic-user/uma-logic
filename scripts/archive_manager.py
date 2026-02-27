# scripts/archive_manager.py
# UMA-Logic PRO - 過去データアーカイブマネージャー
# 完全版（Full Code）- そのままコピー＆ペーストで動作

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
import sys
import re

# --- 定数 ---
DATA_DIR = Path("data")
ARCHIVE_DIR = DATA_DIR / "archive"
INDEX_FILE = ARCHIVE_DIR / "index.json"
RESULTS_PREFIX = "results_"
PREDICTIONS_PREFIX = "predictions_"


# --- アーカイブマネージャークラス ---

class ArchiveManager:
    """
    過去データアーカイブマネージャー
    data/archive/YYYY/MM/DD/ 形式でデータを管理
    """

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        self.index = self._load_index()

    def _load_index(self) -> Dict:
        """インデックスを読み込み"""
        if INDEX_FILE.exists():
            try:
                with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] インデックス読み込みエラー: {e}")
        return {
            "updated_at": "",
            "total_dates": 0,
            "total_races": 0,
            "years": {},
            "venues": {},
            "date_index": {}
        }

    def _save_index(self):
        """インデックスを保存"""
        self.index["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def _get_archive_path(self, date_str: str) -> Path:
        """
        日付文字列からアーカイブパスを取得
        date_str: YYYYMMDD形式
        returns: data/archive/YYYY/MM/DD/
        """
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        return ARCHIVE_DIR / year / month / day

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """日付文字列をパース"""
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return None

    def archive_file(self, source_file: Path, date_str: str) -> bool:
        """
        ファイルをアーカイブディレクトリに移動/コピー
        一度保存したデータは上書きしない（不変データ化）
        """
        if not source_file.exists():
            print(f"[WARN] ソースファイルが存在しません: {source_file}")
            return False

        archive_path = self._get_archive_path(date_str)
        archive_path.mkdir(parents=True, exist_ok=True)

        dest_file = archive_path / source_file.name

        # 既存ファイルがある場合はスキップ（不変データ化）
        if dest_file.exists():
            print(f"[SKIP] 既にアーカイブ済み: {dest_file}")
            return True

        try:
            # コピー（元ファイルは残す）
            shutil.copy2(source_file, dest_file)
            print(f"[ARCHIVED] {source_file.name} → {archive_path}")
            return True
        except Exception as e:
            print(f"[ERROR] アーカイブ失敗: {e}")
            return False

    def archive_all_results(self) -> Dict:
        """
        data/ 内の全results_*.jsonをアーカイブ
        """
        print("\n" + "=" * 60)
        print("📚 全結果ファイルをアーカイブ")
        print("=" * 60)

        archived_count = 0
        skipped_count = 0
        failed_count = 0

        # results_*.json を検索
        for result_file in DATA_DIR.glob(f"{RESULTS_PREFIX}*.json"):
            # ファイル名から日付を抽出
            match = re.search(r'results_(\d{8})', result_file.name)
            if not match:
                continue

            date_str = match.group(1)

            if self.archive_file(result_file, date_str):
                # インデックスを更新
                self._update_index_for_file(result_file, date_str)
                archived_count += 1
            else:
                failed_count += 1

        # predictions_*.json も同様にアーカイブ
        for pred_file in DATA_DIR.glob(f"{PREDICTIONS_PREFIX}*.json"):
            match = re.search(r'predictions_(\d{8})', pred_file.name)
            if not match:
                continue

            date_str = match.group(1)
            self.archive_file(pred_file, date_str)

        # インデックスを保存
        self._save_index()

        print("\n" + "-" * 40)
        print(f"✅ アーカイブ完了")
        print(f"   新規: {archived_count}件")
        print(f"   スキップ: {skipped_count}件")
        print(f"   失敗: {failed_count}件")

        return {
            "archived": archived_count,
            "skipped": skipped_count,
            "failed": failed_count
        }

    def _update_index_for_file(self, file_path: Path, date_str: str):
        """ファイルの内容をインデックスに追加"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[WARN] ファイル読み込みエラー: {e}")
            return

        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        date_key = f"{year}-{month}-{day}"

        # 年別インデックス
        if year not in self.index["years"]:
            self.index["years"][year] = {
                "months": {},
                "total_dates": 0,
                "total_races": 0
            }

        # 月別インデックス
        if month not in self.index["years"][year]["months"]:
            self.index["years"][year]["months"][month] = {
                "days": [],
                "total_races": 0
            }

        if day not in self.index["years"][year]["months"][month]["days"]:
            self.index["years"][year]["months"][month]["days"].append(day)
            self.index["years"][year]["total_dates"] += 1

        # レース情報を抽出
        races = data.get("races", [])
        race_count = len(races)

        self.index["years"][year]["months"][month]["total_races"] += race_count
        self.index["years"][year]["total_races"] += race_count

        # 日付インデックス
        if date_key not in self.index["date_index"]:
            self.index["date_index"][date_key] = {
                "file_path": str(self._get_archive_path(date_str) / file_path.name),
                "race_count": race_count,
                "venues": []
            }

        # 競馬場情報を抽出
        venues = set()
        for race in races:
            venue = race.get("venue", "")
            if venue:
                venues.add(venue)

                # 競馬場別インデックス
                if venue not in self.index["venues"]:
                    self.index["venues"][venue] = {
                        "dates": [],
                        "total_races": 0
                    }
                if date_key not in self.index["venues"][venue]["dates"]:
                    self.index["venues"][venue]["dates"].append(date_key)
                self.index["venues"][venue]["total_races"] += 1

        self.index["date_index"][date_key]["venues"] = list(venues)

        # 総計を更新
        self.index["total_dates"] = len(self.index["date_index"])
        self.index["total_races"] = sum(
            self.index["years"][y]["total_races"]
            for y in self.index["years"]
        )

    def rebuild_index(self) -> Dict:
        """
        インデックスを完全に再構築
        アーカイブディレクトリ内の全ファイルをスキャン
        """
        print("\n" + "=" * 60)
        print("🔄 インデックス再構築")
        print("=" * 60)

        # インデックスをリセット
        self.index = {
            "updated_at": "",
            "total_dates": 0,
            "total_races": 0,
            "years": {},
            "venues": {},
            "date_index": {}
        }

        file_count = 0

        # アーカイブディレクトリを再帰的にスキャン
        for year_dir in sorted(ARCHIVE_DIR.iterdir()):
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue

            year = year_dir.name
            print(f"\n[INFO] {year}年をスキャン中...")

            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue

                month = month_dir.name

                for day_dir in sorted(month_dir.iterdir()):
                    if not day_dir.is_dir() or not day_dir.name.isdigit():
                        continue

                    day = day_dir.name
                    date_str = f"{year}{month}{day}"

                    # results_*.json を検索
                    for result_file in day_dir.glob(f"{RESULTS_PREFIX}*.json"):
                        self._update_index_for_file(result_file, date_str)
                        file_count += 1

        # インデックスを保存
        self._save_index()

        print("\n" + "-" * 40)
        print(f"✅ インデックス再構築完了")
        print(f"   スキャンファイル: {file_count}件")
        print(f"   登録日数: {self.index['total_dates']}日")
        print(f"   登録レース: {self.index['total_races']}件")

        return {
            "files_scanned": file_count,
            "total_dates": self.index["total_dates"],
            "total_races": self.index["total_races"]
        }

    def get_available_years(self) -> List[str]:
        """利用可能な年のリストを取得"""
        return sorted(self.index.get("years", {}).keys(), reverse=True)

    def get_available_months(self, year: str) -> List[str]:
        """指定年の利用可能な月のリストを取得"""
        year_data = self.index.get("years", {}).get(year, {})
        return sorted(year_data.get("months", {}).keys())

    def get_available_days(self, year: str, month: str) -> List[str]:
        """指定年月の利用可能な日のリストを取得"""
        year_data = self.index.get("years", {}).get(year, {})
        month_data = year_data.get("months", {}).get(month, {})
        return sorted(month_data.get("days", []))

    def get_available_venues(self, date_str: str) -> List[str]:
        """指定日の利用可能な競馬場のリストを取得"""
        # date_str: YYYYMMDD または YYYY-MM-DD
        if "-" in date_str:
            date_key = date_str
        else:
            date_key = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        date_data = self.index.get("date_index", {}).get(date_key, {})
        return date_data.get("venues", [])

    def get_races_by_date(self, date_str: str) -> Optional[Dict]:
        """
        指定日のレースデータを取得
        アーカイブから高速に読み込み
        """
        # date_str: YYYYMMDD形式に正規化
        if "-" in date_str:
            date_str = date_str.replace("-", "")

        archive_path = self._get_archive_path(date_str)
        result_file = archive_path / f"{RESULTS_PREFIX}{date_str}.json"

        # アーカイブにない場合はdata/から読み込み
        if not result_file.exists():
            result_file = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"

        if not result_file.exists():
            return None

        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] ファイル読み込みエラー: {e}")
            return None

    def get_races_by_date_and_venue(self, date_str: str, venue: str) -> List[Dict]:
        """
        指定日・指定競馬場のレースデータを取得
        """
        data = self.get_races_by_date(date_str)
        if not data:
            return []

        races = data.get("races", [])
        return [r for r in races if r.get("venue", "") == venue]

    def get_statistics(self) -> Dict:
        """アーカイブ統計情報を取得"""
        stats = {
            "updated_at": self.index.get("updated_at", ""),
            "total_dates": self.index.get("total_dates", 0),
            "total_races": self.index.get("total_races", 0),
            "years": {},
            "venues": {}
        }

        # 年別統計
        for year, year_data in self.index.get("years", {}).items():
            stats["years"][year] = {
                "total_dates": year_data.get("total_dates", 0),
                "total_races": year_data.get("total_races", 0),
                "months": list(year_data.get("months", {}).keys())
            }

        # 競馬場別統計
        for venue, venue_data in self.index.get("venues", {}).items():
            stats["venues"][venue] = {
                "total_dates": len(venue_data.get("dates", [])),
                "total_races": venue_data.get("total_races", 0)
            }

        return stats

    def archive_today_results(self) -> bool:
        """本日の結果をアーカイブ"""
        today_str = datetime.now().strftime("%Y%m%d")
        result_file = DATA_DIR / f"{RESULTS_PREFIX}{today_str}.json"

        if result_file.exists():
            success = self.archive_file(result_file, today_str)
            if success:
                self._update_index_for_file(result_file, today_str)
                self._save_index()
            return success
        else:
            print(f"[INFO] 本日の結果ファイルがありません: {result_file}")
            return False

    def check_archived(self, date_str: str) -> bool:
        """指定日のデータがアーカイブ済みかチェック"""
        archive_path = self._get_archive_path(date_str)
        result_file = archive_path / f"{RESULTS_PREFIX}{date_str}.json"
        return result_file.exists()


# --- UI用高速検索クラス ---

class ArchiveSearcher:
    """
    UIからの高速検索用クラス
    インデックスを使用して高速にデータを取得
    """

    def __init__(self):
        self.manager = ArchiveManager()

    def get_hierarchical_data(self) -> Dict:
        """
        階層型検索用のデータ構造を取得
        年 > 月 > 日 > 競馬場 の階層
        """
        result = {
            "years": []
        }

        for year in self.manager.get_available_years():
            year_data = {
                "year": year,
                "months": []
            }

            for month in self.manager.get_available_months(year):
                month_data = {
                    "month": month,
                    "days": []
                }

                for day in self.manager.get_available_days(year, month):
                    date_str = f"{year}{month}{day}"
                    venues = self.manager.get_available_venues(date_str)

                    day_data = {
                        "day": day,
                        "date_str": date_str,
                        "venues": venues
                    }
                    month_data["days"].append(day_data)

                year_data["months"].append(month_data)

            result["years"].append(year_data)

        return result

    def search_races(
        self,
        year: str = None,
        month: str = None,
        day: str = None,
        venue: str = None
    ) -> List[Dict]:
        """
        条件に基づいてレースを検索
        """
        results = []

        # 日付が指定されている場合
        if year and month and day:
            date_str = f"{year}{month}{day}"

            if venue:
                races = self.manager.get_races_by_date_and_venue(date_str, venue)
            else:
                data = self.manager.get_races_by_date(date_str)
                races = data.get("races", []) if data else []

            return races

        # 年月のみ指定されている場合
        if year and month:
            days = self.manager.get_available_days(year, month)
            for d in days:
                date_str = f"{year}{month}{d}"
                data = self.manager.get_races_by_date(date_str)
                if data:
                    for race in data.get("races", []):
                        if venue is None or race.get("venue") == venue:
                            race["date"] = date_str
                            results.append(race)
            return results

        # 年のみ指定されている場合
        if year:
            months = self.manager.get_available_months(year)
            for m in months:
                days = self.manager.get_available_days(year, m)
                for d in days:
                    date_str = f"{year}{m}{d}"
                    data = self.manager.get_races_by_date(date_str)
                    if data:
                        for race in data.get("races", []):
                            if venue is None or race.get("venue") == venue:
                                race["date"] = date_str
                                results.append(race)
            return results

        return results


# --- メイン処理 ---

def main():
    print("=" * 60)
    print("📚 UMA-Logic PRO - アーカイブマネージャー")
    print("=" * 60)

    manager = ArchiveManager()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--archive-all":
            # 全ファイルをアーカイブ
            result = manager.archive_all_results()
            print(f"\n結果: {result}")

        elif command == "--rebuild-index":
            # インデックス再構築
            result = manager.rebuild_index()
            print(f"\n結果: {result}")

        elif command == "--stats":
            # 統計情報表示
            stats = manager.get_statistics()
            print("\n📊 アーカイブ統計")
            print("-" * 40)
            print(f"最終更新: {stats['updated_at']}")
            print(f"総日数: {stats['total_dates']}日")
            print(f"総レース: {stats['total_races']}件")

            print("\n📅 年別統計:")
            for year, data in sorted(stats["years"].items(), reverse=True):
                print(f"  {year}年: {data['total_dates']}日 / {data['total_races']}レース")
                print(f"    月: {', '.join(data['months'])}")

            print("\n🏟️ 競馬場別統計:")
            for venue, data in sorted(stats["venues"].items(), key=lambda x: x[1]["total_races"], reverse=True):
                print(f"  {venue}: {data['total_dates']}日 / {data['total_races']}レース")

        elif command == "--archive-date":
            # 指定日をアーカイブ
            if len(sys.argv) > 2:
                date_str = sys.argv[2]
                result_file = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
                if result_file.exists():
                    manager.archive_file(result_file, date_str)
                    manager._update_index_for_file(result_file, date_str)
                    manager._save_index()
                else:
                    print(f"[ERROR] ファイルが見つかりません: {result_file}")
            else:
                print("[ERROR] 日付を指定してください (例: --archive-date 20240106)")

        elif command == "--search":
            # 検索テスト
            searcher = ArchiveSearcher()
            hierarchical = searcher.get_hierarchical_data()
            print("\n📂 階層型データ構造:")
            for year_data in hierarchical["years"][:2]:  # 最新2年のみ表示
                print(f"\n  {year_data['year']}年:")
                for month_data in year_data["months"][:3]:  # 最新3ヶ月のみ表示
                    print(f"    {month_data['month']}月: {len(month_data['days'])}日")

        elif command == "--check":
            # アーカイブ状態チェック
            if len(sys.argv) > 2:
                date_str = sys.argv[2]
                if manager.check_archived(date_str):
                    print(f"✅ {date_str} はアーカイブ済みです")
                else:
                    print(f"❌ {date_str} はアーカイブされていません")
            else:
                print("[ERROR] 日付を指定してください (例: --check 20240106)")

        else:
            print(f"[ERROR] 不明なコマンド: {command}")
            print("\n使用方法:")
            print("  --archive-all      : 全結果ファイルをアーカイブ")
            print("  --rebuild-index    : インデックスを再構築")
            print("  --stats            : 統計情報を表示")
            print("  --archive-date DATE: 指定日をアーカイブ (例: 20240106)")
            print("  --search           : 検索テスト")
            print("  --check DATE       : アーカイブ状態を確認")

    else:
        # デフォルト: 本日の結果をアーカイブ
        print("\n[INFO] 本日の結果をアーカイブします...")
        manager.archive_today_results()

    print("\n✅ 処理完了")


if __name__ == "__main__":
    main()
