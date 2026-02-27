"""
血統スコアリングシステム
種牡馬のコース×距離別の適性を過去データから算出する
"""
import json
import sys
import io
import math
from pathlib import Path
from collections import defaultdict
from typing import Dict, Tuple

# Windows文字化け対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DATA_DIR = Path("data")
PEDIGREE_SCORES_PATH = DATA_DIR / "pedigree_scores.json"

# 距離カテゴリ定義
def get_distance_category(distance: int) -> str:
    if distance <= 1400:
        return "sprint"      # 短距離
    elif distance <= 1800:
        return "mile"        # マイル
    elif distance <= 2200:
        return "middle"      # 中距離
    else:
        return "long"        # 長距離

# 競馬場の特性タグ
VENUE_TAGS = {
    "中山": ["小回り", "急坂"],
    "東京": ["大箱", "直線長い"],
    "阪神": ["大箱", "急坂"],
    "京都": ["大箱", "平坦"],
    "小倉": ["小回り", "平坦"],
    "新潟": ["大箱", "直線長い"],
    "福島": ["小回り", "平坦"],
    "札幌": ["小回り", "洋芝"],
    "函館": ["小回り", "洋芝"],
    "中京": ["大箱", "急坂"]
}

class PedigreeScorer:
    def __init__(self):
        self.sire_stats = {}          # 種牡馬ごとの統計
        self.broodmare_sire_stats = {} # 母父ごとの統計
        self.scores = {}               # 計算済みスコア
        
    def build_from_data(self, start_date="20240101", end_date="20251231"):
        """過去データから種牡馬の統計を構築"""
        files = sorted(DATA_DIR.glob("results_*.json"))
        
        # 種牡馬×コース×距離の成績集計
        # key: (sire, course_type, distance_category)
        # value: {"runs": int, "top3": int, "wins": int, "total_odds": float}
        sire_data = defaultdict(lambda: {"runs": 0, "top3": 0, "wins": 0, "earnings": 0.0})
        bms_data = defaultdict(lambda: {"runs": 0, "top3": 0, "wins": 0, "earnings": 0.0})
        
        # 種牡馬×競馬場の成績も別途集計
        sire_venue_data = defaultdict(lambda: {"runs": 0, "top3": 0, "wins": 0})
        
        processed_races = 0
        processed_horses = 0
        
        for f in files:
            date_str = f.stem.replace("results_", "")
            if date_str < start_date or date_str > end_date:
                continue
                
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    
                for race in data.get("races", []):
                    course_type = race.get("track_type", "芝")
                    distance = int(race.get("distance", 1600))
                    dist_cat = get_distance_category(distance)
                    venue = race.get("venue", "")
                    
                    for horse in race.get("all_results", []):
                        father = horse.get("father", "")
                        mother_father = horse.get("mother_father", "")
                        rank = horse.get("着順", 99)
                        odds = float(horse.get("オッズ", 0) or 0)
                        
                        if not father or father == "不明":
                            continue
                            
                        # ---- 種牡馬 × コース × 距離 ----
                        key = f"{father}|{course_type}|{dist_cat}"
                        sire_data[key]["runs"] += 1
                        if isinstance(rank, int) and rank <= 3:
                            sire_data[key]["top3"] += 1
                        if isinstance(rank, int) and rank == 1:
                            sire_data[key]["wins"] += 1
                            sire_data[key]["earnings"] += odds * 100  # 100円換算
                        
                        # ---- 種牡馬 × 競馬場 ----
                        venue_key = f"{father}|{venue}"
                        sire_venue_data[venue_key]["runs"] += 1
                        if isinstance(rank, int) and rank <= 3:
                            sire_venue_data[venue_key]["top3"] += 1
                        if isinstance(rank, int) and rank == 1:
                            sire_venue_data[venue_key]["wins"] += 1
                        
                        # ---- 母父 × コース × 距離 ----
                        if mother_father and mother_father != "不明":
                            bms_key = f"{mother_father}|{course_type}|{dist_cat}"
                            bms_data[bms_key]["runs"] += 1
                            if isinstance(rank, int) and rank <= 3:
                                bms_data[bms_key]["top3"] += 1
                            if isinstance(rank, int) and rank == 1:
                                bms_data[bms_key]["wins"] += 1
                        
                        processed_horses += 1
                    processed_races += 1
                    
            except Exception as e:
                continue
        
        print(f"[INFO] 処理完了: {processed_races}レース, {processed_horses}頭")
        
        # スコア計算
        self._calculate_scores(sire_data, bms_data, sire_venue_data)
        
        # 保存
        self._save_scores()
        
        return self.scores
    
    def _calculate_scores(self, sire_data, bms_data, sire_venue_data):
        """ベイズ推定でスコアを計算（サンプル数が少ない場合は全体平均に回帰）"""
        
        # 全体平均（事前分布）
        total_runs = sum(v["runs"] for v in sire_data.values())
        total_top3 = sum(v["top3"] for v in sire_data.values())
        prior_rate = total_top3 / total_runs if total_runs > 0 else 0.3
        
        # サンプル数の閾値（これ以下は事前分布に引っ張られる）
        MIN_SAMPLES = 5
        CONFIDENCE_SAMPLES = 30  # この数以上あれば完全に実データを信頼
        
        scores = {
            "sire": {},       # 種牡馬スコア
            "bms": {},        # 母父スコア
            "sire_venue": {}, # 種牡馬×競馬場
            "metadata": {
                "total_races": 0,
                "total_horses": 0,
                "prior_top3_rate": round(prior_rate, 4)
            }
        }
        
        # 種牡馬×コース×距離スコア
        for key, stats in sire_data.items():
            n = stats["runs"]
            if n < 2:
                continue
                
            # ベイズ推定: 事後平均 = (n * 実績率 + k * 事前率) / (n + k)
            k = max(0, CONFIDENCE_SAMPLES - n)
            observed_rate = stats["top3"] / n
            bayesian_rate = (n * observed_rate + k * prior_rate) / (n + k)
            
            # 回収率ベースのボーナス
            if stats["wins"] > 0:
                roi = stats["earnings"] / (n * 100)  # 回収率
                roi_bonus = min(0.1, max(-0.1, (roi - 0.8) * 0.2))
            else:
                roi_bonus = -0.05
            
            score = round(bayesian_rate * 100 + roi_bonus * 10, 1)
            score = max(0, min(100, score))
            
            scores["sire"][key] = {
                "score": score,
                "runs": n,
                "top3": stats["top3"],
                "wins": stats["wins"],
                "top3_rate": round(observed_rate, 4),
                "confidence": round(min(1.0, n / CONFIDENCE_SAMPLES), 2)
            }
        
        # 母父スコア（同様の計算）
        for key, stats in bms_data.items():
            n = stats["runs"]
            if n < 2:
                continue
            k = max(0, CONFIDENCE_SAMPLES - n)
            observed_rate = stats["top3"] / n
            bayesian_rate = (n * observed_rate + k * prior_rate) / (n + k)
            score = round(bayesian_rate * 100, 1)
            score = max(0, min(100, score))
            
            scores["bms"][key] = {
                "score": score,
                "runs": n,
                "top3": stats["top3"],
                "top3_rate": round(observed_rate, 4)
            }
        
        # 種牡馬×競馬場スコア
        for key, stats in sire_venue_data.items():
            n = stats["runs"]
            if n < 2:
                continue
            k = max(0, CONFIDENCE_SAMPLES - n)
            observed_rate = stats["top3"] / n
            bayesian_rate = (n * observed_rate + k * prior_rate) / (n + k)
            score = round(bayesian_rate * 100, 1)
            
            scores["sire_venue"][key] = {
                "score": score,
                "runs": n,
                "top3": stats["top3"],
                "top3_rate": round(observed_rate, 4)
            }
        
        scores["metadata"]["total_races"] = sum(1 for v in sire_data.values())
        scores["metadata"]["total_horses"] = sum(v["runs"] for v in sire_data.values())
        
        self.scores = scores
        
        # 統計出力
        sire_count = len(scores["sire"])
        bms_count = len(scores["bms"])
        print(f"[INFO] 種牡馬スコア: {sire_count}件, 母父スコア: {bms_count}件")
        
        # トップ10表示
        top_sires = sorted(
            [(k, v) for k, v in scores["sire"].items() if v["runs"] >= 10],
            key=lambda x: x[1]["score"], reverse=True
        )[:10]
        
        print("\n[INFO] 種牡馬スコア TOP10 (出走10回以上):")
        for key, data in top_sires:
            parts = key.split("|")
            print(f"  {parts[0]} ({parts[1]}/{parts[2]}): スコア={data['score']}, "
                  f"3着内率={data['top3_rate']*100:.1f}%, 出走={data['runs']}")
    
    def _save_scores(self):
        """スコアをJSONに保存"""
        with open(PEDIGREE_SCORES_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.scores, f, ensure_ascii=False, indent=2)
        print(f"\n[INFO] 保存完了: {PEDIGREE_SCORES_PATH}")
    
    def load_scores(self) -> bool:
        """保存済みスコアをロード"""
        if PEDIGREE_SCORES_PATH.exists():
            with open(PEDIGREE_SCORES_PATH, 'r', encoding='utf-8') as f:
                self.scores = json.load(f)
            return True
        return False
    
    def get_sire_score(self, father: str, course_type: str, distance: int) -> float:
        """種牡馬のコース×距離スコアを取得"""
        if not self.scores:
            return 30.0  # デフォルト
            
        dist_cat = get_distance_category(distance)
        key = f"{father}|{course_type}|{dist_cat}"
        
        entry = self.scores.get("sire", {}).get(key)
        if entry:
            return entry["score"]
        
        # フォールバック: コース種別だけで探す
        fallback_scores = []
        for k, v in self.scores.get("sire", {}).items():
            if k.startswith(f"{father}|{course_type}|"):
                fallback_scores.append(v["score"])
        
        if fallback_scores:
            return sum(fallback_scores) / len(fallback_scores)
        
        return 30.0  # 未知の種牡馬
    
    def get_bms_score(self, mother_father: str, course_type: str, distance: int) -> float:
        """母父のコース×距離スコアを取得"""
        if not self.scores:
            return 30.0
            
        dist_cat = get_distance_category(distance)
        key = f"{mother_father}|{course_type}|{dist_cat}"
        
        entry = self.scores.get("bms", {}).get(key)
        if entry:
            return entry["score"]
        return 30.0
    
    def get_venue_score(self, father: str, venue: str) -> float:
        """種牡馬×競馬場スコアを取得"""
        if not self.scores:
            return 30.0
            
        key = f"{father}|{venue}"
        entry = self.scores.get("sire_venue", {}).get(key)
        if entry:
            return entry["score"]
        return 30.0


if __name__ == "__main__":
    scorer = PedigreeScorer()
    scorer.build_from_data()
