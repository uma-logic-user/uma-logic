# scripts/ensemble_agents.py
# UMA-Logic PRO - アンサンブル学習エンジン（自己学習機能付き）
# 3つのAIエージェントによる統合予測システム + 重み最適化

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import re

# --- 定数 ---
DATA_DIR = Path("data")
ARCHIVE_DIR = DATA_DIR / "archive"
MODELS_DIR = DATA_DIR / "models"
WEIGHTS_FILE = MODELS_DIR / "weights.json"
OPTIMIZATION_LOG_FILE = MODELS_DIR / "optimization_log.json"


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
    track_aptitude: Dict[str, float] = field(default_factory=dict)


@dataclass
class RaceCondition:
    """レース条件"""
    venue: str = ""
    distance: int = 0
    track_type: str = ""
    track_condition: str = ""
    grade: str = ""
    race_num: int = 0


@dataclass
class AgentPrediction:
    """エージェント予測結果"""
    agent_name: str
    win_probability: float
    confidence: float
    reasoning: str


@dataclass
class IntegratedPrediction:
    """統合予測結果"""
    umaban: int
    horse_name: str
    uma_index: float
    expected_value: float
    win_probability: float
    rank: str
    agent_predictions: List[AgentPrediction] = field(default_factory=list)
    insider_alert: bool = False
    kelly_fraction: float = 0.0


# --- 重み管理クラス ---

