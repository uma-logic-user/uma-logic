#!/usr/bin/env python3
"""
回収率重視UMA指数計算エンジン
実データに基づく精密な評価 + 期待値計算
"""

import re
from typing import Dict, List


class RecoveryFocusedCalculator:
    """回収率重視の指数計算クラス"""
    
    # 各要素の最大スコア
    MAX_SCORES = {
        "bloodline": 20.0,
        "training": 20.0,
        "frame_position": 15.0,
        "jockey_stable": 20.0,
        "past_record": 25.0  # 過去実績を最重視
    }
    
    # 名門血統（父系）
    ELITE_SIRES = {
        "ディープインパクト": 5.0,
        "キングカメハメハ": 4.5,
        "ロードカナロア": 4.5,
        "ハーツクライ": 4.0,
        "オルフェーヴル": 4.0,
        "エピファネイア": 4.0,
        "ドゥラメンテ": 3.5,
        "モーリス": 3.5
    }
    
    # トップ騎手
    TOP_JOCKEYS = {
        "C.ルメール": 5.0,
        "武豊": 4.5,
        "川田将雅": 4.5,
        "M.デムーロ": 4.0,
        "福永祐一": 4.0,
        "横山武史": 3.5,
        "戸崎圭太": 3.5,
        "岩田康誠": 3.0
    }
    
    # 名門厩舎
    TOP_TRAINERS = {
        "藤沢和雄": 4.0,
        "国枝栄": 4.0,
        "堀宣行": 3.5,
        "友道康夫": 3.5,
        "池江泰寿": 3.5,
        "角居勝彦": 3.0,
        "矢作芳人": 3.0
    }
    
    def __init__(self):
        pass
    
    def calculate(self, horse_data: Dict, race_data: Dict, all_horses: List[Dict]) -> Dict:
        """
        回収率重視のUMA指数を計算
        
        Returns:
            {
                "uma_index": 85.2,
                "rank": "A",
                "confidence": 0.85,  # 信頼度（0〜1）
                "expected_value": 1.25,  # 期待値
                "breakdown": {...},
                "reasons": [...]
            }
        """
        breakdown = {}
        reasons = []
        
        # 1. 過去実績（最重視）
        record_score, record_reason, consistency = self._calc_past_record(horse_data, race_data)
        breakdown["past_record"] = record_score
        if record_reason:
            reasons.append(record_reason)
        
        # 2. 血統適性
        bloodline_score, bloodline_reason = self._calc_bloodline(horse_data, race_data)
        breakdown["bloodline"] = bloodline_score
        if bloodline_reason:
            reasons.append(bloodline_reason)
        
        # 3. 調教評価
        training_score, training_reason = self._calc_training(horse_data, race_data)
        breakdown["training"] = training_score
        if training_reason:
            reasons.append(training_reason)
        
        # 4. 枠順/展開
        frame_score, frame_reason = self._calc_frame_position(horse_data, race_data, all_horses)
        breakdown["frame_position"] = frame_score
        if frame_reason:
            reasons.append(frame_reason)
        
        # 5. 騎手/厩舎
        jockey_score, jockey_reason = self._calc_jockey_stable(horse_data)
        breakdown["jockey_stable"] = jockey_score
        if jockey_reason:
            reasons.append(jockey_reason)
        
        # 総合スコア
        total_score = sum(breakdown.values())
        
        # ランク付け
        rank = self._assign_rank(total_score)
        
        # 信頼度計算（過去成績の安定性）
        confidence = self._calc_confidence(consistency, record_score, training_score)
        
        # 期待値計算（スコア / オッズ）
        odds = horse_data.get("odds", 10.0)
        expected_value = self._calc_expected_value(total_score, odds)
        
        return {
            "uma_index": round(total_score, 1),
            "rank": rank,
            "confidence": round(confidence, 2),
            "expected_value": round(expected_value, 2),
            "breakdown": breakdown,
            "reasons": reasons
        }
    
    def _calc_past_record(self, horse_data: Dict, race_data: Dict) -> tuple:
        """
        過去実績を評価（最重視）
        
        Returns:
            (score, reason, consistency)
        """
        score = 0.0
        reason = ""
        consistency = 0.5  # 安定性（0〜1）
        
        past_records = horse_data.get("past_records", [])
        
        if not past_records:
            return 5.0, "実績データ不足", 0.3
        
        # 直近5走の着順
        chakujun_list = [r.get("chakujun", 99) for r in past_records]
        
        # 平均着順
        avg_chakujun = sum(chakujun_list) / len(chakujun_list) if chakujun_list else 99
        
        # 勝率・連対率・複勝率
        win_rate = sum(1 for c in chakujun_list if c == 1) / len(chakujun_list)
        rentan_rate = sum(1 for c in chakujun_list if c <= 2) / len(chakujun_list)
        fukusho_rate = sum(1 for c in chakujun_list if c <= 3) / len(chakujun_list)
        
        # スコア計算
        if avg_chakujun <= 2.0:
            score = 25.0
            reason = "実績◎: 直近5走で平均着順2位以内"
            consistency = 0.9
        elif avg_chakujun <= 3.5:
            score = 20.0
            reason = "実績○: 直近5走で安定して好走"
            consistency = 0.75
        elif avg_chakujun <= 5.0:
            score = 15.0
            reason = "実績△: 直近5走で中位安定"
            consistency = 0.6
        elif avg_chakujun <= 8.0:
            score = 10.0
            reason = "実績▲: 直近成績やや低迷"
            consistency = 0.4
        else:
            score = 5.0
            reason = "実績×: 直近成績不振"
            consistency = 0.2
        
        # 同距離・同馬場での実績をボーナス
        current_distance = race_data.get("distance", "")
        current_surface = race_data.get("surface", "")
        
        same_condition_count = 0
        for record in past_records:
            if current_distance in record.get("distance", "") and current_surface in record.get("baba", ""):
                if record.get("chakujun", 99) <= 3:
                    same_condition_count += 1
        
        if same_condition_count >= 2:
            score = min(score + 3.0, self.MAX_SCORES["past_record"])
            reason += " + 同条件好走歴あり"
        
        return score, reason, consistency
    
    def _calc_bloodline(self, horse_data: Dict, race_data: Dict) -> tuple:
        """血統適性を評価"""
        score = 10.0  # ベーススコア
        reason = ""
        
        pedigree = horse_data.get("pedigree", {})
        father = pedigree.get("father", "")
        mother_father = pedigree.get("mother_father", "")
        
        # 父系評価
        father_bonus = self.ELITE_SIRES.get(father, 0.0)
        
        # 母父系評価
        mother_father_bonus = self.ELITE_SIRES.get(mother_father, 0.0) * 0.5
        
        total_bonus = father_bonus + mother_father_bonus
        score += total_bonus
        
        if total_bonus >= 6.0:
            reason = f"血統◎: 父{father}×母父{mother_father}"
        elif total_bonus >= 3.0:
            reason = f"血統○: 父{father} (名門血統)"
        elif total_bonus > 0:
            reason = "血統△: 血統評価あり"
        else:
            reason = "血統×: 血統評価低"
        
        # 芝・ダート適性
        surface = race_data.get("surface", "")
        
        # 芝適性の高い父系
        turf_sires = ["ディープインパクト", "ハーツクライ", "ドゥラメンテ"]
        # ダート適性の高い父系
        dirt_sires = ["キングカメハメハ", "ロードカナロア"]
        
        if surface == "芝" and father in turf_sires:
            score = min(score + 2.0, self.MAX_SCORES["bloodline"])
            reason += " (芝適性◎)"
        elif surface == "ダート" and father in dirt_sires:
            score = min(score + 2.0, self.MAX_SCORES["bloodline"])
            reason += " (ダート適性◎)"
        
        return min(score, self.MAX_SCORES["bloodline"]), reason
    
    def _calc_training(self, horse_data: Dict, race_data: Dict) -> tuple:
        """調教評価を計算"""
        score = 10.0
        reason = ""
        
        training = horse_data.get("training", {})
        training_time = training.get("time", "不明")
        evaluation = training.get("evaluation", "不明")
        
        # 調教タイムの評価
        if "速" in evaluation or "良" in evaluation:
            score += 8.0
            reason = "調教◎: 追い切り良好"
        elif "平" in evaluation or "普" in evaluation:
            score += 5.0
            reason = "調教○: 追い切り平凡"
        elif "遅" in evaluation or "不" in evaluation:
            score += 2.0
            reason = "調教△: 追い切り物足りず"
        else:
            score += 4.0
            reason = "調教-: データ不足"
        
        # 馬体重の評価
        weight = horse_data.get("weight", 0)
        weight_diff = horse_data.get("weight_diff", 0)
        
        # 馬体重の適正範囲（450kg〜480kg）
        if 450 <= weight <= 480:
            if abs(weight_diff) <= 4:
                score = min(score + 2.0, self.MAX_SCORES["training"])
                reason += " + 馬体充実"
            elif weight_diff > 0:
                reason += " (馬体増)"
        
        return min(score, self.MAX_SCORES["training"]), reason
    
    def _calc_frame_position(self, horse_data: Dict, race_data: Dict, all_horses: List[Dict]) -> tuple:
        """枠順/展開を評価"""
        score = 7.5  # ベース
        reason = ""
        
        umaban = horse_data.get("umaban", 0)
        wakuban = horse_data.get("wakuban", 0)
        surface = race_data.get("surface", "")
        distance = race_data.get("distance", "")
        
        # 距離カテゴリ
        distance_num = int(re.sub(r'\D', '', distance)) if distance else 0
        
        # 芝の場合
        if surface == "芝":
            if distance_num < 1400:  # 短距離
                if wakuban <= 3:
                    score += 6.0
                    reason = "展開◎: 短距離×内枠有利"
                elif wakuban <= 5:
                    score += 3.0
                    reason = "展開○: 中枠から先行可"
                else:
                    score += 1.0
                    reason = "展開△: 外枠不利"
            
            elif distance_num < 2000:  # 中距離
                if 2 <= wakuban <= 5:
                    score += 5.0
                    reason = "展開◎: 中距離×中枠理想"
                elif wakuban <= 7:
                    score += 3.0
                    reason = "展開○: 展開次第"
                else:
                    score += 1.0
                    reason = "展開△: 外枠やや不利"
            
            else:  # 長距離
                if 3 <= wakuban <= 6:
                    score += 4.0
                    reason = "展開○: 長距離で中枠"
                else:
                    score += 2.0
                    reason = "展開△: 展開次第"
        
        # ダートの場合
        else:
            if 3 <= wakuban <= 6:
                score += 6.0
                reason = "展開◎: ダート×中枠有利"
            elif wakuban <= 7:
                score += 4.0
                reason = "展開○: ダート×まずまず"
            else:
                score += 2.0
                reason = "展開△: ダート×やや不利"
        
        return min(score, self.MAX_SCORES["frame_position"]), reason
    
    def _calc_jockey_stable(self, horse_data: Dict) -> tuple:
        """騎手/厩舎を評価"""
        score = 10.0
        reason = ""
        
        jockey = horse_data.get("jockey", "")
        trainer = horse_data.get("trainer", "")
        
        # 騎手評価
        jockey_bonus = self.TOP_JOCKEYS.get(jockey, 1.0)
        
        # 厩舎評価
        trainer_bonus = self.TOP_TRAINERS.get(trainer, 1.0)
        
        score += jockey_bonus + trainer_bonus
        
        if jockey_bonus >= 4.0 and trainer_bonus >= 3.0:
            reason = f"◎: {jockey}×{trainer}の最強コンビ"
        elif jockey_bonus >= 3.5 or trainer_bonus >= 3.0:
            reason = f"○: {jockey}騎手 (トップ級)"
        elif jockey_bonus >= 2.0:
            reason = f"△: {jockey}騎手"
        else:
            reason = f"-: {jockey}騎手"
        
        return min(score, self.MAX_SCORES["jockey_stable"]), reason
    
    def _assign_rank(self, total_score: float) -> str:
        """スコアからランクを付与"""
        if total_score >= 85:
            return "S"
        elif total_score >= 75:
            return "A"
        elif total_score >= 65:
            return "B"
        else:
            return "C"
    
    def _calc_confidence(self, consistency: float, record_score: float, training_score: float) -> float:
        """
        信頼度を計算（0〜1）
        高いほど的中しやすい
        """
        # 過去成績の安定性を最重視
        confidence = consistency * 0.6
        
        # 過去実績スコアの寄与
        confidence += (record_score / self.MAX_SCORES["past_record"]) * 0.3
        
        # 調教スコアの寄与
        confidence += (training_score / self.MAX_SCORES["training"]) * 0.1
        
        return min(confidence, 1.0)
    
    def _calc_expected_value(self, total_score: float, odds: float) -> float:
        """
        期待値を計算
        期待値 = (勝率推定 × オッズ)
        
        1.0以上なら期待値プラス
        """
        # スコアから勝率を推定（簡易）
        if total_score >= 85:
            win_prob = 0.30  # 30%
        elif total_score >= 75:
            win_prob = 0.20
        elif total_score >= 65:
            win_prob = 0.12
        elif total_score >= 55:
            win_prob = 0.08
        else:
            win_prob = 0.05
        
        # 期待値 = 勝率 × オッズ
        expected_value = win_prob * odds
        
        return expected_value


