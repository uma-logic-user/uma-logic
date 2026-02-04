#!/usr/bin/env python3
"""予想と結果の照合・検証スクリプト（全券種対応版）"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path("data")

# 券種リスト
TICKET_TYPES = ["tansho", "fukusho", "umaren", "umatan", "wide", "sanrenpuku", "sanrentan"]

# 券種名マッピング
TICKET_NAMES = {
    "tansho": "単勝",
    "fukusho": "複勝",
    "umaren": "馬連",
    "umatan": "馬単",
    "wide": "ワイド",
    "sanrenpuku": "三連複",
    "sanrentan": "三連単"
}


def load_json(filepath: Path) -> Optional[Dict]:
    """
    JSONファイルを読み込む
    
    Args:
        filepath: JSONファイルのパス
    
    Returns:
        読み込んだデータ、失敗時はNone
    """
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
    
    Args:
        predictions: 予想データ
        results: 結果データ
    
    Returns:
        照合されたレースのリスト
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
    """
    的中判定（全券種対応）
    
    ◎○▲は horses の uma_index 降順で決定
    
    Args:
        pred: 予想データ
        result: 結果データ
    
    Returns:
        的中判定結果
    """
    
    # 予想データから馬番を取得
    horses = pred.get("horses", [])
    
    # uma_index 降順でソートして◎○▲を決定
    sorted_horses = sorted(horses, key=lambda x: x.get("uma_index", 0), reverse=True)
    
    honmei_umaban = sorted_horses[0].get("umaban", 0) if len(sorted_horses) > 0 else 0
    taikou_umaban = sorted_horses[1].get("umaban", 0) if len(sorted_horses) > 1 else 0
    tanana_umaban = sorted_horses[2].get("umaban", 0) if len(sorted_horses) > 2 else 0
    
    # 本命馬の名前を取得
    honmei_name = sorted_horses[0].get("horse_name", "") if len(sorted_horses) > 0 else ""
    
    # 結果データ
    top3 = result.get("top3", [])
    if len(top3) < 3:
        return {
            "race_id": pred.get("race_id"),
            "venue": pred.get("venue"),
            "race_num": pred.get("race_num"),
            "error": "結果データ不足"
        }
    
    first = top3[0].get("馬番", 0)
    second = top3[1].get("馬番", 0)
    third = top3[2].get("馬番", 0)
    
    payouts = result.get("payouts", {})
    
    # 各券種の的中判定と払戻
    ticket_results = {}
    
    # --- 単勝 ---
    tansho_hit = (honmei_umaban == first)
    ticket_results["tansho"] = {
        "hit": tansho_hit,
        "investment": 2000,
        "payout": payouts.get("単勝", 0) if tansho_hit else 0
    }
    
    # --- 複勝 ---
    fukusho_hit = honmei_umaban in [first, second, third]
    fukusho_payout = 0
    
    if fukusho_hit:
        fukusho_data = payouts.get("複勝", {})
        if isinstance(fukusho_data, dict):
            fukusho_payout = fukusho_data.get(str(honmei_umaban), 0)
        elif isinstance(fukusho_data, (int, float)):
            fukusho_payout = fukusho_data
    
    ticket_results["fukusho"] = {
        "hit": fukusho_hit,
        "investment": 2000,
        "payout": fukusho_payout
    }
    
    # --- 馬連 ---
    umaren_hit = {honmei_umaban, taikou_umaban} == {first, second}
    ticket_results["umaren"] = {
        "hit": umaren_hit,
        "investment": 2500,
        "payout": payouts.get("馬連", 0) if umaren_hit else 0
    }
    
    # --- 馬単 ---
    umatan_hit = (honmei_umaban == first and taikou_umaban == second)
    ticket_results["umatan"] = {
        "hit": umatan_hit,
        "investment": 1500,
        "payout": payouts.get("馬単", 0) if umatan_hit else 0
    }
    
    # --- ワイド ---
    wide_hit = {honmei_umaban, taikou_umaban}.issubset({first, second, third})
    wide_payout = 0
    
    if wide_hit:
        wide_data = payouts.get("ワイド", {})
        if isinstance(wide_data, dict):
            # ワイドの組み合わせを探す
            target_combo = {honmei_umaban, taikou_umaban}
            for combo_str, payout in wide_data.items():
                try:
                    combo_nums = set(int(x) for x in str(combo_str).split("-") if x.isdigit())
                    if combo_nums == target_combo:
                        wide_payout = payout
                        break
                except:
                    pass
        elif isinstance(wide_data, (int, float)):
            wide_payout = wide_data
    
    ticket_results["wide"] = {
        "hit": wide_hit,
        "investment": 2000,
        "payout": wide_payout
    }
    
    # --- 三連複 ---
    sanrenpuku_hit = {honmei_umaban, taikou_umaban, tanana_umaban} == {first, second, third}
    ticket_results["sanrenpuku"] = {
        "hit": sanrenpuku_hit,
        "investment": 2000,
        "payout": payouts.get("三連複", 0) if sanrenpuku_hit else 0
    }
    
    # --- 三連単 ---
    sanrentan_hit = (honmei_umaban == first and 
                     taikou_umaban == second and 
                     tanana_umaban == third)
    ticket_results["sanrentan"] = {
        "hit": sanrentan_hit,
        "investment": 2000,
        "payout": payouts.get("三連単", 0) if sanrentan_hit else 0
    }
    
    # 合計計算
    total_investment = sum(r["investment"] for r in ticket_results.values())
    total_payout = sum(r["payout"] for r in ticket_results.values())
    
    return {
        "race_id": pred.get("race_id"),
        "venue": pred.get("venue"),
        "race_num": pred.get("race_num"),
        "race_name": result.get("race_name", ""),
        "honmei_umaban": honmei_umaban,
        "honmei_name": honmei_name,
        "taikou_umaban": taikou_umaban,
        "tanana_umaban": tanana_umaban,
        "result_1st_umaban": first,
        "result_1st_name": top3[0].get("馬名", ""),
        "by_ticket": ticket_results,
        "total": {
            "investment": total_investment,
            "payout": total_payout,
            "profit": total_payout - total_investment
        }
    }


def calculate_summary(results: List[Dict]) -> Dict:
    """
    集計（券種別対応）
    
    Args:
        results: 的中判定結果のリスト
    
    Returns:
        集計結果
    """
    
    total_races = len(results)
    
    if total_races == 0:
        return {
            "total_races": 0,
            "by_ticket": {},
            "tansho": {},
            "fukusho": {},
            "total": {
                "investment": 0,
                "return": 0,
                "profit": 0,
                "recovery_rate": 0
            }
        }
    
    by_ticket = {}
    
    for ticket_type in TICKET_TYPES:
        hits = sum(1 for r in results 
                   if r.get("by_ticket", {}).get(ticket_type, {}).get("hit", False))
        
        investment = sum(r.get("by_ticket", {}).get(ticket_type, {}).get("investment", 0) 
                         for r in results)
        
        payout = sum(r.get("by_ticket", {}).get(ticket_type, {}).get("payout", 0) 
                     for r in results)
        
        profit = payout - investment
        roi = (payout / investment * 100) if investment > 0 else 0.0
        hit_rate = (hits / total_races * 100) if total_races > 0 else 0.0
        
        by_ticket[ticket_type] = {
            "hits": hits,
            "hit_rate": hit_rate,
            "investment": investment,
            "return": payout,
            "profit": profit,
            "roi": roi
        }
    
    # 合計
    total_investment = sum(r.get("total", {}).get("investment", 0) for r in results)
    total_payout = sum(r.get("total", {}).get("payout", 0) for r in results)
    total_profit = total_payout - total_investment
    total_roi = (total_payout / total_investment * 100) if total_investment > 0 else 0.0
    
    # 後方互換性のため tansho, fukusho も直接追加
    return {
        "total_races": total_races,
        "by_ticket": by_ticket,
        "tansho": by_ticket.get("tansho", {}),
        "fukusho": by_ticket.get("fukusho", {}),
        "total": {
            "investment": total_investment,
            "return": total_payout,
            "profit": total_profit,
            "recovery_rate": total_roi
        }
    }


def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("使用方法: python scripts/verify_predictions.py YYYYMMDD")
        print("例: python scripts/verify_predictions.py 20260131")
        sys.exit(1)
    
    date_str = sys.argv[1]
    
    print("=" * 70)
    print(f"🔍 予想結果の検証: {date_str}")
    print("=" * 70)
    
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
        
        if "error" in hit_result:
            print(f"⚠️ スキップ | {match['prediction'].get('venue')}{match['prediction'].get('race_num')}R | {hit_result['error']}")
            continue
        
        hit_results.append(hit_result)
        
        # 個別結果表示（単勝の的中のみ表示）
        tansho_hit = hit_result["by_ticket"]["tansho"]["hit"]
        status = "🎯 的中" if tansho_hit else "❌ 不的中"
        print(f"{status} | {hit_result['venue']}{hit_result['race_num']}R | "
              f"予想◎{hit_result['honmei_umaban']}番 → 結果1着{hit_result['result_1st_umaban']}番")
    
    if not hit_results:
        print("\n[ERROR] 検証できたレースがありません")
        sys.exit(1)
    
    # 集計
    summary = calculate_summary(hit_results)
    
    print("\n" + "=" * 70)
    print("📊 集計結果")
    print("=" * 70)
    print(f"全レース数: {summary['total_races']}レース")
    
    print(f"\n【券種別成績】")
    
    for ticket_type in TICKET_TYPES:
        data = summary['by_ticket'][ticket_type]
        name = TICKET_NAMES[ticket_type]
        
        print(f"\n  {name}:")
        print(f"    的中: {data['hits']}回 ({data['hit_rate']:.1f}%)")
        print(f"    投資: ¥{data['investment']:,}")
        print(f"    払戻: ¥{data['return']:,}")
        profit = data['profit']
        profit_sign = "+" if profit >= 0 else ""
        print(f"    損益: ¥{profit_sign}{profit:,}")
        print(f"    回収率: {data['roi']:.1f}%")
    
    print(f"\n【合計】")
    print(f"  投資額: ¥{summary['total']['investment']:,}")
    print(f"  払戻額: ¥{summary['total']['return']:,}")
    profit = summary['total']['profit']
    profit_sign = "+" if profit >= 0 else ""
    print(f"  損益: ¥{profit_sign}{profit:,}")
    print(f"  回収率: {summary['total']['recovery_rate']:.1f}%")
    print("=" * 70)
    
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
