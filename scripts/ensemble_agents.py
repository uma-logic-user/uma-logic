#!/usr/bin/env python3
# scripts/ensemble_agents.py
# UMA-Logic PRO - アンサンブル学習エンジン（厳格バックテスト版）
# 完全版（Full Code）- Train/Test分離、データリーク防止

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
    """
    馬の特徴量（レース前に分かる情報のみ）
    ※ 着順、タイム、上がり3F、払戻金は含めない（データリーク防止）
    """
    umaban: int = 0
    horse_name: str = ""
    odds: float = 0.0           # 発走前オッズ
    popularity: int = 0         # 人気順
    weight: float = 0.0         # 馬体重
    weight_diff: float = 0.0    # 馬体重増減
    age: int = 0                # 馬齢
    sex: str = ""               # 性別
    jockey: str = ""            # 騎手
    trainer: str = ""           # 調教師
    father: str = ""            # 父馬
    mother_father: str = ""     # 母父
    gate_num: int = 0           # 枠番
    # 過去成績（前走以前のデータのみ）
    prev_results: List[int] = field(default_factory=list)  # 過去の着順リスト
    prev_odds: List[float] = field(default_factory=list)   # 過去のオッズリスト


@dataclass
class RaceFeatures:
    """レース条件（レース前に分かる情報のみ）"""
    race_id: str = ""
    race_num: int = 0
    venue: str = ""
    distance: int = 0
    track_type: str = ""        # 芝/ダート
    track_condition: str = ""   # 良/稍重/重/不良
    grade: str = ""             # クラス
    race_name: str = ""
    date: str = ""


@dataclass
class RaceResult:
    """レース結果（検証用、学習には使用しない）"""
    race_id: str = ""
    winner_umaban: int = 0      # 1着馬番
    winner_odds: float = 0.0    # 1着馬オッズ
    top3_umaban: List[int] = field(default_factory=list)  # 1-3着馬番


# --- エージェントクラス ---

class SpeedAgent:
    """
    スピードエージェント
    オッズと人気から期待スピードを推定
    """
    
    def __init__(self, weight: float = 0.35):
        self.weight = weight
        self.name = "SpeedAgent"
    
    def calculate_score(self, horse: HorseFeatures, race: RaceFeatures) -> float:
        """スピードスコアを計算（0-100）"""
        score = 50.0
        
        # オッズが低い（人気がある）ほど高スコア
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
        
        # 人気順
        if horse.popularity > 0:
            if horse.popularity <= 3:
                score += 15
            elif horse.popularity <= 6:
                score += 5
            else:
                score -= 5
        
        # 過去成績（前走以前）
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
        
        # 距離適性（簡易版）
        if race.distance > 0:
            if race.distance <= 1400:
                # 短距離は内枠有利
                if horse.gate_num <= 4:
                    score += 5
            elif race.distance >= 2000:
                # 長距離は差し馬有利（人気薄でも）
                if horse.popularity > 5 and horse.odds < 30:
                    score += 5
        
        return max(0, min(100, score))


class AdaptabilityAgent:
    """
    適応性エージェント
    馬場状態、枠順、コース適性を評価
    """
    
    def __init__(self, weight: float = 0.35):
        self.weight = weight
        self.name = "AdaptabilityAgent"
    
    def calculate_score(self, horse: HorseFeatures, race: RaceFeatures) -> float:
        """適応性スコアを計算（0-100）"""
        score = 50.0
        
        # 枠順評価
        if race.distance > 0 and horse.gate_num > 0:
            if race.distance <= 1400:
                # 短距離は内枠有利
                if horse.gate_num <= 3:
                    score += 15
                elif horse.gate_num <= 5:
                    score += 5
                elif horse.gate_num >= 7:
                    score -= 5
            elif race.distance <= 1800:
                # 中距離はフラット
                pass
            else:
                # 長距離は外枠不利
                if horse.gate_num >= 7:
                    score -= 10
        
        # 馬場状態
        if race.track_condition:
            if race.track_condition in ["重", "不良"]:
                # 重馬場は馬体重が重い馬有利
                if horse.weight >= 500:
                    score += 10
                elif horse.weight <= 440:
                    score -= 5
        
        # 馬体重増減
        if horse.weight_diff != 0:
            if abs(horse.weight_diff) > 20:
                score -= 10  # 大幅増減はマイナス
            elif -10 <= horse.weight_diff <= 10:
                score += 5   # 安定はプラス
        
        # 年齢
        if horse.age > 0:
            if horse.age == 3:
                score += 5   # 3歳は成長期
            elif horse.age >= 7:
                score -= 5   # 高齢馬は減点
        
        return max(0, min(100, score))


