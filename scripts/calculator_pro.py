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
PREDICTIONS_PREFIX = "predictions_"
RESULTS_PREFIX = "results_"
ALERTS_FILE = DATA_DIR / "insider_alerts.json"

# デフォルトのエージェント重み
DEFAULT_WEIGHTS = {
    "speed": 0.35,
    "adaptability": 0.35,
    "pedigree": 0.30
}

# 枠順 × 脚質 × 距離 の評価マトリクス（1-10スケール）
GATE_STYLE_MATRIX = {
    ("短距離", "逃げ", "内"): 10, ("短距離", "逃げ", "中"): 8, ("短距離", "逃げ", "外"): 6,
    ("短距離", "先行", "内"): 9, ("短距離", "先行", "中"): 8, ("短距離", "先行", "外"): 7,
    ("短距離", "差し", "内"): 6, ("短距離", "差し", "中"): 7, ("短距離", "差し", "外"): 7,
    ("短距離", "追込", "内"): 4, ("短距離", "追込", "中"): 5, ("短距離", "追込", "外"): 6,
    ("中距離", "逃げ", "内"): 8, ("中距離", "逃げ", "中"): 8, ("中距離", "逃げ", "外"): 7,
    ("中距離", "先行", "内"): 9, ("中距離", "先行", "中"): 9, ("中距離", "先行", "外"): 8,
    ("中距離", "差し", "内"): 7, ("中距離", "差し", "中"): 8, ("中距離", "差し", "外"): 8,
    ("中距離", "追込", "内"): 5, ("中距離", "追込", "中"): 6, ("中距離", "追込", "外"): 7,
    ("長距離", "逃げ", "内"): 7, ("長距離", "逃げ", "中"): 7, ("長距離", "逃げ", "外"): 6,
    ("長距離", "先行", "内"): 8, ("長距離", "先行", "中"): 8, ("長距離", "先行", "外"): 8,
    ("長距離", "差し", "内"): 8, ("長距離", "差し", "中"): 9, ("長距離", "差し", "外"): 9,
    ("長距離", "追込", "内"): 6, ("長距離", "追込", "中"): 7, ("長距離", "追込", "外"): 8,
}

# 血統パターン（種牡馬 → 得意条件）
SIRE_PATTERNS = {
    "ディープインパクト": {"芝": 1.2, "ダート": 0.9, "中距離": 1.15, "長距離": 1.1},
    "キングカメハメハ": {"芝": 1.1, "ダート": 1.1, "中距離": 1.1, "短距離": 1.0},
    "ロードカナロア": {"芝": 1.15, "ダート": 0.95, "短距離": 1.2, "中距離": 1.0},
    "ハーツクライ": {"芝": 1.15, "ダート": 0.85, "中距離": 1.1, "長距離": 1.15},
    "エピファネイア": {"芝": 1.1, "ダート": 0.9, "中距離": 1.15, "長距離": 1.1},
    "ドゥラメンテ": {"芝": 1.15, "ダート": 0.9, "中距離": 1.15, "短距離": 1.0},
    "モーリス": {"芝": 1.1, "ダート": 0.95, "中距離": 1.1, "短距離": 1.05},
    "キタサンブラック": {"芝": 1.1, "ダート": 0.9, "中距離": 1.1, "長距離": 1.15},
    "サトノダイヤモンド": {"芝": 1.1, "ダート": 0.85, "中距離": 1.1, "長距離": 1.1},
    "オルフェーヴル": {"芝": 1.1, "ダート": 0.95, "中距離": 1.1, "長距離": 1.1},
}


# --- データクラス ---

@dataclass
class HorseData:
    """馬データ"""
    umaban: int = 0
    horse_name: str = ""
    jockey: str = ""
    trainer: str = ""
    weight: float = 0.0
    age: int = 0
    sex: str = ""
    odds: float = 0.0
    popularity: int = 0
    last_3_results: List[int] = field(default_factory=list)
    best_time: str = ""
    running_style: str = ""
    father: str = ""
    mother_father: str = ""
    wakuban: int = 0


@dataclass
class RaceCondition:
    """レース条件"""
    venue: str = ""
    distance: int = 0
    track_type: str = ""      # "芝" or "ダート"
    track_condition: str = "" # "良", "稍重", "重", "不良"
    grade: str = ""
    race_num: int = 0
    race_name: str = ""
    race_id: str = ""


