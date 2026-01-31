#!/usr/bin/env python3
"""
UMA-Logic データ取得スクリプト（商用グレード完全版）
回収率重視・実データ取得・全券種対応
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 強化版モジュールのインポート
sys.path.append(str(Path(__file__).parent))
from scraper_enhanced import EnhancedNetkeibaScraper
from calculator_enhanced import RecoveryFocusedCalculator
from betting_strategy import RecoveryBettingStrategy

# JST タイムゾーン
JST = timezone(timedelta(hours=9))

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
HISTORY_FILE = DATA_DIR / "history.json"
WIN5_FILE = DATA_DIR / "win5_strategies.json"


def get_jst_date():
    """現在のJST日付を YYYY-MM-DD 形式で取得"""
    return datetime.now(JST).strftime("%Y-%m-%d")


def get_day_of_week():
    """曜日を取得（土/日）"""
    weekday = datetime.now(JST).weekday()
    return "土" if weekday == 5 else "日" if weekday == 6 else "平日"


def get_week_key():
    """週キー（例: 2026-W05）を取得"""
    return datetime.now(JST).strftime("%Y-W%W")


def load_history():
    """history.json を読み込み"""
    if not HISTORY_FILE.exists():
        return []
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []


def save_history(history_data):
    """history.json に保存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ {len(history_data)}件のレース情報を保存")


def merge_race_data(existing_history, new_races):
    """既存履歴に新規レースをマージ（重複排除）"""
    history_dict = {race["race_id"]: race for race in existing_history}
    
    for race in new_races:
        race_id = race["race_id"]
        if race_id in history_dict:
            print(f"🔄 更新: {race['venue']} R{race['race_num']}")
        else:
            print(f"➕ 新規: {race['venue']} R{race['race_num']}")
        
        history_dict[race_id] = race
    
    # 日付降順でソート
    merged_list = sorted(
        history_dict.values(),
        key=lambda x: (x.get("date", "9999-99-99"), x.get("race_id", "")),
        reverse=True
    )
    
    return merged_list


def assign_marks(horses):
    """
    UMA指数順に推奨マークを付与: ◎○▲△△
    """
    marks = ["◎", "○", "▲", "△", "△"]
    sorted_horses = sorted(horses, key=lambda h: h.get("uma_index", 0), reverse=True)
    
    for i, horse in enumerate(sorted_horses[:5]):
        horse["mark"] = marks[i]
    
    return horses


def generate_win5_strategies(today_races):
    """WIN5戦略を生成（日曜のみ・対象5レース）"""
    if get_day_of_week() != "日" or len(today_races) < 5:
        return None
    
    # レース番号の大きい5レースを抽出
    sorted_races = sorted(today_races, key=lambda r: r.get("race_num", 0), reverse=True)
    win5_races = sorted_races[:5]
    
    strategies = {
        "堅実型": {"selections": [], "cost": 0, "description": "本命◎のみ1点買い（的中重視）"},
        "バランス型": {"selections": [], "cost": 0, "description": "◎○の2頭流し（中間戦略）"},
        "波乱型": {"selections": [], "cost": 0, "description": "◎○+穴馬1頭の3頭流し（高配当狙い）"}
    }
    
    for race in win5_races:
        horses = sorted(race.get("horses", []), key=lambda h: h.get("uma_index", 0), reverse=True)
        
        if len(horses) >= 3:
            strategies["堅実型"]["selections"].append([horses[0]["umaban"]])
            strategies["バランス型"]["selections"].append([horses[0]["umaban"], horses[1]["umaban"]])
            
            # 波乱型: ◎○+期待値の高い穴馬
            穴馬 = horses[4]["umaban"] if len(horses) >= 5 else horses[3]["umaban"]
            strategies["波乱型"]["selections"].append([horses[0]["umaban"], horses[1]["umaban"], 穴馬])
    
    # 購入金額を計算
    strategies["堅実型"]["cost"] = 100
    strategies["バランス型"]["cost"] = 32 * 100
    strategies["波乱型"]["cost"] = 243 * 100
    
    strategies["target_races"] = [r["race_num"] for r in win5_races]
    
    return strategies


