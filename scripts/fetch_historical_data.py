# scripts/fetch_historical_data.py
# UMA-Logic Pro - 過去データ一括取得スクリプト（修正版 ）
# db.netkeiba.com から過去レース結果を取得

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import sys

# --- 定数 ---
# 過去データは db.netkeiba.com を使用
DB_BASE_URL = "https://db.netkeiba.com"
RACE_LIST_URL = "https://db.netkeiba.com/race/list"

DATA_DIR = Path("data" )
ARCHIVE_DIR = DATA_DIR / "archive"
RESULTS_PREFIX = "results_"

# リクエスト設定
MAX_RETRIES = 3
RETRY_DELAY = 3
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 2.5  # サーバー負荷軽減

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Referer": "https://db.netkeiba.com/",
}


def fetch_with_retry(url: str ) -> Optional[requests.Response]:
    """リトライ機能付きHTTPリクエスト"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"  [WARN] リクエスト失敗 (試行 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None


def parse_number(text: str) -> int:
    """数値抽出"""
    if not text:
        return 0
    text = text.replace(',', '').replace('円', '').replace('¥', '')
    nums = re.findall(r'\d+', text)
    return int(nums[0]) if nums else 0


def parse_float(text: str) -> float:
    """小数抽出"""
    if not text:
        return 0.0
    nums = re.findall(r'[\d.]+', text)
    return float(nums[0]) if nums else 0.0


def get_jra_race_dates(year: int, month: int) -> List[str]:
    """
    指定年月のJRA開催日リストを取得
    返り値: ['20240106', '20240107', ...] 形式
    """
    # JRAの開催は基本的に土日
    # 年間スケジュールから開催日を推定
    dates = []
    
    # 月の初日から最終日まで
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    
    current = datetime(year, month, 1)
    
    while current < next_month:
        # 土曜(5)と日曜(6)を開催日として追加
        if current.weekday() in [5, 6]:
            dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    
    return dates


def get_race_ids_from_db(date_str: str) -> List[str]:
    """
    db.netkeiba.com から指定日のレースIDを取得
    """
    # 日付からレースIDのプレフィックスを生成
    # レースID形式: YYYYJJKKNNRR
    # YYYY: 年, JJ: 場所コード, KK: 回次, NN: 日次, RR: レース番号
    
    # 開催場所コード
    venue_codes = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉"
    }
    
    race_ids = []
    year = date_str[:4]
    
    # 各競馬場をチェック
    for venue_code in venue_codes.keys():
        # 回次は1〜5程度、日次は1〜12程度
        for kai in range(1, 6):
            for nichi in range(1, 13):
                # 12レース分のIDを生成
                for race_num in range(1, 13):
                    race_id = f"{year}{venue_code}{kai:02d}{nichi:02d}{race_num:02d}"
                    race_ids.append(race_id)
    
    return race_ids


def fetch_race_result_from_db(race_id: str) -> Optional[Dict]:
    """
    db.netkeiba.com からレース結果を取得
    """
    url = f"{DB_BASE_URL}/race/{race_id}/"
    
    response = fetch_with_retry(url)
    if not response:
        return None
    
    # 文字コード処理
    try:
        html = response.content.decode('euc-jp', errors='replace')
    except:
        html = response.text
    
    soup = BeautifulSoup(html, 'lxml')
    
    # ページが存在するか確認
    title = soup.find('title')
    if not title or 'レース結果' not in title.get_text():
        return None
    
    race_data = {
        "race_id": race_id,
        "race_num": 0,
        "race_name": "",
        "venue": "",
        "top3": [],
        "all_results": [],
        "payouts": {}
    }
    
    # レース情報
    race_name_elem = soup.select_one('.racedata fc h1, .data_intro h1, h1')
    if race_name_elem:
        race_data["race_name"] = race_name_elem.get_text(strip=True)
    
    # レース番号を抽出
    race_num_match = re.search(r'(\d+)R', race_data.get("race_name", ""))
    if race_num_match:
        race_data["race_num"] = int(race_num_match.group(1))
    else:
        # レースIDから抽出
        race_data["race_num"] = int(race_id[-2:])
    
    # 競馬場
    venue_code = race_id[4:6]
    venue_map = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉"
    }
    race_data["venue"] = venue_map.get(venue_code, "不明")
    
    # 着順テーブル
    result_table = soup.select_one('.race_table_01, table.nk_tb_common')
    if result_table:
        rows = result_table.select('tr')[1:]  # ヘッダーをスキップ
        
        for row in rows:
            cells = row.select('td')
            if len(cells) < 10:
                continue
            
            try:
                # 着順
                rank_text = cells[0].get_text(strip=True)
                rank = parse_number(rank_text)
                if rank == 0:
                    continue
                
                # 馬番
                umaban = parse_number(cells[2].get_text(strip=True))
                
                # 馬名
                horse_name_elem = cells[3].select_one('a')
                horse_name = horse_name_elem.get_text(strip=True) if horse_name_elem else cells[3].get_text(strip=True)
                
                # 騎手
                jockey_elem = cells[6].select_one('a')
                jockey = jockey_elem.get_text(strip=True) if jockey_elem else cells[6].get_text(strip=True)
                
                # タイム
                race_time = cells[7].get_text(strip=True) if len(cells) > 7 else ""
                
                # 上がり3F
                last3f = ""
                if len(cells) > 11:
                    last3f = cells[11].get_text(strip=True)
                
                # オッズ
                odds = 0.0
                if len(cells) > 12:
                    odds = parse_float(cells[12].get_text(strip=True))
                elif len(cells) > 10:
                    odds = parse_float(cells[10].get_text(strip=True))
                
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
                    
            except Exception as e:
                continue
    
    # データがなければNone
    if not race_data["all_results"]:
        return None
    
    race_data["top3"] = sorted(race_data["top3"], key=lambda x: x.get("着順", 99))[:3]
    race_data["all_results"] = sorted(race_data["all_results"], key=lambda x: x.get("着順", 99))
    
    # 払戻金テーブル
    payout_tables = soup.select('.pay_table_01, .pay_block table')
    
    for table in payout_tables:
        rows = table.select('tr')
        for row in rows:
            header = row.select_one('th')
            value_cell = row.select_one('td')
            
            if not header or not value_cell:
                continue
            
            bet_type = header.get_text(strip=True)
            
            # 払戻金額を取得
            payout_text = value_cell.get_text(strip=True)
            payout_value = parse_number(payout_text)
            
            if "単勝" in bet_type:
                race_data["payouts"]["単勝"] = payout_value
            elif "複勝" in bet_type:
                # 複勝は複数ある場合がある
                if "複勝" not in race_data["payouts"]:
                    race_data["payouts"]["複勝"] = {}
                nums = re.findall(r'(\d+)\s*[\-－]\s*(\d+)', payout_text)
                if nums:
                    for num, pay in nums:
                        race_data["payouts"]["複勝"][num] = parse_number(pay)
                else:
                    race_data["payouts"]["複勝"]["1"] = payout_value
            elif "枠連" in bet_type:
                race_data["payouts"]["枠連"] = payout_value
            elif "馬連" in bet_type:
                race_data["payouts"]["馬連"] = payout_value
            elif "馬単" in bet_type:
                race_data["payouts"]["馬単"] = payout_value
            elif "ワイド" in bet_type:
                if "ワイド" not in race_data["payouts"]:
                    race_data["payouts"]["ワイド"] = {}
                race_data["payouts"]["ワイド"]["1"] = payout_value
            elif "三連複" in bet_type or "3連複" in bet_type:
                race_data["payouts"]["三連複"] = payout_value
            elif "三連単" in bet_type or "3連単" in bet_type:
                race_data["payouts"]["三連単"] = payout_value
    
    return race_data


def file_exists_and_valid(filepath: Path) -> bool:
    """ファイルが存在し、有効なデータを含むか確認"""
    if not filepath.exists():
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            races = data.get("races", [])
            if races and len(races) > 0:
                if races[0].get("top3") or races[0].get("all_results"):
                    return True
    except:
        pass
    
    return False


def save_results(results: List[Dict], target_date: datetime):
    """結果データを保存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = target_date.strftime("%Y%m%d")
    filepath = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
    archive_path = ARCHIVE_DIR / f"{RESULTS_PREFIX}{date_str}.json"
    
    output_data = {
        "date": target_date.strftime("%Y-%m-%d"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "races": results
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"  [SAVED] {filepath} ({len(results)}レース)")


def fetch_date_results(date_str: str) -> List[Dict]:
    """
    指定日の全レース結果を取得
    """
    year = date_str[:4]
    
    # 各競馬場・回次・日次を試す
    venue_codes = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]
    
    results = []
    found_venues = set()
    
    for venue_code in venue_codes:
        # 回次と日次を推定して試す
        for kai in range(1, 6):
            for nichi in range(1, 13):
                venue_found = False
                
                for race_num in range(1, 13):
                    race_id = f"{year}{venue_code}{kai:02d}{nichi:02d}{race_num:02d}"
                    
                    # 既に見つかった競馬場の場合は続ける
                    if venue_code in found_venues and race_num > 1:
                        result = fetch_race_result_from_db(race_id)
                        if result:
                            results.append(result)
                            time.sleep(REQUEST_INTERVAL)
                        continue
                    
                    # 1Rを試してこの開催があるか確認
                    if race_num == 1:
                        result = fetch_race_result_from_db(race_id)
                        if result:
                            results.append(result)
                            found_venues.add(venue_code)
                            venue_found = True
                            time.sleep(REQUEST_INTERVAL)
                        else:
                            break  # この回次・日次は存在しない
                    elif venue_found:
                        result = fetch_race_result_from_db(race_id)
                        if result:
                            results.append(result)
                            time.sleep(REQUEST_INTERVAL)
                
                if not venue_found:
                    break  # この回次は存在しない
    
    return results