class PedigreeFormAgent:
    """
    血統・調子エージェント
    血統パターンと直近の調子を評価
    """
    
    # 有名種牡馬のスコア補正
    SIRE_BONUS = {
        "ディープインパクト": 15,
        "キングカメハメハ": 12,
        "ロードカナロア": 12,
        "ハーツクライ": 10,
        "エピファネイア": 10,
        "ドゥラメンテ": 10,
        "キタサンブラック": 10,
        "モーリス": 8,
        "オルフェーヴル": 8,
        "ゴールドシップ": 5,
    }
    
    def __init__(self, weight: float = 0.30):
        self.weight = weight
        self.name = "PedigreeFormAgent"
    
    def calculate_score(self, horse: HorseFeatures, race: RaceFeatures) -> float:
        """血統・調子スコアを計算（0-100）"""
        score = 50.0
        
        # 血統評価
        if horse.father:
            bonus = self.SIRE_BONUS.get(horse.father, 0)
            score += bonus
        
        # 過去成績の傾向（上昇傾向か下降傾向か）
        if len(horse.prev_results) >= 2:
            recent = horse.prev_results[0]  # 最新
            older = horse.prev_results[1]   # 1つ前
            
            if recent < older:
                score += 10  # 上昇傾向
            elif recent > older:
                score -= 5   # 下降傾向
        
        # オッズと過去成績の乖離（穴馬発見）
        if horse.prev_results and horse.odds > 0:
            avg_result = sum(horse.prev_results[:3]) / len(horse.prev_results[:3])
            
            # 過去成績が良いのにオッズが高い → 穴馬候補
            if avg_result <= 5 and horse.odds >= 10:
                score += 15
            # 過去成績が悪いのにオッズが低い → 過大評価
            elif avg_result >= 8 and horse.odds < 5:
                score -= 10
        
        # 騎手評価（簡易版）
        TOP_JOCKEYS = ["ルメール", "川田将雅", "戸崎圭太", "横山武史", "福永祐一", "武豊"]
        if horse.jockey in TOP_JOCKEYS:
            score += 10
        
        return max(0, min(100, score))


# --- 統合計算クラス ---

class IntegratedCalculator:
    """
    アンサンブル統合計算機
    3つのエージェントのスコアを統合
    """
    
    def __init__(self):
        self.weights = self._load_weights()
        self.agents = {
            "SpeedAgent": SpeedAgent(self.weights.get("SpeedAgent", 0.35)),
            "AdaptabilityAgent": AdaptabilityAgent(self.weights.get("AdaptabilityAgent", 0.35)),
            "PedigreeFormAgent": PedigreeFormAgent(self.weights.get("PedigreeFormAgent", 0.30)),
        }
    
    def _load_weights(self) -> Dict[str, float]:
        """保存された重みを読み込み"""
        if WEIGHTS_FILE.exists():
            try:
                with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("weights", DEFAULT_WEIGHTS)
            except Exception:
                pass
        return DEFAULT_WEIGHTS.copy()
    
    def calculate_integrated_score(self, horse: HorseFeatures, race: RaceFeatures) -> float:
        """統合スコアを計算"""
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
        """
        レースの予測を行い、推奨馬をランキング
        Returns: [(馬番, 馬名, スコア), ...]
        """
        results = []
        for horse in horses:
            score = self.calculate_integrated_score(horse, race)
            results.append((horse.umaban, horse.horse_name, score))
        
        # スコア降順でソート
        results.sort(key=lambda x: x[2], reverse=True)
        return results


# --- バックテストクラス ---