def save_win5_strategies(strategies):
    """WIN5戦略を保存"""
    if not strategies:
        return
    
    win5_data = {
        "date": get_jst_date(),
        "day_of_week": get_day_of_week(),
        **strategies
    }
    
    with open(WIN5_FILE, "w", encoding="utf-8") as f:
        json.dump(win5_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ WIN5戦略を保存（対象: {strategies['target_races']}R）")


def main():
    """メイン処理"""
    print("=" * 70)
    print("🏇 UMA-Logic データ取得開始（商用グレード完全版）")
    print("=" * 70)
    
    current_date = get_jst_date()
    day_of_week = get_day_of_week()
    week_key = get_week_key()
    
    print(f"📅 実行日時: {current_date} ({day_of_week})")
    print(f"📌 週キー: {week_key}")
    
    # 土日のみ実行
    if day_of_week == "平日":
        print("⚠️ 平日は実行をスキップします")
        return
    
    # 強化版スクレイパー初期化
    scraper = EnhancedNetkeibaScraper()
    calculator = RecoveryFocusedCalculator()
    strategy = RecoveryBettingStrategy()
    
    # 既存履歴を読み込み
    existing_history = load_history()
    print(f"📚 既存レース数: {len(existing_history)}件")
    
    # 本日のレース一覧を取得
    print("\n🔍 本日のレース一覧を取得中...")
    race_list = scraper.get_today_race_list()
    
    if not race_list:
        print("⚠️ 本日のレースが見つかりません（ダミーデータで代用）")
        # ダミーデータ
        race_list = [
            {"race_id": f"2026{current_date.replace('-', '')[4:]}0811", "venue": "中山", "race_num": 11},
            {"race_id": f"2026{current_date.replace('-', '')[4:]}0810", "venue": "中山", "race_num": 10},
            {"race_id": f"2026{current_date.replace('-', '')[4:]}1211", "venue": "阪神", "race_num": 11},
        ]
    
    print(f"✅ {len(race_list)}レース発見")
    
    # 各レースの詳細を取得
    new_races = []
    
    for i, race_info in enumerate(race_list, 1):
        print(f"\n[{i}/{len(race_list)}] {race_info['venue']} R{race_info['race_num']} を処理中...")
        
        try:
            # レース詳細取得（強化版）
            race_detail = scraper.get_race_detail(race_info["race_id"])
            
            if not race_detail:
                print(f"  ⚠️ 詳細取得失敗（スキップ）")
                continue
            
            print(f"  📋 {race_detail['race_name']} ({race_detail['surface']}{race_detail['distance']})")
            
            # UMA指数を全馬に計算
            horses_with_index = []
            
            for horse in race_detail.get("horses", []):
                print(f"    🐎 {horse['umaban']}番 {horse['horse_name']} 分析中...", end="")
                
                uma_result = calculator.calculate(horse, race_detail, race_detail.get("horses", []))
                
                horse["uma_index"] = uma_result["uma_index"]
                horse["rank"] = uma_result["rank"]
                horse["confidence"] = uma_result["confidence"]
                horse["expected_value"] = uma_result["expected_value"]
                horse["uma_breakdown"] = uma_result["breakdown"]
                horse["reasons"] = uma_result["reasons"]
                horse["mark"] = ""  # 後で付与
                
                horses_with_index.append(horse)
                
                print(f" 指数{uma_result['uma_index']} (期待値{uma_result['expected_value']})")
            
            # マーク付与
            horses_with_index = assign_marks(horses_with_index)
            
            # 買い目生成（強化版）
            bets = strategy.generate_bets(horses_with_index, race_detail)
            
            # 本命馬
            honmei = max(horses_with_index, key=lambda h: h.get("uma_index", 0))
            
            # 資金配分（デフォルト5000円・回収率重視）
            budget_allocation = strategy.allocate_budget(bets, total_budget=5000, style="回収率重視")
            
            # レースデータを構築
            race_data = {
                "race_id": race_info["race_id"],
                "date": current_date,
                "day_of_week": day_of_week,
                "week_key": week_key,
                "venue": race_info["venue"],
                "race_num": race_info["race_num"],
                "race_name": race_detail.get("race_name", f"第{race_info['race_num']}レース"),
                "distance": race_detail.get("distance", "不明"),
                "surface": race_detail.get("surface", "不明"),
                "weather": race_detail.get("weather", "晴"),
                "track_condition": race_detail.get("track_condition", "良"),
                "grade": race_detail.get("grade", "一般"),
                "horses": horses_with_index,
                "honmei": {
                    "umaban": honmei["umaban"],
                    "horse_name": honmei["horse_name"],
                    "uma_index": honmei["uma_index"],
                    "rank": honmei["rank"],
                    "confidence": honmei["confidence"],
                    "expected_value": honmei["expected_value"]
                },
                "bets": bets,
                "budget_allocation": {
                    "style": "回収率重視",
                    "total_budget": 5000,
                    "breakdown": budget_allocation
                },
                "result": None  # 結果更新時に埋める
            }
            
            new_races.append(race_data)
            
            print(f"  ✅ 完了 - 本命: ◎{honmei['umaban']} {honmei['horse_name']} (指数{honmei['uma_index']} / 期待値{honmei['expected_value']})")
            
            time.sleep(2)  # サーバー負荷軽減
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # マージして保存
    if new_races:
        merged_history = merge_race_data(existing_history, new_races)
        save_history(merged_history)
        
        # WIN5戦略生成（日曜のみ）
        win5_strategies = generate_win5_strategies(new_races)
        if win5_strategies:
            save_win5_strategies(win5_strategies)
        
        print("\n" + "=" * 70)
        print(f"✅ 完了！合計 {len(merged_history)}件のレース履歴")
        print("=" * 70)
    else:
        print("\n⚠️ 新規レースがありませんでした")


if __name__ == "__main__":
    main()
