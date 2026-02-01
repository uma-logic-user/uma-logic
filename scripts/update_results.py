#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UMA-Logic 商用グレード完成版 update_results.py v14.0
- レース結果の自動取得
- 全券種の払い戻し取得
- 的中判定と収支計算
- 履歴・統計の自動更新
"""

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# 定数
BASE_URL = "https://race.netkeiba.com"

# 競馬場コード
VENUE_CODES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"
}


def get_japan_date():
    """日本時間の日付を取得"""
    from datetime import timezone
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst)


def load_predictions():
    """予想データを読み込み"""
    try:
        path = Path(__file__).parent.parent / "data" / "latest_predictions.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"予想データ読み込みエラー: {e}")
    return None


def load_history():
    """履歴データを読み込み"""
    try:
        path = Path(__file__).parent.parent / "data" / "history.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"履歴データ読み込みエラー: {e}")
    return []


def save_history(history):
    """履歴データを保存"""
    try:
        path = Path(__file__).parent.parent / "data" / "history.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"履歴データ保存エラー: {e}")


def load_stats():
    """統計データを読み込み"""
    try:
        path = Path(__file__).parent.parent / "data" / "stats.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"統計データ読み込みエラー: {e}")
    return {
        "total_bets": 0,
        "total_wins": 0,
        "total_payout": 0,
        "total_investment": 0,
        "tansho_stats": {"bets": 0, "hits": 0, "payout": 0, "investment": 0},
        "umaren_stats": {"bets": 0, "hits": 0, "payout": 0, "investment": 0},
        "umatan_stats": {"bets": 0, "hits": 0, "payout": 0, "investment": 0},
        "sanrenpuku_stats": {"bets": 0, "hits": 0, "payout": 0, "investment": 0},
        "sanrentan_stats": {"bets": 0, "hits": 0, "payout": 0, "investment": 0}
    }


def save_stats(stats):
    """統計データを保存"""
    try:
        path = Path(__file__).parent.parent / "data" / "stats.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"統計データ保存エラー: {e}")


def fetch_race_result(race_id):
    """レース結果を取得"""
    try:
        url = f"{BASE_URL}/race/result.html?race_id={race_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.encoding == 'ISO-8859-1':
            response.encoding = 'EUC-JP'
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 着順を取得
        result = {
            "result_1st": {},
            "result_2nd": {},
            "result_3rd": {},
            "payouts": {}
        }
        
        # 着順テーブルから取得
        result_rows = soup.select("tr.HorseList")
        
        for i, row in enumerate(result_rows[:3]):
            try:
                umaban_elem = row.select_one("td.Umaban")
                umaban = int(umaban_elem.get_text(strip=True)) if umaban_elem else 0
                
                name_elem = row.select_one(".HorseName a")
                name = name_elem.get_text(strip=True) if name_elem else ""
                
                key = ["result_1st", "result_2nd", "result_3rd"][i]
                result[key] = {"umaban": umaban, "name": name}
            except:
                continue
        
        # 払い戻しを取得
        payout_table = soup.select_one(".Payout_Detail_Table")
        if payout_table:
            rows = payout_table.select("tr")
            for row in rows:
                try:
                    type_elem = row.select_one("th")
                    value_elem = row.select_one("td")
                    
                    if type_elem and value_elem:
                        bet_type = type_elem.get_text(strip=True)
                        value_text = value_elem.get_text(strip=True)
                        
                        # 金額を抽出
                        amount_match = re.search(r'([\d,]+)円', value_text)
                        if amount_match:
                            amount = int(amount_match.group(1).replace(',', ''))
                            
                            if "単勝" in bet_type:
                                result["payouts"]["tansho"] = amount
                            elif "複勝" in bet_type:
                                result["payouts"]["fukusho"] = value_text
                            elif "馬連" in bet_type:
                                result["payouts"]["umaren"] = amount
                            elif "馬単" in bet_type:
                                result["payouts"]["umatan"] = amount
                            elif "三連複" in bet_type:
                                result["payouts"]["sanrenpuku"] = amount
                            elif "三連単" in bet_type:
                                result["payouts"]["sanrentan"] = amount
                except:
                    continue
        
        return result
        
    except Exception as e:
        print(f"結果取得エラー ({race_id}): {e}")
        return None


def check_hit(prediction, result):
    """的中判定"""
    hits = {}
    
    bets = prediction.get("bets", {})
    payouts = result.get("payouts", {})
    
    first = result.get("result_1st", {}).get("umaban", 0)
    second = result.get("result_2nd", {}).get("umaban", 0)
    third = result.get("result_3rd", {}).get("umaban", 0)
    
    # 単勝
    if bets.get("tansho") == first:
        hits["tansho"] = {
            "is_hit": True,
            "payout": payouts.get("tansho", 0)
        }
    else:
        hits["tansho"] = {"is_hit": False, "payout": 0}
    
    # 馬連
    umaren = bets.get("umaren", [])
    if sorted(umaren) == sorted([first, second]):
        hits["umaren"] = {
            "is_hit": True,
            "payout": payouts.get("umaren", 0)
        }
    else:
        hits["umaren"] = {"is_hit": False, "payout": 0}
    
    # 馬単
    umatan = bets.get("umatan", [])
    if umatan == [first, second]:
        hits["umatan"] = {
            "is_hit": True,
            "payout": payouts.get("umatan", 0)
        }
    else:
        hits["umatan"] = {"is_hit": False, "payout": 0}
    
    # 三連複
    sanrenpuku = bets.get("sanrenpuku", [])
    if sorted(sanrenpuku) == sorted([first, second, third]):
        hits["sanrenpuku"] = {
            "is_hit": True,
            "payout": payouts.get("sanrenpuku", 0)
        }
    else:
        hits["sanrenpuku"] = {"is_hit": False, "payout": 0}
    
    # 三連単（フォーメーション）
    formation = bets.get("sanrentan_formation", {})
    if formation:
        first_list = formation.get("first", [])
        second_list = formation.get("second", [])
        third_list = formation.get("third", [])
        
        if first in first_list and second in second_list and third in third_list:
            hits["sanrentan"] = {
                "is_hit": True,
                "payout": payouts.get("sanrentan", 0)
            }
        else:
            hits["sanrentan"] = {"is_hit": False, "payout": 0}
    else:
        hits["sanrentan"] = {"is_hit": False, "payout": 0}
    
    return hits


def main():
    """メイン処理"""
    print("=" * 50)
    print("UMA-Logic 結果取得開始")
    print("=" * 50)
    
    today = get_japan_date()
    print(f"日付: {today.strftime('%Y-%m-%d %H:%M')} (JST)")
    
    # 予想データ読み込み
    predictions = load_predictions()
    if not predictions:
        print("予想データがありません")
        return
    
    races = predictions.get("races", [])
    if not races:
        print("レースデータがありません")
        return
    
    print(f"対象レース数: {len(races)}")
    
    # 履歴・統計読み込み
    history = load_history()
    stats = load_stats()
    
    # 今日の結果を格納
    today_results = []
    
    for race in races:
        race_id = race.get("race_id", "")
        if not race_id:
            continue
        
        print(f"結果取得中: {race.get('venue', '')} {race.get('race_num', 0)}R")
        
        result = fetch_race_result(race_id)
        
        if result:
            # 的中判定
            hits = check_hit(race, result)
            
            race_result = {
                "race_id": race_id,
                "venue": race.get("venue", ""),
                "race_num": race.get("race_num", 0),
                "race_name": race.get("race_name", ""),
                "result_1st": result.get("result_1st", {}),
                "result_2nd": result.get("result_2nd", {}),
                "result_3rd": result.get("result_3rd", {}),
                "payouts": result.get("payouts", {}),
                "hits": hits
            }
            
            today_results.append(race_result)
            
            # 統計更新
            for bet_type in ["tansho", "umaren", "umatan", "sanrenpuku", "sanrentan"]:
                stats_key = f"{bet_type}_stats"
                if stats_key not in stats:
                    stats[stats_key] = {"bets": 0, "hits": 0, "payout": 0, "investment": 0}
                
                stats[stats_key]["bets"] += 1
                stats["total_bets"] += 1
                
                # 投資額（仮に各100円とする）
                stats[stats_key]["investment"] += 100
                stats["total_investment"] += 100
                
                if hits.get(bet_type, {}).get("is_hit"):
                    stats[stats_key]["hits"] += 1
                    stats[stats_key]["payout"] += hits[bet_type].get("payout", 0)
                    stats["total_wins"] += 1
                    stats["total_payout"] += hits[bet_type].get("payout", 0)
                    print(f"  ✓ {bet_type} 的中！ {hits[bet_type].get('payout', 0)}円")
        
        time.sleep(0.5)
    
    # 履歴に追加
    today_str = today.strftime("%Y-%m-%d")
    
    # 既存の今日のデータを更新または新規追加
    existing_index = None
    for i, day in enumerate(history):
        if day.get("date") == today_str:
            existing_index = i
            break
    
    day_data = {
        "date": today_str,
        "results": today_results
    }
    
    if existing_index is not None:
        history[existing_index] = day_data
    else:
        history.append(day_data)
    
    # 保存
    save_history(history)
    save_stats(stats)
    
    # サマリー表示
    print("\n" + "=" * 50)
    print("結果サマリー")
    print("=" * 50)
    print(f"取得レース数: {len(today_results)}")
    print(f"累計的中数: {stats.get('total_wins', 0)}")
    print(f"累計配当: {stats.get('total_payout', 0):,}円")
    print(f"累計投資: {stats.get('total_investment', 0):,}円")
    
    if stats.get('total_investment', 0) > 0:
        recovery = stats['total_payout'] / stats['total_investment'] * 100
        print(f"回収率: {recovery:.1f}%")
    
    print("=" * 50)


if __name__ == "__main__":
    main()
