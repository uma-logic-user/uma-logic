#!/usr/bin/env python3
# scripts/ensemble_agents.py
# UMA-Logic PRO - アンサンブル学習エンジン（厳格バックテスト版）
# 多券種対応 + ケリー基準投資モデル

import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import sys

# --- 定数 ---
DATA_DIR = Path("data")
ARCHIVE_DIR = DATA_DIR / "archive"
MODELS_DIR = DATA_DIR / "models"
WEIGHTS_FILE = MODELS_DIR / "weights.json"

# デフォルトの重み
DEFAULT_WEIGHTS = {
    "SpeedAgent": 0.35,
    "AdaptabilityAgent": 0.35,
    "PedigreeFormAgent": 0.30
}


# --- データクラス ---

@dataclass
class HorseFeatures:
    """馬の特徴量（レース前に分かる情報のみ）"""
    umaban: int = 0
    horse_name: str = ""
    odds: float = 0.0
    popularity: int = 0
    weight: float = 0.0
    weight_diff: float = 0.0
    age: int = 0
    sex: str = ""
    jockey: str = ""
    trainer: str = ""
    father: str = ""
    mother_father: str = ""
    gate_num: int = 0
    prev_results: List[int] = field(default_factory=list)
    prev_odds: List[float] = field(default_factory=list)


@dataclass
class RaceFeatures:
    """レース条件（レース前に分かる情報のみ）"""
    race_id: str = ""
    race_num: int = 0
    venue: str = ""
    distance: int = 0
    track_type: str = ""
    track_condition: str = ""
    grade: str = ""
    race_name: str = ""
    date: str = ""


@dataclass
class RaceResult:
    """レース結果（検証用、学習には使用しない）"""
    race_id: str = ""
    winner_umaban: int = 0
    winner_odds: float = 0.0
    top3_umaban: List[int] = field(default_factory=list)


# --- エージェントクラス ---

class SpeedAgent:
    """スピードエージェント: オッズと人気から期待スピードを推定"""
    
    def __init__(self, weight: float = 0.35):
        self.weight = weight
        self.name = "SpeedAgent"
    
    def calculate_score(self, horse: HorseFeatures, race: RaceFeatures) -> float:
        score = 50.0
        
        if horse.odds > 0:
            if horse.odds < 2.0:
                score += 30
            elif horse.odds < 5.0:
                score += 20
            elif horse.odds < 10.0:
                score += 10
            elif horse.odds < 20.0:
                score += 0
            else:
                score -= 10
        
        if horse.popularity > 0:
            if horse.popularity <= 3:
                score += 15
            elif horse.popularity <= 6:
                score += 5
            else:
                score -= 5
        
        if horse.prev_results:
            avg_result = sum(horse.prev_results[:3]) / len(horse.prev_results[:3])
            if avg_result <= 3:
                score += 20
            elif avg_result <= 5:
                score += 10
            elif avg_result <= 8:
                score += 0
            else:
                score -= 10
        
        if race.distance > 0:
            if race.distance <= 1400:
                if horse.gate_num <= 4:
                    score += 5
            elif race.distance >= 2000:
                if horse.popularity > 5 and horse.odds < 30:
                    score += 5
        
        return max(0, min(100, score))


class AdaptabilityAgent:
    """適応性エージェント: 馬場状態、枠順、コース適性を評価"""
    
    def __init__(self, weight: float = 0.35):
        self.weight = weight
        self.name = "AdaptabilityAgent"
    
    def calculate_score(self, horse: HorseFeatures, race: RaceFeatures) -> float:
        score = 50.0
        
        if race.distance > 0 and horse.gate_num > 0:
            if race.distance <= 1400:
                if horse.gate_num <= 3:
                    score += 15
                elif horse.gate_num <= 5:
                    score += 5
                elif horse.gate_num >= 7:
                    score -= 5
            elif race.distance <= 1800:
                pass
            else:
                if horse.gate_num >= 7:
                    score -= 10
        
        if race.track_condition:
            if race.track_condition in ["重", "不良"]:
                if horse.weight >= 500:
                    score += 10
                elif horse.weight <= 440:
                    score -= 5
        
        if horse.weight_diff != 0:
            if abs(horse.weight_diff) > 20:
                score -= 10
            elif -10 <= horse.weight_diff <= 10:
                score += 5
        
        if horse.age > 0:
            if horse.age == 3:
                score += 5
            elif horse.age >= 7:
                score -= 5
        
        return max(0, min(100, score))