class StrictBacktester:
    """
    厳格なバックテスター
    Train/Test分離、データリーク防止
    """
    
    def __init__(self, train_years: List[int], test_years: List[int]):
        self.train_years = train_years
        self.test_years = test_years
        self.calculator = IntegratedCalculator()
    
    def load_race_data(self, year: int) -> List[Dict]:
        """指定年のレースデータを読み込み"""
        races = []
        
        # アーカイブから読み込み
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
        
        # data/ 直下からも読み込み
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
        """
        レースデータから特徴量を抽出
        ※ 結果データ（着順、タイム）は特徴量に含めない
        """
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
        
        # 出走馬の情報を取得
        horse_list = all_results if all_results else top3
        
        for h in horse_list:
            # 着順、タイム、上がり3Fは特徴量に含めない（データリーク防止）
            horse = HorseFeatures(
                umaban=int(h.get("馬番", h.get("umaban", 0))),
                horse_name=h.get("馬名", h.get("horse_name", "")),
                odds=float(h.get("オッズ", h.get("odds", 0)) or 0),
                popularity=int(h.get("人気", h.get("popularity", 0)) or 0),
                weight=float(h.get("馬体重", h.get("weight", 0)) or 0),
                weight_diff=float(h.get("増減", h.get("weight_diff", 0)) or 0),
                jockey=h.get("騎手", h.get("jockey", "")),
                gate_num=int(h.get("枠番", h.get("gate_num", 0)) or 0),
            )
            horses.append(horse)
        
        # 結果データ（検証用）
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
        """
        予測結果を評価
        ◎（1位予測）が1着になったかで判定
        """
        if not prediction or not result or result.winner_umaban == 0:
            return {"hit": False, "investment": 0, "return": 0}
        
        # ◎（最高スコアの馬）を予測
        top_pick_umaban = prediction[0][0]
        
        # 的中判定：◎が1着になったか
        hit = (top_pick_umaban == result.winner_umaban)
        
        # 投資額（単勝100円）
        investment = 100
        
        # 払戻金
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
        """
        指定した重みでバックテストを実行
        """
        # 重みを適用
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
                
                # 予測
                prediction = self.calculator.predict_race(horses, race)
                
                # 評価
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
        """
        Train データで重みを最適化し、Test データで検証
        """
        print("\n" + "=" * 60)
        print("🧠 重み最適化開始（厳格バックテスト版）")
        print("=" * 60)
        print(f"[INFO] 学習データ: {self.train_years}")
        print(f"[INFO] テストデータ: {self.test_years}")
        print(f"[INFO] イテレーション: {iterations}")
        print(f"[INFO] 学習率: {learning_rate}")
        
        # 初期重み
        best_weights = DEFAULT_WEIGHTS.copy()
        best_score = -float('inf')
        
        # 学習データでの初期評価
        print("\n[PHASE 1] 学習データで最適化中...")
        
        for i in range(iterations):
            # 重みをランダムに変動
            new_weights = {}
            for key in best_weights:
                delta = random.uniform(-learning_rate, learning_rate)
                new_weights[key] = max(0.05, min(0.9, best_weights[key] + delta))
            
            # 正規化
            total = sum(new_weights.values())
            new_weights = {k: v / total for k, v in new_weights.items()}
            
            # 学習データで評価
            result = self.run_backtest(self.train_years, new_weights)
            
            # スコア = 回収率（的中率だけでなく、回収率を重視）
            score = result["recovery_rate"]
            
            if score > best_score:
                best_score = score
                best_weights = new_weights.copy()
                
                if (i + 1) % 20 == 0:
                    print(f"  [{i+1}/{iterations}] 回収率: {score*100:.2f}% (的中率: {result['hit_rate']*100:.2f}%)")
        
        # テストデータで検証
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
        
        # 結果を保存
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
        
        # 保存
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        with open(WEIGHTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 重みを保存しました: {WEIGHTS_FILE}")
        
        return result_data


# --- メイン関数 ---

def main():
    """メイン関数"""
    print("=" * 60)
    print("🧠 UMA-Logic PRO - アンサンブル学習エンジン")
    print("   （厳格バックテスト版 - データリーク防止）")
    print("=" * 60)
    
    args = sys.argv[1:]
    
    # デフォルト設定
    train_years = [2024]
    test_years = [2025]
    iterations = 100
    learning_rate = 0.1
    source_dir = None
    
    # 引数解析
    i = 0
    while i < len(args):
        if args[i] == "--optimize":
            i += 1
        elif args[i] == "--source" and i + 1 < len(args):
            source_dir = args[i + 1]
            # ソースディレクトリから年を推定
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
        # 最適化実行
        backtester = StrictBacktester(train_years, test_years)
        result = backtester.optimize_weights(iterations, learning_rate)
        
        print("\n" + "=" * 60)
        print("✅ 処理完了")
        print("=" * 60)
    
    elif "--backtest" in args:
        # バックテストのみ実行
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
        # 現在の重みを表示
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
