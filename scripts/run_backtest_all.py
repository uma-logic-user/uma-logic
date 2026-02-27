#!/usr/bin/env python3
"""全期間のバックテストを実行"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

DATA_DIR = Path("data")


def find_prediction_files() -> List[str]:
    """
    predictions_YYYYMMDD.json ファイルを全て取得
    
    Returns:
        日付文字列のリスト（YYYYMMDD形式）
    """
    files = sorted(DATA_DIR.glob("predictions_*.json"))
    dates = []
    
    for f in files:
        date_str = f.stem.replace("predictions_", "")
        if len(date_str) == 8 and date_str.isdigit():
            # 対応する results ファイルが存在するか確認
            results_file = DATA_DIR / f"results_{date_str}.json"
            if results_file.exists():
                dates.append(date_str)
    
    return dates


def run_verification(date_str: str) -> Optional[Dict]:
    """
    指定日の検証を実行
    
    Args:
        date_str: 日付文字列（YYYYMMDD形式）
    
    Returns:
        検証結果の辞書、失敗時はNone
    """
    try:
        result = subprocess.run(
            ["python", "scripts/verify_predictions.py", date_str],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # verification_YYYYMMDD.json を読み込む
        verify_file = DATA_DIR / f"verification_{date_str}.json"
        if verify_file.exists():
            with open(verify_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None
        
    except subprocess.TimeoutExpired:
        print(f"[ERROR] {date_str} の検証がタイムアウト")
        return None
    except Exception as e:
        print(f"[ERROR] {date_str} の検証失敗: {e}")
        return None


def aggregate_results(all_results: List[Dict]) -> Dict:
    """
    全期間の結果を集計
    
    Args:
        all_results: 各日の検証結果リスト
    
    Returns:
        集計結果の辞書
    """
    if not all_results:
        return {}
    
    total_races = sum(r["summary"]["total_races"] for r in all_results)
    
    # 単勝集計
    tansho_hits = sum(r["summary"]["tansho"]["hits"] for r in all_results)
    tansho_investment = sum(r["summary"]["tansho"]["investment"] for r in all_results)
    tansho_return = sum(r["summary"]["tansho"]["return"] for r in all_results)
    
    # 複勝集計
    fukusho_hits = sum(r["summary"]["fukusho"]["hits"] for r in all_results)
    fukusho_return = sum(r["summary"]["fukusho"]["return"] for r in all_results)
    
    # 合計
    total_investment = sum(r["summary"]["total"]["investment"] for r in all_results)
    total_return = sum(r["summary"]["total"]["return"] for r in all_results)
    total_profit = total_return - total_investment
    
    # 月次集計
    monthly = {}
    for result in all_results:
        date_str = result["date"]
        year_month = f"{date_str[:4]}-{date_str[4:6]}"
        
        if year_month not in monthly:
            monthly[year_month] = {
                "races": 0,
                "investment": 0,
                "return": 0,
                "profit": 0
            }
        
        monthly[year_month]["races"] += result["summary"]["total_races"]
        monthly[year_month]["investment"] += result["summary"]["total"]["investment"]
        monthly[year_month]["return"] += result["summary"]["total"]["return"]
        monthly[year_month]["profit"] += result["summary"]["total"]["profit"]
    
    # 月次回収率計算
    for ym in monthly:
        if monthly[ym]["investment"] > 0:
            monthly[ym]["roi"] = monthly[ym]["return"] / monthly[ym]["investment"] * 100
        else:
            monthly[ym]["roi"] = 0.0
    
    # 日次詳細（ドローダウン計算用）
    daily_pnl = []
    cumulative = 0
    for result in all_results:
        profit = result["summary"]["total"]["profit"]
        cumulative += profit
        daily_pnl.append({
            "date": result["date"],
            "profit": profit,
            "cumulative": cumulative
        })
    
    # 最大ドローダウン計算
    peak = 0
    max_drawdown = 0
    max_drawdown_date = ""
    
    for day in daily_pnl:
        if day["cumulative"] > peak:
            peak = day["cumulative"]
        drawdown = peak - day["cumulative"]
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            max_drawdown_date = day["date"]
    
    # 連敗計算
    current_streak = 0
    max_losing_streak = 0
    
    for result in all_results:
        if result["summary"]["total"]["profit"] < 0:
            current_streak += 1
            max_losing_streak = max(max_losing_streak, current_streak)
        else:
            current_streak = 0
    
    return {
        "period": {
            "start": all_results[0]["date"] if all_results else "",
            "end": all_results[-1]["date"] if all_results else "",
            "days": len(all_results)
        },
        "total": {
            "races": total_races,
            "investment": total_investment,
            "return": total_return,
            "profit": total_profit,
            "roi": (total_return / total_investment * 100) if total_investment > 0 else 0
        },
        "tansho": {
            "hits": tansho_hits,
            "hit_rate": (tansho_hits / total_races * 100) if total_races > 0 else 0,
            "investment": tansho_investment,
            "return": tansho_return,
            "roi": (tansho_return / tansho_investment * 100) if tansho_investment > 0 else 0
        },
        "fukusho": {
            "hits": fukusho_hits,
            "hit_rate": (fukusho_hits / total_races * 100) if total_races > 0 else 0,
            "return": fukusho_return
        },
        "risk": {
            "max_drawdown": max_drawdown,
            "max_drawdown_date": max_drawdown_date,
            "max_losing_streak_days": max_losing_streak
        },
        "monthly": monthly,
        "daily_pnl": daily_pnl
    }


def main():
    """メイン処理"""
    print("=" * 80)
    print("📊 UMA-Logic 全期間バックテスト")
    print("=" * 80)
    
    # 全日付取得
    dates = find_prediction_files()
    
    if not dates:
        print("[ERROR] predictions ファイルが見つかりません")
        print("[INFO] data/ ディレクトリに predictions_YYYYMMDD.json と")
        print("       results_YYYYMMDD.json の両方が必要です")
        return
    
    print(f"\n[INFO] {len(dates)}日分のデータを発見")
    print(f"[INFO] 期間: {dates[0]} ～ {dates[-1]}")
    print()
    
    # 各日付の検証実行
    all_results = []
    success_count = 0
    skip_count = 0
    
    for i, date_str in enumerate(dates, 1):
        print(f"[{i}/{len(dates)}] {date_str} を検証中...", end=" ")
        
        result = run_verification(date_str)
        
        if result:
            all_results.append(result)
            races = result["summary"]["total_races"]
            roi = result["summary"]["total"]["recovery_rate"]
            print(f"✓ ({races}R, 回収率{roi:.1f}%)")
            success_count += 1
        else:
            print("✗ スキップ")
            skip_count += 1
    
    if not all_results:
        print("\n[ERROR] 検証できたデータがありません")
        return
    
    # 集計
    print("\n" + "=" * 80)
    print("📈 バックテスト結果")
    print("=" * 80)
    
    summary = aggregate_results(all_results)
    
    print(f"\n【期間】")
    print(f"  開始: {summary['period']['start']}")
    print(f"  終了: {summary['period']['end']}")
    print(f"  日数: {summary['period']['days']}日（成功: {success_count}, スキップ: {skip_count}）")
    
    print(f"\n【全体成績】")
    print(f"  総レース数: {summary['total']['races']:,}レース")
    print(f"  投資総額: ¥{summary['total']['investment']:,}")
    print(f"  払戻総額: ¥{summary['total']['return']:,}")
    profit_sign = "+" if summary['total']['profit'] >= 0 else ""
    print(f"  損益: ¥{profit_sign}{summary['total']['profit']:,}")
    print(f"  回収率: {summary['total']['roi']:.1f}%")
    
    print(f"\n【単勝】")
    print(f"  的中数: {summary['tansho']['hits']:,}レース")
    print(f"  的中率: {summary['tansho']['hit_rate']:.1f}%")
    print(f"  投資額: ¥{summary['tansho']['investment']:,}")
    print(f"  払戻額: ¥{summary['tansho']['return']:,}")
    print(f"  回収率: {summary['tansho']['roi']:.1f}%")
    
    print(f"\n【複勝】")
    print(f"  的中数: {summary['fukusho']['hits']:,}レース")
    print(f"  的中率: {summary['fukusho']['hit_rate']:.1f}%")
    print(f"  払戻額: ¥{summary['fukusho']['return']:,}")
    
    print(f"\n【リスク指標】")
    print(f"  最大ドローダウン: ¥{summary['risk']['max_drawdown']:,}")
    print(f"  最大ドローダウン発生日: {summary['risk']['max_drawdown_date']}")
    print(f"  最大連敗日数: {summary['risk']['max_losing_streak_days']}日")
    
    print(f"\n【月次推移】")
    for ym in sorted(summary['monthly'].keys()):
        m = summary['monthly'][ym]
        profit_sign = "+" if m['profit'] >= 0 else ""
        print(f"  {ym}: {m['races']:3d}R | "
              f"投資¥{m['investment']:7,} | "
              f"回収¥{m['return']:7,} | "
              f"損益¥{profit_sign}{m['profit']:7,} | "
              f"回収率{m['roi']:6.1f}%")
    
    print("=" * 80)
    
    # 保存
    output_file = DATA_DIR / "backtest_summary.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 詳細結果を保存: {output_file}")
    
    # 評価コメント
    print("\n" + "=" * 80)
    print("📝 評価")
    print("=" * 80)
    
    roi = summary['total']['roi']
    hit_rate = summary['tansho']['hit_rate']
    
    if roi >= 100:
        print(f"  回収率 {roi:.1f}% → ✅ 収支プラス")
    else:
        print(f"  回収率 {roi:.1f}% → ❌ 収支マイナス")
    
    if hit_rate >= 20:
        print(f"  的中率 {hit_rate:.1f}% → ✅ 平均以上（単勝平均約20%）")
    else:
        print(f"  的中率 {hit_rate:.1f}% → ❌ 平均以下")
    
    if summary['risk']['max_losing_streak_days'] <= 5:
        print(f"  最大連敗 {summary['risk']['max_losing_streak_days']}日 → ✅ 許容範囲")
    else:
        print(f"  最大連敗 {summary['risk']['max_losing_streak_days']}日 → ⚠️ 要注意")


if __name__ == "__main__":
    main()