class PedigreeFormAgent:
    """血統・調子エージェント: 血統パターンと直近の調子を評価"""
    
    SIRE_BONUS = {
        "ディープインパクト": 15, "キングカメハメハ": 12, "ロードカナロア": 12,
        "ハーツクライ": 10, "エピファネイア": 10, "ドゥラメンテ": 10,
        "キタサンブラック": 10, "モーリス": 8, "オルフェーヴル": 8, "ゴールドシップ": 5,
    }
    
    def __init__(self, weight: float = 0.30):
        self.weight = weight
        self.name = "PedigreeFormAgent"
    
    def calculate_score(self, horse: HorseFeatures, race: RaceFeatures) -> float:
        score = 50.0
        
        if horse.father:
            bonus = self.SIRE_BONUS.get(horse.father, 0)
            score += bonus
        
        if len(horse.prev_results) >= 2:
            recent = horse.prev_results[0]
            older = horse.prev_results[1]
            if recent < older:
                score += 10
            elif recent > older:
                score -= 5
        
        if horse.prev_results and horse.odds > 0:
            avg_result = sum(horse.prev_results[:3]) / len(horse.prev_results[:3])
            if avg_result <= 5 and horse.odds >= 10:
                score += 15
            elif avg_result >= 8 and horse.odds < 5:
                score -= 10
        
        TOP_JOCKEYS = ["ルメール", "川田将雅", "戸崎圭太", "横山武史", "福永祐一", "武豊"]
        if horse.jockey in TOP_JOCKEYS:
            score += 10
        
        return max(0, min(100, score))


# --- ケリー基準計算 ---

class KellyCriterion:
    """
    ケリー基準による最適投資額計算
    f* = (bp - q) / b
    b = オッズ - 1（純利益倍率）
    p = 的中確率
    q = 1 - p（不的中確率）
    """
    
    @staticmethod
    def calculate_fraction(win_probability: float, odds: float, 
                           fraction_cap: float = 0.25) -> float:
        """
        ケリー基準で最適投資比率を計算
        
        Args:
            win_probability: 的中確率 (0-1)
            odds: オッズ
            fraction_cap: 最大投資比率（デフォルト25%）
        
        Returns:
            最適投資比率 (0-fraction_cap)
        """
        if odds <= 1.0 or win_probability <= 0 or win_probability >= 1:
            return 0.0
        
        b = odds - 1.0  # 純利益倍率
        p = win_probability
        q = 1.0 - p
        
        kelly_f = (b * p - q) / b
        
        # 負の値（期待値マイナス）は0にする
        if kelly_f <= 0:
            return 0.0
        
        # ハーフケリー（リスク軽減）
        half_kelly = kelly_f * 0.5
        
        # 上限を設定
        return min(half_kelly, fraction_cap)
    
    @staticmethod
    def calculate_expected_value(win_probability: float, odds: float) -> float:
        """
        期待値を計算
        期待値 = (的中確率 * オッズ) / 1.0
        1.0以上なら期待値プラス
        """
        if odds <= 0 or win_probability <= 0:
            return 0.0
        return win_probability * odds
    
    @staticmethod
    def estimate_win_probability(uma_index: float, num_horses: int = 16) -> float:
        """
        UMA指数から的中確率を推定
        
        シグモイド関数ベースで、UMA指数が高いほど的中確率が高い
        num_horses で補正（出走頭数が少ないほど確率が上がる）
        """
        if uma_index <= 0:
            return 0.01
        
        # ベース確率: シグモイド関数
        # UMA指数70で約30%、60で約20%、50で約10%
        x = (uma_index - 50) / 10
        base_prob = 1.0 / (1.0 + math.exp(-x))
        
        # 出走頭数による補正
        horse_factor = 16.0 / max(num_horses, 5)
        
        # 最終確率（上限80%）
        prob = base_prob * horse_factor * 0.4
        return min(max(prob, 0.01), 0.80)
    
    @staticmethod
    def estimate_place_probability(uma_index: float, num_horses: int = 16) -> float:
        """UMA指数から複勝（3着以内）確率を推定"""
        win_prob = KellyCriterion.estimate_win_probability(uma_index, num_horses)
        # 複勝確率は単勝の約2.5倍（経験的な値）
        return min(win_prob * 2.5, 0.90)
    
    @staticmethod
    def estimate_quinella_probability(uma_index_1: float, uma_index_2: float, 
                                       num_horses: int = 16) -> float:
        """2頭のUMA指数から馬連確率を推定"""
        p1 = KellyCriterion.estimate_win_probability(uma_index_1, num_horses)
        p2 = KellyCriterion.estimate_win_probability(uma_index_2, num_horses)
        # 馬連: 2頭が1-2着（順不同）
        return p1 * p2 * 2 * 0.8  # 補正係数0.8
    
    @staticmethod
    def estimate_wide_probability(uma_index_1: float, uma_index_2: float,
                                   num_horses: int = 16) -> float:
        """2頭のUMA指数からワイド確率を推定"""
        p1 = KellyCriterion.estimate_place_probability(uma_index_1, num_horses)
        p2 = KellyCriterion.estimate_place_probability(uma_index_2, num_horses)
        # ワイド: 2頭が3着以内
        return p1 * p2 * 0.7  # 補正係数0.7


