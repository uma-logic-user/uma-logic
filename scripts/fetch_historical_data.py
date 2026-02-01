# scripts/fetch_historical_data.py
# UMA-Logic Pro - 過去データ一括取得スクリプト（完全修正版）
# netkeibaのカレンダーから開催日を取得し、レース結果を収集

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
import sys

# --- 定数 ---
DATA_DIR = Path("data")
ARCHIVE_DIR = DATA_DIR / "archive"
RESULTS_PREFIX = "results_"

# リクエスト設定
MAX_RETRIES = 3
RETRY_DELAY = 3
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}


def fetch_with_retry(url: str, encoding: str = None) -> Optional[str]:
    """リトライ機能付きHTTPリクエスト"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # 文字コード処理
            if encoding:
                return response.content.decode(encoding, errors='replace')
            
            # 自動検出
            content = response.content[:2000].lower()
            if b'euc-jp' in content:
                return response.content.decode('euc-jp', errors='replace')
            elif b'shift_jis' in content:
                return response.content.decode('shift_jis', errors='replace')
            
            return response.content.decode('utf-8', errors='replace')
            
        except requests.RequestException as e:
            print(f"    [WARN] リクエスト失敗 ({attempt + 1}/{MAX_RETRIES}): {e}")
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


def get_race_dates_from_calendar(year: int, month: int) -> List[str]:
    """
    netkeibaのカレンダーから開催日を取得
    """
    url = f"https://race.netkeiba.com/top/calendar.html?year={year}&month={month}"
    
    html = fetch_with_retry(url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'lxml')
    dates = []
    
    # カレンダーのリンクから開催日を抽出
    for link in soup.find_all('a', href=True):
        href = link['href']
        match = re.search(r'kaisai_date=(\d{8})', href)
        if match:
            date_str = match.group(1)
            if date_str not in dates:
                dates.append(date_str)
    
    return sorted(dates)


def get_race_ids_for_date(date_str: str) -> List[str]:
    """
    指定日のレースIDリストを取得
    """
    url = f"https://race.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
    
    html = fetch_with_retry(url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'lxml')
    race_ids = []
    
    # レースリンクからIDを抽出
    for link in soup.find_all('a', href=True):
        href = link['href']
        match = re.search(r'race_id=(\d+)', href)
        if match:
            race_id = match.group(1)
            if race_id not in race_ids and len(race_id) >= 12:
                race_ids.append(race_id)
    
    return race_ids


def fetch_race_result(race_id: str) -> Optional[Dict]:
    """
    レース結果を取得（race.netkeiba.com/race/result.html）
    """
    url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    
    html = fetch_with_retry(url)
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'lxml')
    
    # ページが存在するか確認
    if 'レース結果' not in html and '着順' not in html:
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
            # 競馬場名を抽出
            for v in ["東京", "中山", "阪神", "京都", "中京", "小倉", "新潟", "福島", "札幌", "函館"]:
                if v in venue_text:
                    race_data["venue"] = v
                    break
    
    # 着順テーブル
    result_table = soup.select_one('.ResultTableWrap table, table.RaceTable01')
    if result_table:
        rows = result_table.select('tr')
        
        for row in rows:
            # ヘッダー行をスキップ
            if row.select('th'):
                continue
            
            cells = row.select('td')
            if len(cells) < 5:
                continue
            
            try:
                # 着順
                rank_elem = row.select_one('.Rank, td:first-child')
                rank = parse_number(rank_elem.get_text()) if rank_elem else 0
                if rank == 0:
                    continue
                
                # 馬番
                umaban_elem = row.select_one('.Umaban, .Waku span')
                umaban = 0
                if umaban_elem:
                    umaban = parse_number(umaban_elem.get_text())
                else:
                    # 2番目か3番目のセルから取得
                    for i in [1, 2]:
                        if i < len(cells):
                            umaban = parse_number(cells[i].get_text())
                            if 1 <= umaban <= 18:
                                break
                
                # 馬名
                horse_name_elem = row.select_one('.Horse_Name a, .HorseName a')
                horse_name = horse_name_elem.get_text(strip=True) if horse_name_elem else ""
                
                # 騎手
                jockey_elem = row.select_one('.Jockey a')
                jockey = jockey_elem.get_text(strip=True) if jockey_elem else ""
                
                # タイム
                time_elem = row.select_one('.Time .RaceTime, .Time')
                race_time = ""
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    time_match = re.search(r'[\d:\.]+', time_text)
                    if time_match:
                        race_time = time_match.group()
                
                # 上がり3F
                last3f_elem = row.select_one('.Time .RapTime')
                last3f = last3f_elem.get_text(strip=True) if last3f_elem else ""
                
                # オッズ
                odds_elem = row.select_one('.Odds span, .Odds')
                odds = parse_float(odds_elem.get_text()) if odds_elem else 0.0
                
                if not horse_name:
                    continue
                
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
    payout_section = soup.select_one('.FullWrap, .PaybackWrap, #All_Result_PayBack')
    if payout_section:
        # 単勝
        tansho = payout_section.select_one('.Tansho .Value, [class*="Tansho"] .Payout')
        if tansho:
            race_data["payouts"]["単勝"] = parse_number(tansho.get_text())
        
        # 馬連
        umaren = payout_section.select_one('.Umaren .Value, [class*="Umaren"] .Payout')
        if umaren:
            race_data["payouts"]["馬連"] = parse_number(umaren.get_text())
        
        # 馬単
        umatan = payout_section.select_one('.Umatan .Value, [class*="Umatan"] .Payout')
        if umatan:
            race_data["payouts"]["馬単"] = parse_number(umatan.get_text())
        
        # 三連複
        sanrenpuku = payout_section.select_one('.Fuku3 .Value, [class*="Sanrenpuku"] .Payout')
        if sanrenpuku:
            race_data["payouts"]["三連複"] = parse_number(sanrenpuku.get_text())
        
        # 三連単
        sanrentan = payout_section.select_one('.Tan3 .Value, [class*="Sanrentan"] .Payout')
        if sanrentan:
            race_data["payouts"]["三連単"] = parse_number(sanrentan.get_text())
    
    # 別パターンの払戻金取得
    if not race_data["payouts"]:
        payout_rows = soup.select('.Payout tr, .PaybackTable tr')
        for row in payout_rows:
            try:
                th = row.select_one('th')
                td = row.select_one('td')
                if th and td:
                    bet_type = th.get_text(strip=True)
                    payout = parse_number(td.get_text())
                    
                    if "単勝" in bet_type:
                        race_data["payouts"]["単勝"] = payout
                    elif "馬連" in bet_type:
                        race_data["payouts"]["馬連"] = payout
                    elif "馬単" in bet_type:
                        race_data["payouts"]["馬単"] = payout
                    elif "三連複" in bet_type or "3連複" in bet_type:
                        race_data["payouts"]["三連複"] = payout
                    elif "三連単" in bet_type or "3連単" in bet_type:
                        race_data["payouts"]["三連単"] = payout
            except:
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
            if races and len(races) >= 6:  # 最低6レース以上
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
    
    print(f"    [SAVED] {len(results)}レース")
    return True


def main():
    print("=" * 60)
    print("🏇 UMA-Logic Pro - 過去データ一括取得（完全修正版）")
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
    total_failed = 0
    
    for year in years:
        print(f"\n{'='*50}")
        print(f"📅 {year}年のデータ取得開始")
        print(f"{'='*50}")
        
        for month in range(1, 13):
            print(f"\n[INFO] {year}年{month}月の開催日を取得中...")
            
            # カレンダーから開催日を取得
            dates = get_race_dates_from_calendar(year, month)
            
            if not dates:
                print(f"  開催日なし")
                continue
            
            print(f"  {len(dates)}日の開催日を発見")
            
            for date_str in dates:
                target_date = datetime.strptime(date_str, "%Y%m%d")
                filepath = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
                
                # 未来の日付はスキップ
                if target_date > datetime.now():
                    continue
                
                weekday_jp = ["月", "火", "水", "木", "金", "土", "日"]
                print(f"\n  [{date_str}] {target_date.month}/{target_date.day}({weekday_jp[target_date.weekday()]})")
                
                # 既存データチェック
                if file_exists_and_valid(filepath):
                    print(f"    [SKIP] 既存データあり")
                    total_skipped += 1
                    continue
                
                # レースID取得
                race_ids = get_race_ids_for_date(date_str)
                
                if not race_ids:
                    print(f"    [WARN] レースIDが見つかりません")
                    total_failed += 1
                    time.sleep(1)
                    continue
                
                print(f"    {len(race_ids)}レースを取得中...")
                
                # 各レースの結果を取得
                results = []
                for race_id in race_ids:
                    result = fetch_race_result(race_id)
                    if result and result.get("all_results"):
                        results.append(result)
                    time.sleep(REQUEST_INTERVAL)
                
                # 保存
                if results:
                    save_results(results, target_date)
                    total_saved += 1
                else:
                    print(f"    [WARN] 有効なデータなし")
                    total_failed += 1
                
                # 日付間の待機
                time.sleep(1)
    
    print("\n" + "=" * 60)
    print(f"✅ 処理完了")
    print(f"   新規保存: {total_saved}日分")
    print(f"   スキップ: {total_skipped}日分（既存データあり）")
    print(f"   失敗: {total_failed}日分")
    print("=" * 60)


if __name__ == "__main__":
    main()
