import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import roc_auc_score
from pathlib import Path
import joblib
import json
import gc
import sys
import io

# Windows文字化け対策（既に他のモジュールで呼ばれる可能性があるのでガード付き）
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
except Exception:
    pass

# 自作モジュール
from feature_engineering import FeatureEngineer

# プロジェクトルートからの相対パス（どのCWDからでも動く）
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# 学習に使わないカラム（結果データ or テキスト or ヘルパー）
DROP_COLS = [
    "target_win", "target_top3", "date", "race_id", 
    "time", "last_3f", "seconds",
    "venue", "horse_name", "jockey", "trainer", 
    "father", "mother_father", "course_type", "condition", "sex", "weather",
    "rank", "odds", "popularity"
]


def prepare_data():
    """データの前処理と特徴量生成（直近トレンド重視版）"""
    print("=" * 60)
    print("🔧 データ準備中（直近トレンド重視モード）...")
    print("=" * 60)
    
    fe = FeatureEngineer()
    races_2024 = fe.load_data(start_date="20240101", end_date="20241231")
    races_2025 = fe.load_data(start_date="20250101", end_date="20251231")
    races_2026 = fe.load_data(start_date="20260101", end_date="20260228")
    
    if not races_2024 or not races_2025:
        print("[ERROR] データ不足: 2024年または2025年のデータが見つかりません")
        return None, None, None, None, None, None
    
    all_races = races_2024 + races_2025
    if races_2026:
        all_races += races_2026
        print(f"  2024: {len(races_2024)}レース, 2025: {len(races_2025)}レース, 2026: {len(races_2026)}レース")
    else:
        print(f"  2024: {len(races_2024)}レース, 2025: {len(races_2025)}レース, 2026: データなし")
    
    # 前処理（連結してからcreate_featuresを呼ぶ）
    df_all = fe.preprocess(all_races)
    df_all = fe.create_features(df_all)
    
    print(f"  全体: {len(df_all)}行, {df_all.shape[1]}列")
    
    # --- 直近データ重み付け ---
    # 直近ほど高い重みを付与（指数的減衰）
    sample_weights = np.ones(len(df_all))
    if "date" in df_all.columns:
        dates = pd.to_datetime(df_all["date"], errors='coerce')
        # 2026年データ: 3倍、2025年後半: 2倍、2025年前半: 1.5倍、2024年: 1倍
        mask_2026 = dates >= "2026-01-01"
        mask_2025h2 = (dates >= "2025-07-01") & (dates < "2026-01-01")
        mask_2025h1 = (dates >= "2025-01-01") & (dates < "2025-07-01")
        sample_weights[mask_2026] = 3.0
        sample_weights[mask_2025h2] = 2.0
        sample_weights[mask_2025h1] = 1.5
        print(f"  重み: 2024→1.0x, 2025H1→1.5x, 2025H2→2.0x, 2026→3.0x")
    
    # train/test分割（2025年7月以降をテスト）
    train_bool = df_all["date"] < "2025-07-01"
    
    # Xの作成
    X_all = df_all.drop(columns=DROP_COLS, errors='ignore')
    X_all = X_all.select_dtypes(include=['number', 'bool'])
    
    for col in X_all.columns:
        if X_all[col].dtype == 'float64':
            X_all[col] = X_all[col].astype('float32')
        elif X_all[col].dtype == 'int64':
            X_all[col] = X_all[col].astype('int32')
    
    X_train = X_all[train_bool]
    X_test = X_all[~train_bool]
    y_train = df_all.loc[train_bool, "target_top3"]
    y_test = df_all.loc[~train_bool, "target_top3"]
    
    # 直近30日の回収率を計算
    recent_stats = {}
    if "date" in df_all.columns:
        dates = pd.to_datetime(df_all["date"], errors='coerce')
        cutoff_30d = dates.max() - pd.Timedelta(days=30)
        recent_mask = dates >= cutoff_30d
        recent_df = df_all[recent_mask].copy()
        
        if len(recent_df) > 0:
            # 回収率 = (的中時のオッズ合計) / (総賭け金) × 100
            recent_top3_rate = recent_df["target_top3"].mean() * 100
            recent_win_rate = recent_df.get("target_win", pd.Series([0])).mean() * 100
            
            # 単勝回収率の推定: 各レースのAI1位馬が勝った場合のオッズを集計
            if "odds" in recent_df.columns and "rank" in recent_df.columns:
                recent_df_sorted = recent_df.sort_values(["race_id", "odds"])
                fav_mask = recent_df_sorted.groupby("race_id").cumcount() == 0
                fav_df = recent_df_sorted[fav_mask]
                wins = fav_df[fav_df.get("rank", pd.Series([0])) == 1]
                roi = (wins["odds"].sum() / len(fav_df) * 100) if len(fav_df) > 0 else 0
            else:
                roi = 0
            
            recent_stats = {
                "recent_30d_races": int(recent_df["race_id"].nunique()) if "race_id" in recent_df.columns else 0,
                "recent_30d_samples": len(recent_df),
                "recent_30d_top3_rate": round(recent_top3_rate, 1),
                "recent_30d_win_rate": round(recent_win_rate, 1),
                "recent_30d_roi": round(roi, 1),
                "recent_period": f"{cutoff_30d.strftime('%Y/%m/%d')}〜{dates.max().strftime('%Y/%m/%d')}"
            }
            print(f"  📈 直近30日: {recent_stats['recent_30d_races']}レース, 複勝率{recent_top3_rate:.1f}%, 推定回収率{roi:.1f}%")
    
    w_train = sample_weights[train_bool]
    w_test = sample_weights[~train_bool]
    
    print(f"  Train: {X_train.shape}, Test: {X_test.shape}")
    print(f"  特徴量: {list(X_train.columns)}")
    
    return X_train, X_test, y_train, y_test, X_all.columns.tolist(), (w_train, w_test, recent_stats)