# --- 多券種期待値計算 ---

class MultiTicketCalculator:
    """
    多券種の期待値を一括計算
    単勝、複勝、馬連、ワイドの期待値とケリー基準を算出
    """
    
    def __init__(self):
        self.kelly = KellyCriterion()
    
    def calculate_all_tickets(self, horses: list, race: dict, 
                               bankroll: float = 100000) -> List[Dict]:
        """
        全券種の推奨馬券リストを生成
        
        Args:
            horses: 馬リスト（uma_index, odds 含む）
            race: レース情報
            bankroll: 現在の資金
        
        Returns:
            推奨馬券リスト（期待値1.0超のみ）
        """
        recommendations = []
        num_horses = len(horses)
        
        if num_horses < 2:
            return recommendations
        
        # UMA指数でソート
        sorted_horses = sorted(horses, key=lambda x: x.get("uma_index", 0), reverse=True)
        
        # --- 単勝 ---
        for horse in sorted_horses[:5]:  # 上位5頭
            uma_idx = horse.get("uma_index", 0)
            odds = float(horse.get("オッズ", horse.get("odds", 0)) or 0)
            if odds <= 0:
                continue
            
            win_prob = self.kelly.estimate_win_probability(uma_idx, num_horses)
            ev = self.kelly.calculate_expected_value(win_prob, odds)
            kelly_f = self.kelly.calculate_fraction(win_prob, odds)
            bet_amount = int(bankroll * kelly_f / 100) * 100  # 100円単位
            
            recommendations.append({
                "券種": "単勝",
                "馬番": horse.get("umaban", horse.get("馬番", "")),
                "馬名": horse.get("horse_name", horse.get("馬名", "")),
                "オッズ": odds,
                "的中確率": round(win_prob * 100, 1),
                "期待値": round(ev, 3),
                "ケリー比率": round(kelly_f * 100, 2),
                "推奨投資額": max(bet_amount, 0),
                "uma_index": uma_idx,
            })
        
        # --- 複勝 ---
        for horse in sorted_horses[:5]:
            uma_idx = horse.get("uma_index", 0)
            odds = float(horse.get("オッズ", horse.get("odds", 0)) or 0)
            if odds <= 0:
                continue
            
            # 複勝オッズは単勝の約1/3（推定）
            place_odds = max(odds * 0.35, 1.1)
            place_prob = self.kelly.estimate_place_probability(uma_idx, num_horses)
            ev = self.kelly.calculate_expected_value(place_prob, place_odds)
            kelly_f = self.kelly.calculate_fraction(place_prob, place_odds)
            bet_amount = int(bankroll * kelly_f / 100) * 100
            
            recommendations.append({
                "券種": "複勝",
                "馬番": horse.get("umaban", horse.get("馬番", "")),
                "馬名": horse.get("horse_name", horse.get("馬名", "")),
                "オッズ": round(place_odds, 1),
                "的中確率": round(place_prob * 100, 1),
                "期待値": round(ev, 3),
                "ケリー比率": round(kelly_f * 100, 2),
                "推奨投資額": max(bet_amount, 0),
                "uma_index": uma_idx,
            })
        
        # --- 馬連（上位3頭の組み合わせ） ---
        top3 = sorted_horses[:3]
        for i in range(len(top3)):
            for j in range(i + 1, len(top3)):
                h1, h2 = top3[i], top3[j]
                uma1 = h1.get("uma_index", 0)
                uma2 = h2.get("uma_index", 0)
                odds1 = float(h1.get("オッズ", h1.get("odds", 0)) or 0)
                odds2 = float(h2.get("オッズ", h2.get("odds", 0)) or 0)
                
                if odds1 <= 0 or odds2 <= 0:
                    continue
                
                # 馬連オッズの推定（2頭の単勝オッズの積の平方根 * 補正）
                quinella_odds = max(math.sqrt(odds1 * odds2) * 1.5, 2.0)
                quinella_prob = self.kelly.estimate_quinella_probability(uma1, uma2, num_horses)
                ev = self.kelly.calculate_expected_value(quinella_prob, quinella_odds)
                kelly_f = self.kelly.calculate_fraction(quinella_prob, quinella_odds)
                bet_amount = int(bankroll * kelly_f / 100) * 100
                
                umaban1 = h1.get("umaban", h1.get("馬番", ""))
                umaban2 = h2.get("umaban", h2.get("馬番", ""))
                name1 = h1.get("horse_name", h1.get("馬名", ""))
                name2 = h2.get("horse_name", h2.get("馬名", ""))
                
                recommendations.append({
                    "券種": "馬連",
                    "馬番": f"{umaban1}-{umaban2}",
                    "馬名": f"{name1} - {name2}",
                    "オッズ": round(quinella_odds, 1),
                    "的中確率": round(quinella_prob * 100, 1),
                    "期待値": round(ev, 3),
                    "ケリー比率": round(kelly_f * 100, 2),
                    "推奨投資額": max(bet_amount, 0),
                    "uma_index": (uma1 + uma2) / 2,
                })
        
        # --- ワイド（上位3頭の組み合わせ） ---
        for i in range(len(top3)):
            for j in range(i + 1, len(top3)):
                h1, h2 = top3[i], top3[j]
                uma1 = h1.get("uma_index", 0)
                uma2 = h2.get("uma_index", 0)
                odds1 = float(h1.get("オッズ", h1.get("odds", 0)) or 0)
                odds2 = float(h2.get("オッズ", h2.get("odds", 0)) or 0)
                
                if odds1 <= 0 or odds2 <= 0:
                    continue
                
                # ワイドオッズの推定
                wide_odds = max(math.sqrt(odds1 * odds2) * 0.5, 1.2)
                wide_prob = self.kelly.estimate_wide_probability(uma1, uma2, num_horses)
                ev = self.kelly.calculate_expected_value(wide_prob, wide_odds)
                kelly_f = self.kelly.calculate_fraction(wide_prob, wide_odds)
                bet_amount = int(bankroll * kelly_f / 100) * 100
                
                umaban1 = h1.get("umaban", h1.get("馬番", ""))
                umaban2 = h2.get("umaban", h2.get("馬番", ""))
                name1 = h1.get("horse_name", h1.get("馬名", ""))
                name2 = h2.get("horse_name", h2.get("馬名", ""))
                
                recommendations.append({
                    "券種": "ワイド",
                    "馬番": f"{umaban1}-{umaban2}",
                    "馬名": f"{name1} - {name2}",
                    "オッズ": round(wide_odds, 1),
                    "的中確率": round(wide_prob * 100, 1),
                    "期待値": round(ev, 3),
                    "ケリー比率": round(kelly_f * 100, 2),
                    "推奨投資額": max(bet_amount, 0),
                    "uma_index": (uma1 + uma2) / 2,
                })
        
        # 期待値でソート（降順）
        recommendations.sort(key=lambda x: x["期待値"], reverse=True)
        
        return recommendations
    
    def get_positive_ev_tickets(self, horses: list, race: dict,
                                 bankroll: float = 100000,
                                 min_ev: float = 1.0) -> List[Dict]:
        """期待値がmin_ev以上の推奨馬券のみ返す"""
        all_tickets = self.calculate_all_tickets(horses, race, bankroll)
        return [t for t in all_tickets if t["期待値"] >= min_ev]


