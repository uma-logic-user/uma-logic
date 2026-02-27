# scripts/fetch_historical_data.py
# UMA-Logic Pro - 過去データ一括取得スクリプト（db.netkeiba.com版）
# 動作確認済み

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys

# --- 定数 ---
DATA_DIR = Path("data")
ARCHIVE_DIR = DATA_DIR / "archive"
RESULTS_PREFIX = "results_"

MAX_RETRIES = 3
RETRY_DELAY = 3
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def fetch_with_retry(url: str, encoding: str = 'euc-jp') -> Optional[str]:
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.content.decode(encoding, errors='replace')
        except requests.RequestException as e:
            print(f"    [WARN] リクエスト失敗 ({attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None


def parse_number(text: str) -> int:
    if not text:
        return 0
    text = text.replace(',', '').replace('円', '')
    nums = re.findall(r'\d+', text)
    return int(nums[0]) if nums else 0


def parse_float(text: str) -> float:
    if not text:
        return 0.0
    nums = re.findall(r'[\d.]+', text)
    return float(nums[0]) if nums else 0.0


def get_race_dates_from_calendar(year: int, month: int) -> List[str]:
    """race.netkeiba.comのカレンダーから開催日を取得"""
    url = f"https://race.netkeiba.com/top/calendar.html?year={year}&month={month}"
    html = fetch_with_retry(url, 'utf-8')
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'lxml')
    dates = []
    for link in soup.find_all('a', href=True):
        match = re.search(r'kaisai_date=(\d{8})', link['href'])
        if match:
            date_str = match.group(1)
            if date_str not in dates and date_str.startswith(str(year)):
                dates.append(date_str)
    return sorted(dates)


def is_jra_race_id(race_id: str) -> bool:
    """venue code 01-10 (JRA中央競馬) のみ Trueを返す"""
    s = str(race_id)
    if len(s) < 10:
        return False
    code = s[4:6]
    return code in {"01","02","03","04","05","06","07","08","09","10"}


def get_race_ids_for_date(date_str: str) -> List[str]:
    """db.netkeiba.comから指定日のレースIDリストを取得 (中央競馬のみ)"""
    url = f"https://db.netkeiba.com/race/list/{date_str}/"
    html = fetch_with_retry(url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'lxml')
    race_ids = []
    for link in soup.select('a[href*="/race/"]'):
        match = re.search(r'/race/(\d{12})/', link.get('href', ''))
        if match:
            rid = match.group(1)
            if rid not in race_ids and is_jra_race_id(rid):  # JRAのみ
                race_ids.append(rid)
    if not race_ids:
        print(f"    [INFO] JRAレースなし: {date_str} (地方競馬は除外)")
    return sorted(race_ids)


