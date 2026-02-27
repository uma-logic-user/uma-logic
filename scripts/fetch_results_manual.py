import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
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

# --- 定数 ---
DATA_DIR = Path("data")
RESULTS_PREFIX = "results_"
MAX_RETRIES = 3
RETRY_DELAY = 3
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

processor = DataProcessor()

# --- 既存のヘルパー関数（再利用） ---
def fetch_with_retry(url: str, encoding: str = 'euc-jp') -> Optional[str]:
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.encoding = encoding
            if response.status_code == 200:
                return response.text
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

def get_race_ids_for_date(date_str: str) -> List[str]:
    """db.netkeiba.comから指定日のレースIDリストを取得"""
    url = f"https://db.netkeiba.com/race/list/{date_str}/"
    html = fetch_with_retry(url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'lxml')
    race_ids = []
    for link in soup.select('a[href*="/race/"]'):
        match = re.search(r'/race/(\d{12})/', link.get('href', ''))
        if match and match.group(1) not in race_ids:
            race_ids.append(match.group(1))
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
                
                rank_str = cells[0].get_text(strip=True)
                try:
                    rank = int(rank_str)
                except ValueError:
                    rank = rank_str # "中止" "除外" など
                
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
                if isinstance(rank, int) and rank <= 3:
                    race_data["top3"].append(horse_result)
            except Exception as e:
                continue

    return race_data

def save_results_with_processing(results: List[Dict], target_date_str: str, alternative_date_str: str = None):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # DataProcessorで処理
    processed_results = []
    for race in results:
        # 日付情報を付与（代替開催の場合はそちらを優先）
        race["date"] = alternative_date_str if alternative_date_str else target_date_str
        processed = processor.process_race_data(race)
        processed_results.append(processed)
    
    # 保存ファイル名はターゲット日付（本来の開催日）にするか、実施日にするか
    # ユーザー要望: 「実施日」の結果として正しく紐付けて保存
    save_date_str = alternative_date_str if alternative_date_str else target_date_str
    
    filepath = DATA_DIR / f"{RESULTS_PREFIX}{save_date_str}.json"
    
    output_data = {
        "date": save_date_str,
        "original_date": target_date_str, # 元の開催予定日も記録
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "races": processed_results
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"    [SAVED] {len(processed_results)}レース ({save_date_str}) -> {filepath.name}")
    processor.log("INFO", f"結果データ保存完了: {filepath.name}", {"count": len(processed_results)})

def main():
    print("=" * 60)
    print("🏇 UMA-Logic Pro - 1/31・2/1 結果補完 & 延期対応モード")
    print("=" * 60)
    
    target_dates = ["20260131", "20260201"]
    
    for date_str in target_dates:
        print(f"\n📅 {date_str} のデータ取得開始")
        
        # 1. まずその日付で検索
        race_ids = get_race_ids_for_date(date_str)
        
        if race_ids:
            print(f"    {len(race_ids)}レースを発見。取得中...")
            results = []
            for race_id in race_ids:
                result = fetch_race_result(race_id)
                if result:
                    results.append(result)
                time.sleep(REQUEST_INTERVAL)
            
            if results:
                # 取得できた場合、そのまま保存
                save_results_with_processing(results, date_str)
            else:
                 print(f"    [WARN] レースIDはあるが結果詳細が取れませんでした（中止の可能性）")
        else:
             print(f"    [WARN] レースIDが見つかりません（開催中止・延期の可能性）")

        # 2. 代替開催のチェック (雪で延期の場合、翌月曜=20260202 などをチェック)
        # 簡易的に +1日, +2日 をチェックしてみる
        dt = datetime.strptime(date_str, "%Y%m%d")
        for i in range(1, 3):
            alt_date = dt + timedelta(days=i)
            alt_date_str = alt_date.strftime("%Y%m%d")
            
            # 既にこのファイルが存在するかチェック（重複取得防止）
            alt_filepath = DATA_DIR / f"{RESULTS_PREFIX}{alt_date_str}.json"
            if alt_filepath.exists():
                print(f"    [INFO] 代替開催候補 {alt_date_str} のデータは既に存在します")
                continue

            print(f"    🔎 代替開催チェック: {alt_date_str}")
            alt_race_ids = get_race_ids_for_date(alt_date_str)
            
            if alt_race_ids:
                print(f"    🎉 代替開催を発見！ {len(alt_race_ids)}レース ({alt_date_str})")
                alt_results = []
                for race_id in alt_race_ids:
                    res = fetch_race_result(race_id)
                    if res:
                        alt_results.append(res)
                    time.sleep(REQUEST_INTERVAL)
                
                if alt_results:
                    # 代替開催として保存（元の日付情報も渡す）
                    save_results_with_processing(alt_results, date_str, alternative_date_str=alt_date_str)

if __name__ == "__main__":
    main()
