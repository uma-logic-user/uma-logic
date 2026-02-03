# scripts/calculator_pro.py
# UMA-Logic PRO - 高精度スコア計算エンジン + ケリー基準資金管理
# 完全版（Full Code）- そのままコピー＆ペーストで動作

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import sys

# --- 定数 ---
DATA_DIR = Path("data")
MODELS_DIR = DATA_DIR / "models"
WEIGHTS_FILE = MODELS_DIR / "weights.json"
ALERTS_FILE = DATA_DIR / "insider_alerts.json"

# デフォルトのエージェント重み
DEFAULT_WEIGHTS = {
    "speed_agent": 0.35,
    "adaptability_agent": 0.35,
    "pedigree_agent": 0.30
}

# ケリー基準モード
KELLY_MODES = {
    "conservative": 0.25,
    "half": 0.50,
    "full": 1.00,
    "aggressive": 1.20
}


# --- データクラス ---

@dataclass
class HorseScore:
    """馬のスコア"""
    umaban: int
    horse_name: str
    speed_score: float = 0.0
    adaptability_score: float = 0.0
    pedigree_score: float = 0.0
    integrated_score: float = 0.0
    win_probability: float = 0.0
    expected_value: float = 0.0
    kelly_fraction: float = 0.0
    recommended_bet: int = 0
    insider_boost: float = 1.0
    confidence: float = 0.0


@dataclass
class RaceAnalysis:
    """レース分析結果"""
    race_id: str
    race_num: int
    venue: str
    race_name: str
    horses: List[HorseScore] = field(default_factory=list)
    top_picks: List[int] = field(default_factory=list)
    analysis_time: str = ""


# --- スピードエージェント ---

class SpeedAgent:
    """
    スピードエージェント
    タイム解析に基づいて勝率を算出
    """

    def __init__(self):
        self.name = "SpeedAgent"
        self.weight = DEFAULT_WEIGHTS["speed_agent"]

    def calculate_score(self, horse_data: Dict, race_condition: Dict) -> float:
        """
        スピードスコアを計算
        - 過去のタイムを距離で正規化
        - 上がり3Fタイムを評価
        - 走破タイムの安定性を評価
        """
        score = 50.0

        distance = race_condition.get("distance", 1600)

        best_time = horse_data.get("best_time", "")
        if best_time:
            try:
                if ":" in best_time:
                    parts = best_time.split(":")
                    seconds = float(parts[0]) * 60 + float(parts[1])
                else:
                    seconds = float(best_time)

                base_time = distance / 16.0
                time_diff = base_time - seconds

                score += time_diff * 5
            except (ValueError, IndexError):
                pass

        last_3f = horse_data.get("last_3f", 0)
        if last_3f:
            try:
                last_3f_val = float(last_3f)
                if last_3f_val < 33.0:
                    score += 15
                elif last_3f_val < 34.0:
                    score += 10
                elif last_3f_val < 35.0:
                    score += 5
                elif last_3f_val > 36.0:
                    score -= 5
            except ValueError:
                pass

        last_results = horse_data.get("last_3_results", [])
        if last_results:
            avg_position = sum(last_results) / len(last_results)
            if avg_position <= 2:
                score += 15
            elif avg_position <= 3:
                score += 10
            elif avg_position <= 5:
                score += 5
            elif avg_position > 10:
                score -= 10

        score = max(0, min(100, score))

        return score


# --- 適性エージェント ---

