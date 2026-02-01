# scripts/calculator_pro.py
# UMA-Logic Pro - 高精度スコア計算エンジン
# 10段階枠順評価、信頼区間算出、動的期待値計算を実装

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# scipy がインストールされていない環境でも動作するようにフォールバック
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("[WARN] scipy が見つかりません。信頼区間計算は簡易版を使用します。")

# --- 定数 ---
DATA_DIR = Path("data")

# 枠順 × 脚質 × 距離 の10段階評価マトリクス
# キー: (距離カテゴリ, 脚質, 枠番カテゴリ) → スコア(1-10)
GATE_STYLE_MATRIX = {
    # 短距離（〜1400m）
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
    
    # マイル（1600m）
    ("マイル", "逃げ", "内"): 9,
    ("マイル", "逃げ", "中"): 8,
    ("マイル", "逃げ", "外"): 6,
    ("マイル", "先行", "内"): 9,
    ("マイル", "先行", "中"): 8,
    ("マイル", "先行", "外"): 7,
    ("マイル", "差し", "内"): 7,
    ("マイル", "差し", "中"): 8,
    ("マイル", "差し", "外"): 7,
    ("マイル", "追込", "内"): 5,
    ("マイル", "追込", "中"): 6,
    ("マイル", "追込", "外"): 6,
    
    # 中距離（1800-2200m）
    ("中距離", "逃げ", "内"): 8,
    ("中距離", "逃げ", "中"): 7,
    ("中距離", "逃げ", "外"): 5,
    ("中距離", "先行", "内"): 9,
    ("中距離", "先行", "中"): 8,
    ("中距離", "先行", "外"): 7,
    ("中距離", "差し", "内"): 8,
    ("中距離", "差し", "中"): 9,
    ("中距離", "差し", "外"): 8,
    ("中距離", "追込", "内"): 6,
    ("中距離", "追込", "中"): 7,
    ("中距離", "追込", "外"): 7,
    
    # 長距離（2400m〜）
    ("長距離", "逃げ", "内"): 7,
    ("長距離", "逃げ", "中"): 6,
    ("長距離", "逃げ", "外"): 4,
    ("長距離", "先行", "内"): 8,
    ("長距離", "先行", "中"): 8,
    ("長距離", "先行", "外"): 7,
    ("長距離", "差し", "内"): 9,
    ("長距離", "差し", "中"): 9,
    ("長距離", "差し", "外"): 8,
    ("長距離", "追込", "内"): 8,
    ("長距離", "追込", "中"): 9,
    ("長距離", "追込", "外"): 9,
}


@dataclass
class ConfidenceInterval:
    """信頼区間データ"""
    lower: float  # 下限
    upper: float  # 上限
    mean: float   # 平均（推定値）
    confidence: float  # 信頼度（0.95など）


@dataclass
class ExpectedValue:
    """期待値データ"""
    raw_ev: float          # 生の期待値
    adjusted_ev: float     # 調整後期待値
    win_probability: float # 推定勝率
    fair_odds: float       # 適正オッズ
    value_rating: str      # 評価（◎/○/△/×）


def get_distance_category(distance: int) -> str:
    """
    距離をカテゴリに変換
    """
    if distance <= 1400:
        return "短距離"
    elif distance <= 1600:
        return "マイル"
    elif distance <= 2200:
        return "中距離"
    else:
        return "長距離"


def get_gate_category(gate: int, total_horses: int = 18) -> str:
    """
    枠番をカテゴリに変換
    """
    ratio = gate / total_horses
    if ratio <= 0.33:
        return "内"
    elif ratio <= 0.66:
        return "中"
    else:
        return "外"


def estimate_running_style(horse: dict) -> str:
    """
    馬の脚質を推定（過去データがない場合はデフォルト）
    """
    style = horse.get("脚質", horse.get("style", ""))
    if style in ["逃げ", "先行", "差し", "追込"]:
        return style
    
    # 人気と枠から推定（簡易版）
    popularity = horse.get("人気", 10)
    gate = horse.get("馬番", 9)
    
    if gate <= 4 and popularity <= 3:
        return "先行"
    elif gate <= 4:
        return "差し"
    elif popularity <= 2:
        return "先行"
    else:
        return "差し"


def calculate_gate_style_score(horse: dict, distance: int, total_horses: int = 18) -> int:
    """
    枠順 × 脚質 × 距離 の10段階スコアを計算
    """
    gate = horse.get("馬番", 9)
    style = estimate_running_style(horse)
    
    distance_cat = get_distance_category(distance)
    gate_cat = get_gate_category(gate, total_horses)
    
    key = (distance_cat, style, gate_cat)
    score = GATE_STYLE_MATRIX.get(key, 5)  # デフォルト5
    
    return score


