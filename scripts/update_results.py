# scripts/update_results.py
# UMA-Logic Pro - レース結果取得・的中判定スクリプト
# 推奨データ構造で results_YYYYMMDD.json を保存

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# pytzがない環境でも動作
try:
    import pytz
    JST = pytz.timezone('Asia/Tokyo')
except ImportError:
    JST = None

# --- 定数 ---
BASE_URL = "https://race.netkeiba.com"
RESULT_URL = "https://race.netkeiba.com/race/result.html"
RACE_LIST_URL = "https://race.netkeiba.com/top/race_list.html"

DATA_DIR = Path("data")
PREDICTIONS_PREFIX = "predictions_"
RESULTS_PREFIX = "results_"
HISTORY_FILE = "history.json"

# リクエスト設定
MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}

# 中央競馬の競馬場コード
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


# --- ヘルパー関数 ---

def get_jst_now():
    """日本時間の現在時刻を取得（確実にJSTで取得）"""
    try:
        import pytz
        JST = pytz.timezone('Asia/Tokyo')
        utc_now = datetime.now(timezone.utc)
        return utc_now.astimezone(JST)
    except ImportError:
        jst = timezone(timedelta(hours=9))
        utc_now = datetime.now(timezone.utc)
        return utc_now.astimezone(jst)


