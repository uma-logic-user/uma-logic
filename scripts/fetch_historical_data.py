# scripts/fetch_historical_data.py
# UMA-Logic Pro - 過去データ一括取得スクリプト
# 過去2年分のレース結果を取得し、アーカイブとして保存

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import sys

# --- 定数 ---
BASE_URL = "https://race.netkeiba.com"
RESULT_URL = "https://race.netkeiba.com/race/result.html"
CALENDAR_URL = "https://race.netkeiba.com/top/calendar.html"

DATA_DIR = Path("data" )
ARCHIVE_DIR = DATA_DIR / "archive"
RESULTS_PREFIX = "results_"

# リクエスト設定
MAX_RETRIES = 3
RETRY_DELAY = 3
REQUEST_TIMEOUT = 20
REQUEST_INTERVAL = 2.0  # サーバー負荷軽減のため長めに

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}


def fetch_with_retry(url: str, params: dict = None) -> Optional[requests.Response]:
    """リトライ機能付きHTTPリクエスト"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"  [WARN] リクエスト失敗 (試行 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None


def detect_encoding(response: requests.Response) -> str:
    """文字コード検出"""
    content = response.content[:1000].lower()
    if b'euc-jp' in content:
        return 'euc-jp'
    elif b'shift_jis' in content:
        return 'shift_jis'
    return 'utf-8'


def parse_number(text: str) -> int:
    """数値抽出"""
    if not text:
        return 0
    nums = re.findall(r'[\d,]+', text.replace(',', ''))
    return int(nums[0]) if nums else 0


def parse_float(text: str) -> float:
    """小数抽出"""
    if not text:
        return 0.0
    nums = re.findall(r'[\d.]+', text)
    return float(nums[0]) if nums else 0.0


def get_race_dates_for_year(year: int) -> List[datetime]:
    """指定年の開催日リストを取得"""
    print(f"[INFO] {year}年の開催日を取得中...")
    
    race_dates = []
    
    for month in range(1, 13):
        url = f"{CALENDAR_URL}?year={year}&month={month}"
        response = fetch_with_retry(url)
        
        if not response:
            continue
        
        encoding = detect_encoding(response)
        soup = BeautifulSoup(response.content.decode(encoding, errors='replace'), 'lxml')
        
        # カレンダーから開催日を抽出
        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'kaisai_date=' in href:
                match = re.search(r'kaisai_date=(\d{8})', href)
                if match:
                    try:
                        date = datetime.strptime(match.group(1), "%Y%m%d")
                        if date not in race_dates:
                            race_dates.append(date)
                    except ValueError:
                        continue
        
        time.sleep(0.5)
    
    race_dates.sort()
    print(f"[INFO] {year}年: {len(race_dates)}日の開催日を取得")
    return race_dates


def get_race_ids_for_date(target_date: datetime) -> List[str]:
    """指定日のレースIDリストを取得"""
    date_str = target_date.strftime("%Y%m%d")
    url = f"https://race.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
    
    response = fetch_with_retry(url )
    if not response:
        return []
    
    encoding = detect_encoding(response)
    soup = BeautifulSoup(response.content.decode(encoding, errors='replace'), 'lxml')
    
    race_ids = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        if 'race_id=' in href:
            match = re.search(r'race_id=(\d+)', href)
            if match:
                race_id = match.group(1)
                if race_id not in race_ids:
                    race_ids.append(race_id)
    
    return race_ids


def fetch_race_result(race_id: str) -> Optional[Dict]:
    """レース結果を取得"""
    url = f"{RESULT_URL}?race_id={race_id}"
    
    response = fetch_with_retry(url)
    if not response:
        return None
    
    encoding = detect_encoding(response)
    soup = BeautifulSoup(response.content.decode(encoding, errors='replace'), 'lxml')
    
    race_data = {
        "race_id": race_id,
        "race_num": 0,
        "race_name": "",
        "venue": "",
        "top3": [],
        "all_results": [],
        "payouts": {}
    }
    
    # レース番号
    race_num_elem = soup.select_one('.RaceNum')
    if race_num_elem:
        race_data["race_num"] = parse_number(race_num_elem.get_text())
    
    # レース名
    race_name_elem = soup.select_one('.RaceName')
    if race_name_elem:
        race_data["race_name"] = race_name_elem.get_text(strip=True)
    
    # 競馬場
    venue_elem = soup.select_one('.RaceData02 span')
    if venue_elem:
        venue_text = venue_elem.get_text(strip=True)
        venue_match = re.search(r'[0-9]+回(.+?)[0-9]+日', venue_text)
        if venue_match:
            race_data["venue"] = venue_match.group(1)
        else:
            race_data["venue"] = venue_text[:2] if len(venue_text) >= 2 else venue_text
    
    # 着順テーブル
    result_table = soup.select_one('.ResultTableWrap table')
    if result_table:
        rows = result_table.select('tr.HorseList')
        
        for row in rows:
            try:
                rank_elem = row.select_one('.Rank')
                rank = parse_number(rank_elem.get_text()) if rank_elem else 0
                
                umaban_elem = row.select_one('.Umaban')
                umaban = parse_number(umaban_elem.get_text()) if umaban_elem else 0
                
                horse_name_elem = row.select_one('.Horse_Name a')
                horse_name = horse_name_elem.get_text(strip=True) if horse_name_elem else ""
                
                jockey_elem = row.select_one('.Jockey a')
                jockey = jockey_elem.get_text(strip=True) if jockey_elem else ""
                
                time_elem = row.select_one('.Time .RaceTime')
                race_time = time_elem.get_text(strip=True) if time_elem else ""
                
                last3f_elem = row.select_one('.Time .RapTime')
                last3f = last3f_elem.get_text(strip=True) if last3f_elem else ""
                
                odds_elem = row.select_one('.Odds span')
                odds = parse_float(odds_elem.get_text()) if odds_elem else 0.0
                
                horse_result = {
                    "着順": rank,
                    "馬番": umaban,
                    "馬名": horse_name,
                    "騎手": jockey,
                    "タイム": race_time,
                    "上がり3F": last3f,
                    "オッズ": odds
                }
                
                race_data["all_results"].append(horse_result)
                
                if rank <= 3:
                    race_data["top3"].append(horse_result)
                    
            except Exception:
                continue
    
    race_data["top3"] = sorted(race_data["top3"], key=lambda x: x.get("着順", 99))[:3]
    race_data["all_results"] = sorted(race_data["all_results"], key=lambda x: x.get("着順", 99))
    
    # 払戻金（簡易版）
    payout_tables = soup.select('.Payout_Detail, .FullWrap .Payout, .PaybackTable')
    
    for table in payout_tables:
        rows = table.select('tr')
        for row in rows:
            try:
                bet_type_elem = row.select_one('.Bet_Type, th')
                if not bet_type_elem:
                    continue
                bet_type = bet_type_elem.get_text(strip=True)
                
                payout_elem = row.select_one('.Payout, .Value, td:nth-child(2)')
                if not payout_elem:
                    continue
                
                payout_value = parse_number(payout_elem.get_text())
                
                bet_type_map = {
                    "単勝": "単勝", "複勝": "複勝", "枠連": "枠連",
                    "馬連": "馬連", "馬単": "馬単", "ワイド": "ワイド",
                    "三連複": "三連複", "3連複": "三連複",
                    "三連単": "三連単", "3連単": "三連単",
                }
                
                for key, val in bet_type_map.items():
                    if key in bet_type:
                        if val in ["複勝", "ワイド"]:
                            result_elem = row.select_one('.Result, .Num')
                            if result_elem:
                                result_nums = re.findall(r'\d+', result_elem.get_text())
                                if result_nums:
                                    k = "-".join(result_nums) if len(result_nums) > 1 else result_nums[0]
                                    if val not in race_data["payouts"]:
                                        race_data["payouts"][val] = {}
                                    race_data["payouts"][val][k] = payout_value
                        else:
                            race_data["payouts"][val] = payout_value
                        break
            except Exception:
                continue
    
    return race_data


def file_exists_and_valid(filepath: Path) -> bool:
    """ファイルが存在し、有効なデータを含むか確認"""
    if not filepath.exists():
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            races = data.get("races", [])
            # レースが1つ以上あり、着順データがあれば有効
            if races and len(races) > 0:
                if races[0].get("top3") or races[0].get("all_results"):
                    return True
    except Exception:
        pass
    
    return False


def save_results(results: List[Dict], target_date: datetime, force: bool = False):
    """結果データを保存（アーカイブ管理付き）"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = target_date.strftime("%Y%m%d")
    filepath = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
    archive_path = ARCHIVE_DIR / f"{RESULTS_PREFIX}{date_str}.json"
    
    # 既存ファイルがあり、有効なデータを含む場合はスキップ（forceでない限り）
    if not force and file_exists_and_valid(filepath):
        print(f"  [SKIP] 既存データあり: {filepath}")
        return False
    
    # 既存ファイルをアーカイブにバックアップ
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            
            # バックアップ（タイムスタンプ付き）
            backup_path = ARCHIVE_DIR / f"{RESULTS_PREFIX}{date_str}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(old_data, f, ensure_ascii=False, indent=2)
            print(f"  [BACKUP] {backup_path}")
        except Exception:
            pass
    
    # 新しいデータを保存
    output_data = {
        "date": target_date.strftime("%Y-%m-%d"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "races": results
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    # アーカイブにもコピー
    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"  [SAVED] {filepath} ({len(results)}レース)")
    return True


def main():
    print("=" * 60)
    print("🏇 UMA-Logic Pro - 過去データ一括取得スクリプト")
    print("=" * 60)
    
    # 引数で年を指定可能
    if len(sys.argv) > 1:
        try:
            years = [int(y) for y in sys.argv[1:]]
        except ValueError:
            print("[ERROR] 年は数字で指定してください（例: 2024 2025）")
            sys.exit(1)
    else:
        # デフォルト: 過去2年
        current_year = datetime.now().year
        years = [current_year - 1, current_year]
    
    print(f"[INFO] 対象年: {years}")
    print()
    
    # ディレクトリ作成
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    total_saved = 0
    total_skipped = 0
    
    for year in years:
        print(f"\n{'='*40}")
        print(f"📅 {year}年のデータ取得開始")
        print(f"{'='*40}")
        
        # 開催日リストを取得
        race_dates = get_race_dates_for_year(year)
        
        if not race_dates:
            print(f"[WARN] {year}年の開催日が見つかりませんでした")
            continue
        
        for i, target_date in enumerate(race_dates):
            date_str = target_date.strftime("%Y-%m-%d")
            filepath = DATA_DIR / f"{RESULTS_PREFIX}{target_date.strftime('%Y%m%d')}.json"
            
            print(f"\n[{i+1}/{len(race_dates)}] {date_str}")
            
            # 既存データチェック
            if file_exists_and_valid(filepath):
                print(f"  [SKIP] 既存データあり")
                total_skipped += 1
                continue
            
            # レースID取得
            race_ids = get_race_ids_for_date(target_date)
            
            if not race_ids:
                print(f"  [WARN] レースIDが見つかりません")
                continue
            
            print(f"  [INFO] {len(race_ids)}レースを取得中...")
            
            # 各レースの結果を取得
            results = []
            for race_id in race_ids:
                result = fetch_race_result(race_id)
                if result:
                    results.append(result)
                time.sleep(REQUEST_INTERVAL)
            
            # 保存
            if results:
                if save_results(results, target_date):
                    total_saved += 1
            
            # 日付間の待機
            time.sleep(1)
    
    print("\n" + "=" * 60)
    print(f"✅ 処理完了")
    print(f"   新規保存: {total_saved}日分")
    print(f"   スキップ: {total_skipped}日分（既存データあり）")
    print("=" * 60)


if __name__ == "__main__":
    main()