def calculate_confidence_interval(
    uma_index: float,
    sample_size: int = 10,
    confidence_level: float = 0.95
) -> ConfidenceInterval:
    """
    UMA指数から95%信頼区間を計算
    
    Args:
        uma_index: UMA指数（0-100）
        sample_size: サンプルサイズ（過去レース数など）
        confidence_level: 信頼水準（デフォルト95%）
    
    Returns:
        ConfidenceInterval オブジェクト
    """
    # 推定勝率（UMA指数を確率に変換）
    mean_prob = uma_index / 100 * 0.35  # 最大35%勝率
    
    # 標準誤差の推定（ベータ分布を仮定）
    # 簡易的に二項分布の標準誤差を使用
    if mean_prob <= 0 or mean_prob >= 1:
        mean_prob = max(0.01, min(0.99, mean_prob))
    
    std_error = math.sqrt(mean_prob * (1 - mean_prob) / sample_size)
    
    if SCIPY_AVAILABLE:
        # scipy を使用した正確な信頼区間
        z_score = stats.norm.ppf((1 + confidence_level) / 2)
    else:
        # 簡易版（95%信頼区間のz値を固定）
        z_score = 1.96 if confidence_level == 0.95 else 1.645
    
    margin = z_score * std_error
    
    lower = max(0, mean_prob - margin)
    upper = min(1, mean_prob + margin)
    
    return ConfidenceInterval(
        lower=round(lower * 100, 2),
        upper=round(upper * 100, 2),
        mean=round(mean_prob * 100, 2),
        confidence=confidence_level
    )


def calculate_dynamic_expected_value(
    uma_index: float,
    live_odds: float,
    confidence_interval: ConfidenceInterval = None
) -> ExpectedValue:
    """
    動的期待値を計算
    
    Args:
        uma_index: UMA指数（0-100）
        live_odds: リアルタイムオッズ
        confidence_interval: 信頼区間（オプション）
    
    Returns:
        ExpectedValue オブジェクト
    """
    if live_odds <= 0:
        return ExpectedValue(
            raw_ev=0,
            adjusted_ev=0,
            win_probability=0,
            fair_odds=0,
            value_rating="×"
        )
    
    # 推定勝率
    win_probability = uma_index / 100 * 0.35
    
    # 適正オッズ（1 / 勝率）
    fair_odds = 1 / win_probability if win_probability > 0 else 100
    
    # 生の期待値（適正オッズ / 実オッズ）
    raw_ev = fair_odds / live_odds
    
    # 調整後期待値（信頼区間の下限を使用してより保守的に）
    if confidence_interval:
        conservative_prob = confidence_interval.lower / 100
        conservative_fair_odds = 1 / conservative_prob if conservative_prob > 0 else 100
        adjusted_ev = conservative_fair_odds / live_odds
    else:
        adjusted_ev = raw_ev * 0.9  # 10%割引
    
    # 評価
    if adjusted_ev >= 1.3:
        value_rating = "◎"
    elif adjusted_ev >= 1.1:
        value_rating = "○"
    elif adjusted_ev >= 0.9:
        value_rating = "△"
    else:
        value_rating = "×"
    
    return ExpectedValue(
        raw_ev=round(raw_ev, 3),
        adjusted_ev=round(adjusted_ev, 3),
        win_probability=round(win_probability * 100, 2),
        fair_odds=round(fair_odds, 1),
        value_rating=value_rating
    )


def process_race(race: dict) -> dict:
    """
    1レースの全馬に対してスコア計算を実行
    """
    distance = race.get("distance", 1600)
    horses = race.get("horses", [])
    total_horses = len(horses)
    
    processed_horses = []
    
    for horse in horses:
        # 枠順×脚質スコア
        gate_style_score = calculate_gate_style_score(horse, distance, total_horses)
        
        # UMA指数
        uma_index = horse.get("UMA指数", 50)
        
        # 信頼区間
        ci = calculate_confidence_interval(uma_index)
        
        # 動的期待値
        live_odds = horse.get("単勝オッズ", 0)
        ev = calculate_dynamic_expected_value(uma_index, live_odds, ci)
        
        # 結果を統合
        processed_horse = {
            **horse,
            "枠順脚質スコア": gate_style_score,
            "信頼区間": asdict(ci),
            "動的期待値": asdict(ev),
            "総合評価": ev.value_rating
        }
        processed_horses.append(processed_horse)
    
    return {
        **race,
        "horses": processed_horses,
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def process_predictions_file(input_path: Path, output_path: Path = None):
    """
    予想ファイルを読み込み、高精度計算を適用して保存
    """
    if not input_path.exists():
        print(f"[ERROR] ファイルが見つかりません: {input_path}")
        return
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    races = data.get("races", [])
    processed_races = []
    
    for race in races:
        processed_race = process_race(race)
        processed_races.append(processed_race)
    
    data["races"] = processed_races
    data["calculator_version"] = "pro_v1.0"
    data["processed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 出力先
    if output_path is None:
        output_path = input_path  # 上書き
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"[INFO] 処理完了: {output_path}")


def main():
    """
    メイン処理
    """
    print("=" * 60)
    print("UMA-Logic Pro - 高精度スコア計算エンジン")
    print("=" * 60)
    
    # 最新の予想ファイルを処理
    latest_path = DATA_DIR / "latest_predictions.json"
    
    if latest_path.exists():
        print(f"[INFO] 処理対象: {latest_path}")
        process_predictions_file(latest_path)
    else:
        print("[INFO] latest_predictions.json が見つかりません。")
        
        # 日付別ファイルを探す
        prediction_files = list(DATA_DIR.glob("predictions_*.json"))
        if prediction_files:
            # 最新のファイルを処理
            latest_file = max(prediction_files, key=lambda p: p.stem)
            print(f"[INFO] 代替ファイルを処理: {latest_file}")
            process_predictions_file(latest_file)
        else:
            print("[INFO] 処理対象のファイルがありません。正常終了します。")
    
    print("[INFO] 処理完了")


if __name__ == "__main__":
    main()