def fetch_with_retry(url: str, params: dict = None) -> Optional[requests.Response]:
    """リトライ機能付きHTTPリクエスト"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"[WARN] リクエスト失敗 (試行 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None


def detect_encoding(response: requests.Response) -> str:
    """レスポンスの文字コードを検出"""
    if response.encoding:
        return response.encoding
    content = response.content[:1000].lower()
    if b'euc-jp' in content:
        return 'euc-jp'
    elif b'shift_jis' in content or b'sjis' in content:
        return 'shift_jis'
    return 'utf-8'


def parse_number(text: str) -> int:
    """文字列から数値を抽出"""
    if not text:
        return 0
    nums = re.findall(r'[\d,]+', text.replace(',', ''))
    return int(nums[0]) if nums else 0


def parse_float(text: str) -> float:
    """文字列から小数を抽出"""
    if not text:
        return 0.0
    nums = re.findall(r'[\d.]+', text)
    return float(nums[0]) if nums else 0.0


# --- レースID生成・検索（新方式） ---

def get_likely_kaisai_codes(target_date: datetime) -> List[str]:
    """
    日付から開催コードを推測
    
    開催コードは年初からの開催週でカウントされる
    例: 1月第1週=01, 1月第2週=02, ...
    """
    month = target_date.month
    
    if month <= 2:
        return ["01", "02", "03", "04", "05"]
    elif month <= 4:
        return ["03", "04", "05", "06", "07", "08"]
    elif month <= 6:
        return ["06", "07", "08", "09", "10", "11"]
    elif month <= 8:
        return ["09", "10", "11", "12", "13", "14"]
    elif month <= 10:
        return ["12", "13", "14", "15", "16", "17"]
    else:
        return ["15", "16", "17", "18", "19", "20"]


def generate_possible_race_ids(target_date: datetime) -> List[str]:
    """
    指定日の全ての可能性のあるrace_idを生成する
    
    中央競馬のrace_id形式: 2026XXYYZZMM
    - 2026: 年
    - XX: 開催コード (01-20程度、開催週による)
    - YY: 競馬場コード (01-10)
    - ZZ: 日付の下2桁
    - MM: レース番号 (01-12)
    """
    year = target_date.year
    date_2digit = target_date.strftime("%d")
    
    # 開催コードを推測
    kaisai_codes = get_likely_kaisai_codes(target_date)
    
    race_ids = []
    
    # 全競馬場×全開催コード×全レース番号の組み合わせを生成
    for kaisai_code in kaisai_codes:
        for venue_code in VENUE_CODES.keys():
            for race_num in range(1, 13):  # 1R～12R
                race_id = f"{year}{kaisai_code}{venue_code}{date_2digit}{race_num:02d}"
                race_ids.append(race_id)
    
    return race_ids


def check_race_exists(race_id: str) -> bool:
    """
    指定したrace_idのレースが存在するか確認
    """
    url = f"{RESULT_URL}?race_id={race_id}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        
        # ステータスコード200 かつ レース結果が含まれているか
        if response.status_code == 200:
            content = response.text
            # 404ページやエラーページでないことを確認
            if "ResultTableWrap" in content or "着順" in content:
                return True
        
        return False
        
    except Exception:
        return False


def get_race_ids_for_date_v2(target_date: datetime) -> List[str]:
    """
    指定日のレースIDリストを取得（改善版・並列処理）
    
    アプローチ:
    1. 可能性のある全race_idを生成
    2. 各IDに対して結果ページが存在するか並列確認
    3. 存在するrace_idのみを返す
    """
    print(f"[INFO] レースID探索開始: {target_date.strftime('%Y年%m月%d日')}")
    
    # 可能性のある全race_idを生成
    possible_ids = generate_possible_race_ids(target_date)
    
    print(f"[INFO] {len(possible_ids)}個の候補をチェック中...")
    
    valid_race_ids = []
    
    # 並列処理で高速化
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_id = {
            executor.submit(check_race_exists, race_id): race_id 
            for race_id in possible_ids
        }
        
        for future in as_completed(future_to_id):
            race_id = future_to_id[future]
            try:
                if future.result():
                    valid_race_ids.append(race_id)
                    # 競馬場名を取得
                    venue_code = race_id[6:8]
                    venue_name = VENUE_CODES.get(venue_code, "不明")
                    race_num = int(race_id[-2:])
                    print(f"  ✓ レース発見: {race_id} ({venue_name}{race_num}R)")
            except Exception as e:
                pass  # エラーは無視して続行
    
    # race_idでソート
    valid_race_ids = sorted(valid_race_ids)
    
    print(f"[INFO] {len(valid_race_ids)}件のレースを発見しました")
    
    return valid_race_ids


def get_race_ids_for_date(target_date: datetime) -> List[str]:
    """
    指定日のレースIDリストを取得（旧方式・フォールバック用）
    """
    date_str = target_date.strftime("%Y%m%d")
    url = f"{RACE_LIST_URL}?kaisai_date={date_str}"
    
    print(f"[INFO] レースリスト取得中（旧方式）: {url}")
    
    response = fetch_with_retry(url)
    if not response:
        print("[ERROR] レースリストの取得に失敗しました")
        return []
    
    encoding = detect_encoding(response)
    soup = BeautifulSoup(response.content.decode(encoding, errors='replace'), 'lxml')
    
    race_ids = []
    
    # レースリンクからIDを抽出
    for link in soup.find_all('a', href=True):
        href = link['href']
        if 'race_id=' in href:
            match = re.search(r'race_id=(\d+)', href)
            if match:
                race_id = match.group(1)
                if race_id not in race_ids:
                    race_ids.append(race_id)
    
    print(f"[INFO] {len(race_ids)}件のレースIDを取得しました")
    return race_ids


# --- レース結果取得 ---

def fetch_race_result(race_id: str) -> Optional[Dict]:
    """
    レース結果を取得し、推奨データ構造で返す
    """
    url = f"{RESULT_URL}?race_id={race_id}"
    
    print(f"[INFO] 結果取得中: {race_id}")
    
    response = fetch_with_retry(url)
    if not response:
        return None
    
    encoding = detect_encoding(response)
    soup = BeautifulSoup(response.content.decode(encoding, errors='replace'), 'lxml')
    
    # --- レース基本情報 ---
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
        # 「1回東京1日」→「東京」
        venue_match = re.search(r'[0-9]+回(.+?)[0-9]+日', venue_text)
        if venue_match:
            race_data["venue"] = venue_match.group(1)
        else:
            race_data["venue"] = venue_text[:2] if len(venue_text) >= 2 else venue_text
    
    # race_idから競馬場を推測（フォールバック）
    if not race_data["venue"]:
        venue_code = race_id[6:8]
        race_data["venue"] = VENUE_CODES.get(venue_code, "不明")
    
    # --- 着順テーブル ---
    result_table = soup.select_one('.ResultTableWrap table')
    if result_table:
        rows = result_table.select('tr.HorseList')
        
        for row in rows:
            try:
                # 着順
                rank_elem = row.select_one('.Rank')
                rank = parse_number(rank_elem.get_text()) if rank_elem else 0
                
                # 馬番
                umaban_elem = row.select_one('.Umaban')
                umaban = parse_number(umaban_elem.get_text()) if umaban_elem else 0
                
                # 馬名
                horse_name_elem = row.select_one('.Horse_Name a')
                horse_name = horse_name_elem.get_text(strip=True) if horse_name_elem else ""
                
                # 騎手
                jockey_elem = row.select_one('.Jockey a')
                jockey = jockey_elem.get_text(strip=True) if jockey_elem else ""
                
                # タイム
                time_elem = row.select_one('.Time .RaceTime')
                race_time = time_elem.get_text(strip=True) if time_elem else ""
                
                # 上がり3F
                last3f_elem = row.select_one('.Time .RapTime')
                last3f = last3f_elem.get_text(strip=True) if last3f_elem else ""
                
                # 単勝オッズ
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
                
                # 上位3頭をtop3に追加
                if rank <= 3:
                    race_data["top3"].append(horse_result)
                    
            except Exception as e:
                print(f"[WARN] 着順データ解析エラー: {e}")
                continue
    
    # top3を着順でソート
    race_data["top3"] = sorted(race_data["top3"], key=lambda x: x.get("着順", 99))[:3]
    race_data["all_results"] = sorted(race_data["all_results"], key=lambda x: x.get("着順", 99))
    
    # --- 払戻金テーブル ---
    payout_tables = soup.select('.Payout_Detail, .FullWrap .Payout')
    
    for table in payout_tables:
        rows = table.select('tr')
        
        for row in rows:
            try:
                # 券種名
                bet_type_elem = row.select_one('.Bet_Type, th')
                if not bet_type_elem:
                    continue
                bet_type = bet_type_elem.get_text(strip=True)
                
                # 払戻金
                payout_elem = row.select_one('.Payout, .Value')
                if not payout_elem:
                    continue
                
                payout_text = payout_elem.get_text(strip=True)
                payout_value = parse_number(payout_text)
                
                # 券種を正規化
                bet_type_map = {
                    "単勝": "単勝",
                    "複勝": "複勝",
                    "枠連": "枠連",
                    "馬連": "馬連",
                    "馬単": "馬単",
                    "ワイド": "ワイド",
                    "三連複": "三連複",
                    "3連複": "三連複",
                    "三連単": "三連単",
                    "3連単": "三連単",
                }
                
                normalized_type = None
                for key, val in bet_type_map.items():
                    if key in bet_type:
                        normalized_type = val
                        break
                
                if normalized_type:
                    # 複勝・ワイドは複数の払戻がある場合がある
                    if normalized_type in ["複勝", "ワイド"]:
                        # 馬番を取得
                        result_elem = row.select_one('.Result, .Num')
                        if result_elem:
                            result_nums = re.findall(r'\d+', result_elem.get_text())
                            if result_nums:
                                key = "-".join(result_nums) if len(result_nums) > 1 else result_nums[0]
                                if normalized_type not in race_data["payouts"]:
                                    race_data["payouts"][normalized_type] = {}
                                race_data["payouts"][normalized_type][key] = payout_value
                    else:
                        race_data["payouts"][normalized_type] = payout_value
                        
            except Exception as e:
                print(f"[WARN] 払戻金解析エラー: {e}")
                continue
    
    # 払戻金の別パターン解析（netkeiba形式）
    if not race_data["payouts"]:
        payout_block = soup.select_one('#All_Result_PayBack, .PaybackTable')
        if payout_block:
            # 単勝
            tansho = payout_block.select_one('.Tansho .Value, [class*="Tansho"] .Payout')
            if tansho:
                race_data["payouts"]["単勝"] = parse_number(tansho.get_text())
            
            # 複勝
            fukusho_rows = payout_block.select('.Fukusho tr, [class*="Fukusho"]')
            if fukusho_rows:
                fukusho_dict = {}
                for fr in fukusho_rows:
                    num_elem = fr.select_one('.Num, .Result')
                    val_elem = fr.select_one('.Value, .Payout')
                    if num_elem and val_elem:
                        num = num_elem.get_text(strip=True)
                        val = parse_number(val_elem.get_text())
                        if num and val:
                            fukusho_dict[num] = val
                if fukusho_dict:
                    race_data["payouts"]["複勝"] = fukusho_dict
            
            # 馬連
            umaren = payout_block.select_one('.Umaren .Value, [class*="Umaren"] .Payout')
            if umaren:
                race_data["payouts"]["馬連"] = parse_number(umaren.get_text())
            
            # 馬単
            umatan = payout_block.select_one('.Umatan .Value, [class*="Umatan"] .Payout')
            if umatan:
                race_data["payouts"]["馬単"] = parse_number(umatan.get_text())
            
            # ワイド
            wide_rows = payout_block.select('.Wide tr, [class*="Wide"]')
            if wide_rows:
                wide_dict = {}
                for wr in wide_rows:
                    num_elem = wr.select_one('.Num, .Result')
                    val_elem = wr.select_one('.Value, .Payout')
                    if num_elem and val_elem:
                        num = num_elem.get_text(strip=True).replace(' ', '-').replace('　', '-')
                        val = parse_number(val_elem.get_text())
                        if num and val:
                            wide_dict[num] = val
                if wide_dict:
                    race_data["payouts"]["ワイド"] = wide_dict
            
            # 三連複
            sanrenpuku = payout_block.select_one('.Sanrenpuku .Value, [class*="Sanrenpuku"] .Payout')
            if sanrenpuku:
                race_data["payouts"]["三連複"] = parse_number(sanrenpuku.get_text())
            
            # 三連単
            sanrentan = payout_block.select_one('.Sanrentan .Value, [class*="Sanrentan"] .Payout')
            if sanrentan:
                race_data["payouts"]["三連単"] = parse_number(sanrentan.get_text())
    
    return race_data


# --- 的中判定 ---

def check_hit(prediction: Dict, result: Dict) -> Dict:
    """予想と結果を照合して的中判定"""
    hit_result = {
        "単勝": {"hit": False, "payout": 0},
        "複勝": {"hit": False, "payout": 0},
        "馬連": {"hit": False, "payout": 0},
        "三連複": {"hit": False, "payout": 0},
    }
    
    if not result or not prediction:
        return hit_result
    
    top3 = result.get("top3", [])
    if len(top3) < 3:
        return hit_result
    
    first = top3[0].get("馬番", 0)
    second = top3[1].get("馬番", 0)
    third = top3[2].get("馬番", 0)
    
    horses = prediction.get("horses", [])
    honmei = next((h["馬番"] for h in horses if h.get("印") == "◎"), 0)
    taikou = next((h["馬番"] for h in horses if h.get("印") == "○"), 0)
    tanpana = next((h["馬番"] for h in horses if h.get("印") == "▲"), 0)
    
    payouts = result.get("payouts", {})
    
    # 単勝
    if honmei == first:
        hit_result["単勝"] = {"hit": True, "payout": payouts.get("単勝", 0)}
    
    # 複勝
    if honmei in [first, second, third]:
        fukusho = payouts.get("複勝", {})
        payout = fukusho.get(str(honmei), 0) if isinstance(fukusho, dict) else 0
        hit_result["複勝"] = {"hit": True, "payout": payout}
    
    # 馬連
    if {honmei, taikou} == {first, second}:
        hit_result["馬連"] = {"hit": True, "payout": payouts.get("馬連", 0)}
    
    # 三連複
    if {honmei, taikou, tanpana} == {first, second, third}:
        hit_result["三連複"] = {"hit": True, "payout": payouts.get("三連複", 0)}
    
    return hit_result


# --- 履歴更新 ---

def load_history() -> List[Dict]:
    """的中履歴を読み込む"""
    history_path = DATA_DIR / HISTORY_FILE
    if history_path.exists():
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_history(history: List[Dict]):
    """的中履歴を保存"""
    history_path = DATA_DIR / HISTORY_FILE
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 履歴保存完了: {history_path}")


def update_history(prediction: Dict, result: Dict, history: List[Dict]):
    """的中した場合、履歴に追加"""
    hit_info = check_hit(prediction, result)
    
    for bet_type, info in hit_info.items():
        if info["hit"] and info["payout"] > 0:
            entry = {
                "日付": prediction.get("date", ""),
                "会場": prediction.get("venue", result.get("venue", "")),
                "R": prediction.get("race_num", result.get("race_num", 0)),
                "レース名": result.get("race_name", ""),
                "券種": bet_type,
                "的中配当金": info["payout"],
                "投資額": 100,  # デフォルト投資額
                "本命馬": next((h.get("馬名", "") for h in prediction.get("horses", []) if h.get("印") == "◎"), ""),
                "記録日時": get_jst_now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 重複チェック
            is_duplicate = any(
                h.get("日付") == entry["日付"] and
                h.get("会場") == entry["会場"] and
                h.get("R") == entry["R"] and
                h.get("券種") == entry["券種"]
                for h in history
            )
            
            if not is_duplicate:
                history.append(entry)
                print(f"[HIT] 🎯 {entry['会場']}{entry['R']}R {bet_type} ¥{info['payout']:,}")


# --- データ保存 ---

def save_results(results: List[Dict], target_date: datetime):
    """結果データを推奨構造で保存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = target_date.strftime("%Y%m%d")
    filepath = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
    
    output_data = {
        "date": target_date.strftime("%Y-%m-%d"),
        "updated_at": get_jst_now().strftime("%Y-%m-%d %H:%M:%S"),
        "races": results
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"[INFO] 結果保存完了: {filepath} ({len(results)}レース)")