class WeightManager:
    """エージェント重みの保存・読み込み管理"""
    
    def __init__(self):
        self.default_weights = {
            "SpeedAgent": 0.35,
            "AdaptabilityAgent": 0.35,
            "PedigreeFormAgent": 0.30
        }
        self.weights = self.load_weights()
    
    def load_weights(self) -> Dict[str, float]:
        """保存された重みを読み込み"""
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        
        if WEIGHTS_FILE.exists():
            try:
                with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("weights", self.default_weights.copy())
            except Exception as e:
                print(f"[WARN] 重み読み込みエラー: {e}")
        
        return self.default_weights.copy()
    
    def save_weights(self, weights: Dict[str, float], metrics: Dict = None):
        """重みを保存"""
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        
        data = {
            "weights": weights,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "metrics": metrics or {}
        }
        
        with open(WEIGHTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.weights = weights
        print(f"[INFO] 重みを保存しました: {WEIGHTS_FILE}")
    
    def get_weight(self, agent_name: str) -> float:
        """エージェントの重みを取得"""
        return self.weights.get(agent_name, 0.33)


# --- スピードエージェント ---

class SpeedAgent:
    """タイム解析に特化したAI"""
    
    def __init__(self, weight_manager: WeightManager = None):
        self.name = "SpeedAgent"
        self.weight_manager = weight_manager
        self.base_times = {
            1000: 56.0, 1200: 68.0, 1400: 80.0, 1600: 92.0,
            1800: 104.0, 2000: 116.0, 2200: 128.0, 2400: 140.0,
            2500: 146.0, 3000: 176.0, 3200: 188.0, 3600: 212.0
        }
        self.track_adjustments = {"良": 0.0, "稍重": 0.5, "重": 1.5, "不良": 3.0}
    
    @property
    def weight(self) -> float:
        if self.weight_manager:
            return self.weight_manager.get_weight(self.name)
        return 0.35
    
    def parse_time(self, time_str: str) -> float:
        if not time_str:
            return 0.0
        try:
            if ":" in time_str:
                parts = time_str.split(":")
                return int(parts[0]) * 60 + float(parts[1])
            return float(time_str)
        except:
            return 0.0
    
    def get_base_time(self, distance: int) -> float:
        if distance in self.base_times:
            return self.base_times[distance]
        distances = sorted(self.base_times.keys())
        for i in range(len(distances) - 1):
            if distances[i] <= distance <= distances[i + 1]:
                ratio = (distance - distances[i]) / (distances[i + 1] - distances[i])
                return self.base_times[distances[i]] + ratio * (
                    self.base_times[distances[i + 1]] - self.base_times[distances[i]]
                )
        return 120.0
    
    def predict(self, horse: HorseData, condition: RaceCondition) -> AgentPrediction:
        base_time = self.get_base_time(condition.distance)
        track_adj = self.track_adjustments.get(condition.track_condition, 0.0)
        best_time = self.parse_time(horse.best_time)
        
        if best_time <= 0:
            return AgentPrediction(self.name, 0.05, 0.3, "タイムデータなし")
        
        time_diff = base_time - best_time + track_adj
        raw_score = max(0, min(100, 50 + time_diff * 5))
        win_prob = 1 / (1 + math.exp(-0.1 * (raw_score - 50)))
        
        confidence = 0.7 if best_time > 0 else 0.3
        
        if horse.running_style == "逃げ" and condition.distance <= 1400:
            win_prob *= 1.1
            reasoning = f"短距離逃げ馬優位 (ベスト{horse.best_time})"
        elif horse.running_style == "差し" and condition.distance >= 2000:
            win_prob *= 1.05
            reasoning = f"長距離差し馬優位 (ベスト{horse.best_time})"
        else:
            reasoning = f"タイム分析 (ベスト{horse.best_time})"
        
        return AgentPrediction(self.name, min(win_prob, 0.95), confidence, reasoning)


# --- 適応性エージェント ---

class AdaptabilityAgent:
    """馬場・コース適性に特化したAI"""
    
    def __init__(self, weight_manager: WeightManager = None):
        self.name = "AdaptabilityAgent"
        self.weight_manager = weight_manager
        self.venue_characteristics = {
            "東京": {"type": "大箱", "bias": "差し有利"},
            "中山": {"type": "小回り", "bias": "先行有利"},
            "阪神": {"type": "大箱", "bias": "フラット"},
            "京都": {"type": "大箱", "bias": "差し有利"},
            "中京": {"type": "中箱", "bias": "フラット"},
            "小倉": {"type": "小回り", "bias": "先行有利"},
            "新潟": {"type": "大箱", "bias": "差し有利"},
            "福島": {"type": "小回り", "bias": "先行有利"},
            "札幌": {"type": "小回り", "bias": "先行有利"},
            "函館": {"type": "小回り", "bias": "先行有利"},
        }
        self.style_compatibility = {
            ("逃げ", "先行有利"): 1.3, ("逃げ", "フラット"): 1.1, ("逃げ", "差し有利"): 0.9,
            ("先行", "先行有利"): 1.2, ("先行", "フラット"): 1.1, ("先行", "差し有利"): 1.0,
            ("差し", "先行有利"): 0.9, ("差し", "フラット"): 1.1, ("差し", "差し有利"): 1.3,
            ("追込", "先行有利"): 0.7, ("追込", "フラット"): 1.0, ("追込", "差し有利"): 1.4,
        }
    
    @property
    def weight(self) -> float:
        if self.weight_manager:
            return self.weight_manager.get_weight(self.name)
        return 0.35
    
    def predict(self, horse: HorseData, condition: RaceCondition) -> AgentPrediction:
        venue_info = self.venue_characteristics.get(condition.venue, {"bias": "フラット"})
        bias = venue_info.get("bias", "フラット")
        style = horse.running_style or "先行"
        compatibility = self.style_compatibility.get((style, bias), 1.0)
        
        track_aptitude = horse.track_aptitude.get(condition.track_type, 0.5)
        
        distance_score = 0.5
        if horse.last_3_results:
            avg_result = sum(horse.last_3_results) / len(horse.last_3_results)
            distance_score = max(0, 1 - (avg_result - 1) / 10)
        
        raw_score = compatibility * 30 + track_aptitude * 35 + distance_score * 35
        raw_score = max(0, min(100, raw_score))
        win_prob = raw_score / 100 * 0.3
        
        confidence = 0.6 if horse.track_aptitude else 0.4
        reasoning = f"{condition.venue}({bias}) × {style} 相性{compatibility:.1f}倍"
        
        return AgentPrediction(self.name, win_prob, confidence, reasoning)


# --- 血統・調子エージェント ---

class PedigreeFormAgent:
    """血統パターンと近走成績に特化したAI"""
    
    def __init__(self, weight_manager: WeightManager = None):
        self.name = "PedigreeFormAgent"
        self.weight_manager = weight_manager
        self.sire_distance_aptitude = {
            "ロードカナロア": {"min": 1000, "max": 1400, "peak": 1200},
            "ダイワメジャー": {"min": 1200, "max": 1800, "peak": 1600},
            "キンシャサノキセキ": {"min": 1000, "max": 1400, "peak": 1200},
            "ディープインパクト": {"min": 1600, "max": 2400, "peak": 2000},
            "キングカメハメハ": {"min": 1600, "max": 2400, "peak": 2000},
            "ハーツクライ": {"min": 1800, "max": 2500, "peak": 2200},
            "エピファネイア": {"min": 1800, "max": 2400, "peak": 2000},
            "キタサンブラック": {"min": 1800, "max": 3200, "peak": 2400},
            "ステイゴールド": {"min": 2000, "max": 3200, "peak": 2400},
            "オルフェーヴル": {"min": 2000, "max": 3000, "peak": 2400},
        }
        self.broodmare_sire_effect = {
            "サンデーサイレンス": 1.1,
            "キングカメハメハ": 1.08,
            "ディープインパクト": 1.05,
        }
    
    @property
    def weight(self) -> float:
        if self.weight_manager:
            return self.weight_manager.get_weight(self.name)
        return 0.30
    
    def calculate_pedigree_score(self, horse: HorseData, condition: RaceCondition) -> float:
        score = 50.0
        sire_info = self.sire_distance_aptitude.get(horse.father, {})
        if sire_info:
            peak = sire_info.get("peak", condition.distance)
            min_dist = sire_info.get("min", 0)
            max_dist = sire_info.get("max", 9999)
            
            if min_dist <= condition.distance <= max_dist:
                distance_diff = abs(condition.distance - peak)
                score = max(40, 90 - distance_diff / 30)
            else:
                score = 30
        
        bms_effect = self.broodmare_sire_effect.get(horse.mother_father, 1.0)
        score *= bms_effect
        
        return min(100, max(0, score))
    
    def calculate_form_score(self, results: List[int]) -> float:
        if not results:
            return 50.0
        
        weights = [0.4, 0.3, 0.2, 0.1]
        score = 50.0
        
        for i, result in enumerate(results[:4]):
            if i < len(weights):
                if result == 1:
                    score += 15 * weights[i]
                elif result == 2:
                    score += 10 * weights[i]
                elif result == 3:
                    score += 7 * weights[i]
                elif result <= 5:
                    score += 3 * weights[i]
                elif result <= 9:
                    score -= 3 * weights[i]
                else:
                    score -= 8 * weights[i]
        
        return max(0, min(100, score))
    
    def predict(self, horse: HorseData, condition: RaceCondition) -> AgentPrediction:
        pedigree_score = self.calculate_pedigree_score(horse, condition)
        form_score = self.calculate_form_score(horse.last_3_results)
        
        combined_score = pedigree_score * 0.4 + form_score * 0.6
        win_prob = combined_score / 100 * 0.25
        
        confidence = 0.5
        if horse.father in self.sire_distance_aptitude:
            confidence += 0.1
        if len(horse.last_3_results) >= 3:
            confidence += 0.1
        
        reasoning = f"血統:{horse.father or '不明'} 調子:{form_score:.0f}"
        
        return AgentPrediction(self.name, win_prob, confidence, reasoning)


# --- 重み最適化クラス ---

class WeightOptimizer:
    """
    過去データから最適な重みを学習
    グリッドサーチ + 評価指標による最適化
    """
    
    def __init__(self):
        self.weight_manager = WeightManager()
        self.optimization_history: List[Dict] = []
    
    def load_archive_data(self) -> List[Dict]:
        """アーカイブから過去データを読み込み"""
        all_data = []
        
        if not ARCHIVE_DIR.exists():
            print("[WARN] アーカイブディレクトリが存在しません")
            return all_data
        
        # 階層構造から読み込み
        for json_file in ARCHIVE_DIR.glob("**/*.json"):
            if json_file.name == "index.json":
                continue
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "races" in data:
                        all_data.append(data)
            except Exception as e:
                continue
        
        # data/ 直下からも読み込み
        for json_file in DATA_DIR.glob("results_*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "races" in data:
                        all_data.append(data)
            except Exception:
                continue
        
        print(f"[INFO] {len(all_data)}日分のデータを読み込みました")
        return all_data
    
    def evaluate_weights(
        self,
        weights: Dict[str, float],
        archive_data: List[Dict]
    ) -> Dict[str, float]:
        """
        指定された重みでの的中率・回収率を評価
        """
        total_races = 0
        correct_predictions = 0
        total_investment = 0
        total_return = 0
        
        # 一時的に重みを設定
        temp_manager = WeightManager()
        temp_manager.weights = weights
        
        agents = [
            SpeedAgent(temp_manager),
            AdaptabilityAgent(temp_manager),
            PedigreeFormAgent(temp_manager)
        ]
        
        for day_data in archive_data:
            races = day_data.get("races", [])
            
            for race in races:
                top3 = race.get("top3", [])
                all_results = race.get("all_results", top3)
                
                if not all_results or len(all_results) < 3:
                    continue
                
                # 1着馬の情報
                winner = all_results[0]
                winner_umaban = winner.get("馬番", 0)
                winner_odds = winner.get("オッズ", 0)
                
                if winner_umaban == 0 or winner_odds <= 0:
                    continue
                
                # 各馬のスコアを計算
                horse_scores = []
                
                for result in all_results:
                    horse = HorseData(
                        umaban=result.get("馬番", 0),
                        horse_name=result.get("馬名", ""),
                        jockey=result.get("騎手", ""),
                        odds=result.get("オッズ", 10.0),
                        running_style="先行"
                    )
                    
                    condition = RaceCondition(
                        venue=race.get("venue", ""),
                        distance=1600,
                        track_type="芝",
                        track_condition="良"
                    )
                    
                    # 各エージェントの予測
                    predictions = [agent.predict(horse, condition) for agent in agents]
                    
                    # 加重平均
                    total_weight = sum(agent.weight for agent in agents)
                    weighted_prob = sum(
                        pred.win_probability * agent.weight
                        for pred, agent in zip(predictions, agents)
                    ) / total_weight
                    
                    horse_scores.append({
                        "umaban": horse.umaban,
                        "score": weighted_prob,
                        "odds": horse.odds
                    })
                
                if not horse_scores:
                    continue
                
                # スコア順にソート
                horse_scores.sort(key=lambda x: x["score"], reverse=True)
                
                # 予測1位の馬
                predicted_winner = horse_scores[0]
                
                total_races += 1
                total_investment += 100  # 100円投資と仮定
                
                # 的中判定
                if predicted_winner["umaban"] == winner_umaban:
                    correct_predictions += 1
                    total_return += 100 * winner_odds
        
        # 評価指標
        hit_rate = correct_predictions / total_races if total_races > 0 else 0
        recovery_rate = total_return / total_investment if total_investment > 0 else 0
        
        return {
            "total_races": total_races,
            "correct_predictions": correct_predictions,
            "hit_rate": hit_rate,
            "recovery_rate": recovery_rate,
            "total_investment": total_investment,
            "total_return": total_return
        }
    
    def optimize_weights(
        self,
        grid_step: float = 0.05,
        min_weight: float = 0.1,
        max_weight: float = 0.6
    ) -> Dict[str, float]:
        """
        グリッドサーチで最適な重みを探索
        """
        print("=" * 60)
        print("🔄 重み最適化を開始")
        print("=" * 60)
        
        archive_data = self.load_archive_data()
        
        if not archive_data:
            print("[WARN] 最適化に必要なデータがありません")
            return self.weight_manager.weights
        
        best_weights = None
        best_score = -1
        best_metrics = {}
        
        # グリッドサーチ
        steps = int((max_weight - min_weight) / grid_step) + 1
        total_combinations = 0
        
        print(f"[INFO] グリッドサーチ開始 (ステップ: {grid_step})")
        
        for i in range(steps):
            w1 = min_weight + i * grid_step
            for j in range(steps):
                w2 = min_weight + j * grid_step
                w3 = 1.0 - w1 - w2
                
                # 重みの制約チェック
                if w3 < min_weight or w3 > max_weight:
                    continue
                
                weights = {
                    "SpeedAgent": round(w1, 2),
                    "AdaptabilityAgent": round(w2, 2),
                    "PedigreeFormAgent": round(w3, 2)
                }
                
                total_combinations += 1
                
                # 評価
                metrics = self.evaluate_weights(weights, archive_data)
                
                # スコア計算（回収率を重視、的中率も考慮）
                score = metrics["recovery_rate"] * 0.7 + metrics["hit_rate"] * 0.3
                
                if score > best_score:
                    best_score = score
                    best_weights = weights
                    best_metrics = metrics
                    print(f"  [UPDATE] 新しい最適解: {weights}")
                    print(f"           回収率: {metrics['recovery_rate']*100:.1f}% 的中率: {metrics['hit_rate']*100:.1f}%")
        
        print(f"\n[INFO] {total_combinations}通りの組み合わせを評価")
        
        if best_weights:
            print("\n" + "=" * 60)
            print("✅ 最適化完了")
            print("=" * 60)
            print(f"最適な重み:")
            print(f"  SpeedAgent:       {best_weights['SpeedAgent']:.2f}")
            print(f"  AdaptabilityAgent: {best_weights['AdaptabilityAgent']:.2f}")
            print(f"  PedigreeFormAgent: {best_weights['PedigreeFormAgent']:.2f}")
            print(f"\n評価指標:")
            print(f"  回収率: {best_metrics['recovery_rate']*100:.1f}%")
            print(f"  的中率: {best_metrics['hit_rate']*100:.1f}%")
            print(f"  評価レース数: {best_metrics['total_races']}")
            
            # 保存
            self.weight_manager.save_weights(best_weights, best_metrics)
            
            # 最適化ログを保存
            self._save_optimization_log(best_weights, best_metrics)
            
            return best_weights
        
        return self.weight_manager.weights
    
    def _save_optimization_log(self, weights: Dict, metrics: Dict):
        """最適化ログを保存"""
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "weights": weights,
            "metrics": metrics
        }
        
        # 既存ログを読み込み
        logs = []
        if OPTIMIZATION_LOG_FILE.exists():
            try:
                with open(OPTIMIZATION_LOG_FILE, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except:
                logs = []
        
        logs.append(log_entry)
        
        # 最新100件のみ保持
        logs = logs[-100:]
        
        with open(OPTIMIZATION_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)


# --- 統合計算クラス ---

class IntegratedCalculator:
    """3つのエージェントを統合してUMA指数と期待値を算出"""
    
    def __init__(self):
        self.weight_manager = WeightManager()
        self.agents = [
            SpeedAgent(self.weight_manager),
            AdaptabilityAgent(self.weight_manager),
            PedigreeFormAgent(self.weight_manager)
        ]
    
    def reload_weights(self):
        """重みを再読み込み"""
        self.weight_manager = WeightManager()
        for agent in self.agents:
            agent.weight_manager = self.weight_manager
        print("[INFO] 重みを再読み込みしました")
    
    def calculate(self, horse: HorseData, condition: RaceCondition) -> IntegratedPrediction:
        predictions = [agent.predict(horse, condition) for agent in self.agents]
        
        # 加重平均で勝率を算出
        total_weight = sum(agent.weight for agent in self.agents)
        weighted_prob = sum(
            pred.win_probability * agent.weight
            for pred, agent in zip(predictions, self.agents)
        ) / total_weight
        
        # UMA指数（0-100）
        uma_index = min(100, max(0, weighted_prob * 100 * 3))
        
        # 期待値
        expected_value = weighted_prob * horse.odds if horse.odds > 0 else 0
        
        # ランク判定
        if uma_index >= 75 and expected_value >= 1.2:
            rank = "S"
        elif uma_index >= 60 and expected_value >= 1.0:
            rank = "A"
        elif uma_index >= 45:
            rank = "B"
        else:
            rank = "C"
        
        # ケリー基準
        kelly = 0.0
        if horse.odds > 1 and weighted_prob > 0:
            b = horse.odds - 1
            kelly = max(0, (b * weighted_prob - (1 - weighted_prob)) / b)
        
        return IntegratedPrediction(
            umaban=horse.umaban,
            horse_name=horse.horse_name,
            uma_index=uma_index,
            expected_value=expected_value,
            win_probability=weighted_prob,
            rank=rank,
            agent_predictions=predictions,
            kelly_fraction=kelly * 0.5
        )


# --- メイン処理 ---

def main():
    import sys
    
    print("=" * 60)
    print("🤖 UMA-Logic PRO - アンサンブル学習エンジン")
    print("=" * 60)
    
    # コマンドライン引数で最適化モードを指定
    if len(sys.argv) > 1 and sys.argv[1] == "--optimize":
        optimizer = WeightOptimizer()
        optimizer.optimize_weights()
    else:
        # 通常の予測モード
        calculator = IntegratedCalculator()
        
        # 現在の重みを表示
        print("\n現在の重み:")
        for agent in calculator.agents:
            print(f"  {agent.name}: {agent.weight:.2f}")
        
        # テスト予測
        horse = HorseData(
            umaban=5, horse_name="テストホース", jockey="川田将雅",
            odds=5.0, last_3_results=[2, 1, 3], best_time="1:35.2",
            running_style="先行", father="ディープインパクト"
        )
        condition = RaceCondition(
            venue="東京", distance=1600, track_type="芝",
            track_condition="良", grade="G1", race_num=11
        )
        
        result = calculator.calculate(horse, condition)
        
        print(f"\n予測結果:")
        print(f"  馬名: {result.horse_name}")
        print(f"  UMA指数: {result.uma_index:.1f}")
        print(f"  期待値: {result.expected_value:.2f}")
        print(f"  勝率: {result.win_probability * 100:.1f}%")
        print(f"  ランク: {result.rank}")
    
    print("\n✅ 処理完了")


if __name__ == "__main__":
    main()