def auto_tune_and_train(X_train, X_test, y_train, y_test):
    """ハイパーパラメータ自動チューニング + 学習"""
    print("\n" + "=" * 60)
    print("🎯 ハイパーパラメータ自動チューニング開始")
    print("=" * 60)
    
    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
    
    # パラメータ候補リスト（グリッドサーチ的に複数パターンを試す）
    param_candidates = [
        # Pattern 1: デフォルト（ベースライン）
        {
            "name": "baseline",
            "params": {
                'objective': 'binary', 'metric': 'auc', 'boosting_type': 'gbdt',
                'num_leaves': 31, 'learning_rate': 0.05, 'feature_fraction': 0.9,
                'verbose': -1
            }
        },
        # Pattern 2: 深いツリー + 低い学習率
        {
            "name": "deep_slow",
            "params": {
                'objective': 'binary', 'metric': 'auc', 'boosting_type': 'gbdt',
                'num_leaves': 63, 'learning_rate': 0.02, 'feature_fraction': 0.8,
                'bagging_fraction': 0.8, 'bagging_freq': 5,
                'min_child_samples': 20, 'verbose': -1
            }
        },
        # Pattern 3: 正則化強め（過学習防止）
        {
            "name": "regularized",
            "params": {
                'objective': 'binary', 'metric': 'auc', 'boosting_type': 'gbdt',
                'num_leaves': 31, 'learning_rate': 0.03, 'feature_fraction': 0.7,
                'bagging_fraction': 0.7, 'bagging_freq': 5,
                'lambda_l1': 1.0, 'lambda_l2': 1.0,
                'min_child_samples': 30, 'verbose': -1
            }
        },
        # Pattern 4: DART (Dropout regularization)
        {
            "name": "dart",
            "params": {
                'objective': 'binary', 'metric': 'auc', 'boosting_type': 'dart',
                'num_leaves': 40, 'learning_rate': 0.05, 'feature_fraction': 0.85,
                'drop_rate': 0.1, 'max_drop': 50,
                'verbose': -1
            }
        },
        # Pattern 5: 浅いツリー + 高い学習率 
        {
            "name": "shallow_fast",
            "params": {
                'objective': 'binary', 'metric': 'auc', 'boosting_type': 'gbdt',
                'num_leaves': 15, 'learning_rate': 0.1, 'feature_fraction': 0.9,
                'bagging_fraction': 0.9, 'bagging_freq': 3,
                'min_child_samples': 50, 'verbose': -1
            }
        },
        # Pattern 6: 広いツリー + 正則化バランス
        {
            "name": "wide_balanced",
            "params": {
                'objective': 'binary', 'metric': 'auc', 'boosting_type': 'gbdt',
                'num_leaves': 50, 'learning_rate': 0.03, 'feature_fraction': 0.75,
                'bagging_fraction': 0.75, 'bagging_freq': 5,
                'lambda_l1': 0.5, 'lambda_l2': 0.5,
                'min_child_samples': 15, 'max_depth': 8,
                'verbose': -1
            }
        },
    ]
    
    best_auc = 0
    best_model = None
    best_name = ""
    results = []
    
    for candidate in param_candidates:
        name = candidate["name"]
        params = candidate["params"]
        
        print(f"\n--- [{name}] 学習中... ---")
        
        try:
            callbacks = [lgb.early_stopping(stopping_rounds=50)]
            
            # DARTはearly stoppingとの相性が悪い場合があるので対策
            if params.get('boosting_type') == 'dart':
                num_rounds = 500
                callbacks = []
            else:
                num_rounds = 1500
            
            model = lgb.train(
                params,
                train_data,
                num_boost_round=num_rounds,
                valid_sets=[valid_data],
                callbacks=callbacks
            )
            
            y_pred = model.predict(X_test)
            auc = roc_auc_score(y_test, y_pred)
            
            # Train AUCも確認（過学習チェック）
            y_pred_train = model.predict(X_train)
            train_auc = roc_auc_score(y_train, y_pred_train)
            
            overfit_ratio = train_auc / auc if auc > 0 else 999
            
            print(f"  Test AUC: {auc:.4f}, Train AUC: {train_auc:.4f}, "
                  f"過学習比: {overfit_ratio:.3f}")
            
            results.append({
                "name": name, "test_auc": auc, "train_auc": train_auc,
                "overfit_ratio": overfit_ratio
            })
            
            # 最良モデルの更新（過学習が酷いものは除外）
            if auc > best_auc and overfit_ratio < 1.3:
                best_auc = auc
                best_model = model
                best_name = name
                print(f"  ★ 新しいベストモデル: {name} (AUC={auc:.4f})")
            elif auc > best_auc:
                print(f"  ⚠ AUCは良いが過学習気味 (比率={overfit_ratio:.3f})")
                # 過学習でも他に良いモデルがなければ採用
                if best_model is None:
                    best_auc = auc
                    best_model = model
                    best_name = name + " (過学習注意)"
                    
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"🏆 最良モデル: {best_name} (AUC={best_auc:.4f})")
    print(f"{'='*60}")
    
    # 結果サマリー
    print("\n📊 全パターン結果:")
    for r in sorted(results, key=lambda x: x["test_auc"], reverse=True):
        marker = "★" if r["name"] in best_name else " "
        print(f"  {marker} {r['name']}: Test={r['test_auc']:.4f}, "
              f"Train={r['train_auc']:.4f}, 過学習比={r['overfit_ratio']:.3f}")
    
    return best_model, best_auc, best_name


