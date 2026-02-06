# scripts/update_results.py
# UMA-Logic Pro - レース結果取得・的中判定スクリプト
# db.netkeiba.com からrace_idを正確に取得する方式

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

# --- 定数 ---
DB_NETKEIBA_URL = "https://db.netkeiba.com"
RESULT_URL = "https://race.netkeiba.com/race/result.html"

DATA_DIR = Path("data")
PREDICTIONS_PREFIX = "predictions_"
RESULTS_PREFIX = "results_"
HISTORY_FILE = "history.json"

MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}

VENUE_CODES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"
}


# --- ヘルパー関数 ---

def get_jst_now():
    """日本時間の現在時刻を取得"""
    try:
        import pytz
        return datetime.now(pytz.timezone('Asia/Tokyo'))
    except ImportError:
        return datetime.now(timezone(timedelta(hours=9)))


def fetch_with_retry(url: str, params: dict = None) -> Optional[requests.Response]:
    """リトライ機能付きHTTPリクエスト"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"[WARN] リクエスト失敗 (試行 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None


def parse_number(text: str) -> int:
    if not text:
        return 0
    nums = re.findall(r'[\d]+', text.replace(',', ''))
    return int(nums[0]) if nums else 0


def parse_float(text: str) -> float:
    if not text:
        return 0.0
    nums = re.findall(r'[\d.]+', text)
    return float(nums[0]) if nums else 0.0


def get_venue_from_race_id(race_id: str) -> str:
    """race_idから競馬場名を取得"""
    if len(race_id) >= 6:
        vv = race_id[4:6]
        return VENUE_CODES.get(vv, "")
    return ""


# --- レースID取得（db.netkeiba.com方式） ---

def get_race_ids_from_db(target_date: datetime) -> List[str]:
    """
    db.netkeiba.com/race/list/YYYYMMDD/ からrace_idリストを取得
    これが最も確実な方法（静的HTML、JavaScriptなし）
    """
    date_str = target_date.strftime("%Y%m%d")
    url = f"{DB_NETKEIBA_URL}/race/list/{date_str}/"

    print(f"[INFO] レースID取得中: {url}")

    response = fetch_with_retry(url)
    if not response:
        print("[ERROR] db.netkeiba.com からのレースリスト取得に失敗しました")
        return []

    # EUC-JPでデコード
    content = response.content.decode('euc-jp', errors='replace')

    # /race/XXXXXXXXXXXX/ 形式のrace_idを抽出
    race_ids = re.findall(r'/race/(\d{12})/', content)
    unique_ids = list(dict.fromkeys(race_ids))  # 重複除去（順序保持）

    # JRA競馬場（VV=01-10）のみフィルタリング
    jra_ids = []
    for rid in unique_ids:
        vv = rid[4:6]
        if vv in VENUE_CODES:
            jra_ids.append(rid)

    jra_ids = sorted(jra_ids)

    # 結果表示
    venues_found = set()
    for rid in jra_ids:
        vv = rid[4:6]
        venues_found.add(VENUE_CODES.get(vv, "不明"))

    print(f"[INFO] {len(jra_ids)}件のJRAレースを発見 ({', '.join(sorted(venues_found))})")

    return jra_ids


# --- レース結果取得 ---

def fetch_race_result(race_id: str) -> Optional[Dict]:
    """レース結果を取得し、推奨データ構造で返す"""
    url = f"{RESULT_URL}?race_id={race_id}"

    response = fetch_with_retry(url)
    if not response:
        print(f"[WARN] 結果取得失敗: {race_id}")
        return None

    # エンコーディング検出
    content_bytes = response.content
    if b'euc-jp' in content_bytes[:2000].lower():
        content = content_bytes.decode('euc-jp', errors='replace')
    elif b'shift_jis' in content_bytes[:2000].lower():
        content = content_bytes.decode('shift_jis', errors='replace')
    else:
        content = content_bytes.decode('utf-8', errors='replace')

    soup = BeautifulSoup(content, 'html.parser')

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

    # race_idからレース番号を取得（フォールバック）
    if race_data["race_num"] == 0 and len(race_id) >= 12:
        race_data["race_num"] = int(race_id[10:12])

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

    # race_idから競馬場を推測（フォールバック）
    if not race_data["venue"]:
        race_data["venue"] = get_venue_from_race_id(race_id)

    # --- 着順テーブル ---
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

            except Exception as e:
                print(f"[WARN] 着順データ解析エラー: {e}")
                continue

    race_data["top3"] = sorted(race_data["top3"], key=lambda x: x.get("着順", 99))[:3]
    race_data["all_results"] = sorted(race_data["all_results"], key=lambda x: x.get("着順", 99))

    # --- 払戻金テーブル ---
    payout_tables = soup.select('.Payout_Detail, .FullWrap .Payout')
    for table in payout_tables:
        rows = table.select('tr')
        for row in rows:
            try:
                bet_type_elem = row.select_one('.Bet_Type, th')
                if not bet_type_elem:
                    continue
                bet_type = bet_type_elem.get_text(strip=True)

                payout_elem = row.select_one('.Payout, .Value')
                if not payout_elem:
                    continue

                payout_value = parse_number(payout_elem.get_text())

                bet_type_map = {
                    "単勝": "単勝", "複勝": "複勝", "枠連": "枠連",
                    "馬連": "馬連", "馬単": "馬単", "ワイド": "ワイド",
                    "三連複": "三連複", "3連複": "三連複",
                    "三連単": "三連単", "3連単": "三連単",
                }

                normalized_type = None
                for key, val in bet_type_map.items():
                    if key in bet_type:
                        normalized_type = val
                        break

                if normalized_type:
                    if normalized_type in ["複勝", "ワイド"]:
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
                continue

    # 払戻金の別パターン解析
    if not race_data["payouts"]:
        payout_block = soup.select_one('#All_Result_PayBack, .PaybackTable')
        if payout_block:
            tansho = payout_block.select_one('.Tansho .Value, [class*="Tansho"] .Payout')
            if tansho:
                race_data["payouts"]["単勝"] = parse_number(tansho.get_text())

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

            umaren = payout_block.select_one('.Umaren .Value, [class*="Umaren"] .Payout')
            if umaren:
                race_data["payouts"]["馬連"] = parse_number(umaren.get_text())

            umatan = payout_block.select_one('.Umatan .Value, [class*="Umatan"] .Payout')
            if umatan:
                race_data["payouts"]["馬単"] = parse_number(umatan.get_text())

            wide_rows = payout_block.select('.Wide tr, [class*="Wide"]')
            if wide_rows:
                wide_dict = {}
                for wr in wide_rows:
                    num_elem = wr.select_one('.Num, .Result')
                    val_elem = wr.select_one('.Value, .Payout')
                    if num_elem and val_elem:
                        num = num_elem.get_text(strip=True).replace(' ', '-').replace('\u3000', '-')
                        val = parse_number(val_elem.get_text())
                        if num and val:
                            wide_dict[num] = val
                if wide_dict:
                    race_data["payouts"]["ワイド"] = wide_dict

            sanrenpuku = payout_block.select_one('.Sanrenpuku .Value, [class*="Sanrenpuku"] .Payout')
            if sanrenpuku:
                race_data["payouts"]["三連複"] = parse_number(sanrenpuku.get_text())

            sanrentan = payout_block.select_one('.Sanrentan .Value, [class*="Sanrentan"] .Payout')
            if sanrentan:
                race_data["payouts"]["三連単"] = parse_number(sanrentan.get_text())

    return race_data


# --- 的中判定 ---

def check_hit(prediction: Dict, result: Dict) -> Dict:
    """予想と結果を照合して的中判定（全券種対応）"""
    hit_result = {
        "単勝": {"hit": False, "payout": 0},
        "複勝": {"hit": False, "payout": 0},
        "馬連": {"hit": False, "payout": 0},
        "馬単": {"hit": False, "payout": 0},
        "ワイド": {"hit": False, "payout": 0},
        "三連複": {"hit": False, "payout": 0},
        "三連単": {"hit": False, "payout": 0},
    }

    if not result or not prediction:
        return hit_result

    top3 = result.get("top3", [])
    if len(top3) < 3:
        return hit_result

    first = top3[0].get("馬番", 0)
    second = top3[1].get("馬番", 0)
    third = top3[2].get("馬番", 0)

    # ◎○▲を取得（uma_index降順 or 印フィールド）
    horses = prediction.get("horses", [])
    honmei, taikou, tanpana = 0, 0, 0

    # uma_index方式
    if horses and "uma_index" in horses[0]:
        sorted_h = sorted(horses, key=lambda x: x.get("uma_index", 0), reverse=True)
        if len(sorted_h) >= 1:
            honmei = sorted_h[0].get("umaban", sorted_h[0].get("馬番", 0))
        if len(sorted_h) >= 2:
            taikou = sorted_h[1].get("umaban", sorted_h[1].get("馬番", 0))
        if len(sorted_h) >= 3:
            tanpana = sorted_h[2].get("umaban", sorted_h[2].get("馬番", 0))
    else:
        # 印方式
        honmei = next((h.get("馬番", h.get("umaban", 0)) for h in horses if h.get("印") == "◎"), 0)
        taikou = next((h.get("馬番", h.get("umaban", 0)) for h in horses if h.get("印") == "○"), 0)
        tanpana = next((h.get("馬番", h.get("umaban", 0)) for h in horses if h.get("印") == "▲"), 0)

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

    # 馬単
    if honmei == first and taikou == second:
        hit_result["馬単"] = {"hit": True, "payout": payouts.get("馬単", 0)}

    # ワイド
    if honmei in [first, second, third] and taikou in [first, second, third]:
        wide_payouts = payouts.get("ワイド", {})
        if isinstance(wide_payouts, dict):
            key1 = f"{min(honmei, taikou)}-{max(honmei, taikou)}"
            payout = wide_payouts.get(key1, 0)
            hit_result["ワイド"] = {"hit": True, "payout": payout}
        else:
            hit_result["ワイド"] = {"hit": True, "payout": 0}

    # 三連複
    if {honmei, taikou, tanpana} == {first, second, third}:
        hit_result["三連複"] = {"hit": True, "payout": payouts.get("三連複", 0)}

    # 三連単
    if honmei == first and taikou == second and tanpana == third:
        hit_result["三連単"] = {"hit": True, "payout": payouts.get("三連単", 0)}

    return hit_result


# --- 履歴管理 ---

def load_history() -> List[Dict]:
    history_path = DATA_DIR / HISTORY_FILE
    if history_path.exists():
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_history(history: List[Dict]):
    history_path = DATA_DIR / HISTORY_FILE
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 履歴保存完了: {history_path}")


def update_history(prediction: Dict, result: Dict, history: List[Dict]):
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
                "投資額": 100,
                "本命馬": "",
                "記録日時": get_jst_now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # 本命馬名を取得
            horses = prediction.get("horses", [])
            if horses:
                if "uma_index" in horses[0]:
                    sorted_h = sorted(horses, key=lambda x: x.get("uma_index", 0), reverse=True)
                    entry["本命馬"] = sorted_h[0].get("馬名", sorted_h[0].get("name", ""))
                else:
                    entry["本命馬"] = next((h.get("馬名", h.get("name", "")) for h in horses if h.get("印") == "◎"), "")

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
    print("🏁 UMA-Logic Pro - 結果取得スクリプト (v2)")
    print("=" * 60)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 対象日を決定
    if len(sys.argv) > 1:
        try:
            target_date = datetime.strptime(sys.argv[1], "%Y%m%d")
        except ValueError:
            print(f"[ERROR] 無効な日付形式: {sys.argv[1]} (YYYYMMDD形式で指定)")
            sys.exit(1)
    else:
        now = get_jst_now()
        print(f"[DEBUG] 現在時刻(JST): {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        if os.getenv('GITHUB_ACTIONS'):
            target_date = now - timedelta(days=1)
            print(f"[INFO] GitHub Actions 検出: 前日({target_date.strftime('%Y-%m-%d')})のデータを取得します")
        else:
            target_date = now
            if now.hour < 18:
                target_date = now - timedelta(days=1)
                print(f"[INFO] 18時前のため前日({target_date.strftime('%Y-%m-%d')})のデータを取得します")
            else:
                print(f"[INFO] 18時以降のため当日({target_date.strftime('%Y-%m-%d')})のデータを取得します")

        print(f"[DEBUG] 対象日: {target_date.strftime('%Y-%m-%d (%A)')}")

    print(f"[INFO] 対象日: {target_date.strftime('%Y年%m月%d日')}")

    # レースID取得（db.netkeiba.com方式）
    race_ids = get_race_ids_from_db(target_date)

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
        venue_name = get_venue_from_race_id(race_id)
        race_num = int(race_id[10:12]) if len(race_id) >= 12 else 0
        print(f"\n[{i+1}/{len(race_ids)}] {venue_name}{race_num}R ({race_id})")

        try:
            result = fetch_race_result(race_id)
            if result and result.get("all_results"):
                all_results.append(result)

                # 予想との照合
                if predictions:
                    pred_races = predictions.get("races", [])
                    pred_race = None
                    for pr in pred_races:
                        pr_venue = pr.get("venue", "")
                        pr_num = pr.get("race_num", 0)
                        if pr_venue == result.get("venue") and pr_num == result.get("race_num"):
                            pred_race = pr
                            break
                    if pred_race:
                        pred_race["date"] = predictions.get("date", target_date.strftime("%Y-%m-%d"))
                        update_history(pred_race, result, history)
            else:
                print(f"  [WARN] 結果データなし")
        except Exception as e:
            print(f"  [ERROR] {e}")
            continue

        if i < len(race_ids) - 1:
            time.sleep(REQUEST_INTERVAL)

    # 保存
    if all_results:
        save_results(all_results, target_date)
        save_history(history)
        print(f"\n[SUCCESS] ✅ 全{len(all_results)}レースの結果を取得しました")
    else:
        print("\n[WARN] 結果を取得できたレースがありませんでした")

    # アーカイブ
    try:
        from archive_manager import AutoArchiver
        archiver = AutoArchiver()
        archiver.archive_today_results()
        print("[INFO] 本日の結果をアーカイブしました")
    except Exception as e:
        print(f"[WARN] アーカイブスキップ: {e}")

    print("=" * 60)
    print("処理完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