# --- 統合計算クラス ---

class IntegratedCalculator:
    """アンサンブル統合計算機"""
    
    def __init__(self):
        self.weights = self._load_weights()
        self.agents = {
            "SpeedAgent": SpeedAgent(self.weights.get("SpeedAgent", 0.35)),
            "AdaptabilityAgent": AdaptabilityAgent(self.weights.get("AdaptabilityAgent", 0.35)),
            "PedigreeFormAgent": PedigreeFormAgent(self.weights.get("PedigreeFormAgent", 0.30)),
        }
        self.ticket_calculator = MultiTicketCalculator()
    
    def _load_weights(self) -> Dict[str, float]:
        if WEIGHTS_FILE.exists():
            try:
                with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("weights", DEFAULT_WEIGHTS)
            except Exception:
                pass
        return DEFAULT_WEIGHTS.copy()
    
    def calculate_integrated_score(self, horse: HorseFeatures, race: RaceFeatures) -> float:
        total_score = 0.0
        total_weight = 0.0
        
        for agent_name, agent in self.agents.items():
            score = agent.calculate_score(horse, race)
            weight = self.weights.get(agent_name, agent.weight)
            total_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            return total_score / total_weight
        return 50.0
    
    def predict_race(self, horses: List[HorseFeatures], race: RaceFeatures) -> List[Tuple[int, str, float]]:
        results = []
        for horse in horses:
            score = self.calculate_integrated_score(horse, race)
            results.append((horse.umaban, horse.horse_name, score))
        
        results.sort(key=lambda x: x[2], reverse=True)
        return results


