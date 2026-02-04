#!/usr/bin/env python3
"""予想と結果の照合・検証スクリプト（簡易版）"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path("data")


def load_json(filepath: Path) -> Optional[Dict]:
    """JSONファイルを読み込む"""
    if not filepath.exists():
        print(f"[ERROR] ファイルが見つかりません: {filepath}")
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 読み込みエラー: {e}")
        return None


def match_races(predictions: Dict, results: Dict) -> List[Dict]:
    """
    predictions と results のレースを照合する。
    
    優先順位:
    1. race_id で完全一致
    2. venue + race_num で照合
    """
    pred_races = predictions.get("races", [])
    result_races = results.get("races", [])
    
    matched = []
    
    for pred in pred_races:
        pred_race_id = pred.get("race_id")
        pred_venue = pred.get("venue", "")
        pred_num = pred.get("race_num", 0)
        
        # 1. race_id で完全一致を探す
        result = next(
            (r for r in result_races if r.get("race_id") == pred_race_id),
            None
        )
        
        # 2. venue + race_num で照合
        if not result and pred_venue and pred_num:
            result = next(
                (r for r in result_races 
                 if r.get("venue") == pred_venue and r.get("race_num") == pred_num),
                None
            )
        
        if result:
            matched.append({
                "prediction": pred,
                "result": result
            })
    
    return matched


def check_hit(pred: Dict, result: Dict) -> Dict:
    """的中判定"""
    
    # 予想の本命馬
    honmei = pred.get("honmei", {})
    honmei_umaban = honmei.get("umaban", 0)
    honmei_name = honmei.get("horse_name", "")
    
    # 実際の結果（上位3頭）
    top3 = result.get("top3", [])
    if len(top3) < 3:
        return {
            "tansho_hit": False,
            "fukusho_hit": False,
            "error": "結果データ不足"
        }
    
    first = top3[0]
    second = top3[1]
    third = top3[2]
    
    first_umaban = first.get("馬番", 0)
    second_umaban = second.get("馬番", 0)
    third_umaban = third.get("馬番", 0)
    
    # 的中判定
    tansho_hit = (honmei_umaban == first_umaban)
    fukusho_hit = honmei_umaban in [first_umaban, second_umaban, third_umaban]
    
    # 払戻金取得
    payouts = result.get("payouts", {})
    tansho_payout = payouts.get("単勝", 0)
    fukusho_payout = 0
    
    # 複勝の払戻（複数ある場合）
    fukusho_data = payouts.get("複勝", {})
    if isinstance(fukusho_data, dict):
        fukusho_payout = fukusho_data.get(str(honmei_umaban), 0)
    elif isinstance(fukusho_data, int):
        fukusho_payout = fukusho_data if fukusho_hit else 0
    
    return {
        "race_id": pred.get("race_id"),
        "venue": pred.get("venue"),
        "race_num": pred.get("race_num"),
        "race_name": result.get("race_name", ""),
        "honmei_umaban": honmei_umaban,
        "honmei_name": honmei_name,
        "honmei_odds": honmei.get("odds", 0),
        "result_1st_umaban": first_umaban,
        "result_1st_name": first.get("馬名", ""),
        "result_1st_odds": first.get("オッズ", 0),
        "tansho_hit": tansho_hit,
        "tansho_payout": tansho_payout if tansho_hit else 0,
        "fukusho_hit": fukusho_hit,
        "fukusho_payout": fukusho_payout if fukusho_hit else 0,
    }


def calculate_summary(results: List[Dict]) -> Dict:
    """集計"""
    total_races = len(results)
    tansho_hits = sum(1 for r in results if r.get("tansho_hit"))
    fukusho_hits = sum(1 for r in results if r.get("fukusho_hit"))
    
    # 投資額（単勝2000円と仮定）
    investment_per_race = 2000
    total_investment = total_races * investment_per_race
    
    # 回収額
    tansho_return = sum(r.get("tansho_payout", 0) for r in results)
    fukusho_return = sum(r.get("fukusho_payout", 0) for r in results)
    total_return = tansho_return + fukusho_return
    
    # 回収率
    recovery_rate = (total_return / total_investment * 100) if total_investment > 0 else 0
    
    return {
        "total_races": total_races,
        "tansho": {
            "hits": tansho_hits,
            "hit_rate": (tansho_hits / total_races * 100) if total_races > 0 else 0,
            "investment": total_investment,
            "return": tansho_return,
            "roi": (tansho_return / total_investment * 100) if total_investment > 0 else 0
        },
        "fukusho": {
            "hits": fukusho_hits,
            "hit_rate": (fukusho_hits / total_races * 100) if total_races > 0 else 0,
            "return": fukusho_return
        },
        "total": {
            "investment": total_investment,
            "return": total_return,
            "profit": total_return - total_investment,
            "recovery_rate": recovery_rate
        }
    }


def main():
    if len(sys.argv) < 2:
        print("使用方法: python scripts/verify_predictions.py YYYYMMDD")
        print("例: python scripts/verify_predictions.py 20260131")
        sys.exit(1)
    
    date_str = sys.argv[1]
    
    print("=" * 60)
    print(f"🔍 予想結果の検証: {date_str}")
    print("=" * 60)
    
    # ファイル読み込み
    pred_path = DATA_DIR / f"predictions_{date_str}.json"
    result_path = DATA_DIR / f"results_{date_str}.json"
    
    predictions = load_json(pred_path)
    results = load_json(result_path)
    
    if not predictions or not results:
        print("[ERROR] データファイルが見つかりません")
        sys.exit(1)
    
    # レース照合
    matched = match_races(predictions, results)
    
    if not matched:
        print("[ERROR] 照合できるレースが見つかりませんでした")
        print(f"  predictions: {len(predictions.get('races', []))}レース")
        print(f"  results: {len(results.get('races', []))}レース")
        sys.exit(1)
    
    print(f"[INFO] {len(matched)}レースを照合しました\n")
    
    # 的中判定
    hit_results = []
    for match in matched:
        hit_result = check_hit(match["prediction"], match["result"])
        hit_results.append(hit_result)
        
        # 個別結果表示
        status = "🎯 的中" if hit_result["tansho_hit"] else "❌ 不的中"
        print(f"{status} | {hit_result['venue']}{hit_result['race_num']}R | "
              f"予想◎{hit_result['honmei_umaban']}番 → 結果1着{hit_result['result_1st_umaban']}番")
    
    # 集計
    summary = calculate_summary(hit_results)
    
    print("\n" + "=" * 60)
    print("📊 集計結果")
    print("=" * 60)
    print(f"全レース数: {summary['total_races']}レース")
    print(f"\n【単勝】")
    print(f"  的中数: {summary['tansho']['hits']}レース")
    print(f"  的中率: {summary['tansho']['hit_rate']:.1f}%")
    print(f"  投資額: ¥{summary['tansho']['investment']:,}")
    print(f"  払戻額: ¥{summary['tansho']['return']:,}")
    print(f"  回収率: {summary['tansho']['roi']:.1f}%")
    print(f"\n【複勝】")
    print(f"  的中数: {summary['fukusho']['hits']}レース")
    print(f"  的中率: {summary['fukusho']['hit_rate']:.1f}%")
    print(f"  払戻額: ¥{summary['fukusho']['return']:,}")
    print(f"\n【合計】")
    print(f"  投資額: ¥{summary['total']['investment']:,}")
    print(f"  払戻額: ¥{summary['total']['return']:,}")
    print(f"  損益: ¥{summary['total']['profit']:,}")
    print(f"  回収率: {summary['total']['recovery_rate']:.1f}%")
    print("=" * 60)
    
    # 保存
    output = {
        "date": date_str,
        "summary": summary,
        "details": hit_results
    }
    
    output_path = DATA_DIR / f"verification_{date_str}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 詳細結果を保存しました: {output_path}")


if __name__ == "__main__":
    main()
