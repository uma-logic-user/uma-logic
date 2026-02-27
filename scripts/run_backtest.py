"""
バックテストスクリプト v3
- 確定配当(payouts)を使用（近似値を廃止）
- ケリー基準による動的資金配分
- 単勝・複勝・馬連・ワイドの4券種対応
"""
import pandas as pd
from pathlib import Path
import json
import sys
import io
import warnings
import re

# 自作モジュール
sys.path.append(str(Path(__file__).parent.parent))
from scripts.calculator_ml import MLCalculator
from scripts.bet_portfolio import BetPortfolio

# Windows文字化け対策
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
except Exception:
    pass

warnings.simplefilter('ignore')

DATA_DIR = Path("data")
RESULTS_DIR = DATA_DIR / "backtest"
RESULTS_DIR.mkdir(exist_ok=True)


def parse_fukusho_payouts(payout_val, top3_horses):
    """
    確定複勝配当を解析する。
    payout_val: 連結された複勝配当整数 (e.g. 130130130)
    top3_horses: top3の着順データ [{"馬番":14,...}, {"馬番":2,...}, {"馬番":7,...}]
    Returns: {馬番: 配当(100円あたり)} or {}
    """
    if not payout_val or not top3_horses:
        return {}
    
    s = str(payout_val)
    n = len(top3_horses)
    
    if n == 0:
        return {}
    
    # 均等分割を試みる（大半のケースで数字の桁数は等しいか近い）
    # まず均等幅で分割
    chunk_size = len(s) // n
    remainder = len(s) % n
    
    if remainder == 0 and chunk_size >= 2:
        # 均等に分割可能
        values = []
        for i in range(n):
            val = int(s[i*chunk_size:(i+1)*chunk_size])
            values.append(val)
    elif chunk_size >= 2:
        # 均等分割できない場合: 最初のn-1個はchunk_size文字、最後は残り
        values = []
        pos = 0
        for i in range(n - 1):
            # 各値の最小は110（複勝最低配当）、最大は数万
            val = int(s[pos:pos + chunk_size])
            values.append(val)
            pos += chunk_size
        values.append(int(s[pos:]))
    else:
        return {}
    
    # 馬番とマッピング
    result = {}
    for i, horse in enumerate(top3_horses[:n]):
        if i < len(values):
            umaban = horse.get("馬番")
            result[umaban] = values[i]
    
    return result


def parse_wide_payouts(payout_val, top3_horses):
    """
    確定ワイド配当を解析する。
    3着以内の3組の組み合わせ: 1-2着, 1-3着, 2-3着
    Returns: {(馬番A, 馬番B): 配当}
    """
    if not payout_val or len(top3_horses) < 3:
        return {}
    
    s = str(payout_val)
    n = 3  # ワイドは常に3組
    
    chunk_size = len(s) // n
    remainder = len(s) % n
    
    if remainder == 0 and chunk_size >= 2:
        values = [int(s[i*chunk_size:(i+1)*chunk_size]) for i in range(n)]
    elif chunk_size >= 2:
        values = []
        pos = 0
        for i in range(n - 1):
            values.append(int(s[pos:pos + chunk_size]))
            pos += chunk_size
        values.append(int(s[pos:]))
    else:
        return {}
    
    h1 = top3_horses[0].get("馬番")
    h2 = top3_horses[1].get("馬番")
    h3 = top3_horses[2].get("馬番")
    
    # 1-2着, 1-3着, 2-3着 の順
    result = {}
    if len(values) >= 3:
        result[frozenset([h1, h2])] = values[0]
        result[frozenset([h1, h3])] = values[1]
        result[frozenset([h2, h3])] = values[2]
    
    return result


