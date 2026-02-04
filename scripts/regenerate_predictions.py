#!/usr/bin/env python3
"""
過去の予想を再生成するスクリプト

results_YYYYMMDD.json から出走表データを抽出し、
calculator_pro.py のロジックで予想を再計算して
predictions_YYYYMMDD.json を生成する
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import math

# パス設定
DATA_DIR = Path("data")
MODELS_DIR = DATA_DIR / "models"
WEIGHTS_FILE = MODELS_DIR / "weights.json"

# デフォルトのエージェント重み
DEFAULT_WEIGHTS = {
    "speed": 0.35,
    "adaptability": 0.35,
    "pedigree": 0.30
}

# トップ騎手リスト
TOP_JOCKEYS = [
    "川田将雅", "ルメール", "戸崎圭太", "横山武史", "福永祐一",
    "松山弘平", "岩田望来", "吉田隼人", "武豊", "デムーロ",
    "坂井瑠星", "横山和生", "田辺裕信", "池添謙一", "北村友一"
]

# 血統パターン
SIRE_PATTERNS = {
    "ディープインパクト": {"芝": 1.2, "ダート": 0.9, "中距離": 1.15, "長距離": 1.1},
    "キングカメハメハ": {"芝": 1.1, "ダート": 1.1, "中距離": 1.1, "短距離": 1.0},
    "ロードカナロア": {"芝": 1.15, "ダート": 0.95, "短距離": 1.2, "中距離": 1.0},
    "ハーツクライ": {"芝": 1.15, "ダート": 0.85, "中距離": 1.1, "長距離": 1.15},
    "エピファネイア": {"芝": 1.1, "ダート": 0.9, "中距離": 1.15, "長距離": 1.1},
    "ドゥラメンテ": {"芝": 1.15, "ダート": 0.9, "中距離": 1.15, "短距離": 1.0},
    "モーリス": {"芝": 1.1, "ダート": 0.95, "中距離": 1.1, "短距離": 1.05},
    "キタサンブラック": {"芝": 1.1, "ダート": 0.9, "中距離": 1.1, "長距離": 1.15},
}


def load_weights() -> Dict[str, float]:
    """重みファイルを読み込む"""
    if WEIGHTS_FILE.exists():
        try:
            with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("weights", DEFAULT_WEIGHTS)
        except:
            pass
    return DEFAULT_WEIGHTS


def get_distance_category(distance: int) -> str:
    """距離カテゴリを取得"""
    if distance <= 1400:
        return "短距離"
    elif distance <= 2000:
        return "中距離"
    else:
        return "長距離"


def calculate_uma_index(horse: Dict, race: Dict, weights: Dict) -> float:
    """
    UMA指数を計算
    
    Args:
        horse: 馬データ
        race: レースデータ
        weights: エージェント重み
    
    Returns:
        UMA指数（0-100）
    """
    
    # 基本スコア
    base_score = 50.0
    
    # --- Speed Agent ---
    speed_score = 50.0
    
    # オッズを取得（複数のキー名に対応）
    odds = horse.get("オッズ", horse.get("単勝オッズ", horse.get("odds", 10.0)))
    if isinstance(odds, str):
        try:
            odds = float(odds)
        except:
            odds = 10.0
    
    # 人気順を取得（なければオッズから推定）
    popularity = horse.get("人気", horse.get("popularity", 0))
    if not popularity or popularity == 0:
        # オッズから人気を推定
        if odds < 2.0:
            popularity = 1
        elif odds < 4.0:
            popularity = 2
        elif odds < 7.0:
            popularity = 3
        elif odds < 15.0:
            popularity = 5
        else:
            popularity = 10
    
    if popularity <= 3:
        speed_score += 20
    elif popularity <= 6:
        speed_score += 10
    if odds < 3.0:
        speed_score += 15
    elif odds < 5.0:
        speed_score += 10
    elif odds < 10.0:
        speed_score += 5
    
    # --- Adaptability Agent ---
    adapt_score = 50.0
    
    # 騎手評価
    jockey = horse.get("騎手", horse.get("jockey", ""))
    if jockey in TOP_JOCKEYS:
        adapt_score += 15
    
    # 馬場適性（簡易版）
    track_condition = race.get("track_condition", race.get("馬場状態", "良"))
    if track_condition in ["重", "不良"]:
        # 重馬場では人気薄が有利になることがある
        if popularity > 5:
            adapt_score += 5
    
    # --- Pedigree Agent ---
    pedigree_score = 50.0
    
    # 血統評価（父馬）
    father = horse.get("父", horse.get("father", ""))
    track_type = race.get("race_type", race.get("track_type", "芝"))
    distance = race.get("distance", 1600)
    distance_cat = get_distance_category(distance)
    
    if father in SIRE_PATTERNS:
        pattern = SIRE_PATTERNS[father]
        if track_type in pattern:
            pedigree_score *= pattern[track_type]
        if distance_cat in pattern:
            pedigree_score *= pattern[distance_cat]
    
    # 重み付け合計
    w_speed = weights.get("speed", 0.35)
    w_adapt = weights.get("adaptability", 0.35)
    w_pedigree = weights.get("pedigree", 0.30)
    
    total_score = (
        speed_score * w_speed +
        adapt_score * w_adapt +
        pedigree_score * w_pedigree
    )
    
    # 0-100にクリップ
    return max(0, min(100, total_score))


def calculate_win_probability(uma_index: float, odds: float) -> float:
    """勝率を推定"""
    # UMA指数ベースの推定勝率
    index_prob = uma_index / 100 * 0.5  # 最大50%
    
    # オッズベースの推定勝率
    odds_prob = 0.8 / odds if odds > 0 else 0.1
    
    # 平均
    return (index_prob + odds_prob) / 2


def calculate_expected_value(win_prob: float, odds: float) -> float:
    """期待値を計算"""
    return win_prob * odds


def get_mark(rank: int) -> str:
    """順位から印を取得"""
    marks = ["◎", "○", "▲", "△", "×"]
    if rank < len(marks):
        return marks[rank]
    return ""


def process_race(race: Dict, weights: Dict) -> Dict:
    """
    レースを処理して予想を生成
    
    Args:
        race: 結果データのレース
        weights: エージェント重み
    
    Returns:
        予想データ
    """
    
    # horses または all_results から馬データを取得
    horses = race.get("horses", []) or race.get("all_results", [])
    if not horses:
        return None
    
    # 各馬のUMA指数を計算
    horse_scores = []
    
    for horse in horses:
        try:
            uma_index = calculate_uma_index(horse, race, weights)
            odds = horse.get("オッズ", horse.get("単勝オッズ", horse.get("odds", 10.0)))
            if isinstance(odds, str):
                try:
                    odds = float(odds)
                except:
                    odds = 10.0
            win_prob = calculate_win_probability(uma_index, odds)
            expected_value = calculate_expected_value(win_prob, odds)
            
            horse_scores.append({
                "umaban": horse.get("馬番", horse.get("umaban", 0)),
                "horse_name": horse.get("馬名", horse.get("horse_name", "")),
                "jockey": horse.get("騎手", horse.get("jockey", "")),
                "odds": odds,
                "popularity": horse.get("人気", horse.get("popularity", 0)),
                "uma_index": round(uma_index, 1),
                "win_probability": round(win_prob, 4),
                "expected_value": round(expected_value, 2),
                "mark": ""
            })
        except Exception as e:
            print(f"    [WARN] 馬データ処理エラー: {e}")
            continue
    
    if not horse_scores:
        return None
    
    # UMA指数でソート
    horse_scores.sort(key=lambda x: x["uma_index"], reverse=True)
    
    # 印を付与
    for i, h in enumerate(horse_scores):
        h["mark"] = get_mark(i)
    
    # 本命馬（◎）
    honmei = horse_scores[0] if horse_scores else {}
    
    # ランク判定
    if honmei.get("uma_index", 0) >= 75:
        rank = "S"
    elif honmei.get("uma_index", 0) >= 65:
        rank = "A"
    else:
        rank = "B"
    
    return {
        "race_id": race.get("race_id", ""),
        "race_num": race.get("race_num", 0),
        "race_name": race.get("race_name", ""),
        "venue": race.get("venue", ""),
        "distance": race.get("distance", 0),
        "track_type": race.get("race_type", race.get("track_type", "")),
        "track_condition": race.get("track_condition", race.get("馬場状態", "")),
        "rank": rank,
        "honmei": {
            "umaban": honmei.get("umaban", 0),
            "horse_name": honmei.get("horse_name", ""),
            "uma_index": honmei.get("uma_index", 0),
            "expected_value": honmei.get("expected_value", 0)
        },
        "horses": horse_scores
    }


def regenerate_predictions(date_str: str) -> bool:
    """
    指定日の予想を再生成
    
    Args:
        date_str: 日付（YYYYMMDD形式）
    
    Returns:
        成功したかどうか
    """
    
    results_file = DATA_DIR / f"results_{date_str}.json"
    predictions_file = DATA_DIR / f"predictions_{date_str}.json"
    
    if not results_file.exists():
        print(f"[ERROR] 結果ファイルが見つかりません: {results_file}")
        return False
    
    # 結果ファイルを読み込み
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            results_data = json.load(f)
    except Exception as e:
        print(f"[ERROR] ファイル読み込みエラー: {e}")
        return False
    
    races = results_data.get("races", [])
    if not races:
        print(f"[WARN] レースデータがありません: {date_str}")
        return False
    
    # 重みを読み込み
    weights = load_weights()
    
    # 各レースを処理
    processed_races = []
    
    for race in races:
        try:
            prediction = process_race(race, weights)
            if prediction:
                processed_races.append(prediction)
        except Exception as e:
            print(f"    [WARN] レース処理エラー ({race.get('race_name', '')}): {e}")
            continue
    
    if not processed_races:
        print(f"[WARN] 処理できたレースがありません: {date_str}")
        return False
    
    # 予想ファイルを保存
    predictions_data = {
        "date": date_str,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "regenerated": True,
        "races": processed_races
    }
    
    try:
        with open(predictions_file, 'w', encoding='utf-8') as f:
            json.dump(predictions_data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ 保存: {predictions_file} ({len(processed_races)}レース)")
        return True
    except Exception as e:
        print(f"[ERROR] 保存エラー: {e}")
        return False


def main():
    """メイン処理"""
    print("=" * 70)
    print("🔄 UMA-Logic - 過去予想再生成スクリプト")
    print("=" * 70)
    
    # コマンドライン引数
    if len(sys.argv) > 1:
        # 特定の日付を指定
        dates = sys.argv[1:]
        print(f"\n[INFO] 指定された日付を処理: {dates}")
    else:
        # 全ての結果ファイルを処理
        results_files = sorted(DATA_DIR.glob("results_*.json"))
        dates = [f.stem.replace("results_", "") for f in results_files]
        print(f"\n[INFO] {len(dates)}日分のデータを処理します")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for date_str in dates:
        predictions_file = DATA_DIR / f"predictions_{date_str}.json"
        
        # 既存の予想ファイルがあればスキップ（--force オプションがない場合）
        if predictions_file.exists() and "--force" not in sys.argv:
            print(f"[SKIP] {date_str} - 予想ファイルが既に存在します")
            skip_count += 1
            continue
        
        print(f"\n[{date_str}] 処理中...")
        
        if regenerate_predictions(date_str):
            success_count += 1
        else:
            error_count += 1
    
    print("\n" + "=" * 70)
    print("📊 処理結果")
    print("=" * 70)
    print(f"  成功: {success_count}日")
    print(f"  スキップ: {skip_count}日")
    print(f"  エラー: {error_count}日")
    print("=" * 70)


if __name__ == "__main__":
    main()