def main():
    print("=" * 60)
    print("🏇 UMA-Logic Pro - 過去データ一括取得（修正版）")
    print("=" * 60)
    
    # 引数で年を指定可能
    if len(sys.argv) > 1:
        try:
            years = [int(y) for y in sys.argv[1:]]
        except ValueError:
            print("[ERROR] 年は数字で指定してください")
            sys.exit(1)
    else:
        current_year = datetime.now().year
        years = [current_year - 1, current_year]
    
    print(f"[INFO] 対象年: {years}")
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    total_saved = 0
    total_skipped = 0
    
    for year in years:
        print(f"\n{'='*40}")
        print(f"📅 {year}年のデータ取得開始")
        print(f"{'='*40}")
        
        for month in range(1, 13):
            print(f"\n[INFO] {year}年{month}月")
            
            # 土日の日付リストを取得
            dates = get_jra_race_dates(year, month)
            
            for date_str in dates:
                target_date = datetime.strptime(date_str, "%Y%m%d")
                filepath = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
                
                # 未来の日付はスキップ
                if target_date > datetime.now():
                    continue
                
                print(f"\n  [{date_str}] {target_date.strftime('%m/%d')}")
                
                # 既存データチェック
                if file_exists_and_valid(filepath):
                    print(f"    [SKIP] 既存データあり")
                    total_skipped += 1
                    continue
                
                # レース結果を取得
                results = fetch_date_results(date_str)
                
                if results:
                    save_results(results, target_date)
                    total_saved += 1
                else:
                    print(f"    [WARN] データなし")
    
    print("\n" + "=" * 60)
    print(f"✅ 処理完了")
    print(f"   新規保存: {total_saved}日分")
    print(f"   スキップ: {total_skipped}日分")
    print("=" * 60)


if __name__ == "__main__":
    main()
