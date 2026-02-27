import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from pathlib import Path
import json
import re

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def get_distance_category(distance):
    """距離カテゴリを返す"""
    if distance <= 1400:
        return 0  # sprint
    elif distance <= 1800:
        return 1  # mile
    elif distance <= 2200:
        return 2  # middle
    else:
        return 3  # long

# 競馬場の小回り/大箱フラグ
VENUE_SMALL_TRACK = {"中山": 1, "小倉": 1, "福島": 1, "札幌": 1, "函館": 1}
VENUE_STEEP_SLOPE = {"中山": 1, "阪神": 1, "中京": 1}

class FeatureEngineer:
    def __init__(self):
        self.venue_encoder = LabelEncoder()
        self.jockey_encoder = LabelEncoder()
        self.trainer_encoder = LabelEncoder()
        self.father_encoder = LabelEncoder()
        
    def load_data(self, start_date=None, end_date=None):
        """指定期間のレース結果データを読み込んでリストにする"""
        files = sorted(list(DATA_DIR.glob("results_*.json")))
        all_races = []
        
        for f in files:
            date_str = f.stem.replace("results_", "")
            if start_date and date_str < start_date: continue
            if end_date and date_str > end_date: continue
            
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    races = data.get("races", [])
                    for race in races:
                        race["date"] = data.get("date")
                        all_races.append(race)
            except Exception:
                continue
                
        return all_races

    def preprocess(self, races):
        """レースデータをDataFrameに変換し、前処理を行う"""
        rows = []
        for race in races:
            race_id = race.get("race_id")
            venue = race.get("venue", "不明")
            course_type = race.get("track_type", "芝")
            distance = int(race.get("distance", 1600) or 1600)
            condition = race.get("track_condition", "良")
            
            for horse in race.get("all_results", []):
                row = {
                    "race_id": race_id,
                    "date": pd.to_datetime(race.get("date")),
                    "venue": venue,
                    "course_type": course_type,
                    "distance": distance,
                    "condition": condition,
                    "weather": race.get("weather", "晴"),
                    
                    "umaban": horse.get("馬番"),
                    "horse_name": horse.get("馬名"),
                    "jockey": horse.get("騎手", "不明"),
                    "trainer": horse.get("trainer", "不明"),
                    "weight": horse.get("weight", 470),
                    "father": horse.get("father", "不明"),
                    "mother_father": horse.get("mother_father", "不明"),
                    "sex": "牡",
                    "age": 3,
                    
                    "odds": float(horse.get("オッズ", 0) or 0),
                    "popularity": horse.get("人気", 0),
                    "rank": horse.get("着順", 99),
                    "time": horse.get("タイム", "0:00.0"),
                    "last_3f": float(horse.get("上がり3F", 0) or 0),
                    
                    # --- 新規特徴量(レースレベル) ---
                    "distance_category": get_distance_category(distance),
                    "is_turf": 1 if course_type == "芝" else 0,
                    "is_small_track": VENUE_SMALL_TRACK.get(venue, 0),
                    "is_steep_slope": VENUE_STEEP_SLOPE.get(venue, 0),
                    "num_runners": len(race.get("all_results", [])),
                }
                
                # 馬場状態の数値化
                condition_map = {"良": 0, "稍重": 1, "重": 2, "不良": 3}
                row["condition_score"] = condition_map.get(condition, 0)
                
                # タイムを秒に変換
                try:
                    t_str = str(row["time"])
                    if ":" in t_str:
                        m, s = t_str.split(":")
                        row["seconds"] = int(m)*60 + float(s)
                    else:
                        row["seconds"] = float(t_str) if t_str.replace('.', '', 1).isdigit() else 0.0
                except:
                    row["seconds"] = 0.0
                    
                rows.append(row)
                
        df = pd.DataFrame(rows)
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna(0)
        return df

    def create_features(self, df):
        """特徴量エンジニアリング（究極版）"""
        
        # ターゲット（rank列に文字列が混在する場合を安全処理）
        df["rank"] = pd.to_numeric(df["rank"], errors='coerce').fillna(99).astype(int)
        df["target_win"] = (df["rank"] == 1).astype(int)
        df["target_top3"] = (df["rank"] <= 3).astype(int)
        
        # --- カテゴリID化 ---
        for col in ["venue", "jockey", "trainer", "father", "course_type", "condition"]:
            if col in df.columns:
                df[f"{col}_id"] = df[col].astype("category").cat.codes
        
        # --- 騎手×競馬場 連対率 (Expanding Window) ---
        df = df.sort_values("date").reset_index(drop=True)
        
        # 騎手のグローバル連対率（Expanding）
        df["jockey_cumwin"] = df.groupby("jockey")["target_top3"].cumsum() - df["target_top3"]
        df["jockey_cumcount"] = df.groupby("jockey").cumcount()
        df["jockey_top3_rate"] = np.where(
            df["jockey_cumcount"] > 0,
            df["jockey_cumwin"] / df["jockey_cumcount"],
            0.3  # 初回はデフォルト値
        )
        
        # 騎手×競馬場の連対率
        df["jv_key"] = df["jockey"] + "_" + df["venue"]
        df["jv_cumwin"] = df.groupby("jv_key")["target_top3"].cumsum() - df["target_top3"]
        df["jv_cumcount"] = df.groupby("jv_key").cumcount()
        df["jockey_venue_rate"] = np.where(
            df["jv_cumcount"] > 2,
            df["jv_cumwin"] / df["jv_cumcount"],
            df["jockey_top3_rate"]  # サンプル不足時はグローバル率で代替
        )
        
        # 騎手×距離カテゴリの連対率
        df["jd_key"] = df["jockey"] + "_" + df["distance_category"].astype(str)
        df["jd_cumwin"] = df.groupby("jd_key")["target_top3"].cumsum() - df["target_top3"]
        df["jd_cumcount"] = df.groupby("jd_key").cumcount()
        df["jockey_distance_rate"] = np.where(
            df["jd_cumcount"] > 2,
            df["jd_cumwin"] / df["jd_cumcount"],
            df["jockey_top3_rate"]
        )
        
        # === NEW: 調教師のグローバル連対率（Expanding）===
        df["trainer_cumwin"] = df.groupby("trainer")["target_top3"].cumsum() - df["target_top3"]
        df["trainer_cumcount"] = df.groupby("trainer").cumcount()
        df["trainer_top3_rate"] = np.where(
            df["trainer_cumcount"] > 0,
            df["trainer_cumwin"] / df["trainer_cumcount"],
            0.25
        )
        
        # === NEW: 騎手・調教師の直近3ヶ月モメンタム ===
        try:
            df["date_dt"] = pd.to_datetime(df["date"])
            df["jockey_recent_rate"] = df["jockey_top3_rate"].copy()
            df["trainer_recent_rate"] = df["trainer_top3_rate"].copy()
            
            # 効率化: ユニークな騎手・調教師×日付のみ計算
            for jockey_name in df["jockey"].unique():
                jockey_mask = df["jockey"] == jockey_name
                jockey_df = df[jockey_mask].copy()
                for idx in jockey_df.index:
                    current_date = jockey_df.loc[idx, "date_dt"]
                    cutoff = current_date - pd.Timedelta(days=90)
                    recent = jockey_df[(jockey_df["date_dt"] >= cutoff) & (jockey_df["date_dt"] < current_date)]
                    if len(recent) >= 5:
                        df.loc[idx, "jockey_recent_rate"] = recent["target_top3"].mean()
            
            for trainer_name in df["trainer"].unique():
                trainer_mask = df["trainer"] == trainer_name
                trainer_df = df[trainer_mask].copy()
                for idx in trainer_df.index:
                    current_date = trainer_df.loc[idx, "date_dt"]
                    cutoff = current_date - pd.Timedelta(days=90)
                    recent = trainer_df[(trainer_df["date_dt"] >= cutoff) & (trainer_df["date_dt"] < current_date)]
                    if len(recent) >= 5:
                        df.loc[idx, "trainer_recent_rate"] = recent["target_top3"].mean()
            
            df = df.drop(columns=["date_dt"], errors="ignore")
        except Exception:
            df["jockey_recent_rate"] = 0.3
            df["trainer_recent_rate"] = 0.25
        
        # === NEW: 血統系統分類 ===
        SPEED_SIRES = {"ロードカナロア", "ダイワメジャー", "キンシャサノキセキ", "アドマイヤムーン",
                       "ミッキーアイル", "ビッグアーサー", "モーリス", "サクソンウォリアー"}
        STAMINA_SIRES = {"ディープインパクト", "ステイゴールド", "ハーツクライ", "キタサンブラック",
                         "ゴールドシップ", "ドゥラメンテ", "オルフェーヴル", "エピファネイア",
                         "サトノダイヤモンド", "コントレイル", "シャフリヤール", "イクイノックス"}
        DIRT_SIRES = {"ヘニーヒューズ", "パイロ", "シニスターミニスター", "マジェスティックウォリアー",
                      "カネヒキリ", "ドレフォン", "マインドユアビスケッツ", "ホッコータルマエ"}
        
        def classify_sire(father):
            if father in SPEED_SIRES: return 1
            if father in STAMINA_SIRES: return 2
            if father in DIRT_SIRES: return 3
            return 0
        
        df["sire_type"] = df["father"].apply(classify_sire)
        df["sire_speed"] = (df["sire_type"] == 1).astype(int)
        df["sire_stamina"] = (df["sire_type"] == 2).astype(int)
        df["sire_dirt"] = (df["sire_type"] == 3).astype(int)
        
        # === NEW: 斤量偏差 ===
        if "weight" in df.columns:
            df["weight_mean"] = df.groupby("race_id")["weight"].transform("mean")
            df["weight_deviation"] = df["weight"] - df["weight_mean"]
        else:
            df["weight_deviation"] = 0
        
        # --- 競馬場ごとの平均配当（安全な実装）---
        try:
            win_odds = df["odds"].where(df["rank"] == 1)
            df["venue_cumwin_odds"] = win_odds.expanding().mean().fillna(0)
        except Exception:
            df["venue_cumwin_odds"] = 0.0
        
        # --- 馬番のバイアス（内枠/外枠の有利不利）---
        df["gate_position"] = np.where(
            df["num_runners"] > 0,
            df["umaban"] / df["num_runners"],
            0.5
        )
        
        # --- オッズベースの特徴量 ---
        df["odds_rank_in_race"] = df.groupby("race_id")["odds"].rank(method="min")
        df["odds_ratio"] = np.where(
            df["num_runners"] > 0,
            df["odds_rank_in_race"] / df["num_runners"],
            0.5
        )
        
        # --- 不要なキーを削除 ---
        drop_helper_cols = ["jockey_cumwin", "jockey_cumcount", "jv_key", 
                           "jv_cumwin", "jv_cumcount", "jd_key", "jd_cumwin", 
                           "jd_cumcount", "odds_rank_in_race",
                           "trainer_cumwin", "trainer_cumcount", "weight_mean",
                           "sire_type"]
        df = df.drop(columns=drop_helper_cols, errors='ignore')
        
        # --- 最終クリーニング ---
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna(0)
        
        return df



if __name__ == "__main__":
    fe = FeatureEngineer()
    races = fe.load_data(start_date="20240101", end_date="20241231")
    df = fe.preprocess(races)
    print(f"Data loaded: {len(df)} rows")
    
    df = fe.create_features(df)
    print(f"Features created: {df.shape}")
    print("Columns:", list(df.columns))
    print("\nSample jockey rates:")
    print(df[["jockey", "jockey_top3_rate", "jockey_venue_rate", "jockey_distance_rate"]].tail(10))