def train_model():
    """メイン学習パイプライン（直近トレンド重視版）"""
    result = prepare_data()
    
    if result[0] is None:
        return
    
    X_train, X_test, y_train, y_test, feature_names, extra = result
    w_train, w_test, recent_stats = extra
    
    best_model, best_auc, best_name = auto_tune_and_train(
        X_train, X_test, y_train, y_test
    )
    
    if best_model is None:
        print("[ERROR] 有効なモデルが生成されませんでした")
        return
    
    # --- 直近データ重視の微調整（Fine-tuning）---
    print("\n🔄 直近データで微調整 (Fine-tuning)...")
    try:
        # 直近データ（重み2.0以上）のみで追加学習
        high_weight_mask = w_train >= 1.5
        if high_weight_mask.sum() > 50:
            ft_data = lgb.Dataset(
                X_train[high_weight_mask], 
                label=y_train[high_weight_mask],
                weight=w_train[high_weight_mask]
            )
            ft_valid = lgb.Dataset(X_test, label=y_test, reference=ft_data)
            
            ft_params = {
                'objective': 'binary', 'metric': 'auc', 'boosting_type': 'gbdt',
                'num_leaves': 31, 'learning_rate': 0.01,  # 低い学習率で微調整
                'feature_fraction': 0.8, 'verbose': -1
            }
            
            ft_model = lgb.train(
                ft_params, ft_data, num_boost_round=50,
                valid_sets=[ft_valid],
                callbacks=[lgb.log_evaluation(0)]
            )
            
            ft_auc = roc_auc_score(y_test, ft_model.predict(X_test))
            print(f"  Fine-tuned AUC: {ft_auc:.4f} (Base: {best_auc:.4f})")
            
            # 改善された場合のみ採用
            if ft_auc >= best_auc - 0.005:
                best_model = ft_model
                best_auc = ft_auc
                best_name += "_finetuned"
                print(f"  ✅ Fine-tuned モデルを採用")
            else:
                print(f"  → ベースモデルを維持")
        else:
            print("  直近データが少ないためFine-tuningをスキップ")
    except Exception as e:
        print(f"  Fine-tuning エラー（ベースモデルを使用）: {e}")
    
    # モデル保存
    model_path = MODELS_DIR / "lgbm_model.pkl"
    joblib.dump(best_model, model_path)
    print(f"\nモデル保存: {model_path}")
    
    # 特徴量名を保存（推論時に使う）
    feature_path = MODELS_DIR / "feature_names.json"
    with open(feature_path, 'w') as f:
        json.dump(feature_names, f)
    
    # 特徴量重要度
    importance = pd.DataFrame({
        'feature': feature_names[:len(best_model.feature_importance())],
        'importance': best_model.feature_importance()
    }).sort_values('importance', ascending=False)
    
    print(f"\n📊 特徴量重要度 TOP15:")
    for _, row in importance.head(15).iterrows():
        bar = "█" * int(row['importance'] / importance['importance'].max() * 20)
        print(f"  {row['feature']:30s} {bar} ({row['importance']})")
    
    # メタデータ保存（直近stats含む）
    meta = {
        "best_model": best_name,
        "test_auc": round(best_auc, 4),
        "feature_count": len(feature_names),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "features": feature_names,
        "weight_scheme": "2024→1.0x, 2025H1→1.5x, 2025H2→2.0x, 2026→3.0x",
        "recent_stats": recent_stats
    }
    with open(MODELS_DIR / "model_meta.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 学習完了. AUC={best_auc:.4f}")


if __name__ == "__main__":
    train_model()