class AdaptabilityAgent:
    """
    適性エージェント
    馬場適性・距離適性・枠順適性を評価
    """

    def __init__(self):
        self.name = "AdaptabilityAgent"
        self.weight = DEFAULT_WEIGHTS["adaptability_agent"]

        self.gate_matrix = {
            ("短距離", "逃げ", "内"): 10,
            ("短距離", "逃げ", "中"): 8,
            ("短距離", "逃げ", "外"): 6,
            ("短距離", "先行", "内"): 9,
            ("短距離", "先行", "中"): 8,
            ("短距離", "先行", "外"): 7,
            ("短距離", "差し", "内"): 6,
            ("短距離", "差し", "中"): 7,
            ("短距離", "差し", "外"): 7,
            ("短距離", "追込", "内"): 4,
            ("短距離", "追込", "中"): 5,
            ("短距離", "追込", "外"): 6,
            ("中距離", "逃げ", "内"): 9,
            ("中距離", "逃げ", "中"): 8,
            ("中距離", "逃げ", "外"): 7,
            ("中距離", "先行", "内"): 9,
            ("中距離", "先行", "中"): 9,
            ("中距離", "先行", "外"): 8,
            ("中距離", "差し", "内"): 7,
            ("中距離", "差し", "中"): 8,
            ("中距離", "差し", "外"): 8,
            ("中距離", "追込", "内"): 5,
            ("中距離", "追込", "中"): 6,
            ("中距離", "追込", "外"): 7,
            ("長距離", "逃げ", "内"): 7,
            ("長距離", "逃げ", "中"): 7,
            ("長距離", "逃げ", "外"): 6,
            ("長距離", "先行", "内"): 8,
            ("長距離", "先行", "中"): 8,
            ("長距離", "先行", "外"): 8,
            ("長距離", "差し", "内"): 8,
            ("長距離", "差し", "中"): 9,
            ("長距離", "差し", "外"): 9,
            ("長距離", "追込", "内"): 7,
            ("長距離", "追込", "中"): 8,
            ("長距離", "追込", "外"): 9,
        }

    def _get_distance_category(self, distance: int) -> str:
        if distance <= 1400:
            return "短距離"
        elif distance <= 2000:
            return "中距離"
        else:
            return "長距離"

    def _get_gate_category(self, umaban: int, total_horses: int) -> str:
        ratio = umaban / max(total_horses, 1)
        if ratio <= 0.33:
            return "内"
        elif ratio <= 0.67:
            return "中"
        else:
            return "外"

    def calculate_score(self, horse_data: Dict, race_condition: Dict) -> float:
        """
        適性スコアを計算
        - 枠順 × 脚質 × 距離の相性
        - 馬場状態への適性
        - コース適性
        """
        score = 50.0

        distance = race_condition.get("distance", 1600)
        distance_cat = self._get_distance_category(distance)

        umaban = horse_data.get("umaban", 1)
        total_horses = race_condition.get("total_horses", 18)
        gate_cat = self._get_gate_category(umaban, total_horses)

        running_style = horse_data.get("running_style", "先行")

        gate_score = self.gate_matrix.get((distance_cat, running_style, gate_cat), 5)
        score += (gate_score - 5) * 5

        track_condition = race_condition.get("track_condition", "良")
        track_aptitude = horse_data.get("track_aptitude", {})

        if track_condition in track_aptitude:
            apt_score = track_aptitude[track_condition]
            score += (apt_score - 50) * 0.3

        if track_condition in ["重", "不良"]:
            if horse_data.get("heavy_track_wins", 0) > 0:
                score += 10

        venue = race_condition.get("venue", "")
        venue_wins = horse_data.get("venue_wins", {}).get(venue, 0)
        if venue_wins > 0:
            score += min(15, venue_wins * 5)

        score = max(0, min(100, score))

        return score


# --- 血統エージェント ---