# --- メイン処理 ---

def main():
    print("=" * 60)
    print("🏁 UMA-Logic Pro - 結果取得スクリプト")
    print("=" * 60)
    
    # データディレクトリ作成
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # 対象日を決定（引数または自動判定）
    import sys
    if len(sys.argv) > 1:
        try:
            target_date = datetime.strptime(sys.argv[1], "%Y%m%d")
        except ValueError:
            print(f"[ERROR] 日付形式が不正です: {sys.argv[1]} (YYYYMMDD形式で指定)")
            sys.exit(1)
    else:
        # 自動判定：GitHub Actions 実行時は環境変数で判別
        now = get_jst_now()
        print(f"[DEBUG] 現在時刻(JST): {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        if os.getenv('GITHUB_ACTIONS'):
            # GitHub Actions 実行時は明示的に前日を指定
            target_date = now - timedelta(days=1)
            print(f"[INFO] GitHub Actions 検出: 前日({target_date.strftime('%Y-%m-%d')})のデータを取得します")
        else:
            # ローカル実行時は時刻で判定
            target_date = now
            
            # 18時以降なら当日の結果を取得
            # 18時以前なら前日の結果を取得
            if now.hour < 18:
                target_date = now - timedelta(days=1)
                print(f"[INFO] 18時前のため前日({target_date.strftime('%Y-%m-%d')})のデータを取得します")
            else:
                print(f"[INFO] 18時以降のため当日({target_date.strftime('%Y-%m-%d')})のデータを取得します")
        
        print(f"[DEBUG] 対象日: {target_date.strftime('%Y-%m-%d (%A)')}")
    
    print(f"[INFO] 対象日: {target_date.strftime('%Y年%m月%d日')}")
    
    # レースID取得（新方式を優先、失敗したら旧方式にフォールバック）
    race_ids = get_race_ids_for_date_v2(target_date)
    
    if not race_ids:
        print("[INFO] 新方式で見つからなかったため、旧方式を試行...")
        race_ids = get_race_ids_for_date(target_date)
    
    if not race_ids:
        print("[INFO] 本日は開催がないか、レースが見つかりませんでした。")
        sys.exit(0)
    
    # 予想データ読み込み（的中判定用）
    pred_path = DATA_DIR / f"{PREDICTIONS_PREFIX}{target_date.strftime('%Y%m%d')}.json"
    predictions = {}
    if pred_path.exists():
        try:
            with open(pred_path, 'r', encoding='utf-8') as f:
                predictions = json.load(f)
            print(f"[INFO] 予想データ読み込み完了: {pred_path}")
        except Exception as e:
            print(f"[WARN] 予想データ読み込み失敗: {e}")
    
    # 履歴読み込み
    history = load_history()
    
    # 結果取得
    all_results = []
    
    for i, race_id in enumerate(race_ids):
        print(f"\n[{i+1}/{len(race_ids)}] レースID: {race_id}")
        
        result = fetch_race_result(race_id)
        
        if result:
            all_results.append(result)
            
            # 予想との照合
            if predictions:
                pred_race = next(
                    (r for r in predictions.get("races", [])
                     if r.get("venue") == result.get("venue") and
                        r.get("race_num") == result.get("race_num")),
                    None
                )
                if pred_race:
                    pred_race["date"] = predictions.get("date", target_date.strftime("%Y-%m-%d"))
                    update_history(pred_race, result, history)
        
        # リクエスト間隔
        if i < len(race_ids) - 1:
            time.sleep(REQUEST_INTERVAL)
    
    # 保存
    if all_results:
        save_results(all_results, target_date)
        save_history(history)
        print(f"\n[SUCCESS] ✅ 全{len(all_results)}レースの結果を取得しました")
    else:
        print("\n[WARN] 結果を取得できたレースがありませんでした")
    
    # === 自動アーカイブ ===
    try:
        from archive_manager import AutoArchiver
        archiver = AutoArchiver()
        archiver.archive_today_results()
        print("[INFO] 本日の結果をアーカイブしました")
    except Exception as e:
        print(f"[WARN] アーカイブエラー: {e}")
    
    print("=" * 60)
    print("処理完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