@dataclass
class CalculationResult:
    """計算結果"""
    umaban: int
    horse_name: str
    uma_index: float          # UMA指数（0-100）
    win_probability: float    # 勝率（0-1）
    expected_value: float     # 期待値
    rank: str                 # S+, S, A, B, C, D
    speed_score: float
    adaptability_score: float
    pedigree_score: float
    confidence: float
    kelly_fraction: float = 0.0
    bet_amount: float = 0.0
    insider_alert: bool = False
    aggressive_mode: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


# --- 重み管理クラス ---

class WeightManager:
    """エージェント重みの管理"""

    def __init__(self):
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.weights = self._load_weights()

    def _load_weights(self) -> Dict[str, float]:
        """重みを読み込み"""
        if WEIGHTS_FILE.exists():
            try:
                with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("weights", DEFAULT_WEIGHTS.copy())
            except Exception:
                pass
        return DEFAULT_WEIGHTS.copy()

    def save_weights(self, weights: Dict[str, float]):
        """重みを保存"""
        data = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "weights": weights
        }
        with open(WEIGHTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.weights = weights

    def get_weight(self, agent_name: str) -> float:
        """エージェントの重みを取得"""
        return self.weights.get(agent_name, 0.33)


# --- スコア計算エージェント ---

class SpeedAgent:
    """
    スピードエージェント
    タイム解析に基づく勝率算出
    """

    def __init__(self, weight_manager: WeightManager):
        self.weight_manager = weight_manager
        self.name = "speed"

    def calculate(self, horse: HorseData, condition: RaceCondition) -> float:
        """
        スピードスコアを計算（0-100）
        """
        score = 50.0  # ベーススコア

        # 1. 過去成績による評価
        if horse.last_3_results:
            avg_rank = sum(horse.last_3_results) / len(horse.last_3_results)
            if avg_rank <= 2:
                score += 25
            elif avg_rank <= 3:
                score += 20
            elif avg_rank <= 5:
                score += 10
            elif avg_rank <= 8:
                score += 0
            else:
                score -= 10

        # 2. 人気による評価（オッズの逆数）
        if horse.odds > 0:
            if horse.odds <= 2.0:
                score += 20
            elif horse.odds <= 5.0:
                score += 15
            elif horse.odds <= 10.0:
                score += 10
            elif horse.odds <= 20.0:
                score += 5
            else:
                score -= 5

        # 3. 距離適性（ベストタイムから推定）
        if horse.best_time:
            try:
                parts = horse.best_time.split(":")
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = float(parts[1])
                    total_seconds = minutes * 60 + seconds

                    # 距離に対する標準タイムとの比較
                    standard_time = condition.distance / 16.0  # 秒速16m想定
                    if total_seconds < standard_time * 0.98:
                        score += 15
                    elif total_seconds < standard_time:
                        score += 10
            except Exception:
                pass

        # 4. 脚質と枠順の相性
        distance_cat = self._get_distance_category(condition.distance)
        gate_cat = self._get_gate_category(horse.wakuban, 18)  # 18頭立て想定
        style = horse.running_style if horse.running_style else "先行"

        gate_score = GATE_STYLE_MATRIX.get((distance_cat, style, gate_cat), 5)
        score += (gate_score - 5) * 3  # -12 to +15

        return max(0, min(100, score))

    def _get_distance_category(self, distance: int) -> str:
        if distance <= 1400:
            return "短距離"
        elif distance <= 2000:
            return "中距離"
        else:
            return "長距離"

    def _get_gate_category(self, wakuban: int, total_horses: int) -> str:
        if total_horses == 0:
            return "中"
        ratio = wakuban / total_horses
        if ratio <= 0.33:
            return "内"
        elif ratio <= 0.66:
            return "中"
        else:
            return "外"


class AdaptabilityAgent:
    """
    適性エージェント
    馬場適性・コース適性に基づく勝率算出
    """

    def __init__(self, weight_manager: WeightManager):
        self.weight_manager = weight_manager
        self.name = "adaptability"

    def calculate(self, horse: HorseData, condition: RaceCondition) -> float:
        """
        適性スコアを計算（0-100）
        """
        score = 50.0  # ベーススコア

        # 1. 馬場状態への適性
        track_cond = condition.track_condition
        if track_cond in ["良", ""]:
            # 良馬場は標準
            pass
        elif track_cond == "稍重":
            # 稍重は若干マイナス
            score -= 3
        elif track_cond == "重":
            # 重馬場は適性が分かれる
            if horse.father in ["キングカメハメハ", "ロードカナロア"]:
                score += 5
            else:
                score -= 5
        elif track_cond == "不良":
            # 不良馬場は大きく適性が分かれる
            if horse.father in ["キングカメハメハ"]:
                score += 10
            else:
                score -= 10

        # 2. コース適性（競馬場別）
        venue_scores = {
            "東京": {"差し": 10, "追込": 8, "先行": 5, "逃げ": 3},
            "中山": {"先行": 10, "逃げ": 8, "差し": 5, "追込": 3},
            "阪神": {"先行": 8, "差し": 8, "逃げ": 6, "追込": 5},
            "京都": {"差し": 10, "先行": 7, "追込": 7, "逃げ": 5},
            "中京": {"先行": 8, "差し": 7, "逃げ": 6, "追込": 5},
            "小倉": {"逃げ": 10, "先行": 8, "差し": 5, "追込": 3},
            "新潟": {"逃げ": 8, "先行": 8, "差し": 6, "追込": 5},
            "福島": {"先行": 9, "逃げ": 7, "差し": 5, "追込": 4},
            "札幌": {"先行": 8, "差し": 7, "逃げ": 6, "追込": 5},
            "函館": {"逃げ": 9, "先行": 8, "差し": 5, "追込": 4},
        }

        venue = condition.venue
        style = horse.running_style if horse.running_style else "先行"

        if venue in venue_scores and style in venue_scores[venue]:
            venue_bonus = venue_scores[venue][style]
            score += (venue_bonus - 5) * 3  # -6 to +15

        # 3. 芝/ダート適性
        track_type = condition.track_type
        if track_type == "芝":
            if horse.father in ["ディープインパクト", "ハーツクライ", "ロードカナロア"]:
                score += 10
        elif track_type == "ダート":
            if horse.father in ["キングカメハメハ"]:
                score += 10

        # 4. 年齢による適性
        if horse.age == 3:
            score += 5  # 3歳は成長期
        elif horse.age == 4:
            score += 8  # 4歳は充実期
        elif horse.age == 5:
            score += 5  # 5歳は安定期
        elif horse.age >= 6:
            score -= 5  # 6歳以上は衰え

        return max(0, min(100, score))


class PedigreeFormAgent:
    """
    血統・調子エージェント
    血統パターンと近走成績に基づく勝率算出
    """

    def __init__(self, weight_manager: WeightManager):
        self.weight_manager = weight_manager
        self.name = "pedigree"

    def calculate(self, horse: HorseData, condition: RaceCondition) -> float:
        """
        血統・調子スコアを計算（0-100）
        """
        score = 50.0  # ベーススコア

        # 1. 血統パターンによる評価
        father = horse.father
        if father in SIRE_PATTERNS:
            pattern = SIRE_PATTERNS[father]

            # 芝/ダート適性
            if condition.track_type in pattern:
                score += (pattern[condition.track_type] - 1.0) * 30

            # 距離適性
            distance_cat = self._get_distance_category(condition.distance)
            if distance_cat in pattern:
                score += (pattern[distance_cat] - 1.0) * 25

        # 2. 近走成績による調子判定
        if horse.last_3_results:
            # 上昇傾向かどうか
            if len(horse.last_3_results) >= 2:
                if horse.last_3_results[0] < horse.last_3_results[-1]:
                    score += 10  # 上昇傾向
                elif horse.last_3_results[0] > horse.last_3_results[-1]:
                    score -= 5   # 下降傾向

            # 連続好走
            good_runs = sum(1 for r in horse.last_3_results if r <= 3)
            score += good_runs * 5

        # 3. 騎手評価
        top_jockeys = [
            "ルメール", "川田将雅", "福永祐一", "武豊", "戸崎圭太",
            "横山武史", "松山弘平", "岩田望来", "坂井瑠星", "レーン"
        ]
        if horse.jockey in top_jockeys:
            score += 10

        # 4. 調教師評価
        top_trainers = [
            "矢作芳人", "国枝栄", "藤原英昭", "友道康夫", "堀宣行",
            "中内田充正", "木村哲也", "手塚貴久", "池江泰寿", "須貝尚介"
        ]
        if horse.trainer in top_trainers:
            score += 5

        return max(0, min(100, score))

    def _get_distance_category(self, distance: int) -> str:
        if distance <= 1400:
            return "短距離"
        elif distance <= 2000:
            return "中距離"
        else:
            return "長距離"


# --- メイン計算クラス ---

class IntegratedCalculator:
    """
    統合計算エンジン
    3つのエージェントを統合してUMA指数と期待値を算出
    """

    def __init__(self):
        self.weight_manager = WeightManager()
        self.agents = {
            "speed": SpeedAgent(self.weight_manager),
            "adaptability": AdaptabilityAgent(self.weight_manager),
            "pedigree": PedigreeFormAgent(self.weight_manager)
        }
        self.insider_alerts = self._load_insider_alerts()

    def _load_insider_alerts(self) -> Dict:
        """インサイダーアラートを読み込み"""
        if ALERTS_FILE.exists():
            try:
                with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"alerts": []}

    def calculate(
        self,
        horse: HorseData,
        condition: RaceCondition,
        bankroll: float = 100000
    ) -> CalculationResult:
        """
        馬のスコアを計算
        """
        # 各エージェントのスコアを計算
        speed_score = self.agents["speed"].calculate(horse, condition)
        adaptability_score = self.agents["adaptability"].calculate(horse, condition)
        pedigree_score = self.agents["pedigree"].calculate(horse, condition)

        # 重み付き平均でUMA指数を算出
        weights = self.weight_manager.weights
        uma_index = (
            speed_score * weights.get("speed", 0.35) +
            adaptability_score * weights.get("adaptability", 0.35) +
            pedigree_score * weights.get("pedigree", 0.30)
        )

        # 勝率を算出（UMA指数を確率に変換）
        # シグモイド関数で0-1に正規化
        win_probability = 1 / (1 + math.exp(-(uma_index - 50) / 15))
        win_probability = max(0.01, min(0.95, win_probability))

        # 期待値を算出
        if horse.odds > 0:
            expected_value = win_probability * horse.odds
        else:
            expected_value = 0

        # インサイダーアラートをチェック
        insider_alert = False
        aggressive_mode = False
        ev_boost = 1.0

        for alert in self.insider_alerts.get("alerts", []):
            if (alert.get("race_id") == condition.race_id and
                alert.get("umaban") == horse.umaban):
                insider_alert = True
                aggressive_mode = alert.get("aggressive_mode", False)
                ev_boost = alert.get("expected_value_boost", 1.0)
                break

        # インサイダー検知時は期待値をブースト
        if insider_alert:
            expected_value *= ev_boost
            win_probability = min(0.95, win_probability * 1.1)

        # ランクを決定
        rank = self._determine_rank(uma_index, expected_value)

        # 信頼度を計算
        confidence = self._calculate_confidence(
            speed_score, adaptability_score, pedigree_score
        )

        # ケリー基準で投資額を計算
        kelly_fraction, bet_amount = self._calculate_kelly(
            win_probability, horse.odds, bankroll, aggressive_mode
        )

        return CalculationResult(
            umaban=horse.umaban,
            horse_name=horse.horse_name,
            uma_index=round(uma_index, 1),
            win_probability=round(win_probability, 3),
            expected_value=round(expected_value, 2),
            rank=rank,
            speed_score=round(speed_score, 1),
            adaptability_score=round(adaptability_score, 1),
            pedigree_score=round(pedigree_score, 1),
            confidence=round(confidence, 2),
            kelly_fraction=round(kelly_fraction, 4),
            bet_amount=bet_amount,
            insider_alert=insider_alert,
            aggressive_mode=aggressive_mode
        )

    def _determine_rank(self, uma_index: float, expected_value: float) -> str:
        """ランクを決定"""
        if uma_index >= 75 and expected_value >= 1.5:
            return "S+"
        elif uma_index >= 70 and expected_value >= 1.3:
            return "S"
        elif uma_index >= 65 and expected_value >= 1.1:
            return "A"
        elif uma_index >= 55 and expected_value >= 0.9:
            return "B"
        elif uma_index >= 45:
            return "C"
        else:
            return "D"

    def _calculate_confidence(
        self,
        speed: float,
        adaptability: float,
        pedigree: float
    ) -> float:
        """
        信頼度を計算
        3つのスコアの一致度が高いほど信頼度が高い
        """
        scores = [speed, adaptability, pedigree]
        avg = sum(scores) / len(scores)
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)
        std_dev = math.sqrt(variance)

        # 標準偏差が小さいほど信頼度が高い
        confidence = max(0, 1 - std_dev / 30)
        return confidence

    def _calculate_kelly(
        self,
        win_probability: float,
        odds: float,
        bankroll: float,
        aggressive_mode: bool = False
    ) -> Tuple[float, float]:
        """
        ケリー基準で最適投資額を計算

        ケリー公式: f* = (bp - q) / b
        f*: 最適投資比率
        b: オッズ - 1（純利益倍率）
        p: 勝率
        q: 敗率（1 - p）

        通常モード: ハーフケリー（f* / 2）
        Aggressiveモード: フルケリー × 1.2
        """
        if odds <= 1 or win_probability <= 0:
            return 0.0, 0

        b = odds - 1  # 純利益倍率
        p = win_probability
        q = 1 - p

        # ケリー公式
        kelly = (b * p - q) / b

        # 負の値は賭けない
        if kelly <= 0:
            return 0.0, 0

        # モード別の乗数
        if aggressive_mode:
            # Aggressiveモード: フルケリー × 1.2
            kelly_multiplier = 1.2
        else:
            # 通常モード: ハーフケリー
            kelly_multiplier = 0.5

        final_kelly = kelly * kelly_multiplier

        # 上限設定（最大20%）
        final_kelly = min(0.20, final_kelly)

        # 下限設定（最小0.5%）
        if final_kelly < 0.005:
            return 0.0, 0

        # 賭け金計算（100円単位に丸め）
        bet_amount = bankroll * final_kelly
        bet_amount = round(bet_amount / 100) * 100
        bet_amount = max(0, int(bet_amount))

        return final_kelly, bet_amount

    def calculate_batch(
        self,
        horses: List[HorseData],
        condition: RaceCondition,
        bankroll: float = 100000
    ) -> List[CalculationResult]:
        """
        複数馬をまとめて計算
        """
        results = []
        for horse in horses:
            try:
                result = self.calculate(horse, condition, bankroll)
                results.append(result)
            except Exception as e:
                print(f"[WARN] 計算エラー ({horse.horse_name}): {e}")
                continue

        # UMA指数でソート
        results.sort(key=lambda x: x.uma_index, reverse=True)

        return results

    def process_predictions_file(
        self,
        predictions_file: Path,
        bankroll: float = 100000
    ) -> Dict:
        """
        予想ファイルを処理してスコアを計算
        """
        if not predictions_file.exists():
            print(f"[ERROR] ファイルが見つかりません: {predictions_file}")
            return {}

        try:
            with open(predictions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[ERROR] ファイル読み込みエラー: {e}")
            return {}

        races = data.get("races", [])
        processed_races = []

        for race in races:
            try:
                # レース条件を構築
                condition = RaceCondition(
                    venue=race.get("venue", ""),
                    distance=race.get("distance", 0),
                    track_type=race.get("track_type", "芝"),
                    track_condition=race.get("track_condition", "良"),
                    grade=race.get("grade", ""),
                    race_num=race.get("race_num", 0),
                    race_name=race.get("race_name", ""),
                    race_id=race.get("race_id", "")
                )

                # 馬データを構築
                horses = []
                for h in race.get("horses", []):
                    horse = HorseData(
                        umaban=h.get("umaban", 0),
                        horse_name=h.get("horse_name", ""),
                        jockey=h.get("jockey", ""),
                        trainer=h.get("trainer", ""),
                        weight=h.get("weight", 0),
                        age=h.get("age", 0),
                        sex=h.get("sex", ""),
                        odds=h.get("odds", 0),
                        popularity=h.get("popularity", 0),
                        last_3_results=h.get("last_3_results", []),
                        best_time=h.get("best_time", ""),
                        running_style=h.get("running_style", ""),
                        father=h.get("father", ""),
                        mother_father=h.get("mother_father", ""),
                        wakuban=h.get("wakuban", 0)
                    )
                    horses.append(horse)

                # 計算実行
                results = self.calculate_batch(horses, condition, bankroll)

                # 結果を追加
                processed_race = {
                    "race_id": condition.race_id,
                    "race_num": condition.race_num,
                    "race_name": condition.race_name,
                    "venue": condition.venue,
                    "distance": condition.distance,
                    "track_type": condition.track_type,
                    "predictions": [r.to_dict() for r in results]
                }
                processed_races.append(processed_race)

            except Exception as e:
                print(f"[WARN] レース処理エラー: {e}")
                continue

        # 結果を保存
        output_data = {
            "date": data.get("date", ""),
            "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bankroll": bankroll,
            "races": processed_races
        }

        return output_data


# --- メイン処理 ---

def main():
    print("=" * 60)
    print("🧮 UMA-Logic PRO - 高精度スコア計算エンジン")
    print("=" * 60)

    calculator = IntegratedCalculator()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--process":
            # 予想ファイルを処理
            today_str = datetime.now().strftime("%Y%m%d")
            predictions_file = DATA_DIR / f"{PREDICTIONS_PREFIX}{today_str}.json"

            bankroll = 100000
            if len(sys.argv) > 2:
                try:
                    bankroll = float(sys.argv[2])
                except ValueError:
                    pass

            print(f"\n[INFO] 予想ファイルを処理: {predictions_file}")
            print(f"[INFO] 資金: ¥{bankroll:,.0f}")

            result = calculator.process_predictions_file(predictions_file, bankroll)

            if result:
                output_file = DATA_DIR / f"calculated_{today_str}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n✅ 計算結果を保存: {output_file}")

        elif command == "--test":
            # テストモード
            print("\n📊 計算テスト")

            # テスト用馬データ
            test_horse = HorseData(
                umaban=5,
                horse_name="テストホース",
                jockey="ルメール",
                trainer="矢作芳人",
                weight=480,
                age=4,
                sex="牡",
                odds=5.0,
                popularity=2,
                last_3_results=[1, 2, 3],
                best_time="1:35.0",
                running_style="先行",
                father="ディープインパクト",
                mother_father="キングカメハメハ",
                wakuban=3
            )

            test_condition = RaceCondition(
                venue="東京",
                distance=1600,
                track_type="芝",
                track_condition="良",
                grade="G1",
                race_num=11,
                race_name="テストレース",
                race_id="TEST001"
            )

            result = calculator.calculate(test_horse, test_condition, bankroll=100000)

            print(f"\n  馬名: {result.horse_name}")
            print(f"  UMA指数: {result.uma_index}")
            print(f"  勝率: {result.win_probability*100:.1f}%")
            print(f"  期待値: {result.expected_value:.2f}")
            print(f"  ランク: {result.rank}")
            print(f"  信頼度: {result.confidence*100:.0f}%")
            print(f"\n  スピード: {result.speed_score}")
            print(f"  適性: {result.adaptability_score}")
            print(f"  血統: {result.pedigree_score}")
            print(f"\n  ケリー比率: {result.kelly_fraction*100:.2f}%")
            print(f"  推奨投資額: ¥{result.bet_amount:,}")

        elif command == "--kelly":
            # ケリー基準計算テスト
            print("\n📈 ケリー基準計算テスト")

            test_cases = [
                {"win_prob": 0.20, "odds": 5.0, "mode": "normal"},
                {"win_prob": 0.30, "odds": 4.0, "mode": "normal"},
                {"win_prob": 0.25, "odds": 6.0, "mode": "aggressive"},
                {"win_prob": 0.15, "odds": 10.0, "mode": "normal"},
            ]

            bankroll = 100000

            for case in test_cases:
                aggressive = case["mode"] == "aggressive"
                kelly, bet = calculator._calculate_kelly(
                    case["win_prob"], case["odds"], bankroll, aggressive
                )
                print(f"\n  勝率: {case['win_prob']*100:.0f}% / オッズ: {case['odds']:.1f} / モード: {case['mode']}")
                print(f"  → ケリー: {kelly*100:.2f}% / 推奨額: ¥{bet:,}")

        else:
            print(f"[ERROR] 不明なコマンド: {command}")
            print("\n使用方法:")
            print("  --process [bankroll] : 予想ファイルを処理")
            print("  --test               : テストモードで実行")
            print("  --kelly              : ケリー基準計算テスト")

    else:
        # デフォルト: 本日の予想ファイルを処理
        today_str = datetime.now().strftime("%Y%m%d")
        predictions_file = DATA_DIR / f"{PREDICTIONS_PREFIX}{today_str}.json"

        if predictions_file.exists():
            print(f"\n[INFO] 本日の予想ファイルを処理します")
            result = calculator.process_predictions_file(predictions_file)
            if result:
                output_file = DATA_DIR / f"calculated_{today_str}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n✅ 計算結果を保存: {output_file}")
        else:
            print(f"\n[INFO] 予想ファイルがありません: {predictions_file}")
            print("[INFO] --test オプションでテスト実行できます")

    print("\n✅ 処理完了")


if __name__ == "__main__":
    main()