class PedigreeAgent:
    """
    血統エージェント
    血統パターンに基づいて勝率を算出
    """

    def __init__(self):
        self.name = "PedigreeAgent"
        self.weight = DEFAULT_WEIGHTS["pedigree_agent"]

        self.sire_ratings = {
            "ディープインパクト": 95,
            "キングカメハメハ": 90,
            "ハーツクライ": 88,
            "ロードカナロア": 92,
            "エピファネイア": 85,
            "キタサンブラック": 88,
            "ドゥラメンテ": 87,
            "モーリス": 86,
            "オルフェーヴル": 84,
            "ルーラーシップ": 83,
            "ダイワメジャー": 82,
            "ゴールドシップ": 80,
            "ジャスタウェイ": 81,
            "リアルスティール": 79,
            "サトノダイヤモンド": 78,
        }

        self.distance_sire_aptitude = {
            "ディープインパクト": {"短距離": 70, "中距離": 95, "長距離": 90},
            "キングカメハメハ": {"短距離": 80, "中距離": 90, "長距離": 75},
            "ロードカナロア": {"短距離": 95, "中距離": 80, "長距離": 60},
            "ハーツクライ": {"短距離": 60, "中距離": 85, "長距離": 95},
            "キタサンブラック": {"短距離": 65, "中距離": 90, "長距離": 95},
        }

    def _get_distance_category(self, distance: int) -> str:
        if distance <= 1400:
            return "短距離"
        elif distance <= 2000:
            return "中距離"
        else:
            return "長距離"

    def calculate_score(self, horse_data: Dict, race_condition: Dict) -> float:
        """
        血統スコアを計算
        - 父の実績評価
        - 距離適性（血統ベース）
        - 母父の影響
        """
        score = 50.0

        father = horse_data.get("father", "")
        if father in self.sire_ratings:
            sire_score = self.sire_ratings[father]
            score += (sire_score - 80) * 0.5

        distance = race_condition.get("distance", 1600)
        distance_cat = self._get_distance_category(distance)

        if father in self.distance_sire_aptitude:
            apt = self.distance_sire_aptitude[father].get(distance_cat, 75)
            score += (apt - 75) * 0.3

        mother_father = horse_data.get("mother_father", "")
        if mother_father in self.sire_ratings:
            mf_score = self.sire_ratings[mother_father]
            score += (mf_score - 80) * 0.2

        score = max(0, min(100, score))

        return score


# --- 統合計算クラス ---

