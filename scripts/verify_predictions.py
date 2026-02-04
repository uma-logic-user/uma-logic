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


def get_horse_by_mark(horses: List[Dict], mark: str) -> int:
    """印から馬番を取得"""
    for h in horses:
        if h.get("mark") == mark:
            return h.get("umaban", 0)
    return 0


def get_horse_by_popularity(horses: List[Dict], popularity: int) -> int:
    """人気順から馬番を取得"""
    for h in horses:
        if h.get("popularity") == popularity:
            return h.get("umaban", 0)
    return 0


def check_hit(pred: Dict, result: Dict) -> Dict:
    """的中判定（全券種対応）"""
    
    # 予想データ
    honmei = pred.get("honmei", {})
    horses = pred.get("horses", [])
    bets = pred.get("bets", {})
    
    # 本命・対抗・単穴の馬番を取得
    honmei_umaban = honmei.get("umaban", 0)
    honmei_name = honmei.get("horse_name", "")
    
    # horses から印で判別（◎○▲）
    taikou_umaban = get_horse_by_mark(horses, "○")
    tanana_umaban = get_horse_by_mark(horses, "▲")
    
    # 印がない場合は人気順で代用
    if taikou_umaban == 0:
        taikou_umaban = get_horse_by_popularity(horses, 2)
    if tanana_umaban == 0:
        tanana_umaban = get_horse_by_popularity(horses, 3)
    
    # 結果
    top3 = result.get("top3", [])
    if len(top3) < 3:
        return {"error": "結果データ不足"}
    
    first = top3[0].get("馬番", 0)
    second = top3[1].get("馬番", 0)
    third = top3[2].get("馬番", 0)
    
    payouts = result.get("payouts", {})
    
    # 各券種の的中判定
    by_ticket = {}
    
    # 単勝
    tansho_hit = (honmei_umaban == first)
    by_ticket["tansho"] = {
        "hit": tansho_hit,
        "investment": 2000,
        "payout": payouts.get("単勝", 0) * 20 if tansho_hit else 0  # 100円単位→2000円換算
    }
    
    # 複勝
    fukusho_hit = honmei_umaban in [first, second, third]
    fukusho_data = payouts.get("複勝", {})
    fukusho_payout = 0
    if isinstance(fukusho_data, dict):
        fukusho_payout = fukusho_data.get(str(honmei_umaban), 0)
    elif isinstance(fukusho_data, (int, float)):
        fukusho_payout = fukusho_data if fukusho_hit else 0
    
    by_ticket["fukusho"] = {
        "hit": fukusho_hit,
        "investment": 2000,
        "payout": fukusho_payout * 20 if fukusho_hit else 0
    }
    
    # 馬連（本命-対抗）
    umaren_hit = {honmei_umaban, taikou_umaban} == {first, second}
    by_ticket["umaren"] = {
        "hit": umaren_hit,
        "investment": 2500,
        "payout": payouts.get("馬連", 0) * 25 if umaren_hit else 0
    }
    
    # 馬単（本命→対抗）
    umatan_hit = (honmei_umaban == first and taikou_umaban == second)
    by_ticket["umatan"] = {
        "hit": umatan_hit,
        "investment": 1500,
        "payout": payouts.get("馬単", 0) * 15 if umatan_hit else 0
    }
    
    # ワイド（本命-対抗）
    wide_hit = {honmei_umaban, taikou_umaban}.issubset({first, second, third})
    wide_data = payouts.get("ワイド", {})
    wide_payout = 0
    
    if isinstance(wide_data, dict) and wide_hit:
        # ワイドの組み合わせを探す
        for combo, payout in wide_data.items():
            try:
                nums = set(int(x) for x in str(combo).split("-"))
                if nums == {honmei_umaban, taikou_umaban}:
                    wide_payout = payout
                    break
            except:
                pass
    elif isinstance(wide_data, (int, float)) and wide_hit:
        wide_payout = wide_data
    
    by_ticket["wide"] = {
        "hit": wide_hit,
        "investment": 2000,
        "payout": wide_payout * 20 if wide_hit else 0
    }
    
    # 三連複（本命-対抗-単穴）
    sanrenpuku_hit = {honmei_umaban, taikou_umaban, tanana_umaban} == {first, second, third}
    by_ticket["sanrenpuku"] = {
        "hit": sanrenpuku_hit,
        "investment": 2000,
        "payout": payouts.get("三連複", 0) * 20 if sanrenpuku_hit else 0
    }
    
    # 三連単（フォーメーション）
    # bets.sanrentan_formation から投資点数を取得
    sanrentan_investment = 2000  # デフォルト
    if "sanrentan_formation" in bets:
        point_count = bets["sanrentan_formation"].get("point_count", 1)
        sanrentan_investment = 100 * point_count  # 1点100円と仮定
    
    # 三連単は的中判定が複雑（フォーメーションなので複数パターン）
    # 簡易版: 本命→対抗→単穴 の順序が完全一致
    sanrentan_hit = (honmei_umaban == first and 
                     taikou_umaban == second and 
                     tanana_umaban == third)
    
    by_ticket["sanrentan"] = {
        "hit": sanrentan_hit,
        "investment": sanrentan_investment,
        "payout": payouts.get("三連単", 0) * (sanrentan_investment // 100) if sanrentan_hit else 0
    }
    
    # 合計
    total_investment = sum(r["investment"] for r in by_ticket.values())
    total_payout = sum(r["payout"] for r in by_ticket.values())
    
    return {
        "race_id": pred.get("race_id"),
        "venue": pred.get("venue"),
        "race_num": pred.get("race_num"),
        "race_name": result.get("race_name", ""),
        "honmei_umaban": honmei_umaban,
        "honmei_name": honmei_name,
        "taikou_umaban": taikou_umaban,
        "tanana_umaban": tanana_umaban,
        "result_1st": first,
        "result_2nd": second,
        "result_3rd": third,
        "by_ticket": by_ticket,
        "total": {
            "investment": total_investment,
            "payout": total_payout,
            "profit": total_payout - total_investment
        }
    }


def calculate_summary(results: List[Dict]) -> Dict:
    """集計（券種別対応）"""
    
    if not results:
        return {}
    
    by_ticket = {}
    
    for ticket_type in TICKET_TYPES:
        hits = sum(1 for r in results if r.get("by_ticket", {}).get(ticket_type, {}).get("hit"))
        investment = sum(r.get("by_ticket", {}).get(ticket_type, {}).get("investment", 0) for r in results)
        payout = sum(r.get("by_ticket", {}).get(ticket_type, {}).get("payout", 0) for r in results)
        
        by_ticket[ticket_type] = {
            "hits": hits,
            "hit_rate": (hits / len(results) * 100) if results else 0,
            "investment": investment,
            "return": payout,
            "profit": payout - investment,
            "roi": (payout / investment * 100) if investment > 0 else 0
        }
    
    # 合計
    total_investment = sum(r.get("total", {}).get("investment", 0) for r in results)
    total_payout = sum(r.get("total", {}).get("payout", 0) for r in results)
    
    # 後方互換性のため tansho, fukusho も直接追加
    return {
        "total_races": len(results),
        "by_ticket": by_ticket,
        "tansho": by_ticket.get("tansho", {}),
        "fukusho": by_ticket.get("fukusho", {}),
        "total": {
            "investment": total_investment,
            "return": total_payout,
            "profit": total_payout - total_investment,
            "recovery_rate": (total_payout / total_investment * 100) if total_investment > 0 else 0
        }
    }


def main():
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
              f"予想◎{hit_result['honmei_umaban']}番 → 結果1着{hit_result['result_1st']}番")
    
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
        data = summary['by_ticket'].get(ticket_type, {})
        ticket_name = TICKET_NAMES.get(ticket_type, ticket_type)
        
        print(f"\n  {ticket_name}:")
        print(f"    的中: {data.get('hits', 0)}回 ({data.get('hit_rate', 0):.1f}%)")
        print(f"    投資: ¥{data.get('investment', 0):,}")
        print(f"    払戻: ¥{data.get('return', 0):,}")
        profit = data.get('profit', 0)
        profit_sign = "+" if profit >= 0 else ""
        print(f"    損益: ¥{profit_sign}{profit:,}")
        print(f"    回収率: {data.get('roi', 0):.1f}%")
    
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