# --- バックテストクラス ---

class StrictBacktester:
    """厳格なバックテスター（Train/Test分離、データリーク防止）"""
    
    def __init__(self, train_years: List[int], test_years: List[int]):
        self.train_years = train_years
        self.test_years = test_years
        self.calculator = IntegratedCalculator()
    
    def load_race_data(self, year: int) -> List[Dict]:
        races = []
        
        year_dir = ARCHIVE_DIR / str(year)
        if year_dir.exists():
            for month_dir in sorted(year_dir.iterdir()):
                if month_dir.is_dir():
                    for day_dir in sorted(month_dir.iterdir()):
                        if day_dir.is_dir():
                            for json_file in day_dir.glob("*.json"):
                                try:
                                    with open(json_file, 'r', encoding='utf-8') as f:
                                        data = json.load(f)
                                        if "races" in data:
                                            races.extend(data["races"])
                                except Exception:
                                    continue
        
        for json_file in DATA_DIR.glob(f"results_{year}*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "races" in data:
                        races.extend(data["races"])
            except Exception:
                continue
        
        return races
    
    def extract_features(self, race_data: Dict) -> Tuple[RaceFeatures, List[HorseFeatures], Optional[RaceResult]]:
        race = RaceFeatures(
            race_id=race_data.get("race_id", ""),
            race_num=race_data.get("race_num", 0),
            venue=race_data.get("venue", ""),
            distance=race_data.get("distance", 0),
            track_type=race_data.get("track_type", ""),
            track_condition=race_data.get("track_condition", ""),
            grade=race_data.get("grade", ""),
            race_name=race_data.get("race_name", ""),
            date=race_data.get("date", ""),
        )
        
        horses = []
        all_results = race_data.get("all_results", [])
        top3 = race_data.get("top3", [])
        horse_list = all_results if all_results else top3
        
        for h in horse_list:
            horse = HorseFeatures(
                umaban=int(h.get("馬番", h.get("umaban", 0)) or 0),
                horse_name=h.get("馬名", h.get("horse_name", "")),
                odds=float(h.get("オッズ", h.get("odds", 0)) or 0),
                popularity=int(h.get("人気", h.get("popularity", 0)) or 0),
                weight=float(h.get("馬体重", h.get("weight", 0)) or 0),
                weight_diff=float(h.get("増減", h.get("weight_diff", 0)) or 0),
                jockey=h.get("騎手", h.get("jockey", "")),
                gate_num=int(h.get("枠番", h.get("gate_num", 0)) or 0),
            )
            horses.append(horse)
        
        result = None
        if top3:
            winner = top3[0] if top3 else {}
            result = RaceResult(
                race_id=race.race_id,
                winner_umaban=int(winner.get("馬番", winner.get("umaban", 0)) or 0),
                winner_odds=float(winner.get("オッズ", winner.get("odds", 0)) or 0),
                top3_umaban=[int(h.get("馬番", h.get("umaban", 0)) or 0) for h in top3[:3]],
            )
        
        return race, horses, result
    
    def evaluate_prediction(self, prediction: List[Tuple[int, str, float]], result: RaceResult) -> Dict:
        if not prediction or not result or result.winner_umaban == 0:
            return {"hit": False, "investment": 0, "return": 0}
        
        top_pick_umaban = prediction[0][0]
        hit = (top_pick_umaban == result.winner_umaban)
        investment = 100
        
        if hit and result.winner_odds > 0:
            payout = int(result.winner_odds * 100)
        else:
            payout = 0
        
        return {
            "hit": hit,
            "investment": investment,
            "return": payout,
            "predicted_umaban": top_pick_umaban,
            "winner_umaban": result.winner_umaban,
            "winner_odds": result.winner_odds,
        }
    
    def run_backtest(self, years: List[int], weights: Dict[str, float]) -> Dict:
        self.calculator.weights = weights
        for agent_name, agent in self.calculator.agents.items():
            agent.weight = weights.get(agent_name, agent.weight)
        
        total_races = 0
        total_hits = 0
        total_investment = 0
        total_return = 0
        
        for year in years:
            races = self.load_race_data(year)
            
            for race_data in races:
                race, horses, result = self.extract_features(race_data)
                
                if not horses or not result:
                    continue
                
                prediction = self.calculator.predict_race(horses, race)
                eval_result = self.evaluate_prediction(prediction, result)
                
                total_races += 1
                if eval_result["hit"]:
                    total_hits += 1
                total_investment += eval_result["investment"]
                total_return += eval_result["return"]
        
        hit_rate = total_hits / total_races if total_races > 0 else 0
        recovery_rate = total_return / total_investment if total_investment > 0 else 0
        
        return {
            "total_races": total_races,
            "total_hits": total_hits,
            "hit_rate": hit_rate,
            "recovery_rate": recovery_rate,
            "total_investment": total_investment,
            "total_return": total_return,
        }
    
    def optimize_weights(self, iterations: int = 100, learning_rate: float = 0.1) -> Dict:
        print("\n" + "=" * 60)
        print("🧠 重み最適化開始（厳格バックテスト版）")
        print("=" * 60)
        print(f"[INFO] 学習データ: {self.train_years}")
        print(f"[INFO] テストデータ: {self.test_years}")
        print(f"[INFO] イテレーション: {iterations}")
        print(f"[INFO] 学習率: {learning_rate}")
        
        best_weights = DEFAULT_WEIGHTS.copy()
        best_score = -float('inf')
        
        print("\n[PHASE 1] 学習データで最適化中...")
        
        for i in range(iterations):
            new_weights = {}
            for key in best_weights:
                delta = random.uniform(-learning_rate, learning_rate)
                new_weights[key] = max(0.05, min(0.9, best_weights[key] + delta))
            
            total = sum(new_weights.values())
            new_weights = {k: v / total for k, v in new_weights.items()}
            
            result = self.run_backtest(self.train_years, new_weights)
            score = result["recovery_rate"]
            
            if score > best_score:
                best_score = score
                best_weights = new_weights.copy()
                
                if (i + 1) % 20 == 0:
                    print(f"  [{i+1}/{iterations}] 回収率: {score*100:.2f}% (的中率: {result['hit_rate']*100:.2f}%)")
        
        print("\n[PHASE 2] テストデータで検証中...")
        train_result = self.run_backtest(self.train_years, best_weights)
        test_result = self.run_backtest(self.test_years, best_weights)
        
        print("\n" + "=" * 60)
        print("📊 最適化結果")
        print("=" * 60)
        
        print("\n【学習データ（Train）】")
        print(f"  対象レース数: {train_result['total_races']:,}")
        print(f"  的中数: {train_result['total_hits']:,}")
        print(f"  的中率: {train_result['hit_rate']*100:.2f}%")
        print(f"  回収率: {train_result['recovery_rate']*100:.2f}%")
        
        print("\n【テストデータ（Test）】")
        print(f"  対象レース数: {test_result['total_races']:,}")
        print(f"  的中数: {test_result['total_hits']:,}")
        print(f"  的中率: {test_result['hit_rate']*100:.2f}%")
        print(f"  回収率: {test_result['recovery_rate']*100:.2f}%")
        
        print("\n【最適化された重み】")
        for agent, weight in best_weights.items():
            print(f"  {agent}: {weight*100:.1f}%")
        
        result_data = {
            "weights": best_weights,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "train_metrics": {
                "years": self.train_years,
                "total_races": train_result["total_races"],
                "hit_rate": train_result["hit_rate"],
                "recovery_rate": train_result["recovery_rate"],
            },
            "test_metrics": {
                "years": self.test_years,
                "total_races": test_result["total_races"],
                "hit_rate": test_result["hit_rate"],
                "recovery_rate": test_result["recovery_rate"],
            },
            "metrics": {
                "total_races": test_result["total_races"],
                "correct_predictions": test_result["total_hits"],
                "hit_rate": test_result["hit_rate"],
                "recovery_rate": test_result["recovery_rate"],
                "total_investment": test_result["total_investment"],
                "total_return": test_result["total_return"],
            }
        }
        
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        with open(WEIGHTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 重みを保存しました: {WEIGHTS_FILE}")
        
        return result_data


# --- メイン関数 ---

def main():
    print("=" * 60)
    print("🧠 UMA-Logic PRO - アンサンブル学習エンジン")
    print("   （厳格バックテスト版 - データリーク防止）")
    print("   （多券種対応 + ケリー基準投資モデル）")
    print("=" * 60)
    
    args = sys.argv[1:]
    
    train_years = [2024]
    test_years = [2025]
    iterations = 100
    learning_rate = 0.1
    source_dir = None
    
    i = 0
    while i < len(args):
        if args[i] == "--optimize":
            i += 1
        elif args[i] == "--source" and i + 1 < len(args):
            source_dir = args[i + 1]
            if "2024" in source_dir:
                train_years = [2024]
                test_years = [2025]
            elif "2025" in source_dir:
                train_years = [2024]
                test_years = [2025]
            i += 2
        elif args[i] == "--train-years" and i + 1 < len(args):
            train_years = [int(y) for y in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--test-years" and i + 1 < len(args):
            test_years = [int(y) for y in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--iterations" and i + 1 < len(args):
            iterations = int(args[i + 1])
            i += 2
        elif args[i] == "--learning-rate" and i + 1 < len(args):
            learning_rate = float(args[i + 1])
            i += 2
        else:
            i += 1
    
    if "--optimize" in args or not args:
        backtester = StrictBacktester(train_years, test_years)
        result = backtester.optimize_weights(iterations, learning_rate)
        
        print("\n" + "=" * 60)
        print("✅ 処理完了")
        print("=" * 60)
    
    elif "--backtest" in args:
        backtester = StrictBacktester(train_years, test_years)
        
        print("\n[INFO] 現在の重みでバックテスト実行中...")
        
        weights = backtester.calculator.weights
        train_result = backtester.run_backtest(train_years, weights)
        test_result = backtester.run_backtest(test_years, weights)
        
        print("\n【学習データ】")
        print(f"  的中率: {train_result['hit_rate']*100:.2f}%")
        print(f"  回収率: {train_result['recovery_rate']*100:.2f}%")
        
        print("\n【テストデータ】")
        print(f"  的中率: {test_result['hit_rate']*100:.2f}%")
        print(f"  回収率: {test_result['recovery_rate']*100:.2f}%")
    
    elif "--show-weights" in args:
        calculator = IntegratedCalculator()
        print("\n【現在の重み】")
        for agent, weight in calculator.weights.items():
            print(f"  {agent}: {weight*100:.1f}%")
    
    else:
        print("\n使用方法:")
        print("  python ensemble_agents.py --optimize")
        print("  python ensemble_agents.py --optimize --train-years 2024 --test-years 2025")
        print("  python ensemble_agents.py --optimize --iterations 200 --learning-rate 0.05")
        print("  python ensemble_agents.py --backtest")
        print("  python ensemble_agents.py --show-weights")


if __name__ == "__main__":
    main()