class IntegratedCalculator:
    """
    統合計算クラス
    3つのエージェントを統合してUMA指数と期待値を算出
    """

    def __init__(self):
        self.speed_agent = SpeedAgent()
        self.adaptability_agent = AdaptabilityAgent()
        self.pedigree_agent = PedigreeAgent()

        self.weights = self._load_weights()
        self.insider_alerts = self._load_insider_alerts()

    def _load_weights(self) -> Dict:
        """重みを読み込み"""
        if WEIGHTS_FILE.exists():
            try:
                with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return DEFAULT_WEIGHTS.copy()

    def _save_weights(self):
        """重みを保存"""
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        with open(WEIGHTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.weights, f, ensure_ascii=False, indent=2)

    def _load_insider_alerts(self) -> Dict:
        """インサイダーアラートを読み込み"""
        if ALERTS_FILE.exists():
            try:
                with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"alerts": []}

    def get_insider_boost(self, race_id: str, umaban: int) -> Tuple[float, bool]:
        """
        インサイダーブースト係数を取得
        returns: (boost_factor, aggressive_mode)
        """
        alerts = self.insider_alerts.get("alerts", [])

        for alert in alerts:
            if alert.get("status") != "active":
                continue
            if alert.get("race_id") == race_id and alert.get("umaban") == umaban:
                boost = alert.get("expected_value_boost", 1.0)
                aggressive = alert.get("aggressive_mode", False)
                return (boost, aggressive)

        return (1.0, False)

    def calculate_horse_score(
        self,
        horse_data: Dict,
        race_condition: Dict
    ) -> HorseScore:
        """馬のスコアを計算"""

        speed_score = self.speed_agent.calculate_score(horse_data, race_condition)
        adaptability_score = self.adaptability_agent.calculate_score(horse_data, race_condition)
        pedigree_score = self.pedigree_agent.calculate_score(horse_data, race_condition)

        integrated_score = (
            speed_score * self.weights.get("speed_agent", 0.35) +
            adaptability_score * self.weights.get("adaptability_agent", 0.35) +
            pedigree_score * self.weights.get("pedigree_agent", 0.30)
        )

        win_probability = self._score_to_probability(integrated_score)

        race_id = race_condition.get("race_id", "")
        umaban = horse_data.get("umaban", 0)
        insider_boost, aggressive_mode = self.get_insider_boost(race_id, umaban)

        odds = horse_data.get("odds", 10.0)
        expected_value = win_probability * odds * insider_boost

        confidence = min(1.0, integrated_score / 80)

        return HorseScore(
            umaban=umaban,
            horse_name=horse_data.get("horse_name", ""),
            speed_score=speed_score,
            adaptability_score=adaptability_score,
            pedigree_score=pedigree_score,
            integrated_score=integrated_score,
            win_probability=win_probability,
            expected_value=expected_value,
            insider_boost=insider_boost,
            confidence=confidence
        )

    def _score_to_probability(self, score: float) -> float:
        """スコアを勝率に変換"""
        normalized = (score - 30) / 50
        probability = 1 / (1 + math.exp(-normalized * 2))
        probability = probability * 0.4
        return max(0.01, min(0.5, probability))

    def calculate_kelly_bet(
        self,
        win_probability: float,
        odds: float,
        bankroll: int,
        mode: str = "half",
        aggressive_override: bool = False
    ) -> Tuple[float, int]:
        """
        ケリー基準で投資額を計算

        Args:
            win_probability: 勝率 (0-1)
            odds: オッズ
            bankroll: 総資金
            mode: ケリーモード (conservative/half/full/aggressive)
            aggressive_override: インサイダー検知時のアグレッシブモード強制

        Returns:
            (kelly_fraction, recommended_bet)
        """
        if aggressive_override:
            mode = "aggressive"

        b = odds - 1
        p = win_probability
        q = 1 - p

        if b <= 0 or p <= 0:
            return (0.0, 0)

        kelly = (b * p - q) / b

        kelly = max(0, kelly)

        mode_multiplier = KELLY_MODES.get(mode, 0.5)
        adjusted_kelly = kelly * mode_multiplier

        adjusted_kelly = min(0.25, adjusted_kelly)

        recommended_bet = int(bankroll * adjusted_kelly / 100) * 100

        return (adjusted_kelly, recommended_bet)

    def analyze_race(
        self,
        race_data: Dict,
        bankroll: int = 100000,
        kelly_mode: str = "half"
    ) -> RaceAnalysis:
        """レース全体を分析"""

        race_condition = {
            "race_id": race_data.get("race_id", ""),
            "distance": race_data.get("distance", 1600),
            "track_type": race_data.get("track_type", "芝"),
            "track_condition": race_data.get("track_condition", "良"),
            "venue": race_data.get("venue", ""),
            "total_horses": len(race_data.get("horses", []))
        }

        horse_scores = []

        for horse in race_data.get("horses", []):
            score = self.calculate_horse_score(horse, race_condition)

            _, aggressive = self.get_insider_boost(
                race_condition["race_id"],
                horse.get("umaban", 0)
            )

            kelly_fraction, recommended_bet = self.calculate_kelly_bet(
                score.win_probability,
                horse.get("odds", 10.0),
                bankroll,
                kelly_mode,
                aggressive
            )

            score.kelly_fraction = kelly_fraction
            score.recommended_bet = recommended_bet

            horse_scores.append(score)

        horse_scores.sort(key=lambda x: x.integrated_score, reverse=True)

        top_picks = [h.umaban for h in horse_scores[:3]]

        return RaceAnalysis(
            race_id=race_data.get("race_id", ""),
            race_num=race_data.get("race_num", 0),
            venue=race_data.get("venue", ""),
            race_name=race_data.get("race_name", ""),
            horses=horse_scores,
            top_picks=top_picks,
            analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )


# --- ケリー基準計算ユーティリティ ---

