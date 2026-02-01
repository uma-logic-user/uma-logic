# scripts/update_results.py
# UMA-Logic Pro - 商用グレード結果取得・的中判定スクリプト
# レース結果と全券種の払戻金を取得し、日付別JSONに保存。予想と照合して的中履歴を更新。

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pytz

# --- 定数 ---
BASE_URL = "https://race.netkeiba.com"
RESULT_URL = "https://race.netkeiba.com/race/result.html"

DATA_DIR = Path("data" )
PREDICTIONS_PREFIX = "predictions_"
RESULTS_PREFIX = "results_"
HISTORY_FILE = "history.json"

# リクエスト設定
MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 1.5  # リクエスト間隔（秒）

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}

# --- ヘルパー関数 ---

def fetch_with_retry(url: str, params: dict = None) -> Optional[requests.Response]:
    """
    リトライ機能付きHTTPリクエスト
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"[WARN] リクエスト失敗 (試行 {attempt + 1}/{MAX_RETRIES}): {url}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    print(f"[ERROR] 最大リトライ回数超過: {url}")
    return None


def decode_html(response: requests.Response) -> str:
    """
    netkeibaのHTMLをデコード（EUC-JP対応）
    """
    try:
        return response.content.decode("euc-jp", errors="replace")
    except Exception:
        return response.text


def parse_payout(text: str) -> int:
    """
    払戻金テキスト（例: "1,230円"）を整数に変換
    """
    if not text:
        return 0
    try:
        return int(text.replace(",", "").replace("円", ""))
    except (ValueError, TypeError):
        return 0


# --- スクレイピング関数 ---

def scrape_race_result(race_id: str) -> Optional[dict]:
    """
    レース結果ページから着順と払戻金をスクレイピング
    """
    url = f"{RESULT_URL}?race_id={race_id}"
    print(f"[INFO] 結果を取得中: {race_id}")
    
    response = fetch_with_retry(url)
    if not response:
        return None
    
    html = decode_html(response)
    soup = BeautifulSoup(html, "lxml")
    
    # 結果テーブルから着順を取得
    result_table = soup.select_one("table.RaceTable01")
    if not result_table:
        print(f"[WARN] 結果テーブルが見つかりません: {race_id}")
        return None
    
    top_horses = []
    rows = result_table.select("tr")[1:]  # ヘッダーを除外
    for row in rows:
        try:
            cells = row.select("td")
            if len(cells) < 11:
                continue
            
            horse_info = {
                "着順": int(cells[0].get_text(strip=True)),
                "馬番": int(cells[2].get_text(strip=True)),
                "馬名": cells[3].get_text(strip=True),
                "騎手": cells[6].get_text(strip=True),
                "タイム": cells[7].get_text(strip=True),
                "上がり3F": cells[10].get_text(strip=True),
            }
            top_horses.append(horse_info)
        except (ValueError, IndexError):
            continue
    
    # 払戻金テーブルを取得
    payouts = {}
    payout_tables = soup.select(".Payback_Table_Simple, .Payback_Table_Trifecta")
    
    for table in payout_tables:
        for row in table.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if not th or not td:
                continue
            
            bet_type = th.get_text(strip=True)
            numbers = td.select_one(".Results_Txt").get_text(strip=True) if td.select_one(".Results_Txt") else ""
            payout_yen = parse_payout(td.select_one(".Payout").get_text(strip=True) if td.select_one(".Payout") else "")
            
            if bet_type == "複勝":
                payouts["複勝"] = {}
                num_list = numbers.split()
                payout_list = [parse_payout(p) for p in td.select_one(".Payout").get_text().split()]
                for i in range(len(num_list)):
                    payouts["複勝"][num_list[i]] = payout_list[i]
            elif bet_type == "ワイド":
                payouts["ワイド"] = {}
                num_list = numbers.split("\n")
                payout_list = [parse_payout(p) for p in td.select_one(".Payout").get_text().split("\n")]
                for i in range(len(num_list)):
                    payouts["ワイド"][num_list[i].strip()] = payout_list[i]
            else:
                payouts[bet_type] = payout_yen

    # レース基本情報を取得
    race_header = soup.select_one(".RaceName")
    race_name = race_header.get_text(strip=True) if race_header else ""
    race_num_match = re.search(r"(\d{1,2})R", soup.select_one(".RaceNum").get_text()) if soup.select_one(".RaceNum") else None
    race_num = int(race_num_match.group(1)) if race_num_match else 0
    venue = soup.select_one(".RaceData02 .Active").get_text(strip=True) if soup.select_one(".RaceData02 .Active") else ""

    return {
        "race_id": race_id,
        "race_name": race_name,
        "race_num": race_num,
        "venue": venue,
        "top3": top_horses[:3],
        "all_results": top_horses,
        "payouts": payouts,
    }


# --- データ処理・保存関数 ---

def update_history(prediction_race: dict, result_race: dict, history: List[dict]):
    """
    予想と結果を照合し、的中履歴を更新する
    """
    if not prediction_race or not result_race:
        return

    # 投資額はシミュレーション（ここでは固定100円とする）
    investment_per_bet = 100
    
    # 結果から着順を取得
    top3 = result_race.get("top3", [])
    if len(top3) < 3:
        return
    
    first = top3[0].get("馬番", 0)
    second = top3[1].get("馬番", 0)
    third = top3[2].get("馬番", 0)
    
    # 予想から推奨馬を取得
    horses = prediction_race.get("horses", [])
    if not horses:
        return
    
    honmei = next((h["馬番"] for h in horses if h.get("印") == "◎"), 0)
    taikou = next((h["馬番"] for h in horses if h.get("印") == "○"), 0)
    tanpana = next((h["馬番"] for h in horses if h.get("印") == "▲"), 0)
    
    payouts = result_race.get("payouts", {})
    
    # 的中判定と履歴追加
    def add_history(bet_type, payout):
        history.append({
            "日付": prediction_race["date"],
            "レース名": prediction_race["race_name"],
            "的中券種": bet_type,
            "投資額": investment_per_bet,
            "的中配当金": payout,
        })

    # 単勝（◎が1着）
    if honmei == first:
        add_history("単勝", payouts.get("単勝", 0))

    # 複勝（◎が3着以内）
    if honmei in [first, second, third]:
        payout = payouts.get("複勝", {}).get(str(honmei), 0)
        add_history("複勝", payout)

    # 馬連（◎○が1-2着）
    if {honmei, taikou} == {first, second}:
        add_history("馬連", payouts.get("馬連", 0))

    # 三連複（◎○▲が1-2-3着）
    if {honmei, taikou, tanpana} == {first, second, third}:
        add_history("三連複", payouts.get("三連複", 0))


def save_data(results: List[dict], history: List[dict], target_date: datetime.date):
    """
    結果データと履歴データをJSONで保存
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    date_str = target_date.strftime("%Y%m%d")
    
    # 結果データの保存
    results_data = {
        "date": target_date.strftime("%Y-%m-%d"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "races": results,
    }
    filepath = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 結果を保存しました: {filepath}")

    # 履歴データの保存
    history_path = DATA_DIR / HISTORY_FILE
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 履歴を更新しました: {history_path}")


# --- メイン処理 ---

def main():
    """
    メイン処理
    """
    print("=" * 60)
    print("UMA-Logic Pro - 結果取得・的中判定スクリプト")
    print("=" * 60)

    # 対象日を決定（引数があればそれ、なければ昨日）
    import sys
    if len(sys.argv) > 1:
        try:
            target_date = datetime.strptime(sys.argv[1], "%Y%m%d").date()
        except ValueError:
            print("[ERROR] 日付の形式が不正です。YYYYMMDD形式で指定してください。")
            return
    else:
        jst = pytz.timezone("Asia/Tokyo")
        target_date = (datetime.now(jst) - timedelta(days=1)).date()
    
    print(f"[INFO] 対象日: {target_date.strftime('%Y年%m月%d日')}")

    # 予想データを読み込み
    date_str = target_date.strftime("%Y%m%d")
    prediction_filepath = DATA_DIR / f"{PREDICTIONS_PREFIX}{date_str}.json"
    if not prediction_filepath.exists():
        print(f"[ERROR] 予想ファイルが見つかりません: {prediction_filepath}")
        return
    
    with open(prediction_filepath, "r", encoding="utf-8") as f:
        predictions = json.load(f)
    
    prediction_races = predictions.get("races", [])
    if not prediction_races:
        print("[ERROR] 予想データにレース情報が含まれていません。")
        return
    
    # 履歴データを読み込み
    history_path = DATA_DIR / HISTORY_FILE
    history = []
    if history_path.exists():
        with open(history_path, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                print("[WARN] 履歴ファイルが空か壊れています。新規作成します。")

    # 各レースの結果を取得
    all_results = []
    race_ids = [r["race_id"] for r in prediction_races]
    
    for i, race_id in enumerate(race_ids):
        print(f"\n[INFO] 処理中: {i + 1}/{len(race_ids)}")
        result = scrape_race_result(race_id)
        if result:
            all_results.append(result)
            
            # 予想と照合して履歴を更新
            prediction_race = next((p for p in prediction_races if p["race_id"] == race_id), None)
            if prediction_race:
                prediction_race["date"] = predictions["date"] # 日付情報を付与
                update_history(prediction_race, result, history)
        
        if i < len(race_ids) - 1:
            time.sleep(REQUEST_INTERVAL)

    # データを保存
    if all_results:
        save_data(all_results, history, target_date)
        print("\n[INFO] 全ての処理が完了しました。")
    else:
        print("\n[WARN] 結果を取得できたレースがありませんでした。")


if __name__ == "__main__":
    main()
