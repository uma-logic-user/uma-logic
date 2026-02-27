#!/usr/bin/env python3
import argparse
import json
import sys
import io
import re
from pathlib import Path
from datetime import datetime

# Windows文字化け対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DATA_DIR = Path("data")
HISTORY_DIR = DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

def _load_weights():
    try:
        from scripts.regenerate_predictions import load_weights
        return load_weights()
    except Exception:
        try:
            from regenerate_predictions import load_weights
            return load_weights()
        except Exception:
            return {"speed": 0.35, "adaptability": 0.35, "pedigree": 0.30}

def _process_race(race, weights):
    try:
        from scripts.regenerate_predictions import process_race
        return process_race(race, weights)
    except Exception:
        try:
            from regenerate_predictions import process_race
            return process_race(race, weights)
        except Exception:
            from scripts.calculator_pro import IntegratedCalculator, RaceCondition
            ic = IntegratedCalculator(weights)
            cond = RaceCondition(
                distance=int(race.get("distance", 1600) or 1600),
                track_type=str(race.get("track_type", "") or ""),
                track_condition=str(race.get("track_condition", "") or "")
            )
            horses_in = race.get("horses", race.get("all_results", []))
            res_list = ic.calculate_batch(horses_in, cond)
            res_list.sort(key=lambda x: (x.final_score, x.expected_value), reverse=True)
            honmei = {"umaban": res_list[0].umaban, "horse_name": res_list[0].horse_name,
                      "uma_index": round(res_list[0].final_score, 1),
                      "expected_value": round(res_list[0].expected_value, 2)} if res_list else {}
            horses_out = []
            for r in res_list:
                horses_out.append({
                    "umaban": r.umaban,
                    "horse_name": r.horse_name,
                    "jockey": r.jockey,
                    "odds": r.odds,
                    "popularity": r.popularity,
                    "uma_index": round(r.final_score, 1),
                    "win_probability": round(r.prob, 4),
                    "expected_value": round(r.expected_value, 2),
                    "mark": ""
                })
            return {
                "race_id": race.get("race_id", ""),
                "race_num": race.get("race_num", 0),
                "race_name": race.get("race_name", ""),
                "venue": race.get("venue", ""),
                "distance": race.get("distance", 0),
                "track_type": race.get("track_type", ""),
                "track_condition": race.get("track_condition", ""),
                "rank": "B",
                "honmei": honmei,
                "horses": horses_out
            }
        except Exception:
            from calculator_pro import IntegratedCalculator, RaceCondition
            ic = IntegratedCalculator(weights)
            cond = RaceCondition(
                distance=int(race.get("distance", 1600) or 1600),
                track_type=str(race.get("track_type", "") or ""),
                track_condition=str(race.get("track_condition", "") or "")
            )
            horses_in = race.get("horses", race.get("all_results", []))
            res_list = ic.calculate_batch(horses_in, cond)
            res_list.sort(key=lambda x: (x.final_score, x.expected_value), reverse=True)
            honmei = {"umaban": res_list[0].umaban, "horse_name": res_list[0].horse_name,
                      "uma_index": round(res_list[0].final_score, 1),
                      "expected_value": round(res_list[0].expected_value, 2)} if res_list else {}
            horses_out = []
            for r in res_list:
                horses_out.append({
                    "umaban": r.umaban,
                    "horse_name": r.horse_name,
                    "jockey": r.jockey,
                    "odds": r.odds,
                    "popularity": r.popularity,
                    "uma_index": round(r.final_score, 1),
                    "win_probability": round(r.prob, 4),
                    "expected_value": round(r.expected_value, 2),
                    "mark": ""
                })
            return {
                "race_id": race.get("race_id", ""),
                "race_num": race.get("race_num", 0),
                "race_name": race.get("race_name", ""),
                "venue": race.get("venue", ""),
                "distance": race.get("distance", 0),
                "track_type": race.get("track_type", ""),
                "track_condition": race.get("track_condition", ""),
                "rank": "B",
                "honmei": honmei,
                "horses": horses_out
            }