class KellyCalculator:
    """ケリー基準計算のユーティリティクラス"""

    @staticmethod
    def calculate(
        win_probability: float,
        odds: float,
        bankroll: int,
        mode: str = "half"
    ) -> Dict:
        """
        ケリー基準で投資額を計算

        Returns:
            {
                "kelly_fraction": float,
                "recommended_bet": int,
                "expected_value": float,
                "edge": float,
                "mode": str
            }
        """
        b = odds - 1
        p = win_probability
        q = 1 - p

        if b <= 0 or p <= 0:
            return {
                "kelly_fraction": 0,
                "recommended_bet": 0,
                "expected_value": 0,
                "edge": 0,
                "mode": mode
            }

        kelly = (b * p - q) / b
        kelly = max(0, kelly)

        mode_multiplier = KELLY_MODES.get(mode, 0.5)
        adjusted_kelly = kelly * mode_multiplier
        adjusted_kelly = min(0.25, adjusted_kelly)

        recommended_bet = int(bankroll * adjusted_kelly / 100) * 100

        expected_value = p * odds
        edge = expected_value - 1

        return {
            "kelly_fraction": adjusted_kelly,
            "recommended_bet": recommended_bet,
            "expected_value": expected_value,
            "edge": edge,
            "mode": mode
        }

    @staticmethod
    def calculate_portfolio(
        bets: List[Dict],
        bankroll: int,
        mode: str = "half",
        max_total_fraction: float = 0.5
    ) -> List[Dict]:
        """
        複数の賭けに対するポートフォリオ配分を計算

        Args:
            bets: [{"win_probability": float, "odds": float, "name": str}, ...]
            bankroll: 総資金
            mode: ケリーモード
            max_total_fraction: 最大投資比率

        Returns:
            配分結果のリスト
        """
        results = []
        total_fraction = 0

        for bet in bets:
            result = KellyCalculator.calculate(
                bet["win_probability"],
                bet["odds"],
                bankroll,
                mode
            )
            result["name"] = bet.get("name", "")
            results.append(result)
            total_fraction += result["kelly_fraction"]

        if total_fraction > max_total_fraction:
            scale = max_total_fraction / total_fraction
            for result in results:
                result["kelly_fraction"] *= scale
                result["recommended_bet"] = int(bankroll * result["kelly_fraction"] / 100) * 100

        return results


# --- メイン処理 ---

def main():
    print("=" * 60)
    print("🧮 UMA-Logic PRO - 高精度スコア計算エンジン")
    print("=" * 60)

    calculator = IntegratedCalculator()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--kelly":
            print("\n💰 ケリー基準シミュレーター")
            print("-" * 40)

            prob = float(sys.argv[2]) if len(sys.argv) > 2 else 0.2
            odds = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
            bankroll = int(sys.argv[4]) if len(sys.argv) > 4 else 100000

            print(f"勝率: {prob*100:.1f}%")
            print(f"オッズ: {odds:.1f}")
            print(f"資金: ¥{bankroll:,}")

            for mode in ["conservative", "half", "full", "aggressive"]:
                result = KellyCalculator.calculate(prob, odds, bankroll, mode)
                print(f"\n{mode.upper()}:")
                print(f"  投資比率: {result['kelly_fraction']*100:.2f}%")
                print(f"  推奨投資額: ¥{result['recommended_bet']:,}")
                print(f"  期待値: {result['expected_value']:.2f}")

        elif command == "--analyze":
            print("\n📊 レース分析デモ")

            demo_race = {
                "race_id": "202401010101",
                "race_num": 1,
                "venue": "中山",
                "race_name": "3歳未勝利",
                "distance": 1600,
                "track_type": "芝",
                "track_condition": "良",
                "horses": [
                    {"umaban": 1, "horse_name": "テスト馬A", "odds": 3.5, "father": "ディープインパクト"},
                    {"umaban": 2, "horse_name": "テスト馬B", "odds": 5.0, "father": "キングカメハメハ"},
                    {"umaban": 3, "horse_name": "テスト馬C", "odds": 8.0, "father": "ロードカナロア"},
                ]
            }

            analysis = calculator.analyze_race(demo_race)

            print(f"\nレース: {analysis.venue} {analysis.race_num}R {analysis.race_name}")
            print("-" * 40)

            for horse in analysis.horses:
                print(f"\n{horse.umaban}番 {horse.horse_name}")
                print(f"  統合スコア: {horse.integrated_score:.1f}")
                print(f"  勝率: {horse.win_probability*100:.1f}%")
                print(f" 