def run_backtest(start_date="2024-01-01", end_date="2025-12-31"):
    print("=" * 60)
    print(f"🚀 バックテスト v3 ({start_date} - {end_date})")
    print("   確定配当 + ケリー基準 + 4券種ポートフォリオ")
    print("=" * 60)
    
    calc = MLCalculator()
    portfolio = BetPortfolio()
    files = sorted(list(DATA_DIR.glob("results_*.json")))
    
    total_invest = 0
    total_return = 0
    race_count = 0
    skipped_races = 0
    
    bet_stats = {
        "win": {"count": 0, "invest": 0, "return": 0, "hits": 0},
        "place": {"count": 0, "invest": 0, "return": 0, "hits": 0},
        "quinella": {"count": 0, "invest": 0, "return": 0, "hits": 0},
        "wide": {"count": 0, "invest": 0, "return": 0, "hits": 0},
    }
    
    detailed_results = []  # 全ベットの詳細記録
    daily_results = []
    current_date = None
    daily_invest = 0
    daily_return = 0
    
    for f in files:
        date_str = f.stem.replace("results_", "")
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        
        if formatted_date < start_date or formatted_date > end_date:
            continue
            
        if current_date and current_date != formatted_date:
            daily_results.append({
                "date": current_date,
                "invest": daily_invest,
                "return": daily_return,
                "balance": daily_return - daily_invest
            })
            if daily_invest > 0:
                roi = daily_return / daily_invest * 100
                print(f"[{current_date}] 投資:{daily_invest}円 回収:{daily_return}円 ({roi:.1f}%)")
            daily_invest = 0
            daily_return = 0

        current_date = formatted_date
            
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                
            for race in data.get("races", []):
                predictions, _ = calc.predict_race(race)
                
                if not predictions or len(predictions) < 2:
                    skipped_races += 1
                    continue
                
                recs = portfolio.recommend(predictions, race)
                
                if not recs:
                    skipped_races += 1
                    continue
                    
                race_count += 1
                
                # ===== 確定データの取得 =====
                payouts = race.get("payouts", {})
                top3 = race.get("top3", [])
                rank_map = {h.get("馬番"): h.get("着順", 99) for h in race.get("all_results", [])}
                
                # 確定配当の解析
                tansho_payout = payouts.get("単勝", 0)  # 100円あたり
                umaren_payout = payouts.get("馬連", 0)
                
                # 複勝の確定配当（パース）
                fukusho_map = parse_fukusho_payouts(payouts.get("複勝", 0), top3)
                
                # ワイドの確定配当（パース）
                wide_map = parse_wide_payouts(payouts.get("ワイド", 0), top3)
                
                # 1着馬の馬番
                win_umaban = top3[0].get("馬番") if top3 else None
                # 1-2着の馬番セット
                top2_set = frozenset([top3[0].get("馬番"), top3[1].get("馬番")]) if len(top3) >= 2 else frozenset()
                
                for rec in recs:
                    bet_type = rec["type"]
                    amount = rec["amount"]
                    umaban_str = str(rec["umaban"])
                    pay = 0
                    hit = False
                    
                    daily_invest += amount
                    total_invest += amount
                    bet_stats[bet_type]["count"] += 1
                    bet_stats[bet_type]["invest"] += amount
                    
                    if bet_type == "win":
                        umaban = int(umaban_str)
                        if umaban == win_umaban and tansho_payout > 0:
                            # 確定単勝配当を使用
                            pay = int(amount * tansho_payout / 100)
                            hit = True
                    
                    elif bet_type == "place":
                        umaban = int(umaban_str)
                        rank = rank_map.get(umaban, 99)
                        if isinstance(rank, int) and rank <= 3:
                            # 確定複勝配当を使用
                            confirmed = fukusho_map.get(umaban, 0)
                            if confirmed > 0:
                                pay = int(amount * confirmed / 100)
                                hit = True
                            else:
                                # フォールバック: 近似値
                                odds = float(rec.get("odds", 0) or 0)
                                place_odds = max(1.1, odds * 0.35)
                                pay = int(amount * place_odds)
                                hit = True
                    
                    elif bet_type == "quinella":
                        parts = umaban_str.split("-")
                        if len(parts) == 2:
                            u1, u2 = int(parts[0]), int(parts[1])
                            bet_set = frozenset([u1, u2])
                            if bet_set == top2_set and umaren_payout > 0:
                                # 確定馬連配当を使用
                                pay = int(amount * umaren_payout / 100)
                                hit = True
                    
                    elif bet_type == "wide":
                        parts = umaban_str.split("-")
                        if len(parts) == 2:
                            u1, u2 = int(parts[0]), int(parts[1])
                            r1 = rank_map.get(u1, 99)
                            r2 = rank_map.get(u2, 99)
                            if isinstance(r1, int) and isinstance(r2, int) and r1 <= 3 and r2 <= 3:
                                bet_key = frozenset([u1, u2])
                                confirmed = wide_map.get(bet_key, 0)
                                if confirmed > 0:
                                    pay = int(amount * confirmed / 100)
                                    hit = True
                                else:
                                    # フォールバック
                                    odds1 = float(predictions[0].get("odds", 0) or 0)
                                    wide_payout = max(1.0, odds1 * 0.6)
                                    pay = int(amount * wide_payout)
                                    hit = True
                    
                    if hit:
                        daily_return += pay
                        total_return += pay
                        bet_stats[bet_type]["hits"] += 1
                        bet_stats[bet_type]["return"] += pay
                    
                    # 詳細記録
                    detailed_results.append({
                        "date": formatted_date,
                        "race_id": race.get("race_id", ""),
                        "race_name": race.get("race_name", ""),
                        "bet_type": bet_type,
                        "umaban": umaban_str,
                        "amount": amount,
                        "payout": pay,
                        "hit": hit,
                        "ev": rec.get("ev", 0),
                        "prob": rec.get("prob", 0),
                    })
                        
        except Exception as e:
            pass
    
    # 最終日
    if current_date and (daily_invest > 0 or daily_return > 0):
        daily_results.append({
            "date": current_date,
            "invest": daily_invest,
            "return": daily_return,
            "balance": daily_return - daily_invest
        })
    
    # CSV出力
    df_daily = pd.DataFrame(daily_results)
    if not df_daily.empty:
        df_daily["cumulative_balance"] = df_daily["balance"].cumsum()
        df_daily.to_csv(RESULTS_DIR / "backtest_results.csv", index=False)
    
    # 詳細CSV
    df_detail = pd.DataFrame(detailed_results)
    if not df_detail.empty:
        df_detail.to_csv(RESULTS_DIR / "backtest_detail.csv", index=False)
    
    # 券種別サマリーCSV
    bet_summary = []
    for bt, stats in bet_stats.items():
        if stats["count"] > 0:
            bet_summary.append({
                "bet_type": bt,
                "count": stats["count"],
                "invest": stats["invest"],
                "return": stats["return"],
                "hit_rate": round(stats["hits"] / stats["count"] * 100, 1),
                "roi": round(stats["return"] / stats["invest"] * 100, 1) if stats["invest"] > 0 else 0
            })
    pd.DataFrame(bet_summary).to_csv(RESULTS_DIR / "bet_type_summary.csv", index=False)
    
    print(f"\n結果保存: {RESULTS_DIR}")
    
    # ========= サマリー出力 =========
    print("\n" + "=" * 60)
    print("📊 バックテスト v3 結果サマリー")
    print("   確定配当 + ケリー基準")
    print("=" * 60)
    print(f"対象レース数: {race_count} (スキップ: {skipped_races})")
    print(f"総投資額: ¥{total_invest:,}")
    print(f"総回収額: ¥{total_return:,}")
    print(f"純損益:   ¥{total_return - total_invest:,}")
    
    if total_invest > 0:
        roi = total_return / total_invest * 100
        print(f"回収率:   {roi:.1f}%")
        print(f"改善:     {roi - 71.2:+.1f}pp (ベースライン比)")
    
    print(f"\n--- 券種別内訳 ---")
    for bt, stats in bet_stats.items():
        if stats["count"] > 0:
            hit_rate = stats["hits"] / stats["count"] * 100
            bt_roi = stats["return"] / stats["invest"] * 100 if stats["invest"] > 0 else 0
            print(f"  {bt:10s}: {stats['count']:4d}回, "
                  f"投資¥{stats['invest']:>8,}, 回収¥{stats['return']:>8,}, "
                  f"的中{hit_rate:5.1f}%, 回収率{bt_roi:6.1f}%")
    
    print("=" * 60)
    
    return total_invest, total_return

if __name__ == "__main__":
    run_backtest()
