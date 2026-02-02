# scripts/archive_manager.py
# UMA-Logic PRO - 鉄壁アーカイブマネージャー（完全自動化版）
# 階層構造保存 + 高速インデックス機能

import json
import hashlib
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import re

# --- 定数 ---
DATA_DIR = Path("data")
ARCHIVE_DIR = DATA_DIR / "archive"
INDEX_FILE = ARCHIVE_DIR / "index.json"
CACHE_FILE = ARCHIVE_DIR / "cache.json"
RESULTS_PREFIX = "results_"


# --- アーカイブインデックス ---

class ArchiveIndex:
    """
    高速検索のためのインデックス管理
    年 > 月 > 日 > 競馬場 の階層構造でデータを管理
    """
    
    def __init__(self):
        self.index: Dict = {
            "version": "2.0",
            "updated_at": "",
            "years": {},  # {year: {months: {month: {days: [...]}}}}
            "dates": {},  # {date_str: {path, race_count, venues, checksum, locked}}
            "venues": {},  # {venue: [date_str, ...]}
            "stats": {
                "total_dates": 0,
                "total_races": 0,
                "date_range": {"start": "", "end": ""}
            }
        }
        self.load()
    
    def load(self):
        """インデックスを読み込み"""
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        
        if INDEX_FILE.exists():
            try:
                with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    if loaded.get("version") == "2.0":
                        self.index = loaded
                    else:
                        # 旧バージョンからマイグレーション
                        self._migrate_from_v1(loaded)
            except Exception as e:
                print(f"[WARN] インデックス読み込みエラー: {e}")
    
    def _migrate_from_v1(self, old_index: Dict):
        """v1インデックスからマイグレーション"""
        print("[INFO] インデックスをv2にマイグレーション中...")
        
        for date_str, info in old_index.items():
            if isinstance(info, dict) and "locked" in info:
                self.index["dates"][date_str] = info
        
        self._rebuild_hierarchy()
        self.save()
    
    def _rebuild_hierarchy(self):
        """階層構造を再構築"""
        self.index["years"] = {}
        self.index["venues"] = {}
        
        for date_str in self.index["dates"].keys():
            self._add_to_hierarchy(date_str)
        
        self._update_stats()
    
    def _add_to_hierarchy(self, date_str: str):
        """日付を階層構造に追加"""
        try:
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            
            # 年 > 月 > 日 の階層
            if year not in self.index["years"]:
                self.index["years"][year] = {"months": {}}
            
            if month not in self.index["years"][year]["months"]:
                self.index["years"][year]["months"][month] = {"days": []}
            
            if day not in self.index["years"][year]["months"][month]["days"]:
                self.index["years"][year]["months"][month]["days"].append(day)
                self.index["years"][year]["months"][month]["days"].sort()
            
            # 競馬場インデックス
            date_info = self.index["dates"].get(date_str, {})
            venues = date_info.get("venues", [])
            for venue in venues:
                if venue not in self.index["venues"]:
                    self.index["venues"][venue] = []
                if date_str not in self.index["venues"][venue]:
                    self.index["venues"][venue].append(date_str)
        except Exception:
            pass
    
    def _update_stats(self):
        """統計情報を更新"""
        dates = list(self.index["dates"].keys())
        
        self.index["stats"]["total_dates"] = len(dates)
        self.index["stats"]["total_races"] = sum(
            info.get("race_count", 0) for info in self.index["dates"].values()
        )
        
        if dates:
            dates.sort()
            self.index["stats"]["date_range"]["start"] = dates[0]
            self.index["stats"]["date_range"]["end"] = dates[-1]
    
    def save(self):
        """インデックスを保存"""
        self.index["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)
    
    def is_archived(self, date_str: str) -> bool:
        """指定日付がアーカイブ済みか確認"""
        return date_str in self.index["dates"] and self.index["dates"][date_str].get("locked", False)
    
    def add_entry(self, date_str: str, path: str, race_count: int, venues: List[str], checksum: str):
        """エントリを追加"""
        self.index["dates"][date_str] = {
            "path": str(path),
            "race_count": race_count,
            "venues": venues,
            "checksum": checksum,
            "locked": True,
            "archived_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self._add_to_hierarchy(date_str)
        self._update_stats()
        self.save()
    
    def get_years(self) -> List[str]:
        """利用可能な年のリストを取得"""
        return sorted(self.index["years"].keys(), reverse=True)
    
    def get_months(self, year: str) -> List[str]:
        """指定年の月リストを取得"""
        year_data = self.index["years"].get(year, {})
        return sorted(year_data.get("months", {}).keys())
    
    def get_days(self, year: str, month: str) -> List[str]:
        """指定年月の日リストを取得"""
        year_data = self.index["years"].get(year, {})
        month_data = year_data.get("months", {}).get(month, {})
        return sorted(month_data.get("days", []))
    
    def get_venues_for_date(self, date_str: str) -> List[str]:
        """指定日の競馬場リストを取得"""
        return self.index["dates"].get(date_str, {}).get("venues", [])
    
    def get_dates_for_venue(self, venue: str) -> List[str]:
        """指定競馬場の開催日リストを取得"""
        return sorted(self.index["venues"].get(venue, []), reverse=True)
    
    def get_path(self, date_str: str) -> Optional[str]:
        """指定日のファイルパスを取得"""
        return self.index["dates"].get(date_str, {}).get("path")


# --- アーカイブストレージ ---

class ArchiveStorage:
    """
    階層型アーカイブストレージ
    data/archive/YYYY/MM/DD/ 形式で保存
    """
    
    def __init__(self):
        self.index = ArchiveIndex()
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    def get_archive_path(self, date_str: str) -> Path:
        """アーカイブパスを取得"""
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        return ARCHIVE_DIR / year / month / day
    
    def archive_results(self, date_str: str, data: Dict) -> Tuple[Path, str]:
        """
        結果データをアーカイブに保存
        Returns: (保存パス, チェックサム)
        """
        # 既にアーカイブ済みの場合はスキップ
        if self.index.is_archived(date_str):
            print(f"[SKIP] {date_str} は既にアーカイブ済みです")
            existing_path = self.index.get_path(date_str)
            return Path(existing_path) if existing_path else None, ""
        
        archive_path = self.get_archive_path(date_str)
        archive_path.mkdir(parents=True, exist_ok=True)
        
        filepath = archive_path / f"results_{date_str}.json"
        
        # チェックサム計算
        data_for_checksum = {k: v for k, v in data.items() if k != "_meta"}
        data_str = json.dumps(data_for_checksum, ensure_ascii=False, sort_keys=True)
        checksum = hashlib.md5(data_str.encode()).hexdigest()
        
        # メタデータ追加
        races = data.get("races", [])
        venues = list(set(r.get("venue", "不明") for r in races))
        
        data["_meta"] = {
            "archived_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "checksum": checksum,
            "race_count": len(races),
            "venues": venues,
            "immutable": True
        }
        
        # 保存
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 読み取り専用に設定
        try:
            filepath.chmod(0o444)
        except:
            pass
        
        # インデックスに追加
        self.index.add_entry(date_str, str(filepath), len(races), venues, checksum)
        
        print(f"[ARCHIVED] {date_str} → {filepath} ({len(races)}レース)")
        
        return filepath, checksum
    
    def load_from_archive(self, date_str: str) -> Optional[Dict]:
        """アーカイブからデータを読み込み"""
        # インデックスからパスを取得
        path_str = self.index.get_path(date_str)
        
        if path_str:
            filepath = Path(path_str)
            if filepath.exists():
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[ERROR] 読み込みエラー ({date_str}): {e}")
        
        # フォールバック: 直接パスを探索
        archive_path = self.get_archive_path(date_str)
        filepath = archive_path / f"results_{date_str}.json"
        
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        return None
    
    def sync_to_data_dir(self, date_str: str):
        """アーカイブからdata/ディレクトリにコピー"""
        archive_data = self.load_from_archive(date_str)
        if not archive_data:
            return
        
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        target_path = DATA_DIR / f"results_{date_str}.json"
        
        if target_path.exists():
            return
        
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(archive_data, f, ensure_ascii=False, indent=2)
    
    def verify_integrity(self, date_str: str) -> bool:
        """データ整合性を検証"""
        data = self.load_from_archive(date_str)
        if not data:
            return False
        
        meta = data.get("_meta", {})
        stored_checksum = meta.get("checksum", "")
        
        data_for_checksum = {k: v for k, v in data.items() if k != "_meta"}
        data_str = json.dumps(data_for_checksum, ensure_ascii=False, sort_keys=True)
        current_checksum = hashlib.md5(data_str.encode()).hexdigest()
        
        return stored_checksum == current_checksum


# --- 自動アーカイブ機能 ---

class AutoArchiver:
    """
    update_results.py から呼び出される自動アーカイブ機能
    """
    
    def __init__(self):
        self.storage = ArchiveStorage()
    
    def archive_today_results(self):
        """本日の結果を自動アーカイブ"""
        today = datetime.now().strftime("%Y%m%d")
        return self.archive_date_results(today)
    
    def archive_date_results(self, date_str: str) -> bool:
        """指定日の結果をアーカイブ"""
        # data/ ディレクトリから結果ファイルを探す
        source_file = DATA_DIR / f"results_{date_str}.json"
        
        if not source_file.exists():
            print(f"[WARN] 結果ファイルが見つかりません: {source_file}")
            return False
        
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # アーカイブに保存
            filepath, checksum = self.storage.archive_results(date_str, data)
            
            return filepath is not None
        
        except Exception as e:
            print(f"[ERROR] アーカイブエラー ({date_str}): {e}")
            return False
    
    def archive_all_existing(self):
        """data/ ディレクトリの全結果ファイルをアーカイブ"""
        print("=" * 60)
        print("📦 既存データの一括アーカイブ")
        print("=" * 60)
        
        archived = 0
        skipped = 0
        
        for filepath in DATA_DIR.glob(f"{RESULTS_PREFIX}*.json"):
            date_str = filepath.stem.replace(RESULTS_PREFIX, "")[:8]
            
            if self.storage.index.is_archived(date_str):
                skipped += 1
                continue
            
            if self.archive_date_results(date_str):
                archived += 1
        
        print(f"\n✅ 完了: {archived}件アーカイブ, {skipped}件スキップ")
        return archived
    
    def rebuild_index(self):
        """インデックスを再構築"""
        print("=" * 60)
        print("🔄 インデックス再構築")
        print("=" * 60)
        
        # 既存のインデックスをクリア
        self.storage.index.index["dates"] = {}
        self.storage.index.index["years"] = {}
        self.storage.index.index["venues"] = {}
        
        # アーカイブディレクトリを走査
        count = 0
        for json_file in ARCHIVE_DIR.glob("**/*.json"):
            if json_file.name in ["index.json", "cache.json"]:
                continue
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 日付を抽出
                date_match = re.search(r'results_(\d{8})', json_file.name)
                if not date_match:
                    continue
                
                date_str = date_match.group(1)
                races = data.get("races", [])
                venues = list(set(r.get("venue", "不明") for r in races))
                
                # チェックサム計算
                data_for_checksum = {k: v for k, v in data.items() if k != "_meta"}
                data_str = json.dumps(data_for_checksum, ensure_ascii=False, sort_keys=True)
                checksum = hashlib.md5(data_str.encode()).hexdigest()
                
                # インデックスに追加
                self.storage.index.add_entry(date_str, str(json_file), len(races), venues, checksum)
                count += 1
                
            except Exception as e:
                print(f"[WARN] {json_file}: {e}")
                continue
        
        print(f"\n✅ {count}件のエントリを再構築しました")
        return count


# --- UI用データローダー ---

class ArchiveDataLoader:
    """
    app_commercial.py から呼び出されるデータローダー
    高速な階層検索を提供
    """
    
    def __init__(self):
        self.storage = ArchiveStorage()
        self._cache: Dict[str, Dict] = {}
    
    def get_available_years(self) -> List[int]:
        """利用可能な年のリストを取得"""
        years = self.storage.index.get_years()
        return [int(y) for y in years]
    
    def get_available_months(self, year: int) -> List[int]:
        """指定年の月リストを取得"""
        months = self.storage.index.get_months(str(year))
        return [int(m) for m in months]
    
    def get_available_days(self, year: int, month: int) -> List[int]:
        """指定年月の日リストを取得"""
        days = self.storage.index.get_days(str(year), f"{month:02d}")
        return [int(d) for d in days]
    
    def get_venues_for_date(self, year: int, month: int, day: int) -> List[str]:
        """指定日の競馬場リストを取得"""
        date_str = f"{year}{month:02d}{day:02d}"
        return self.storage.index.get_venues_for_date(date_str)
    
    def load_races_for_date(self, year: int, month: int, day: int) -> List[Dict]:
        """指定日のレースデータを取得"""
        date_str = f"{year}{month:02d}{day:02d}"
        
        # キャッシュチェック
        if date_str in self._cache:
            return self._cache[date_str].get("races", [])
        
        # アーカイブから読み込み
        data = self.storage.load_from_archive(date_str)
        
        if not data:
            # data/ ディレクトリからフォールバック
            filepath = DATA_DIR / f"results_{date_str}.json"
            if filepath.exists():
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    return []
        
        if data:
            self._cache[date_str] = data
            return data.get("races", [])
        
        return []
    
    def load_races_for_venue(self, year: int, month: int, day: int, venue: str) -> List[Dict]:
        """指定日・競馬場のレースデータを取得"""
        all_races = self.load_races_for_date(year, month, day)
        return [r for r in all_races if r.get("venue") == venue]
    
    def get_stats(self) -> Dict:
        """統計情報を取得"""
        return self.storage.index.index.get("stats", {})
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self._cache = {}


# --- メイン処理 ---

def main():
    import sys
    
    print("=" * 60)
    print("📦 UMA-Logic PRO - アーカイブマネージャー")
    print("=" * 60)
    
    archiver = AutoArchiver()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--archive-all":
            archiver.archive_all_existing()
        
        elif command == "--rebuild-index":
            archiver.rebuild_index()
        
        elif command == "--archive-date" and len(sys.argv) > 2:
            date_str = sys.argv[2]
            archiver.archive_date_results(date_str)
        
        elif command == "--stats":
            loader = ArchiveDataLoader()
            stats = loader.get_stats()
            print(f"\n📊 アーカイブ統計:")
            print(f"  総日数: {stats.get('total_dates', 0)}")
            print(f"  総レース数: {stats.get('total_races', 0)}")
            date_range = stats.get('date_range', {})
            print(f"  期間: {date_range.get('start', '-')} 〜 {date_range.get('end', '-')}")
        
        else:
            print("使用方法:")
            print("  --archive-all      : 全既存データをアーカイブ")
            print("  --rebuild-index    : インデックスを再構築")
            print("  --archive-date DATE: 指定日をアーカイブ")
            print("  --stats            : 統計情報を表示")
    
    else:
        # デフォルト: 本日の結果をアーカイブ
        archiver.archive_today_results()
    
    print("\n✅ 処理完了")


if __name__ == "__main__":
    main()