def _generate_from_results(date_str: str) -> bool:
    results_file = DATA_DIR / f"results_{date_str}.json"
    if not results_file.exists():
        return False
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            results_data = json.load(f)
    except Exception as e:
        print(f"[ERROR] 結果ファイル読込失敗: {e}")
        return False

    races = results_data.get("races", [])
    if not races:
        print(f"[WARN] レースデータなし: {date_str}")
        return False

    weights = _load_weights()
    processed = []
    try:
        from scripts.calculator_ml import MLCalculator
        mlc = MLCalculator()
    except Exception:
        try:
            from calculator_ml import MLCalculator
            mlc = MLCalculator()
        except Exception:
            mlc = None
    race_bets_map = {}
    
    def _convert_multi_bets_to_display(multi_bets: dict) -> dict:
        if not multi_bets:
            return {}
        def first_nums(label: str) -> list:
            if not label: return []
            nums = re.findall(r'\d+', str(label))
            return [n for n in nums]
        out = {}
        # 単勝
        win = (multi_bets.get("単勝") or [])
        if win:
            n = first_nums(win[0].get("label"))
            out["tansho_display"] = n[0] if n else None
        # 複勝
        plc = (multi_bets.get("複勝") or [])
        if plc:
            n = first_nums(plc[0].get("label"))
            out["fukusho_display"] = n[0] if n else None
        # 枠連
        brq = (multi_bets.get("枠連") or [])
        if brq:
            n = first_nums(brq[0].get("label"))
            if len(n) >= 2:
                out["wakuren_display"] = f"{n[0]}-{n[1]}"
        # 馬連
        qnl = (multi_bets.get("馬連") or [])
        if qnl:
            n = first_nums(qnl[0].get("label"))
            if len(n) >= 2:
                out["umaren_display"] = f"{n[0]}-{n[1]}"
        # ワイド
        wde = (multi_bets.get("ワイド") or [])
        if wde:
            n = first_nums(wde[0].get("label"))
            if len(n) >= 2:
                out["wide_display"] = f"{n[0]}-{n[1]}"
        # 馬単
        ext = (multi_bets.get("馬単") or [])
        if ext:
            n = first_nums(ext[0].get("label"))
            if len(n) >= 2:
                out["umatan_display"] = f"{n[0]}-{n[1]}"
        # 三連複
        trio = (multi_bets.get("3連複") or [])
        if trio:
            n = first_nums(trio[0].get("label"))
            if len(n) >= 3:
                out["sanrenpuku_display"] = f"{n[0]}-{n[1]}-{n[2]}"
        # 三連単
        trf = (multi_bets.get("3連単") or [])
        if trf:
            n = first_nums(trf[0].get("label"))
            if len(n) >= 3:
                out["sanrentan_display"] = f"{n[0]}-{n[1]}-{n[2]}"
        return out
    for race in races:
        try:
            pr = _process_race(race, weights)
            if pr:
                processed.append(pr)
                if mlc:
                    race_for_ml = {
                        "race_id": race.get("race_id", ""),
                        "race_num": race.get("race_num", 0),
                        "race_name": race.get("race_name", ""),
                        "venue": race.get("venue", ""),
                        "distance": race.get("distance", 1600),
                        "track_type": race.get("track_type", ""),
                        "track_condition": race.get("track_condition", ""),
                        "date": date_str,
                        "all_results": race.get("all_results", race.get("horses", [])),
                    }
                    sorted_h, recs = mlc.predict_race(race_for_ml)
                    multi_bets = sorted_h[0].get("multi_bets", {}) if sorted_h else {}
                    display_bets = _convert_multi_bets_to_display(multi_bets)
                    race_bets_map[race.get("race_id", "")] = display_bets
        except Exception as e:
            print(f"  [WARN] レース処理失敗: {e}")
            continue

    if not processed:
        print(f"[WARN] 生成できた予想がありません: {date_str}")
        return False

    out = {
        "date": date_str,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test_mode": True,
        "source": "results",
        "races": processed,
    }
    for r in out["races"]:
        rid = r.get("race_id", "")
        if rid in race_bets_map:
            r["bets"] = race_bets_map[rid]
    outfile = HISTORY_DIR / f"predictions_{date_str}.json"
    try:
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"✅ 生成: {outfile} ({len(processed)}レース)")
        return True
    except Exception as e:
        print(f"[ERROR] 保存失敗: {e}")
        return False

