# scripts/path_utils.py
# UMA-Logic PRO - パス統一ユーティリティ
# PC・GitHub Actions両対応のディレクトリ管理

from pathlib import Path
import os
import json
from datetime import datetime
from typing import Optional, Dict

# --- 基本パス設定 ---
# GitHub Actions と ローカル PC 両方で動作するように自動判定

def get_project_root() -> Path:
    """プロジェクトルートを取得"""
    # 環境変数で指定されている場合
    if os.environ.get("UMA_LOGIC_ROOT"):
        return Path(os.environ["UMA_LOGIC_ROOT"])
    
    # GitHub Actions の場合
    if os.environ.get("GITHUB_WORKSPACE"):
        return Path(os.environ["GITHUB_WORKSPACE"])
    
    # このファイルからの相対パスで判定
    current_file = Path(__file__).resolve()
    
    # scripts/ にいる場合
    if current_file.parent.name == "scripts":
        return current_file.parent.parent
    
    # プロジェクトルートにいる場合
    if (current_file.parent / "data").exists():
        return current_file.parent
    
    # デフォルト: カレントディレクトリ
    return Path.cwd()


def get_data_dir() -> Path:
    """データディレクトリを取得"""
    data_dir = get_project_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_archive_dir() -> Path:
    """アーカイブディレクトリを取得"""
    archive_dir = get_data_dir() / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir


def get_models_dir() -> Path:
    """モデルディレクトリを取得"""
    models_dir = get_data_dir() / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_odds_dir() -> Path:
    """オッズディレクトリを取得"""
    odds_dir = get_data_dir() / "odds"
    odds_dir.mkdir(parents=True, exist_ok=True)
    return odds_dir


# --- アーカイブパス生成 ---

def get_archive_path(date_str: str, file_type: str = "results") -> Path:
    """
    日付からアーカイブパスを生成
    data/archive/YYYY/MM/DD/results_YYYYMMDD.json
    """
    # 日付文字列を正規化
    if len(date_str) == 8:
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
    elif "-" in date_str:
        parts = date_str.split("-")
        year, month, day = parts[0], parts[1], parts[2]
        date_str = f"{year}{month}{day}"
    else:
        raise ValueError(f"Invalid date format: {date_str}")
    
    archive_path = get_archive_dir() / year / month / day
    archive_path.mkdir(parents=True, exist_ok=True)
    
    return archive_path / f"{file_type}_{date_str}.json"


def get_predictions_path(date_str: str = None) -> Path:
    """予想ファイルのパスを取得"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    return get_data_dir() / f"predictions_{date_str}.json"


def get_results_path(date_str: str = None, use_archive: bool = True) -> Path:
    """結果ファイルのパスを取得（アーカイブ優先）"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    
    if use_archive:
        archive_path = get_archive_path(date_str, "results")
        if archive_path.exists():
            return archive_path
    
    return get_data_dir() / f"results_{date_str}.json"


def get_weights_path() -> Path:
    """重みファイルのパスを取得"""
    return get_models_dir() / "weights.json"


def get_alerts_path() -> Path:
    """インサイダーアラートファイルのパスを取得"""
    return get_data_dir() / "insider_alerts.json"


def get_history_path() -> Path:
    """的中履歴ファイルのパスを取得"""
    return get_data_dir() / "history.json"


def get_index_path() -> Path:
    """アーカイブインデックスファイルのパスを取得"""
    return get_archive_dir() / "index.json"


# --- ファイル操作ユーティリティ ---

def load_json(filepath: Path) -> Optional[Dict]:
    """JSONファイルを読み込み"""
    if not filepath.exists():
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] JSON読み込みエラー ({filepath}): {e}")
        return None


def save_json(filepath: Path, data: Dict, indent: int = 2):
    """JSONファイルを保存"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception as e:
        print(f"[ERROR] JSON保存エラー ({filepath}): {e}")
        return False


def check_archived(date_str: str) -> bool:
    """指定日がアーカイブ済みか確認"""
    archive_path = get_archive_path(date_str, "results")
    return archive_path.exists()


def ensure_directories():
    """必要なディレクトリをすべて作成"""
    get_data_dir()
    get_archive_dir()
    get_models_dir()
    get_odds_dir()
    print(f"[INFO] ディレクトリ構成を確認しました")
    print(f"  プロジェクトルート: {get_project_root()}")
    print(f"  データディレクトリ: {get_data_dir()}")
    print(f"  アーカイブディレクトリ: {get_archive_dir()}")


# --- メイン（テスト用） ---

if __name__ == "__main__":
    print("=" * 60)
    print("📁 UMA-Logic PRO - パス統一ユーティリティ")
    print("=" * 60)
    
    ensure_directories()
    
    print(f"\n[TEST] 今日の予想パス: {get_predictions_path()}")
    print(f"[TEST] 今日の結果パス: {get_results_path()}")
    print(f"[TEST] 重みファイルパス: {get_weights_path()}")
    print(f"[TEST] アーカイブパス例: {get_archive_path('20240106')}")
