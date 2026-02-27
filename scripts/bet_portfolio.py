"""
券種別ポートフォリオ最適化AI v2
- ケリー基準（Kelly Criterion）による動的資金配分
- 確定オッズ対応
"""
import math
from typing import Dict, List, Tuple
from pathlib import Path

class BetPortfolio:
    """
    レースの特性と予測結果に基づいて、最適な券種と投資配分を算出する。
    ケリー基準で投資額を動的に決定。
    """
    
    # 資金管理パラメータ
    BASE_BANKROLL = 100000  # 仮想資金100万円
    KELLY_FRACTION = 0.20   # ケリー基準の1/5（保守的に）
    MIN_BET = 100           # 最小賭金
    MAX_BET = 500           # 最大賭金（1回あたり上限）
    
    def recommend(self, sorted_horses: List[Dict], race_info: Dict = None) -> List[Dict]:
        """
        ソート済みの馬リストから最適な買い目を推奨する。
        Returns:
            list of {"type": str, "umaban": int/str, "amount": int, "ev": float, ...}
        """
        if len(sorted_horses) < 2:
            return []
        
        h1 = sorted_horses[0]
        h2 = sorted_horses[1]
        h3 = sorted_horses[2] if len(sorted_horses) > 2 else None
        
        prob1 = h1.get("prob_top3", 0.3)
        prob2 = h2.get("prob_top3", 0.2)
        
        odds1 = float(h1.get("odds", 0) or 0)
        odds2 = float(h2.get("odds", 0) or 0)
        
        recommendations = []
        
        # ========== 1. 単勝（厳選: EVが高い場合のみ）==========
        win_prob = prob1 * 0.4  # 3着以内→1着への変換係数
        if odds1 > 0:
            win_ev = win_prob * odds1
            if win_ev > 1.5:  # EV 1.5以上の高確信度のみ
                amount = self._kelly_bet(win_prob, odds1)
                if amount >= self.MIN_BET:
                    recommendations.append({
                        "type": "win",
                        "name": "単勝",
                        "umaban": h1.get("umaban"),
                        "horse_name": h1.get("horse_name", ""),
                        "amount": amount,
                        "ev": round(win_ev, 2),
                        "prob": round(win_prob, 3),
                        "reason": f"勝率{win_prob*100:.0f}% EV{win_ev:.2f}"
                    })
        
        # ========== 2. 複勝（廃止: 確定配当ベースで赤字のため）==========
        # NOTE: 確定配当バックテストで回収率60.5%と赤字だったため、複勝は買わない
        
        # ========== 3. 馬連（メイン戦略: 確定配当で唯一黒字）==========
        if odds1 > 0 and odds2 > 0:
            quinella_prob = prob1 * prob2 * 0.15
            quinella_odds = (odds1 + odds2) * 1.8
            quinella_ev = quinella_prob * quinella_odds
            
            if quinella_ev > 1.0:  # 閾値を下げて購入頻度を上げる
                amount = self._kelly_bet(quinella_prob, quinella_odds)
                amount = max(amount, 200)  # 馬連は最低200円
                if amount >= self.MIN_BET:
                    recommendations.append({
                        "type": "quinella",
                        "name": "馬連",
                        "umaban": f"{h1.get('umaban')}-{h2.get('umaban')}",
                        "horse_name": f"{h1.get('horse_name','')}-{h2.get('horse_name','')}",
                        "amount": amount,
                        "ev": round(quinella_ev, 2),
                        "prob": round(quinella_prob, 3),
                        "reason": f"◎○軸 EV{quinella_ev:.2f}"
                    })
        
        # ========== 4. ワイド（一時停止: 確定配当ベースで回収率90.4%と赤字）==========
        # NOTE: 単勝182.5% + 馬連105.8% の黒字戦略に集中するため一時停止
        # if h3 and odds1 > 0:
        #     prob3 = h3.get("prob_top3", 0.15)
        #     odds3 = float(h3.get("odds", 0) or 0)
        #     wide_prob = prob1 * prob3 * 0.5
        #     wide_odds = max(odds1, odds3) * 0.6
        #     wide_ev = wide_prob * wide_odds
        #     if wide_ev > 1.5:
        #         amount = self._kelly_bet(wide_prob, wide_odds)
        #         if amount >= self.MIN_BET:
        #             recommendations.append({...})
        
        # EVでソート
        recommendations.sort(key=lambda x: x["ev"], reverse=True)
        
        return recommendations
    
    def _kelly_bet(self, prob: float, odds: float) -> int:
        """
        ケリー基準（Quarter Kelly）で最適投資額を計算。
        
        Kelly公式: f* = (bp - q) / b
          b = odds - 1 (ネットオッズ)
          p = 勝率
          q = 1 - p
          f* = 最適投資比率（バンクロールに対する割合）
        
        フルケリーは変動が激しいため、1/4 Kelly を使用。
        """
        if prob <= 0 or odds <= 1.0:
            return 0
        
        b = odds - 1.0  # ネットオッズ（利益分）
        q = 1.0 - prob
        
        kelly_fraction = (b * prob - q) / b
        
        if kelly_fraction <= 0:
            return 0  # ベッティングエッジがない
        
        # 1/4 Kelly で保守的に
        adjusted_fraction = kelly_fraction * self.KELLY_FRACTION
        
        # 投資額算出（バンクロール × ケリー比率）
        raw_amount = self.BASE_BANKROLL * adjusted_fraction
        
        # 100円単位に丸め、上限・下限を適用
        amount = max(self.MIN_BET, min(self.MAX_BET, int(raw_amount / 100) * 100))
        
        return amount

if __name__ == "__main__":
    portfolio = BetPortfolio()
    
    test_horses = [
        {"umaban": 3, "horse_name": "テスト1号", "prob_top3": 0.45, "odds": 3.5, "uma_score": 72},
        {"umaban": 7, "horse_name": "テスト2号", "prob_top3": 0.38, "odds": 5.0, "uma_score": 65},
        {"umaban": 1, "horse_name": "テスト3号", "prob_top3": 0.30, "odds": 8.0, "uma_score": 58},
    ]
    
    recs = portfolio.recommend(test_horses)
    print("推奨買い目 (ケリー基準):")
    for r in recs:
        print(f"  {r['name']} {r['umaban']} ¥{r['amount']} "
              f"(EV:{r['ev']}, 確率:{r['prob']}, {r['reason']})")