def _generate_from_future(date_str: str) -> bool:
    try:
        from scripts.fetch_future_races import fetch_future_predictions
    except Exception as e:
        try:
            from fetch_future_races import fetch_future_predictions
        except Exception as e2:
            print(f"[ERROR] 未来レース取得モジュールの読み込み失敗: {e} / {e2}")
            return False

    ok = fetch_future_predictions(date_str)
    if not ok:
        return False

    # fetch_future_predictions は HISTORY_DIR/predictions_YYYYMMDD.json（未計算）を保存する
    skeleton_file = HISTORY_DIR / f"predictions_{date_str}.json"
    if not skeleton_file.exists():
        print(f"[ERROR] 取得後ファイルが見つかりません: {skeleton_file}")
        return False

    try:
        with open(skeleton_file, "r", encoding="utf-8") as f:
            skeleton = json.load(f)
    except Exception as e:
        print(f"[ERROR] 取得ファイル読込失敗: {e}")
        return False

    races = skeleton.get("races", [])
    if not races:
        print(f"[WARN] レースデータなし（未公開の可能性）: {date_str}")
        return False

    weights = _load_weights()
    processed = []
    try:
        from scripts.calculator_ml import MLCalculator
        mlc = MLCalculator()
    except Exception:
        try:
            from calculator_ml import MLCalculator
            mlc = MLCalculator()
        except Exception:
            mlc = None
    race_bets_map = {}
    for race in races:
        try:
            pr = _process_race(race, weights)
            if pr:
                processed.append(pr)
                if mlc:
                    race_for_ml = {
                        "race_id": race.get("race_id", ""),
                        "race_num": race.get("race_num", 0),
                        "race_name": race.get("race_name", ""),
                        "venue": race.get("venue", ""),
                        "distance": race.get("distance", 1600),
                        "track_type": race.get("track_type", ""),
                        "track_condition": race.get("track_condition", ""),
                        "date": date_str,
                        "all_results": race.get("horses", []),
                    }
                    sorted_h, recs = mlc.predict_race(race_for_ml)
                    multi_bets = sorted_h[0].get("multi_bets", {}) if sorted_h else {}
                    display_bets = _convert_multi_bets_to_display(multi_bets)
                    race_bets_map[race.get("race_id", "")] = display_bets
        except Exception as e:
            print(f"  [WARN] レース処理失敗: {e}")
            continue

    if not processed:
        print(f"[WARN] 生成できた予想がありません: {date_str}")
        return False

    out = {
        "date": date_str,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test_mode": True,
        "source": "future_entries",
        "races": processed,
    }
    for r in out["races"]:
        rid = r.get("race_id", "")
        if rid in race_bets_map:
            r["bets"] = race_bets_map[rid]
    outfile = HISTORY_DIR / f"predictions_{date_str}.json"
    try:
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"✅ 生成: {outfile} ({len(processed)}レース)")
        return True
    except Exception as e:
        print(f"[ERROR] 保存失敗: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="指定日付の予想JSONを安全に生成（HISTORYディレクトリ）")
    parser.add_argument("--date", required=True, help="YYYYMMDD 形式の日付（例: 20260228）")
    args = parser.parse_args()
    date_str = args.date
    if not (len(date_str) == 8 and date_str.isdigit()):
        print("[ERROR] --date は YYYYMMDD 形式で指定してください")
        sys.exit(1)

    # 1) 過去日付等で results がある場合は結果から生成
    if _generate_from_results(date_str):
        sys.exit(0)

    # 2) 未来日付など results が無い場合は出馬表を取得して生成
    if _generate_from_future(date_str):
        sys.exit(0)

    print("[ERROR] 予想生成に失敗しました（結果も出馬表も取得不可）")
    sys.exit(2)

if __name__ == "__main__":
    main()