# テスト
if __name__ == "__main__":
    calculator = RecoveryFocusedCalculator()
    
    # サンプルデータ
    horse = {
        "umaban": 3,
        "wakuban": 3,
        "horse_name": "サンプルホース",
        "jockey": "C.ルメール",
        "trainer": "藤沢和雄",
        "weight": 476,
        "weight_diff": 2,
        "odds": 2.8,
        "pedigree": {
            "father": "ディープインパクト",
            "mother_father": "キングカメハメハ"
        },
        "past_records": [
            {"chakujun": 1, "distance": "1600m", "baba": "芝"},
            {"chakujun": 2, "distance": "1800m", "baba": "芝"},
            {"chakujun": 3, "distance": "1600m", "baba": "芝"},
            {"chakujun": 1, "distance": "1400m", "baba": "芝"},
            {"chakujun": 2, "distance": "1600m", "baba": "芝"}
        ],
        "training": {
            "time": "52.0",
            "evaluation": "速い"
        }
    }
    
    race = {
        "surface": "芝",
        "distance": "1600m"
    }
    
    result = calculator.calculate(horse, race, [])
    
    print(f"🏇 {horse['horse_name']}")
    print(f"   UMA指数: {result['uma_index']} (ランク: {result['rank']})")
    print(f"   信頼度: {result['confidence']*100:.1f}%")
    print(f"   期待値: {result['expected_value']}")
    print(f"   内訳: {result['breakdown']}")
    print(f"   理由:")
    for r in result['reasons']:
        print(f"     - {r}")
