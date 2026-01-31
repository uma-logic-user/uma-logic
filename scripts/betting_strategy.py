#!/usr/bin/env python3
"""
回収率重視の買い目戦略
ワイド・枠連を追加し、期待値に基づく券種選択
"""

from typing import Dict, List, Tuple


class RecoveryBettingStrategy:
    """回収率重視の買い目戦略クラス"""
    
    def __init__(self):
        pass
    
    def generate_bets(self, horses: List[Dict], race_data: Dict) -> Dict:
        """
        回収率を最大化する買い目を生成
        
        Args:
            horses: 全出走馬の情報（UMA指数・信頼度・期待値を含む）
            race_data: レース情報
        
        Returns:
            {
                "単勝": [...],
                "複勝": [...],
                "ワイド": [...],
                "枠連": [...],
                "馬連": [...],
                "馬単": [...],
                "三連複": [...],
                "三連単": [...]
            }
        """
        # 指数順にソート
        sorted_horses = sorted(horses, key=lambda h: h.get("uma_index", 0), reverse=True)
        
        # 上位5頭を抽出
        top5 = sorted_horses[:5]
        
        # 期待値順にソート
        by_expected = sorted(horses, key=lambda h: h.get("expected_value", 0), reverse=True)
        high_expected = by_expected[:5]
        
        # 信頼度順にソート
        by_confidence = sorted(horses, key=lambda h: h.get("confidence", 0), reverse=True)
        high_confidence = by_confidence[:3]
        
        bets = {}
        
        # 1. 単勝（期待値1.2以上のみ）
        bets["単勝"] = self._generate_tansho(high_expected)
        
        # 2. 複勝（信頼度0.7以上）
        bets["複勝"] = self._generate_fukusho(high_confidence)
        
        # 3. ワイド（的中率高・回収率安定）
        bets["ワイド"] = self._generate_wide(top5, high_confidence)
        
        # 4. 枠連（少頭数レースで有効）
        if len(horses) <= 12:
            bets["枠連"] = self._generate_wakuren(top5)
        else:
            bets["枠連"] = []
        
        # 5. 馬連
        bets["馬連"] = self._generate_umaren(top5)
        
        # 6. 馬単
        bets["馬単"] = self._generate_umatan(top5, high_confidence)
        
        # 7. 三連複
        bets["三連複"] = self._generate_sanrenpuku(top5)
        
        # 8. 三連単
        bets["三連単"] = self._generate_sanrentan(top5, high_confidence)
        
        return bets
    
    def _generate_tansho(self, horses: List[Dict]) -> List[int]:
        """
        単勝: 期待値1.2以上のみ購入
        """
        candidates = []
        
        for horse in horses:
            expected_value = horse.get("expected_value", 0)
            
            # 期待値1.2以上（20%以上のプラス期待値）
            if expected_value >= 1.2:
                candidates.append(horse["umaban"])
        
        return candidates[:2]  # 最大2頭
    
    def _generate_fukusho(self, horses: List[Dict]) -> List[int]:
        """
        複勝: 信頼度0.7以上
        """
        candidates = []
        
        for horse in horses:
            confidence = horse.get("confidence", 0)
            
            if confidence >= 0.7:
                candidates.append(horse["umaban"])
        
        return candidates[:3]  # 最大3頭
    
    def _generate_wide(self, top5: List[Dict], high_confidence: List[Dict]) -> List[List[int]]:
        """
        ワイド: 的中率重視
        本命×信頼度上位馬
        """
        bets = []
        
        if not top5:
            return bets
        
        honmei = top5[0]
        
        # 本命×信頼度上位2〜4頭
        for horse in high_confidence[1:4]:
            if horse["umaban"] != honmei["umaban"]:
                bets.append(sorted([honmei["umaban"], horse["umaban"]]))
        
        # 信頼度上位馬同士
        if len(high_confidence) >= 3:
            bets.append(sorted([high_confidence[1]["umaban"], high_confidence[2]["umaban"]]))
        
        # 重複削除
        unique_bets = []
        for bet in bets:
            if bet not in unique_bets:
                unique_bets.append(bet)
        
        return unique_bets[:4]  # 最大4点
    
    def _generate_wakuren(self, top5: List[Dict]) -> List[List[int]]:
        """
        枠連: 少頭数レースで有効
        本命枠×上位馬枠
        """
        bets = []
        
        if not top5:
            return bets
        
        honmei = top5[0]
        honmei_waku = honmei.get("wakuban", 0)
        
        # 本命枠×上位3頭の枠
        for horse in top5[1:4]:
            waku = horse.get("wakuban", 0)
            if waku != honmei_waku and waku > 0:
                bets.append(sorted([honmei_waku, waku]))
        
        # 重複削除
        unique_bets = []
        for bet in bets:
            if bet not in unique_bets:
                unique_bets.append(bet)
        
        return unique_bets[:3]  # 最大3点
    
    def _generate_umaren(self, top5: List[Dict]) -> List[List[int]]:
        """
        馬連: 本命軸+上位4頭
        """
        bets = []
        
        if len(top5) < 2:
            return bets
        
        honmei = top5[0]
        
        # 本命×上位2〜5頭
        for horse in top5[1:5]:
            bets.append(sorted([honmei["umaban"], horse["umaban"]]))
        
        # 上位馬同士（2-3, 2-4）
        if len(top5) >= 4:
            bets.append(sorted([top5[1]["umaban"], top5[2]["umaban"]]))
            bets.append(sorted([top5[1]["umaban"], top5[3]["umaban"]]))
        
        return bets[:5]  # 最大5点
    
    def _generate_umatan(self, top5: List[Dict], high_confidence: List[Dict]) -> List[List[int]]:
        """
        馬単: 本命→信頼度上位
        """
        bets = []
        
        if len(top5) < 2:
            return bets
        
        honmei = top5[0]
        
        # 本命→信頼度上位2〜4頭
        for horse in high_confidence[1:4]:
            if horse["umaban"] != honmei["umaban"]:
                bets.append([honmei["umaban"], horse["umaban"]])
        
        # 信頼度2位→本命（保険）
        if len(high_confidence) >= 2:
            bets.append([high_confidence[1]["umaban"], honmei["umaban"]])
        
        return bets[:4]  # 最大4点
    
    def _generate_sanrenpuku(self, top5: List[Dict]) -> List[List[int]]:
        """
        三連複: 本命軸+上位馬
        """
        bets = []
        
        if len(top5) < 3:
            return bets
        
        honmei = top5[0]
        
        # 本命-2位-3位
        bets.append(sorted([top5[0]["umaban"], top5[1]["umaban"], top5[2]["umaban"]]))
        
        # 本命-2位-4位
        if len(top5) >= 4:
            bets.append(sorted([top5[0]["umaban"], top5[1]["umaban"], top5[3]["umaban"]]))
        
        # 本命-2位-5位
        if len(top5) >= 5:
            bets.append(sorted([top5[0]["umaban"], top5[1]["umaban"], top5[4]["umaban"]]))
        
        # 本命-3位-4位
        if len(top5) >= 4:
            bets.append(sorted([top5[0]["umaban"], top5[2]["umaban"], top5[3]["umaban"]]))
        
        return bets[:4]  # 最大4点
    
    def _generate_sanrentan(self, top5: List[Dict], high_confidence: List[Dict]) -> List[List[int]]:
        """
        三連単: 信頼度ベース
        """
        bets = []
        
        if len(top5) < 3:
            return bets
        
        # 1-2-3
        bets.append([top5[0]["umaban"], top5[1]["umaban"], top5[2]["umaban"]])
        
        # 1-3-2（保険）
        bets.append([top5[0]["umaban"], top5[2]["umaban"], top5[1]["umaban"]])
        
        # 信頼度ベース
        if len(high_confidence) >= 3:
            bet1 = [high_confidence[0]["umaban"], high_confidence[1]["umaban"], high_confidence[2]["umaban"]]
            if bet1 not in bets:
                bets.append(bet1)
        
        # 2-1-3（押さえ）
        if len(top5) >= 3:
            bets.append([top5[1]["umaban"], top5[0]["umaban"], top5[2]["umaban"]])
        
        return bets[:4]  # 最大4点
    
    def allocate_budget(self, bets: Dict, total_budget: int, style: str = "回収率重視") -> Dict:
        """
        予算配分（回収率重視）
        
        Args:
            bets: 買い目
            total_budget: 総予算（円）
            style: "回収率重視" or "的中率重視"
        
        Returns:
            券種別の投資額
        """
        if style == "回収率重視":
            # 期待値の高い券種に多く配分
            weights = {
                "単勝": 0.15,    # 期待値プラスのみ
                "複勝": 0.10,    # 安定収入
                "ワイド": 0.20,  # 的中率高・回収率安定
                "枠連": 0.05,    # 少頭数のみ
                "馬連": 0.15,
                "馬単": 0.10,
                "三連複": 0.15,
                "三連単": 0.10
            }
        else:  # 的中率重視
            weights = {
                "単勝": 0.10,
                "複勝": 0.20,
                "ワイド": 0.25,
                "枠連": 0.05,
                "馬連": 0.15,
                "馬単": 0.10,
                "三連複": 0.10,
                "三連単": 0.05
            }
        
        allocation = {}
        
        for ticket_type, weight in weights.items():
            bet_count = len(bets.get(ticket_type, []))
            
            if bet_count == 0:
                allocation[ticket_type] = 0
            else:
                # その券種への総投資額
                ticket_budget = int(total_budget * weight)
                
                # 1点あたりの投資額（100円単位）
                per_bet = (ticket_budget // bet_count // 100) * 100
                
                allocation[ticket_type] = per_bet * bet_count
        
        # 端数調整
        allocated_total = sum(allocation.values())
        diff = total_budget - allocated_total
        
        # 差額を複勝に追加（最も安全な券種）
        if "複勝" in allocation and diff > 0:
            allocation["複勝"] += diff
        
        return allocation


# テスト
if __name__ == "__main__":
    strategy = RecoveryBettingStrategy()
    
    # サンプル馬データ
    horses = [
        {"umaban": 1, "wakuban": 1, "uma_index": 88.0, "confidence": 0.85, "expected_value": 1.35},
        {"umaban": 2, "wakuban": 2, "uma_index": 82.0, "confidence": 0.75, "expected_value": 1.15},
        {"umaban": 3, "wakuban": 3, "uma_index": 78.0, "confidence": 0.70, "expected_value": 1.05},
        {"umaban": 4, "wakuban": 4, "uma_index": 74.0, "confidence": 0.65, "expected_value": 0.95},
        {"umaban": 5, "wakuban": 5, "uma_index": 70.0, "confidence": 0.60, "expected_value": 0.85},
    ]
    
    # 買い目生成
    bets = strategy.generate_bets(horses, {})
    
    print("🎯 回収率重視の買い目")
    for ticket_type, bet_list in bets.items():
        if bet_list:
            print(f"\n{ticket_type}:")
            for bet in bet_list:
                if isinstance(bet, list):
                    print(f"  {'-'.join(map(str, bet))}")
                else:
                    print(f"  {bet}")
    
    # 予算配分
    allocation = strategy.allocate_budget(bets, 5000, "回収率重視")
    
    print("\n💰 予算配分（5,000円）")
    for ticket_type, amount in allocation.items():
        if amount > 0:
            print(f"  {ticket_type}: {amount:,}円")
    
    print(f"\n合計: {sum(allocation.values()):,}円")