def fetch_race_result(race_id: str) -> Optional[Dict]:
    """db.netkeiba.comからレース結果を取得"""
    url = f"https://db.netkeiba.com/race/{race_id}/"
    html = fetch_with_retry(url)
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'lxml')
    
    race_data = {
        "race_id": race_id,
        "race_num": int(race_id[-2:]),
        "race_name": "",
        "venue": "",
        "top3": [],
        "all_results": [],
        "payouts": {}
    }
    
    # レース名
    race_name_elem = soup.select_one('.racedata h1, .data_intro h1')
    if race_name_elem:
        race_data["race_name"] = race_name_elem.get_text(strip=True)
    
    # 競馬場
    race_info = soup.select_one('.racedata, .data_intro')
    if race_info:
        info_text = race_info.get_text()
        for v in ["東京", "中山", "阪神", "京都", "中京", "小倉", "新潟", "福島", "札幌", "函館"]:
            if v in info_text:
                race_data["venue"] = v
                break
    
    # 着順テーブル
    result_table = soup.select_one('table.race_table_01')
    if result_table:
        rows = result_table.select('tr')
        for row in rows[1:]:
            try:
                cells = row.select('td')
                if len(cells) < 10:
                    continue
                
                rank = parse_number(cells[0].get_text(strip=True))
                if rank == 0:
                    continue
                
                horse_name_elem = cells[3].select_one('a')
                horse_name = horse_name_elem.get_text(strip=True) if horse_name_elem else cells[3].get_text(strip=True)
                
                jockey_elem = cells[6].select_one('a') if len(cells) > 6 else None
                jockey = jockey_elem.get_text(strip=True) if jockey_elem else ""
                
                horse_result = {
                    "着順": rank,
                    "馬番": parse_number(cells[2].get_text(strip=True)),
                    "馬名": horse_name,
                    "騎手": jockey,
                    "タイム": cells[7].get_text(strip=True) if len(cells) > 7 else "",
                    "上がり3F": cells[11].get_text(strip=True) if len(cells) > 11 else "",
                    "オッズ": parse_float(cells[12].get_text(strip=True)) if len(cells) > 12 else 0.0
                }
                
                race_data["all_results"].append(horse_result)
                if rank <= 3:
                    race_data["top3"].append(horse_result)
            except:
                continue
    
    if not race_data["all_results"]:
        return None
    
    # 払戻金
    for table in soup.select('table.pay_table_01'):
        for row in table.select('tr'):
            try:
                th = row.select_one('th')
                tds = row.select('td')
                if th and len(tds) >= 2:
                    bet_type = th.get_text(strip=True)
                    payout = parse_number(tds[1].get_text(strip=True))
                    if "単勝" in bet_type:
                        race_data["payouts"]["単勝"] = payout
                    elif "複勝" in bet_type:
                        race_data["payouts"]["複勝"] = payout
                    elif "枠連" in bet_type:
                        race_data["payouts"]["枠連"] = payout
                    elif "馬連" in bet_type:
                        race_data["payouts"]["馬連"] = payout
                    elif "馬単" in bet_type:
                        race_data["payouts"]["馬単"] = payout
                    elif "ワイド" in bet_type:
                        race_data["payouts"]["ワイド"] = payout
                    elif "三連複" in bet_type:
                        race_data["payouts"]["三連複"] = payout
                    elif "三連単" in bet_type:
                        race_data["payouts"]["三連単"] = payout
            except:
                continue
    
    return race_data


def file_exists_and_valid(filepath: Path) -> bool:
    if not filepath.exists():
        return False
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            races = data.get("races", [])
            return len(races) >= 6 and races[0].get("all_results")
    except:
        return False


def save_results(results: List[Dict], target_date: datetime):
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
    
    for path in [filepath, archive_path]:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"    [SAVED] {len(results)}レース → {filepath.name}")


def main():
    print("=" * 60)
    print("🏇 UMA-Logic Pro - 過去データ一括取得（db.netkeiba.com版）")
    print("=" * 60)
    
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
    total_failed = 0
    
    for year in years:
        print(f"\n{'='*50}")
        print(f"📅 {year}年のデータ取得開始")
        print(f"{'='*50}")
        
        for month in range(1, 13):
            print(f"\n[INFO] {year}年{month}月")
            
            dates = get_race_dates_from_calendar(year, month)
            if not dates:
                print(f"  開催日なし")
                continue
            
            print(f"  {len(dates)}日の開催日")
            
            for date_str in dates:
                target_date = datetime.strptime(date_str, "%Y%m%d")
                filepath = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
                
                if target_date > datetime.now():
                    continue
                
                weekday_jp = ["月", "火", "水", "木", "金", "土", "日"]
                print(f"\n  [{date_str}] {target_date.month}/{target_date.day}({weekday_jp[target_date.weekday()]})")
                
                if file_exists_and_valid(filepath):
                    print(f"    [SKIP] 既存データあり")
                    total_skipped += 1
                    continue
                
                race_ids = get_race_ids_for_date(date_str)
                if not race_ids:
                    print(f"    [WARN] レースIDなし")
                    total_failed += 1
                    time.sleep(1)
                    continue
                
                print(f"    {len(race_ids)}レース取得中...")
                
                results = []
                for race_id in race_ids:
                    result = fetch_race_result(race_id)
                    if result:
                        results.append(result)
                    time.sleep(REQUEST_INTERVAL)
                
                if results:
                    save_results(results, target_date)
                    total_saved += 1
                else:
                    print(f"    [WARN] 有効データなし")
                    total_failed += 1
                
                time.sleep(1)
    
    print("\n" + "=" * 60)
    print(f"✅ 処理完了")
    print(f"   新規保存: {total_saved}日分")
    print(f"   スキップ: {total_skipped}日分")
    print(f"   失敗: {total_failed}日分")
    print("=" * 60)


if __name__ == "__main__":
    main()
