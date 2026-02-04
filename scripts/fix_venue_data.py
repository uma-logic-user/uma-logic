#!/usr/bin/env python3
"""
既存のresultsファイルのvenueを修正するスクリプト
race_idから競馬場名を復元する
"""

import json
import sys
from pathlib import Path
from typing import Dict

# 競馬場コード
VENUE_CODES = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉"
}

DATA_DIR = Path("data")


def get_venue_from_race_id(race_id: str) -> str:
    """race_idから競馬場名を取得"""
    if len(race_id) >= 8:
        venue_code = race_id[6:8]
        return VENUE_CODES.get(venue_code, "")
    return ""


def fix_results_file(file_path: Path) -> Dict:
    """resultsファイルのvenueを修正"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] ファイル読み込みエラー: {file_path} - {e}")
        return {"fixed": 0, "total": 0}
    
    races = data.get("races", [])
    fixed_count = 0
    
    for race in races:
        race_id = race.get("race_id", "")
        current_venue = race.get("venue", "")
        
        # venueが空または不正な場合、race_idから復元
        if not current_venue or current_venue == "不明":
            new_venue = get_venue_from_race_id(race_id)
            if new_venue:
                race["venue"] = new_venue
                fixed_count += 1
    
    if fixed_count > 0:
        # 修正を保存
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] ファイル保存エラー: {file_path} - {e}")
            return {"fixed": 0, "total": len(races)}
    
    return {"fixed": fixed_count, "total": len(races)}


def main():
    """メイン処理"""
    print("=" * 60)
    print("🔧 UMA-Logic - venue データ修正スクリプト")
    print("=" * 60)
    
    # 対象ファイルを取得
    results_files = sorted(DATA_DIR.glob("results_*.json"))
    
    if not results_files:
        print("[INFO] 修正対象のファイルがありません")
        return
    
    print(f"\n[INFO] {len(results_files)}件のファイルを処理します\n")
    
    total_fixed = 0
    total_races = 0
    files_modified = 0
    
    for file_path in results_files:
        result = fix_results_file(file_path)
        
        if result["fixed"] > 0:
            print(f"  ✅ {file_path.name}: {result['fixed']}/{result['total']}件を修正")
            files_modified += 1
        
        total_fixed += result["fixed"]
        total_races += result["total"]
    
    print("\n" + "=" * 60)
    print("📊 修正結果")
    print("=" * 60)
    print(f"  処理ファイル数: {len(results_files)}件")
    print(f"  修正ファイル数: {files_modified}件")
    print(f"  修正レース数: {total_fixed}/{total_races}件")
    print("=" * 60)


if __name__ == "__main__":
    main()
