# app_commercial.py
# UMA-Logic PRO - 商用グレード完全版UI
# 完全版（Full Code）- そのままコピー＆ペーストで動作
# レース番号昇順ソート対応 + 階層型検索UI統合
# weights.json 自動適用機能追加

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import subprocess
import csv

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from scripts.calculator_ml import MLCalculator

# Plotlyのインポート
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# 自動更新
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# AgGridのインポート
try:
    from st_aggrid import AgGrid, GridOptionsBuilder
    AGGRID_AVAILABLE = True
except ImportError:
    AGGRID_AVAILABLE = False

# --- ページ設定 ---
st.set_page_config(
    page_title="UMA-Logic PRO",
    page_icon="🐎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === 認証機能 ===
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        try:
            stored_password = st.secrets["password"]
        except (FileNotFoundError, KeyError):
            stored_password = "uma2026"  # Fallback password

        if st.session_state.get("password_input", "") == stored_password:
            st.session_state["password_correct"] = True
            if "password_input" in st.session_state:
                del st.session_state["password_input"]  # Don't store password
        else:
            st.session_state["password_correct"] = False
            st.error("パスワードが違います")

    # セッション状態の初期化 - より堅牢に
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    # 認証済みの場合は即時返却
    if st.session_state["password_correct"]:
        return True
    
    # 認証が必要な場合
    st.text_input(
        "🔑 パスワードを入力してください", 
        type="password", 
        on_change=password_entered, 
        key="password_input"
    )
    st.info("初期パスワード: uma2026")
    
    # 認証状態をチェック
    if st.session_state.get("password_correct", False):
        return True
    
    st.stop()
    return False

# メインの認証チェック
if "password_checked" not in st.session_state:
    if not check_password():
        st.stop()
    st.session_state["password_checked"] = True

# --- 定数 ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR = DATA_DIR / "archive"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
PREDICTIONS_PREFIX = "predictions_"
HISTORY_DIR = DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_PREFIX = "results_"
ALERTS_FILE = DATA_DIR / "insider_alerts.json"
HISTORY_FILE = DATA_DIR / "history.json"
INDEX_FILE = ARCHIVE_DIR / "index.json"
WEIGHTS_FILE = MODELS_DIR / "weights.json"

# 曜日の日本語表記
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]

# デフォルトの重み
DEFAULT_WEIGHTS = {
    "SpeedAgent": 0.35,
    "AdaptabilityAgent": 0.35,
    "PedigreeFormAgent": 0.30
}

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

# トップ騎手
TOP_JOCKEYS = ["ルメール", "川田将雅", "戸崎圭太", "横山武史", "福永祐一", "武豊"]

# --- CSSスタイル（プレミアムダークテーマ: ゴールド×エメラルド） ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;700&display=swap');

    html, body, [class*="st-"], .stApp {
        font-family: 'Inter', 'Noto Sans JP', sans-serif;
        background-color: #0a0f1a;
        color: #FFFFFF;
        font-weight: 500;
        font-size: 17px;
    }

    .block-container {
        background-color: #0a0f1a;
    }

    [data-testid="stSidebar"] {
        background-color: #0a0f1a;
    }

    [data-testid="stExpander"] > div {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(16, 185, 129, 0.25);
    }

    .stTabs [data-baseweb="tab-panel"] {
        background-color: #0a0f1a;
    }

    .stMarkdown table, .stMarkdown th, .stMarkdown td {
        background-color: #0f172a;
        color: #e2e8f0;
        border-color: #1f2937;
        font-size: 1rem;
    }

    /* 全テキストにドロップシャドウ */
    h1, h2, h3, h4, h5, h6, p, span, div, td, th, label {
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
    }

    /* Streamlit DataFrameの背景色強制 */
    [data-testid="stDataFrame"], 
    [data-testid="stDataFrame"] > div,
    [data-testid="stDataFrame"] iframe {
        background-color: #0a0f1a !important;
    }
    .stDataFrame {
        background-color: #0a0f1a !important;
    }
    .stDataFrame div, .stDataFrame table, .stDataFrame th, .stDataFrame td {
        background-color: #0a0f1a !important;
        color: #e2e8f0 !important;
        border-color: #1f2937 !important;
        font-size: 1rem !important;
    }
    [data-testid="stTable"] table, [data-testid="stTable"] th, [data-testid="stTable"] td {
        background-color: #0a0f1a !important;
        color: #e2e8f0 !important;
        border-color: #1f2937 !important;
    }

    /* カウントダウン表示 */
    .countdown-bar {
        background: rgba(255, 215, 0, 0.08);
        border: 1px solid rgba(255, 215, 0, 0.2);
        border-radius: 8px;
        padding: 6px 14px;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 0.9rem;
        color: #ffd700;
        font-weight: 600;
    }

    /* メトリクスのフォントサイズ強化 */
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: #ffd700 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        color: #FFFFFF !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
    }

    .main-header {
        background: linear-gradient(135deg, #0a1628 0%, #14243a 50%, #0a1628 100%);
        padding: 1.8rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        border-left: 4px solid #ffd700;
        box-shadow: 0 8px 32px rgba(255, 215, 0, 0.1);
    }

    .main-header h1 {
        color: #ffd700;
        margin: 0;
        font-size: 2.4rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }

    .main-header p {
        color: #e2e8f0;
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
        font-weight: 600;
    }

    .race-card {
        background: #0B1224;
        border-radius: 14px;
        padding: 1.4rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(255, 215, 0, 0.3);
        transition: transform 0.2s, box-shadow 0.2s;
    }

    .race-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 32px rgba(255, 215, 0, 0.12);
        border-color: rgba(255, 215, 0, 0.3);
    }

    .race-title {
        color: #ffd700;
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 0 0 8px rgba(255, 215, 0, 0.15);
    }

    .race-info {
        color: #e2e8f0;
        font-size: 1rem;
        font-weight: 600;
    }

    .horse-row {
        display: flex;
        align-items: center;
        padding: 0.6rem 0;
        border-bottom: 1px solid rgba(255, 215, 0, 0.1);
    }

    .horse-row:last-child {
        border-bottom: none;
    }

    .horse-number {
        background: linear-gradient(135deg, #ffd700, #f59e0b);
        color: #0a0f1a;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        margin-right: 0.8rem;
        font-size: 0.9rem;
    }

    .horse-name {
        color: #FFFFFF;
        font-weight: 700;
        flex: 1;
        font-size: 1.15rem;
    }

    .horse-odds {
        color: #34d399;
        font-weight: 700;
        font-size: 1.15rem;
    }

    .rank-badge {
        padding: 0.25rem 0.8rem;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.9rem;
        margin-right: 0.5rem;
        letter-spacing: 0.03em;
    }

    .rank-s-plus {
        background: linear-gradient(135deg, #ffd700, #f59e0b);
        color: #05070a;
        box-shadow: 0 0 16px rgba(255, 215, 0, 0.5);
        text-shadow: 0 0 4px rgba(255, 215, 0, 0.3);
    }

    .rank-s {
        background: linear-gradient(135deg, #ef4444, #f87171);
        color: #fff;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.4);
        text-shadow: 0 0 4px rgba(239, 68, 68, 0.3);
    }

    .rank-a {
        background: linear-gradient(135deg, #10b981, #34d399);
        color: #0a0f1a;
    }

    .rank-b {
        background: #3b82f6;
        color: #fff;
    }

    .rank-c {
        background: #475569;
        color: #e2e8f0;
    }

    .insider-alert {
        background: linear-gradient(135deg, #dc2626, #b91c1c);
        color: white;
        padding: 1rem 1.2rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        animation: pulse 2s infinite;
        font-size: 0.95rem;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.85; }
    }

    .metric-card {
        background: #0B1224;
        border-radius: 14px;
        padding: 1.4rem;
        text-align: center;
        border: 1px solid rgba(255, 215, 0, 0.1);
    }

    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #ffd700;
    }

    .metric-label {
        color: #e2e8f0;
        font-size: 1rem;
        font-weight: 700;
    }

    .payout-table {
        width: 100%;
        border-collapse: collapse;
    }

    .payout-table th, .payout-table td {
        padding: 0.7rem 0.9rem;
        text-align: left;
        border-bottom: 1px solid rgba(255, 215, 0, 0.1);
        font-size: 1.1rem;
        font-weight: 600;
    }

    .payout-table th {
        color: #e2e8f0;
        font-weight: 700;
    }

    .payout-table td {
        color: #FFFFFF;
        font-weight: 500;
    }

    .payout-amount {
        color: #34d399;
        font-weight: 700;
    }

    .venue-button {
        background: #0B1224;
        color: #FFFFFF;
        border: 1px solid rgba(255, 215, 0, 0.25);
        padding: 0.6rem 1.3rem;
        border-radius: 8px;
        margin-right: 0.5rem;
        cursor: pointer;
        transition: all 0.2s;
        font-weight: 700;
        font-size: 1rem;
    }

    .venue-button:hover {
        background: linear-gradient(135deg, #ffd700, #f59e0b);
        color: #0a0f1a;
    }

    .venue-button.active {
        background: linear-gradient(135deg, #ffd700, #f59e0b);
        color: #0a0f1a;
    }

    .ai-weights-card {
        background: #0B1224;
        border-radius: 14px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .ai-weights-title {
        color: #10b981;
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }

    .weight-bar {
        height: 10px;
        background: #0f1a2e;
        border-radius: 4px;
        margin: 0.3rem 0;
        overflow: hidden;
    }

    .weight-fill {
        height: 100%;
        border-radius: 4px;
    }

    .weight-speed {
        background: linear-gradient(90deg, #ffd700, #f59e0b);
    }

    .weight-adapt {
        background: linear-gradient(90deg, #3b82f6, #60a5fa);
    }

    .weight-pedigree {
        background: linear-gradient(90deg, #10b981, #34d399);
    }

    /* タブデザイン */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 700 !important;
        font-size: 1rem !important;
    }

    /* 再予想ボタン */
    .repredict-btn {
        background: linear-gradient(135deg, #ffd700, #f59e0b) !important;
        color: #0a0f1a !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.6rem 1.5rem !important;
        font-size: 1rem !important;
        transition: all 0.3s !important;
    }

    /* リアルタイムインジケーター */
    .live-indicator {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 0.95rem;
        color: #10b981;
        font-weight: 700;
    }

    .live-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #10b981;
        animation: blink 1.5s infinite;
    }

    @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }

    /* データ品質バッジ */
    .data-quality-badge {
        font-size: 0.7rem;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
    }
    .dq-complete { background: #10b981; color: #fff; }
    .dq-partial { background: #f59e0b; color: #0a0f1a; }

    /* ⚠️ データ不足警告ボックス（ゴールド枠） */
    .data-warning-box {
        background: rgba(255, 215, 0, 0.06);
        border: 2px solid #ffd700;
        border-radius: 12px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.8rem;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .data-warning-box .warning-icon {
        font-size: 1.4rem;
        flex-shrink: 0;
    }
    .data-warning-box .warning-text {
        color: #ffd700;
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.4;
    }
    .data-warning-box .warning-detail {
        color: #e2e8f0;
        font-size: 0.9rem;
        font-weight: 500;
    }

    /* ========== モバイルレスポンシブ ========== */
    @media (max-width: 768px) {
        html, body, [class*="st-"], .stApp {
            font-size: 14px;
        }

        .main-header {
            padding: 1rem;
            border-radius: 10px;
        }
        .main-header h1 {
            font-size: 1.4rem;
        }

        /* メトリクスを小さく */
        [data-testid="stMetricValue"] {
            font-size: 1.2rem !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.8rem !important;
        }

        /* 馬情報の行をコンパクトに */
        .horse-number {
            width: 24px;
            height: 24px;
            font-size: 0.75rem;
            margin-right: 0.5rem;
        }
        .horse-name {
            font-size: 0.85rem;
        }
        .horse-odds {
            font-size: 0.85rem;
        }

        /* ランクバッジ */
        .rank-badge {
            padding: 0.15rem 0.4rem;
            font-size: 0.7rem;
        }

        /* レースカード */
        .race-card {
            padding: 0.8rem;
            border-radius: 10px;
        }

        /* タブを横スクロール */
        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto;
            flex-wrap: nowrap;
            -webkit-overflow-scrolling: touch;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 0.75rem !important;
            white-space: nowrap;
            padding: 0.4rem 0.6rem !important;
        }

        /* データ不足警告 */
        .data-warning-box {
            padding: 0.6rem 0.8rem;
        }
        .data-warning-box .warning-text {
            font-size: 0.8rem;
        }

        /* LIVEインジケーター */
        .live-indicator {
            font-size: 0.7rem;
            padding: 3px 8px;
        }

        /* パイチャートを小さく */
        .js-plotly-plot {
            max-height: 250px;
        }

        /* 円グラフのラベル */
        .payout-table th, .payout-table td {
            padding: 0.4rem;
            font-size: 0.8rem;
        }
    }

    /* さらに小さいスマホ(iPhone SE等) */
    @media (max-width: 375px) {
        .main-header h1 {
            font-size: 1.2rem;
        }
        [data-testid="stMetricValue"] {
            font-size: 1rem !important;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 0.65rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)


# --- AI重み読み込み関数 ---

@st.cache_data(ttl=300)  # 5分間キャッシュ
def load_ai_weights() -> dict:
    """weights.json から最新のAI重みを読み込み"""
    if WEIGHTS_FILE.exists():
        try:
            with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            st.warning(f"AI重み読み込みエラー: {e}")
    return {
        "weights": DEFAULT_WEIGHTS.copy(),
        "metrics": {},
        "train_metrics": {},
        "test_metrics": {},
        "updated_at": ""
    }


def get_agent_weights() -> dict:
    """エージェント重みを取得"""
    data = load_ai_weights()
    return data.get("weights", DEFAULT_WEIGHTS.copy())


# --- スコア計算関数（アンサンブル） ---

def calculate_speed_score(horse: dict, race: dict, weight: float = 0.35) -> float:
    """スピードスコアを計算（0-100）"""
    score = 50.0
    
    odds = float(horse.get("オッズ", horse.get("odds", 0)) or 0)
    popularity = int(horse.get("人気", horse.get("popularity", 0)) or 0)
    gate_num = int(horse.get("枠番", horse.get("gate_num", 0)) or 0)
    distance = int(race.get("distance", 0) or 0)
    
    # オッズが低い（人気がある）ほど高スコア
    if odds > 0:
        if odds < 2.0:
            score += 30
        elif odds < 5.0:
            score += 20
        elif odds < 10.0:
            score += 10
        elif odds < 20.0:
            score += 0
        else:
            score -= 10
    
    # 人気順
    if popularity > 0:
        if popularity <= 3:
            score += 15
        elif popularity <= 6:
            score += 5
        else:
            score -= 5
    
    # 距離適性（簡易版）
    if distance > 0:
        if distance <= 1400:
            # 短距離は内枠有利
            if gate_num <= 4:
                score += 5
        elif distance >= 2000:
            # 長距離は差し馬有利（人気薄でも）
            if popularity > 5 and odds < 30:
                score += 5
    
    return max(0, min(100, score)) * weight


def calculate_adaptability_score(horse: dict, race: dict, weight: float = 0.35) -> float:
    """適応性スコアを計算（0-100）"""
    score = 50.0
    
    gate_num = int(horse.get("枠番", horse.get("gate_num", 0)) or 0)
    horse_weight = float(horse.get("馬体重", horse.get("weight", 0)) or 0)
    weight_diff = float(horse.get("増減", horse.get("weight_diff", 0)) or 0)
    distance = int(race.get("distance", 0) or 0)
    track_condition = race.get("track_condition", "")
    
    # 枠順評価
    if distance > 0 and gate_num > 0:
        if distance <= 1400:
            if gate_num <= 3:
                score += 15
            elif gate_num <= 5:
                score += 5
            elif gate_num >= 7:
                score -= 5
        elif distance <= 1800:
            pass
        else:
            if gate_num >= 7:
                score -= 10
    
    # 馬場状態
    if track_condition in ["重", "不良"]:
        if horse_weight >= 500:
            score += 10
        elif horse_weight <= 440:
            score -= 5
    
    # 馬体重増減
    if weight_diff != 0:
        if abs(weight_diff) > 20:
            score -= 10
        elif -10 <= weight_diff <= 10:
            score += 5
    
    return max(0, min(100, score)) * weight


def calculate_pedigree_score(horse: dict, race: dict, weight: float = 0.30) -> float:
    """血統・調子スコアを計算（0-100）"""
    score = 50.0
    
    father = horse.get("父", horse.get("father", ""))
    jockey = horse.get("騎手", horse.get("jockey", ""))
    odds = float(horse.get("オッズ", horse.get("odds", 0)) or 0)
    
    # 血統評価
    if father:
        bonus = SIRE_BONUS.get(father, 0)
        score += bonus
    
    # 騎手評価
    if jockey in TOP_JOCKEYS:
        score += 10
    
    return max(0, min(100, score)) * weight


@st.cache_resource
def load_ml_calculator():
    return MLCalculator()

ml_calc = load_ml_calculator()


def calculate_uma_index(horse: dict, race: dict) -> float:
    """
    UMA指数を計算（3エージェントのアンサンブル）
    weights.json の重みを自動適用
    """
    weights = get_agent_weights()
    
    speed_weight = weights.get("SpeedAgent", 0.35)
    adapt_weight = weights.get("AdaptabilityAgent", 0.35)
    pedigree_weight = weights.get("PedigreeFormAgent", 0.30)
    
    # 各エージェントのスコアを計算
    speed_score = calculate_speed_score(horse, race, speed_weight)
    adapt_score = calculate_adaptability_score(horse, race, adapt_weight)
    pedigree_score = calculate_pedigree_score(horse, race, pedigree_weight)
    
    # 統合スコア
    total_score = speed_score + adapt_score + pedigree_score
    
    return total_score


def calculate_expected_value(uma_index: float, odds: float) -> float:
    """期待値を計算"""
    if odds <= 0:
        return 0
    
    # UMA指数を勝率に変換（簡易版）
    # 指数70以上 → 勝率約25%
    # 指数60以上 → 勝率約15%
    # 指数50以上 → 勝率約10%
    if uma_index >= 70:
        win_prob = 0.25
    elif uma_index >= 60:
        win_prob = 0.15
    elif uma_index >= 50:
        win_prob = 0.10
    else:
        win_prob = 0.05
    
    return win_prob * odds


def get_rank_from_score(score: float) -> str:
    """スコアからランクを決定"""
    if score >= 75:
        return "S+"
    elif score >= 65:
        return "S"
    elif score >= 55:
        return "A"
    elif score >= 45:
        return "B"
    else:
        return "C"


# --- ヘルパー関数 ---

def load_json_file(file_path: Path) -> dict:
    """JSONファイルを読み込み（UTF-8エンコーディング強制）"""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"ファイル読み込みエラー: {file_path}: {e}")
        return {}


def save_json_file(file_path: Path, data: dict) -> bool:
    """JSONファイルを保存（UTF-8エンコーディング強制）"""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"ファイル保存エラー: {file_path}: {e}")
        return False


def get_all_bet_types_display(race_data: dict) -> dict:
    """全券種の表示用データを取得"""
    bets = race_data.get("bets", {})
    if not bets:
        horses = race_data.get("horses", []) or race_data.get("predictions", [])
        multi_bets = {}
        if horses:
            # horses 内に multi_bets があればそれを使用
            for h in horses:
                mb = h.get("multi_bets")
                if mb:
                    multi_bets = mb
                    break
        # multi_bets から display 形式に変換
        if multi_bets:
            def _nums_from_label(label: str) -> list:
                import re
                if not label: return []
                return re.findall(r'\d+', str(label))
            display = {}
            # 単勝
            win = (multi_bets.get("単勝") or [])
            if win:
                n = _nums_from_label(win[0].get("label"))
                display["tansho_display"] = n[0] if n else None
            # 複勝
            plc = (multi_bets.get("複勝") or [])
            if plc:
                n = _nums_from_label(plc[0].get("label"))
                display["fukusho_display"] = n[0] if n else None
            # 枠連
            brq = (multi_bets.get("枠連") or [])
            if brq:
                n = _nums_from_label(brq[0].get("label"))
                if len(n) >= 2:
                    display["wakuren_display"] = f"{n[0]}-{n[1]}"
            # 馬連
            qnl = (multi_bets.get("馬連") or [])
            if qnl:
                n = _nums_from_label(qnl[0].get("label"))
                if len(n) >= 2:
                    display["umaren_display"] = f"{n[0]}-{n[1]}"
            # ワイド
            wde = (multi_bets.get("ワイド") or [])
            if wde:
                n = _nums_from_label(wde[0].get("label"))
                if len(n) >= 2:
                    display["wide_display"] = f"{n[0]}-{n[1]}"
            # 馬単
            ext = (multi_bets.get("馬単") or [])
            if ext:
                n = _nums_from_label(ext[0].get("label"))
                if len(n) >= 2:
                    display["umatan_display"] = f"{n[0]}-{n[1]}"
            # 三連複
            trio = (multi_bets.get("3連複") or [])
            if trio:
                n = _nums_from_label(trio[0].get("label"))
                if len(n) >= 3:
                    display["sanrenpuku_display"] = f"{n[0]}-{n[1]}-{n[2]}"
            # 三連単
            trf = (multi_bets.get("3連単") or [])
            if trf:
                n = _nums_from_label(trf[0].get("label"))
                if len(n) >= 3:
                    display["sanrentan_display"] = f"{n[0]}-{n[1]}-{n[2]}"
            bets = display

    horses = race_data.get("horses", []) or race_data.get("predictions", [])
    top3 = [str(h.get("umaban", h.get("馬番", ""))) for h in horses[:3] if h.get("umaban") or h.get("馬番")]

    def _normalize_combo(value):
        if value is None or value == "":
            return "-"
        if isinstance(value, (list, tuple)):
            return "-".join(str(v) for v in value if v is not None and v != "")
        text = str(value)
        text = text.replace("→", "-")
        return text

    def _fallback(key: str) -> str:
        if not top3:
            return "-"
        if key in ("tansho", "fukusho"):
            return top3[0]
        if key in ("wakuren", "umaren", "umatan"):
            return "-".join(top3[:2]) if len(top3) >= 2 else top3[0]
        if key == "wide":
            if len(top3) >= 3:
                return f"{top3[0]}-{top3[1]} / {top3[0]}-{top3[2]}"
            return "-".join(top3[:2]) if len(top3) >= 2 else top3[0]
        if key in ("sanrenpuku", "sanrentan"):
            return "-".join(top3) if len(top3) >= 3 else "-".join(top3[:2])
        return "-"

    result = {}
    for key, src in {
        "tansho": "tansho_display",
        "fukusho": "fukusho_display",
        "wakuren": "wakuren_display",
        "umaren": "umaren_display",
        "wide": "wide_display",
        "umatan": "umatan_display",
        "sanrenpuku": "sanrenpuku_display",
        "sanrentan": "sanrentan_display",
    }.items():
        value = bets.get(src)
        normalized = _normalize_combo(value) if value else _fallback(key)
        result[key] = normalized
    return result


def check_hit_result(race_pred: dict, race_result: dict) -> dict:
    """予想と結果を照合して的中判定"""
    if not race_result or not race_result.get("horses"):
        return {"is_hit": False, "hit_types": [], "actual_order": []}
    
    # 結果データから着順を取得
    result_horses = sorted(race_result["horses"], key=lambda x: x.get("order", 99))
    top3 = [h.get("umaban") for h in result_horses[:3] if h.get("umaban")]
    
    if not top3 or len(top3) < 3:
        return {"is_hit": False, "hit_types": [], "actual_order": []}
    
    hit_types = []
    bets = race_pred.get("bets", {})
    
    # 単勝的中判定
    tansho_pred = bets.get("tansho_display")
    if tansho_pred and str(tansho_pred) == str(top3[0]):
        hit_types.append("単勝")
    
    # 複勝的中判定（1-3着のいずれか）
    fukusho_pred = bets.get("fukusho_display")
    if fukusho_pred and str(fukusho_pred) in [str(x) for x in top3]:
        hit_types.append("複勝")
    
    # 馬連的中判定（1-2着の組み合わせ）
    umaren_pred = bets.get("umaren_display")
    if umaren_pred:
        pred_nums = sorted([str(x) for x in umaren_pred.split("-")])
        result_nums = sorted([str(top3[0]), str(top3[1])])
        if pred_nums == result_nums:
            hit_types.append("馬連")
    
    # 馬単的中判定（1→2着の流れ）
    umatan_pred = bets.get("umatan_display")
    if umatan_pred:
        pred_nums = [str(x) for x in str(umatan_pred).replace("→", "-").split("-") if x]
        if len(pred_nums) >= 2 and pred_nums[0] == str(top3[0]) and pred_nums[1] == str(top3[1]):
            hit_types.append("馬単")
    
    # 三連複的中判定（1-2-3着の組み合わせ）
    sanrenpuku_pred = bets.get("sanrenpuku_display")
    if sanrenpuku_pred:
        pred_nums = sorted([str(x) for x in sanrenpuku_pred.split("-")])
        result_nums = sorted([str(top3[0]), str(top3[1]), str(top3[2])])
        if pred_nums == result_nums:
            hit_types.append("三連複")
    
    # 三連単的中判定（1→2→3着の流れ）
    sanrentan_pred = bets.get("sanrentan_display")
    if sanrentan_pred:
        pred_nums = [str(x) for x in str(sanrentan_pred).replace("→", "-").split("-") if x]
        if (len(pred_nums) >= 3 and 
            pred_nums[0] == str(top3[0]) and 
            pred_nums[1] == str(top3[1]) and 
            pred_nums[2] == str(top3[2])):
            hit_types.append("三連単")
    
    return {
        "is_hit": len(hit_types) > 0,
        "hit_types": hit_types,
        "actual_order": top3
    }


def load_predictions(date_str: str = None) -> dict:
    """予想データを読み込み"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    file_path = HISTORY_DIR / f"{PREDICTIONS_PREFIX}{date_str}.json"
    if not file_path.exists():
        # フォールバック: data直下も探す
        file_path = DATA_DIR / f"{PREDICTIONS_PREFIX}{date_str}.json"
    return load_json_file(file_path)


def load_results(date_str: str = None) -> dict:
    """結果データを読み込み（アーカイブ対応）"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    # まずアーカイブから探す
    year = date_str[:4]
    month = date_str[4:6]
    day = date_str[6:8]
    archive_path = ARCHIVE_DIR / year / month / day / f"{RESULTS_PREFIX}{date_str}.json"

    if archive_path.exists():
        return load_json_file(archive_path)

    # なければdata/から探す
    file_path = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
    return load_json_file(file_path)


def load_insider_alerts() -> dict:
    """インサイダーアラートを読み込み"""
    return load_json_file(ALERTS_FILE)


def load_history() -> list:
    """的中履歴を読み込み"""
    data = load_json_file(HISTORY_FILE)
    return data.get("history", [])


def load_archive_index() -> dict:
    """アーカイブインデックスを読み込み"""
    return load_json_file(INDEX_FILE)


def get_available_dates() -> list:
    """利用可能な日付リストを取得"""
    dates = set()

    # data/から取得
    for f in DATA_DIR.glob(f"{RESULTS_PREFIX}*.json"):
        match = f.stem.replace(RESULTS_PREFIX, "")
        if len(match) == 8 and match.isdigit():
            dates.add(match)

    # アーカイブから取得
    if ARCHIVE_DIR.exists():
        for year_dir in ARCHIVE_DIR.iterdir():
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue
                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir() or not day_dir.name.isdigit():
                        continue
                    date_str = f"{year_dir.name}{month_dir.name}{day_dir.name}"
                    dates.add(date_str)

    return sorted(dates, reverse=True)


def format_date_jp(date_str: str) -> str:
    """日付を日本語形式にフォーマット"""
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        weekday = WEEKDAY_JP[dt.weekday()]
        return f"{dt.month}月{dt.day}日 ({weekday})"
    except Exception:
        return date_str


def get_rank_badge_html(rank: str) -> str:
    """ランクバッジのHTMLを生成"""
    rank_classes = {
        "S+": "rank-s-plus",
        "S": "rank-s",
        "A": "rank-a",
        "B": "rank-b",
        "C": "rank-c",
        "D": "rank-c"
    }
    css_class = rank_classes.get(rank, "rank-c")
    return f'<span class="rank-badge {css_class}">{rank}</span>'


def sort_races_by_number(races: list) -> list:
    """レースを番号順にソート（1R→12R）"""
    def get_race_num(race):
        race_num = race.get("race_num", 0)
        if isinstance(race_num, str):
            # "1R" → 1 のように変換
            num_str = ''.join(filter(str.isdigit, race_num))
            return int(num_str) if num_str else 0
        return race_num if race_num else 0

    return sorted(races, key=get_race_num)


# --- メインヘッダー ---
st.markdown("""
<div class="main-header">
    <h1>🐎 UMA-Logic PRO</h1>
    <p>AI競馬予想システム - 商用グレード完全版（アンサンブル学習対応）</p>
</div>
""", unsafe_allow_html=True)


# --- サイドバー ---
with st.sidebar:
    st.markdown("### ⚙️ 設定")

    # 資金設定
    bankroll = st.number_input(
        "💰 総資金 (円)",
        min_value=10000,
        max_value=10000000,
        value=100000,
        step=10000
    )

    # ケリー基準モード
    kelly_mode = st.selectbox(
        "📊 投資モード",
        ["ハーフケリー（安全）", "フルケリー（標準）", "アグレッシブ（積極的）"]
    )

    st.markdown("---")

    # AI重み表示
    st.markdown("### 🧠 AI重み（自動適用）")
    
    ai_data = load_ai_weights()
    weights = ai_data.get("weights", DEFAULT_WEIGHTS)
    metrics = ai_data.get("metrics", {})
    test_metrics = ai_data.get("test_metrics", {})
    updated_at = ai_data.get("updated_at", "未更新")
    
    # 重みバー表示
    speed_pct = weights.get("SpeedAgent", 0.35) * 100
    adapt_pct = weights.get("AdaptabilityAgent", 0.35) * 100
    pedigree_pct = weights.get("PedigreeFormAgent", 0.30) * 100
    
    st.markdown(f"""
    <div class="ai-weights-card">
        <div class="ai-weights-title">🔥 Speed: {speed_pct:.0f}%</div>
        <div class="weight-bar"><div class="weight-fill weight-speed" style="width: {speed_pct}%;"></div></div>
        <div class="ai-weights-title">🎯 Adapt: {adapt_pct:.0f}%</div>
        <div class="weight-bar"><div class="weight-fill weight-adapt" style="width: {adapt_pct}%;"></div></div>
        <div class="ai-weights-title">🧬 Pedigree: {pedigree_pct:.0f}%</div>
        <div class="weight-bar"><div class="weight-fill weight-pedigree" style="width: {pedigree_pct}%;"></div></div>
    </div>
    """, unsafe_allow_html=True)
    
    # テストデータの成績
    if test_metrics:
        test_hit_rate = test_metrics.get("hit_rate", 0) * 100
        test_recovery = test_metrics.get("recovery_rate", 0) * 100
        st.markdown(f"**テスト成績**: 的中率 {test_hit_rate:.1f}% / 回収率 {test_recovery:.1f}%")
    elif metrics:
        hit_rate = metrics.get("hit_rate", 0) * 100
        recovery = metrics.get("recovery_rate", 0) * 100
        st.markdown(f"**成績**: 的中率 {hit_rate:.1f}% / 回収率 {recovery:.1f}%")
    
    st.markdown(f"<small>更新: {updated_at}</small>", unsafe_allow_html=True)
    
    # 重み再読み込みボタン
    if st.button("🔄 重み再読み込み"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")

    # システム状態
    st.markdown("### 📈 システム状態")

    # 予想データの最新日付を直接取得（キャッシュを使わない）
    pred_files = sorted(DATA_DIR.glob(f"{PREDICTIONS_PREFIX}*.json"), reverse=True)
    latest_pred_date = None
    for pf in pred_files:
        dm = pf.stem.replace(PREDICTIONS_PREFIX, "")
        if len(dm) == 8 and dm.isdigit():
            latest_pred_date = dm
            break

    if latest_pred_date:
        st.metric("🎯 予想データ", format_date_jp(latest_pred_date))
    
    # 結果データ（アーカイブ）
    available_dates = get_available_dates()
    st.metric("📅 結果データ", f"{len(available_dates)}日分")


# --- メインタブ ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "🏇 本日の予想", 
    "📊 レース結果", 
    "✅ 的中実績",
    "📈 回収率分析", 
    "💰 資金配分", 
    "🧠 AI学習状況", 
    "📁 予想アーカイブ",
    "⚙️ 設定"
])


# === タブ1: 本日の予想 ===
with tab1:
    # ヘッダー + 再予想ボタン
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.header("🎯 本日の予想")
    with header_col2:
        if st.button("🔄 最新データで再予想", type="primary", key="repredict_btn"):
            with st.spinner("最新データを取得して再予想中..."):
                try:
                    today_str = datetime.now().strftime("%Y%m%d")
                    base_dir = Path(__file__).parent
                    ro_path = base_dir / "scripts" / "fetch_realtime_odds.py"
                    tp_path = base_dir / "scripts" / "test_predictions.py"
                    if ro_path.exists():
                        subprocess.run([sys.executable, str(ro_path)], check=False, capture_output=True, text=True, encoding='utf-8', errors='replace')
                    if tp_path.exists():
                        subprocess.run([sys.executable, str(tp_path), "--date", today_str], check=False, capture_output=True, text=True, encoding='utf-8', errors='replace')
                except Exception:
                    st.error("再予想の実行に失敗しました")
                else:
                    st.success("最新のオッズ・データで再予想を完了しました")
                    st.cache_data.clear()
                    st.rerun()
    st.info("📅 予想データ更新スケジュール：土・日 7:00頃（自動更新）")
    
    # 5分おき自動更新
    if HAS_AUTOREFRESH:
        refresh_count = st_autorefresh(interval=5 * 60 * 1000, limit=None, key="auto_refresh_5min")
    else:
        refresh_count = 0
    
    # 最終更新時刻 + ライブインジケーター + カウントダウン
    now = datetime.now()
    next_refresh = now + timedelta(minutes=5)
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 1rem; flex-wrap: wrap;">
        <span class="live-indicator"><span class="live-dot"></span> LIVE</span>
        <span class="countdown-bar">🔄 次回自動更新: {next_refresh.strftime('%H:%M')}</span>
        <span style="color: #e2e8f0; font-size: 0.9rem; font-weight: 600;">
            最終更新: {now.strftime('%H:%M:%S')}
        </span>
    </div>
    """, unsafe_allow_html=True)

    # インサイダーアラート表示
    alerts_data = load_insider_alerts()
    active_alerts = [a for a in alerts_data.get("alerts", [])
                     if a.get("status") == "active"]

    if active_alerts:
        st.markdown("### 🚨 インサイダーアラート")
        for alert in active_alerts[:3]:
            st.markdown(f"""
            <div class="insider-alert">
                <strong>⚡ {alert.get('venue', '')} {alert.get('race_num', '')}R - {alert.get('horse_name', '')}</strong><br>
                オッズ急落検知: {alert.get('odds_before', 0):.1f} → {alert.get('odds_after', 0):.1f}
                （{alert.get('drop_rate', 0)*100:.1f}%低下）<br>
                <small>検出時刻: {alert.get('detected_at', '')}</small>
            </div>
            """, unsafe_allow_html=True)

    # 予想データ読み込み（当日データのみ）
    today_str = datetime.now().strftime("%Y%m%d")
    predictions = load_predictions(today_str)
    display_date = today_str

    if not (predictions and predictions.get("races")):
        st.info("本日開催のレースはありません（過去のデータは予想アーカイブをご覧ください）")

    if predictions and predictions.get("races"):
        # 日付バナー
        if display_date != today_str:
            st.info(f"📅 最新の予想データを表示中: **{format_date_jp(display_date)}** ｜ 予想データ更新スケジュール：土・日 7:00頃（自動更新）")
        else:
            st.success(f"✅ 本日 {format_date_jp(today_str)} の予想データを表示中")
        
        save_col1, save_col2 = st.columns(2)
        with save_col1:
            if st.button("💾 本日の予想を保存（JSON）", key="save_today_json"):
                ts = datetime.now().strftime("%H%M%S")
                outfile = HISTORY_DIR / f"{PREDICTIONS_PREFIX}{today_str}_snapshot_{ts}.json"
                if predictions:
                    ok = save_json_file(outfile, predictions)
                    if ok:
                        st.success(f"保存しました: {outfile.name}")
                    else:
                        st.error("保存に失敗しました")
        with save_col2:
            if st.button("💾 本日の買い目を保存（CSV）", key="save_today_csv"):
                ts = datetime.now().strftime("%H%M%S")
                csvfile = HISTORY_DIR / f"bets_{today_str}_snapshot_{ts}.csv"
                try:
                    with open(csvfile, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["date", "venue", "race_num", "race_name", "bet_type", "combo"])
                        for race in predictions.get("races", []):
                            bets_map = get_all_bet_types_display(race)
                            for bt, combo in bets_map.items():
                                writer.writerow([today_str, race.get("venue",""), race.get("race_num",0), race.get("race_name",""), bt, combo])
                    st.success(f"保存しました: {csvfile.name}")
                except Exception:
                    st.error("保存に失敗しました")

        races = predictions.get("races", [])
        races = sort_races_by_number(races)  # レース番号順にソート

        # 競馬場でグループ化
        venues = list(set(r.get("venue", "") for r in races))
        venues = sorted(venues)

        if venues:
            selected_venue = st.selectbox("🏟️ 競馬場を選択", venues)

            venue_races = [r for r in races if r.get("venue") == selected_venue]
            venue_races = sort_races_by_number(venue_races)

            for race in venue_races:
                race_num = race.get("race_num", 0)
                race_name = race.get("race_name", "")
                distance = race.get("distance", 0)
                track_type = race.get("track_type", "")
                rank = race.get("rank", "")

                # S+/Sランクは自動展開
                auto_expand = rank in ["S+", "S"]
                with st.expander(f"🏇 {race_num}R {race_name} ({track_type}{distance}m) {get_rank_badge_html(rank) if rank else ''}", expanded=auto_expand):
                    horses = race.get("horses", []) or race.get("predictions", [])

                    if horses:
                        # AI予測実行（キー正規化: calculator_pro出力→calculator_ml入力）
                        normalized_horses = []
                        for h in horses:
                            nh = dict(h)  # コピー
                            # calculator_pro出力キー→calculator_ml入力キーに変換
                            if "umaban" in nh and "馬番" not in nh:
                                nh["馬番"] = nh["umaban"]
                            if "horse_name" in nh and "馬名" not in nh:
                                nh["馬名"] = nh["horse_name"]
                            normalized_horses.append(nh)
                        
                        race_for_ml = race.copy()
                        race_for_ml["all_results"] = normalized_horses
                        
                        sorted_horses_ml, recommendations = ml_calc.predict_race(race_for_ml)
                        
                        if sorted_horses_ml:
                            horses = sorted_horses_ml
                            
                            # 🌟 注目馬を強制表示（EV問わず上位5頭）
                            top5_names = []
                            for th in horses[:5]:
                                tn = th.get("horse_name", th.get("馬名", ""))
                                tb = th.get("umaban", th.get("馬番", ""))
                                to = float(th.get("odds", 0) or 0)
                                top5_names.append(f"{tb}番 {tn}({to:.1f}倍)" if to > 0 else f"{tb}番 {tn}")
                            
                            # AI指数1位の馬番で単勝推奨
                            best_horse = horses[0] if horses else None
                            best_umaban = best_horse.get("umaban", best_horse.get("馬番", "")) if best_horse else ""
                            best_name = best_horse.get("horse_name", best_horse.get("馬名", "")) if best_horse else ""
                            
                            st.markdown(f"""
                            <div style="background: rgba(255, 215, 0, 0.08); border: 1px solid #ffd700; padding: 0.7rem 1rem; border-radius: 10px; margin-bottom: 0.6rem;">
                                <strong style="color:#ffd700;">🌟 注目馬 TOP5:</strong>
                                <span style="color:#FFFFFF; font-weight:700;"> {' ／ '.join(top5_names)}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # AI推奨単勝 + 馬連を常にクッキリ表示
                            if best_umaban:
                                # 馬連: 上位2頭
                                second_horse = horses[1] if len(horses) > 1 else None
                                second_umaban = second_horse.get("umaban", second_horse.get("馬番", "")) if second_horse else ""
                                quinella_display = f"馬連 {best_umaban}-{second_umaban}" if second_umaban else f"単勝 {best_umaban}"
                                
                                st.markdown(f"""
                                <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid #10b981; padding: 0.6rem 1rem; border-radius: 10px; margin-bottom: 0.8rem;">
                                    <strong>🤖 AI推奨:</strong> <span style="color:#ffd700; font-weight:700; font-size:1.1rem;">単勝 {best_umaban}番 {best_name}</span>
                                    <span style="color:#FFFFFF; font-weight:700; font-size:1.05rem; margin-left:1rem;">📊 {quinella_display}</span>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            # 🛠️ データ補完済み表示
                            complemented_horses = [h for h in horses[:5] if h.get("data_quality", "完全") != "完全" or h.get("is_estimated", False)]
                            if complemented_horses:
                                st.markdown(f"""
                                <div style="background: rgba(16, 185, 129, 0.06); border: 1px solid rgba(16, 185, 129, 0.3); padding: 0.3rem 0.8rem; border-radius: 8px; margin-bottom: 0.5rem; font-size: 0.8rem;">
                                    🛠️ <span style="color:#34d399;">リアルタイムデータ補完済み</span>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            # UI互換性のためにキー変換
                            for h in horses:
                                h["uma_index"] = h.get("uma_score", 0)
                                h["rank"] = get_rank_from_score(h["uma_index"])
                        else:
                            # フォールバック（既存ロジック）
                            for horse in horses:
                                uma_index = calculate_uma_index(horse, race)
                                horse["uma_index"] = uma_index
                                horse["rank"] = get_rank_from_score(uma_index)
    
                                odds = float(horse.get("オッズ", horse.get("odds", 0)) or 0)
                                horse["expected_value"] = calculate_expected_value(uma_index, odds)
    
                            # UMA指数でソート
                            horses = sorted(horses, key=lambda x: x.get("uma_index", 0), reverse=True)

                        for i, horse in enumerate(horses[:5]):  # 上位5頭表示
                            umaban = horse.get("umaban", horse.get("馬番", ""))
                            name = horse.get("horse_name", horse.get("馬名", ""))
                            odds_val = float(horse.get("odds", horse.get("オッズ", 0)) or 0)
                            uma_index = horse.get("uma_index", 0)
                            rank_h = horse.get("rank", "C")
                            ev = horse.get("expected_value", 0)
                            prob = horse.get("prob_top3", 0)

                            # ケリー推奨投資額を計算（積極運用モード）
                            kelly_bet_str = ""
                            if odds_val > 0 and prob > 0:
                                b = odds_val - 1
                                kelly_f = (b * prob - (1 - prob)) / b if b > 0 else 0
                                kelly_f = max(0, kelly_f) * 0.25  # Quarter Kelly
                                if kelly_f > 0 and ev > 1.0:
                                    bet_amt = max(200, min(500, int(bankroll * kelly_f / 100) * 100))
                                    kelly_bet_str = f"💰{bet_amt:,}円"
                                elif ev >= 0.90 and i < 3:  # 積極運用モード: EV≥0.90で0.5-1%
                                    agg_rate = 0.005 + (ev - 0.90) * 0.05  # 0.5%〜1%
                                    agg_amt = max(200, min(1000, int(bankroll * agg_rate / 100) * 100))
                                    kelly_bet_str = f"🔥{agg_amt:,}円"
                                elif i == 0:  # AI指数1位は常に最低額表示
                                    kelly_bet_str = f"🔸¥200"

                            # 印を決定
                            marks = ["◎", "○", "▲", "△", "☆"]
                            mark = marks[i] if i < len(marks) else ""

                            col1, col2, col3, col4, col5, col6, col7 = st.columns([0.8, 0.8, 3, 1.8, 1.8, 1.2, 1])
                            with col1:
                                st.markdown(f"**{mark}**")
                            with col2:
                                st.markdown(f"**{umaban}**")
                            with col3:
                                st.markdown(f"**{name}**")
                            with col4:
                                if uma_index > 0:
                                    st.markdown(f"指数: **{uma_index:.1f}**")
                            with col5:
                                if odds_val > 0:
                                    st.markdown(f"オッズ: **{odds_val:.1f}**")
                            with col6:
                                st.markdown(get_rank_badge_html(rank_h), unsafe_allow_html=True)
                            with col7:
                                if kelly_bet_str:
                                    st.markdown(f'<span style="color:#ffd700;font-size:0.85rem;font-weight:700;">{kelly_bet_str}</span>', unsafe_allow_html=True)
                        
                        # === 全券種 複数買い目パネル ===
                        multi_bets = horses[0].get("multi_bets", {}) if horses else {}
                        if multi_bets:
                            st.markdown("---")
                            st.markdown('<p style="color:#ffd700;font-weight:700;font-size:1.05rem;margin-bottom:0.5rem;">📋 全券種 AI推奨買い目</p>', unsafe_allow_html=True)
                            
                            # 券種を2列で表示
                            bet_types_order = ["単勝", "複勝", "馬連", "ワイド", "馬単", "3連複", "3連単"]
                            bet_icons = {"単勝": "🎯", "複勝": "🛡️", "馬連": "🔗", "ワイド": "🌊", "馬単": "➡️", "3連複": "🔺", "3連単": "💎"}
                            
                            col_left, col_right = st.columns(2)
                            for idx, bt in enumerate(bet_types_order):
                                bets = multi_bets.get(bt, [])
                                if not bets:
                                    continue
                                target_col = col_left if idx % 2 == 0 else col_right
                                with target_col:
                                    icon = bet_icons.get(bt, "📌")
                                    rows_html = ""
                                    for bi, b in enumerate(bets[:4]):
                                        ev_color = "#ffd700" if b["ev"] >= 1.0 else "#60a5fa" if b["ev"] >= 0.9 else "#94a3b8"
                                        rank_mark = "◎" if bi == 0 else "○" if bi == 1 else "▲" if bi == 2 else "△"
                                        type_badge = ""
                                        if b.get("type"):
                                            type_badge = f'<span style="color:#f97316;font-size:0.7rem;margin-left:4px;">({b["type"]})</span>'
                                        rows_html += f"""<tr>
                                            <td style="color:#ffd700;font-weight:700;width:24px;">{rank_mark}</td>
                                            <td style="font-weight:700;color:#FFFFFF;">{b['label']}{type_badge}</td>
                                            <td style="color:#34d399;font-size:0.8rem;white-space:nowrap;">{b['prob']}%</td>
                                            <td style="color:{ev_color};font-weight:700;font-size:0.8rem;white-space:nowrap;">EV {b['ev']}</td>
                                        </tr>"""
                                    st.markdown(f"""
                                    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,215,0,0.15);border-radius:8px;padding:0.5rem;margin-bottom:0.5rem;">
                                        <div style="color:#ffd700;font-weight:700;font-size:0.9rem;margin-bottom:0.3rem;">{icon} {bt}</div>
                                        <table style="width:100%;border-collapse:collapse;font-size:0.82rem;">
                                            {rows_html}
                                        </table>
                                    </div>
                                    """, unsafe_allow_html=True)
                    else:
                        st.info("出馬データがありません")
    else:
        st.info("📭 予想データがありません。")


# === タブ2: レース結果（階層型検索UI） ===
with tab2:
    st.header("📊 レース結果")

    # 利用可能な日付を取得
    available_dates = get_available_dates()

    if not available_dates:
        st.info("📭 レース結果データがありません。")
    else:
        # 年でグループ化
        dates_by_year = {}
        for date_str in available_dates:
            year = date_str[:4]
            if year not in dates_by_year:
                dates_by_year[year] = []
            dates_by_year[year].append(date_str)

        # 階層型フィルター
        filter_col1, filter_col2 = st.columns(2)

        with filter_col1:
            years = sorted(dates_by_year.keys(), reverse=True)
            selected_year = st.selectbox("📅 年を選択", years, key="result_year")

        with filter_col2:
            year_dates = dates_by_year.get(selected_year, [])
            date_options = [(d, format_date_jp(d)) for d in year_dates]

            if date_options:
                selected_date_idx = st.selectbox(
                    "📆 開催日を選択",
                    range(len(date_options)),
                    format_func=lambda x: date_options[x][1],
                    key="result_date"
                )
                selected_date = date_options[selected_date_idx][0]
            else:
                selected_date = None

        if selected_date:
            # 結果データを読み込み
            results_data = load_results(selected_date)

            if results_data and results_data.get("races"):
                races = results_data.get("races", [])
                races = sort_races_by_number(races)  # レース番号順にソート

                # 競馬場でグループ化 (venue が空の場合は race_id から補完)
                _VENUE_CODE_MAP = {
                    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
                    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
                    "09": "阪神", "10": "小倉", "30": "門別", "35": "帯広",
                    "42": "盛岡", "43": "水沢", "46": "上山", "50": "浦和",
                    "51": "船橋", "54": "大井", "55": "川崎", "58": "金沢",
                    "59": "笠松", "60": "名古屋", "62": "園田", "63": "姫路",
                    "65": "福山", "66": "高知", "70": "佐賀",
                }
                def _resolve_venue(race: dict) -> str:
                    v = race.get("venue", "")
                    if v:
                        return v
                    rid = str(race.get("race_id", ""))
                    if len(rid) >= 10:
                        return _VENUE_CODE_MAP.get(rid[4:6], f"会場{rid[4:6]}")
                    return "不明"

                # venue を補完してからグループ化
                for _r in races:
                    if not _r.get("venue"):
                        _r["venue"] = _resolve_venue(_r)

                venues = sorted(set(r.get("venue", "不明") for r in races))


                if venues:
                    # 競馬場タブ
                    venue_tabs = st.tabs(venues)

                    for venue_tab, venue in zip(venue_tabs, venues):
                        with venue_tab:
                            venue_races = [r for r in races if r.get("venue") == venue]
                            venue_races = sort_races_by_number(venue_races)

                            for race in venue_races:
                                race_num = race.get("race_num", 0)
                                race_name = race.get("race_name", "")

                                # レースカード
                                _dist = race.get('distance', '')
                                _track = race.get('track_type', '')
                                _info_parts = [venue]
                                if _dist:
                                    _info_parts.append(f"{_dist}m")
                                if _track:
                                    _info_parts.append(_track)
                                _race_info_str = " / ".join(_info_parts)
                                st.markdown(f"""
                                <div class="race-card">
                                    <div class="race-title">{race_num}R {race_name}</div>
                                    <div class="race-info">{_race_info_str}</div>
                                </div>
                                """, unsafe_allow_html=True)


                                with st.expander(f"📋 詳細を見る", expanded=False):
                                    # 着順表
                                    st.markdown("#### 🏆 着順")
                                    top3 = race.get("top3", [])
                                    all_results = race.get("all_results", top3)

                                    if all_results:
                                        result_df = pd.DataFrame(all_results)

                                        # カラム名を日本語に
                                        column_mapping = {
                                            "着順": "着順",
                                            "rank": "着順",
                                            "馬番": "馬番",
                                            "umaban": "馬番",
                                            "馬名": "馬名",
                                            "horse_name": "馬名",
                                            "騎手": "騎手",
                                            "jockey": "騎手",
                                            "タイム": "タイム",
                                            "time": "タイム",
                                            "上がり3F": "上がり3F",
                                            "last_3f": "上がり3F",
                                            "オッズ": "オッズ",
                                            "odds": "オッズ",
                                            "人気": "人気",
                                            "popularity": "人気"
                                        }

                                        result_df = result_df.rename(columns=column_mapping)

                                        display_cols = ["着順", "馬番", "馬名", "騎手", "タイム", "上がり3F", "オッズ", "人気"]
                                        display_cols = [c for c in display_cols if c in result_df.columns]

                                        if display_cols:
                                            header_html = "".join([f"<th style='padding:6px 10px;border:1px solid #1f2937;background:#0f172a;color:#e2e8f0;'>{c}</th>" for c in display_cols])
                                            body_rows = []
                                            for _, row in result_df[display_cols].iterrows():
                                                tds = "".join([
                                                    f"<td style='padding:6px 10px;border:1px solid #1f2937;background:#0a0f1a;color:#e2e8f0;'>{row[c] if pd.notna(row[c]) else '-'}</td>"
                                                    for c in display_cols
                                                ])
                                                body_rows.append(f"<tr>{tds}</tr>")
                                            table_html = f"""
                                            <table style="width:100%;border-collapse:collapse;">
                                                <thead><tr>{header_html}</tr></thead>
                                                <tbody>{"".join(body_rows)}</tbody>
                                            </table>
                                            """
                                            st.markdown(table_html, unsafe_allow_html=True)
                                    else:
                                        st.info("着順データがありません")

                                    # 払戻金表
                                    st.markdown("#### 💰 払戻金")
                                    payouts = race.get("payouts", {})

                                    if payouts:
                                        def _get_umaban(h):
                                            return h.get("馬番") or h.get("umaban")
                                        pop_map = {}
                                        for h in all_results or []:
                                            n = _get_umaban(h)
                                            p = h.get("人気") or h.get("popularity")
                                            if n is not None:
                                                pop_map[str(n)] = p
                                        def _label_with_pop(n):
                                            if n in (None, "", "-"):
                                                return "-"
                                            p = pop_map.get(str(n))
                                            return f"{n}番 ({p}人気)" if p is not None else f"{n}番"
                                        def _top_order_nums():
                                            nums = []
                                            if isinstance(top3, list) and top3 and isinstance(top3[0], dict):
                                                for h in top3[:3]:
                                                    n = _get_umaban(h)
                                                    if n is not None:
                                                        nums.append(str(n))
                                            elif isinstance(all_results, list) and all_results and isinstance(all_results[0], dict):
                                                try:
                                                    sorted_res = sorted(all_results, key=lambda x: int(str(x.get("着順", x.get("rank", 999)))))
                                                    for h in sorted_res[:3]:
                                                        n = _get_umaban(h)
                                                        if n is not None:
                                                            nums.append(str(n))
                                                except Exception:
                                                    pass
                                            return nums
                                        _top = _top_order_nums()
                                        res_annot = ""
                                        if len(_top) >= 3:
                                            res_annot = f"【結果 1着:{_top[0]}番 / 2着:{_top[1]}番 / 3着:{_top[2]}番】"

                                        payout_col1, payout_col2 = st.columns(2)

                                        payout_items = list(payouts.items())
                                        mid = len(payout_items) // 2 + len(payout_items) % 2

                                        with payout_col1:
                                            for key, value in payout_items[:mid]:
                                                if isinstance(value, dict):
                                                    parts = []
                                                    for k, v in value.items():
                                                        k_str = str(k)
                                                        if "-" in k_str:
                                                            parts.append(f"{k_str}: ¥{v:,}")
                                                        else:
                                                            parts.append(f"{_label_with_pop(k_str)}: ¥{v:,}")
                                                    st.markdown(f"**{key}**: " + " / ".join(parts) + (f" {res_annot}" if res_annot else ""))
                                                else:
                                                    combo = ""
                                                    if key in ["単勝"]:
                                                        if _top:
                                                            combo = _label_with_pop(_top[0])
                                                    elif key in ["馬連", "馬単", "ワイド"]:
                                                        if len(_top) >= 2:
                                                            combo = f"{_top[0]}-{_top[1]}"
                                                    elif key in ["三連複", "三連単"]:
                                                        if len(_top) >= 3:
                                                            combo = f"{_top[0]}-{_top[1]}-{_top[2]}"
                                                    elif key in ["枠連"]:
                                                        combo = "-"
                                                    extra = (f" 【{combo}】" if combo else "")
                                                    st.markdown(f"**{key}**: ¥{value:,}" + extra + (f" {res_annot}" if res_annot else ""))

                                        with payout_col2:
                                            for key, value in payout_items[mid:]:
                                                if isinstance(value, dict):
                                                    parts = []
                                                    for k, v in value.items():
                                                        k_str = str(k)
                                                        if "-" in k_str:
                                                            parts.append(f"{k_str}: ¥{v:,}")
                                                        else:
                                                            parts.append(f"{_label_with_pop(k_str)}: ¥{v:,}")
                                                    st.markdown(f"**{key}**: " + " / ".join(parts) + (f" {res_annot}" if res_annot else ""))
                                                else:
                                                    combo = ""
                                                    if key in ["単勝"]:
                                                        if _top:
                                                            combo = _label_with_pop(_top[0])
                                                    elif key in ["馬連", "馬単", "ワイド"]:
                                                        if len(_top) >= 2:
                                                            combo = f"{_top[0]}-{_top[1]}"
                                                    elif key in ["三連複", "三連単"]:
                                                        if len(_top) >= 3:
                                                            combo = f"{_top[0]}-{_top[1]}-{_top[2]}"
                                                    elif key in ["枠連"]:
                                                        combo = "-"
                                                    extra = (f" 【{combo}】" if combo else "")
                                                    st.markdown(f"**{key}**: ¥{value:,}" + extra + (f" {res_annot}" if res_annot else ""))
                                    else:
                                        st.info("払戻金データがありません")

                                st.markdown("---")
                else:
                    st.warning("競馬場情報がありません")
            else:
                st.warning(f"{format_date_jp(selected_date)} のデータがありません")


# === タブ3: 的中実績 ===
with tab3:
    st.header("✅ 的中実績")

    # --- history.json から的中データを読み込む ---
    hist_data = {}
    _hist_path = DATA_DIR / "history.json"
    if _hist_path.exists():
        try:
            hist_data = json.loads(_hist_path.read_text(encoding='utf-8'))
        except Exception:
            hist_data = {}

    hit_log        = hist_data.get("hit_log", [])
    total_stats    = hist_data.get("total_stats", {})
    daily_records  = hist_data.get("daily_records", [])

    # --- ヘルパー: results_*.json から着順(1-2-3 馬番)を取得 ---
    @st.cache_data(ttl=300)
    def get_result_order(date_str: str) -> dict:
        """
        race_id -> "1着-2着-3着馬番" の辞書を返す
        例: {202605010811: "11-5-3"}
        """
        fp = DATA_DIR / f"results_{date_str}.json"
        out = {}
        if not fp.exists():
            return out
        try:
            data = json.loads(fp.read_text(encoding='utf-8'))
            for r in data.get("races", []):
                rid = r.get("race_id")
                top = r.get("top3") or r.get("all_results", [])[:3]
                if rid and len(top) >= 1:
                    nums = []
                    for h in top[:3]:
                        n = h.get("馬番") or h.get("umaban", "?")
                        nums.append(str(n))
                    out[str(rid)] = "-".join(nums)
        except Exception:
            pass
        return out

    @st.cache_data(ttl=300)
    def index_results(date_str: str) -> dict:
        fp = DATA_DIR / f"results_{date_str}.json"
        out = {"by_rid": {}, "by_sig": {}}
        if not fp.exists():
            return out
        try:
            data = json.loads(fp.read_text(encoding='utf-8'))
            for r in data.get("races", []):
                rid = str(r.get("race_id", ""))
                v = r.get("venue", "") or ""
                rn = r.get("race_num", 0)
                sig = f"{v}|{rn}"
                if rid:
                    out["by_rid"][rid] = r
                out["by_sig"][sig] = r
        except Exception:
            pass
        return out

    @st.cache_data(ttl=300)
    def get_pred_combos(date_str: str) -> dict:
        fp = HISTORY_DIR / f"{PREDICTIONS_PREFIX}{date_str}.json"
        out = {}
        if not fp.exists():
            return out
        try:
            data = json.loads(fp.read_text(encoding='utf-8'))
            for r in data.get("races", []):
                rid = str(r.get("race_id", ""))
                preds = r.get("predictions") or r.get("horses", [])
                if rid and preds:
                    top3 = [str(p.get("umaban", p.get("馬番", "?"))) for p in preds[:3]]
                    honmei_um = str(preds[0].get("umaban", preds[0].get("馬番", "?")) if preds else "?")
                    v_raw = r.get("venue", "")
                    rn = r.get("race_num", 0)
                    v_label = v_raw if v_raw else "-"
                    out[rid] = {
                        "honmei": honmei_um,
                        "combo_tansho": honmei_um,
                        "combo_umaren": f"{top3[0]}-{top3[1]}" if len(top3) >= 2 else honmei_um,
                        "combo_sanrentan": f"{top3[0]}-{top3[1]}-{top3[2]}" if len(top3) >= 3 else honmei_um,
                        "top3": top3,
                        "venue": v_label,
                        "race_num": rn,
                        "race_name": r.get("race_name", ""),
                    }
        except Exception:
            pass
        return out

    # --- サマリーカード ---
    if total_stats or hit_log:
        total_return = total_stats.get("total_return", 0)
        total_invest = total_stats.get("total_investment", 0)
        roi          = total_stats.get("roi", 0)
        hit_count    = len(hit_log)
        best_payout  = max((h.get("payout", 0) for h in hit_log), default=0)

        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.metric("📊 的中件数", f"{hit_count}件")
        with sc2:
            st.metric("💎 最高配当", f"¥{best_payout:,}")
        with sc3:
            st.metric("💰 回収総額", f"¥{total_return:,}")
        with sc4:
            st.metric("📈 回収率", f"{roi:.1f}%", delta=f"{roi-100:.1f}%")

        st.markdown("---")

    # --- 日別成績（着順+買い目 自動照合表示） ---
    if daily_records:
        st.markdown("### 📅 日別成績")
        for day in sorted(daily_records, key=lambda d: d.get("date", ""), reverse=True):
            day_date   = day.get("date", "")
            day_races  = day.get("races", 0)
            hi_list    = day.get("highlights", [])
            roi_d      = day.get("roi", 0)

            # date_str (YYYYMMDD) を作成
            date_str_raw = day_date.replace("-", "").replace("/", "")

            # 当日の着順情報を取得
            result_orders = get_result_order(date_str_raw)

            with st.expander(
                f"📆 {day_date} ({day.get('day_of_week', '')}) ― {day_races}R | ROI {roi_d:.1f}%",
                expanded=(day_date >= "2026-02-21")
            ):
                if hi_list:
                    for hi in hi_list:
                        payout      = hi.get("payout", 0)
                        bet         = hi.get("bet", 100)
                        ticket      = hi.get("ticket", "")
                        race_lbl    = hi.get("race", "")
                        combo       = hi.get("combination", hi.get("combo", ""))
                        result_ord  = hi.get("result_order", "")

                        # result_order が未記録なら race_id から自動取得を試みる
                        if not result_ord and hi.get("race_id"):
                            result_ord = result_orders.get(str(hi.get("race_id")), "")

                        color = "#ffd700" if payout >= 10000 else "#10b981" if payout >= 1000 else "#60a5fa"

                        # 着順行
                        order_html = ""
                        if result_ord:
                            order_html = (
                                f'<div style="color:#94a3b8;font-size:0.82rem;margin-top:2px;">'
                                f'着順：<span style="color:#e2e8f0;font-weight:700;">{result_ord}</span></div>'
                            )
                        combo_html = ""
                        if combo:
                            combo_html = (
                                f'<div style="color:#94a3b8;font-size:0.82rem;">'
                                f'買い目：<span style="color:#60a5fa;font-weight:700;">{combo}</span></div>'
                            )

                        st.markdown(f"""
                        <div style="background:rgba(255,215,0,0.06);border:1px solid {color};
                                    border-radius:10px;padding:0.7rem 1rem;margin:0.4rem 0;">
                            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                                <div>
                                    <span style="color:{color};font-weight:700;font-size:1rem;">{race_lbl}</span>
                                    &nbsp;｜&nbsp;<span style="color:#e2e8f0;">{ticket}</span>
                                    {combo_html}
                                    {order_html}
                                </div>
                                <div style="text-align:right;">
                                    <div style="color:#ffd700;font-weight:800;font-size:1.1rem;">¥{payout:,}</div>
                                    <div style="color:#94a3b8;font-size:0.8rem;">投資 ¥{bet:,}</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    # highlights が空の場合は predictions vs results を自動照合
                    pred_combos = get_pred_combos(date_str_raw)
                    res_index = index_results(date_str_raw)
                    if result_orders and pred_combos:
                        auto_hits_day = []
                        for rid, orders in result_orders.items():
                            pc = pred_combos.get(rid)
                            if not pc:
                                r_obj = res_index["by_rid"].get(rid)
                                if r_obj:
                                    sig = f'{r_obj.get("venue","")}|{r_obj.get("race_num",0)}'
                                    for pr_id, pr in pred_combos.items():
                                        if f'{pr.get("venue","")}|{pr.get("race_num",0)}' == sig:
                                            pc = pr
                                            break
                            if not pc:
                                continue
                            top_result = orders.split("-")
                            if top_result and pc["honmei"] == top_result[0]:
                                auto_hits_day.append({
                                    "race_id": rid,
                                    "combo": pc["combo_tansho"],
                                    "ticket": "単勝",
                                    "order": orders,
                                })
                            elif len(top_result) >= 2 and set(pc["top3"][:2]) == set(top_result[:2]):
                                auto_hits_day.append({
                                    "race_id": rid,
                                    "combo": pc["combo_umaren"],
                                    "ticket": "馬連",
                                    "order": orders,
                                })
                        if auto_hits_day:
                            st.markdown(f"**{len(auto_hits_day)} 件の的中を自動検出:**")
                            for ah in auto_hits_day:
                                r_detail = res_index["by_rid"].get(ah["race_id"])
                                payout_val = 0
                                race_name_disp = ""
                                if r_detail:
                                    vn = r_detail.get("venue", "")
                                    rn = r_detail.get("race_num", 0)
                                    rnm = r_detail.get("race_name", "")
                                    race_name_disp = f'{vn}{rn}R {rnm}' if vn else f'{rn}R {rnm}'
                                    pays = r_detail.get("payouts", {})
                                    if ah["ticket"] == "単勝":
                                        if isinstance(pays.get("単勝"), dict):
                                            win = ah["order"].split("-")[0] if ah["order"] else ""
                                            payout_val = int(pays["単勝"].get(win, 0) or 0)
                                        else:
                                            payout_val = int(pays.get("単勝", 0) or 0)
                                    elif ah["ticket"] == "馬連":
                                        key_um = None
                                        parts = ah["order"].split("-")
                                        if len(parts) >= 2:
                                            a, b = parts[0], parts[1]
                                            key_um = f"{min(a,b)}-{max(a,b)}"
                                        if isinstance(pays.get("馬連"), dict) and key_um:
                                            payout_val = int(pays["馬連"].get(key_um, 0) or 0)
                                        else:
                                            payout_val = int(pays.get("馬連", 0) or 0)
                                res_triplet = ah["order"].split("-")
                                ord_annot = ""
                                if res_triplet:
                                    one = res_triplet[0] if len(res_triplet) > 0 else "-"
                                    two = res_triplet[1] if len(res_triplet) > 1 else "-"
                                    three = res_triplet[2] if len(res_triplet) > 2 else "-"
                                    ord_annot = f'結果 1着:{one}番 / 2着:{two}番 / 3着:{three}番'
                                st.markdown(
                                    f'<div style="background:rgba(16,185,129,0.1);border:1px solid #10b981;'
                                    f'border-radius:10px;padding:0.7rem 1rem;margin:0.4rem 0;">'
                                    f'<div style="display:flex;justify-content:space-between;">'
                                    f'<div>'
                                    f'<div style="color:#e2e8f0;font-weight:700;">{race_name_disp}</div>'
                                    f'<div><span style="color:#10b981;font-weight:700;">{ah["ticket"]}</span>'
                                    f'｜<span style="color:#60a5fa;font-weight:700;">{ah["combo"]}</span></div>'
                                    f'<div style="color:#94a3b8;font-size:0.85rem;">{ord_annot}</div>'
                                    f'</div>'
                                    f'<div style="text-align:right;">'
                                    f'<div style="color:#ffd700;font-weight:800;font-size:1.1rem;">¥{payout_val:,}</div>'
                                    f'</div>'
                                    f'</div>'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                        else:
                            st.caption("この日の自動照合では的中なし（予想ファイルと結果ファイルが一致しませんでした）")
                    elif result_orders:
                        st.caption(f"この日の予想ファイルが見つかりません（results: {len(result_orders)}R取得済）")
                    else:
                        st.caption("この日の結果データがまだ取得されていません")

    # --- hit_log 全件一覧 ---
    if hit_log:
        st.markdown("---")
        st.markdown("### 📋 的中ログ全件")

        for h in sorted(hit_log, key=lambda x: x.get("date", ""), reverse=True):
            payout     = h.get("payout", 0)
            ticket     = h.get("ticket", "")
            race       = h.get("race", "")
            date_h     = h.get("date", "")
            combo      = h.get("combination", h.get("combo", ""))
            result_ord = h.get("result_order", "")

            # result_order が未記録なら自動取得を試みる
            if not result_ord and h.get("race_id"):
                ds = date_h.replace("-","").replace("/","")
                ros = get_result_order(ds)
                result_ord = ros.get(str(h.get("race_id")), "")

            color = "#ffd700" if payout >= 10000 else "#10b981" if payout >= 1000 else "#60a5fa"

            extra = ""
            if combo:
                extra += f'<span style="color:#60a5fa;font-size:0.85rem;font-weight:600;margin-left:0.7rem;">買: {combo}</span>'
            if result_ord:
                extra += f'<span style="color:#94a3b8;font-size:0.85rem;margin-left:0.7rem;">着順：{result_ord}</span>'

            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'border-bottom:1px solid rgba(255,255,255,0.08);padding:0.4rem 0;">'
                f'<span style="color:#e2e8f0;">{date_h}&nbsp;&nbsp;<strong>{race}</strong>'
                f'&nbsp;<span style="color:#94a3b8;">{ticket}</span>{extra}</span>'
                f'<span style="color:{color};font-weight:700;font-size:1.05rem;">¥{payout:,}</span></div>',
                unsafe_allow_html=True
            )
    elif not daily_records:
        # --- 自動照合フォールバック（history.json が空の場合） ---
        st.info("予想ファイルと結果ファイルを自動照合して的中を検索中...")
        auto_hits = []
        all_pred_files = sorted(HISTORY_DIR.glob(f"{PREDICTIONS_PREFIX}*.json"), reverse=True)
        for pred_file in all_pred_files[:10]:
            date_str = pred_file.stem.replace(PREDICTIONS_PREFIX, "")
            result_data = load_results(date_str)
            if result_data and result_data.get("races"):
                try:
                    pred_data  = json.loads(pred_file.read_text(encoding='utf-8'))
                    pred_races = pred_data.get("races", [])
                    res_races  = result_data.get("races", [])
                    for pr in pred_races:
                        rid = pr.get("race_id")
                        rr = next((r for r in res_races if r.get("race_id") == rid), None)
                        if rr:
                            p_horses = (pr.get("predictions") or pr.get("horses", []))[:3]
                            r_horses = (rr.get("top3") or rr.get("all_results", []))[:3]
                            if p_horses and r_horses:
                                p_win = str(p_horses[0].get("umaban", p_horses[0].get("馬番", "")))
                                r_win = str(r_horses[0].get("馬番", r_horses[0].get("umaban", "")))
                                top3_str = "-".join(
                                    str(h.get("馬番", h.get("umaban", "?"))) for h in r_horses[:3]
                                )
                                if p_win == r_win:
                                    win_odds = float(r_horses[0].get("オッズ", r_horses[0].get("odds", 0)) or 0)
                                    auto_hits.append({
                                        "date": f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}",
                                        "venue": pr.get("venue", ""),
                                        "race_num": pr.get("race_num", ""),
                                        "race_name": pr.get("race_name", ""),
                                        "bet_type": "単勝",
                                        "combination": p_win,
                                        "result_order": top3_str,
                                        "odds": win_odds,
                                        "payout": int(win_odds * 1000) if win_odds else 0
                                    })
                except Exception:
                    pass

        if auto_hits:
            st.success(f"自動照合で的中 {len(auto_hits)} 件検出")
            for h in auto_hits:
                c = "#ffd700" if h['payout'] >= 10000 else "#10b981"
                st.markdown(
                    f'<div style="border:1px solid {c};border-radius:8px;padding:0.5rem 1rem;margin:0.3rem 0;">'
                    f'✅ {h["date"]} <strong>{h["venue"]}{h["race_num"]}R {h["race_name"]}</strong>'
                    f'&nbsp;単勝 <span style="color:#60a5fa;font-weight:700;">{h["combination"]}番</span>'
                    f'&nbsp;｜&nbsp;着順：<span style="color:#e2e8f0;font-weight:700;">{h["result_order"]}</span>'
                    f'&nbsp;｜&nbsp;<span style="color:{c};font-weight:700;">¥{h["payout"]:,}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.info("的中データが見つかりませんでした。レース結果が取得済みの日付を確認してください。")

# === タブ4: 回収率分析 ===
with tab4:
    st.header("📈 収支・回収率分析")
    
    analysis_tab1, analysis_tab2 = st.tabs(["📊 パフォーマンス分析", "📒 収支履歴"])
    
    with analysis_tab1:
        st.markdown("### AIバックテスト成績")
        backtest_file = DATA_DIR / "backtest" / "backtest_results.csv"
        if backtest_file.exists():
            df_bt = pd.read_csv(backtest_file)
            col1, col2 = st.columns(2)
            with col1:
                st.metric("トータル投資額", f"¥{int(df_bt['invest'].sum()):,}")
            with col2:
                recovery_rate = (df_bt['return'].sum() / df_bt['invest'].sum() * 100) if df_bt['invest'].sum() > 0 else 0
                st.metric("トータル回収率", f"{recovery_rate:.1f}%")
            
            if PLOTLY_AVAILABLE:
                fig = px.line(df_bt, x="date", y="cumulative_balance", title="累積収支推移")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("バックテストデータがありません。`scripts/run_backtest.py` を実行してください。")

    with analysis_tab2:
        st.markdown("### 手動記録・収支履歴")
        history = load_history()
        if history:
            st.dataframe(pd.DataFrame(history), use_container_width=True)
        else:
            st.info("履歴データがありません。")


# === タブ5: 資金配分 ===
with tab5:
    st.header("💰 資金配分（ケリー基準）")

    st.markdown("""
    **ケリー基準**で最適な投資比率を自動算出。本日の予測データと連動し、各レースの推奨投資額をリアルタイム表示します。
    """)

    st.markdown("---")

    # === 本日の予測データから自動連動 ===
    st.markdown("### 🏇 本日のレース別・推奨投資額")

    today_str_tab5 = datetime.now().strftime("%Y%m%d")
    pred_tab5 = load_predictions(today_str_tab5)
    
    if not (pred_tab5 and pred_tab5.get("races")):
        st.info("本日開催のレースはありません（過去のデータは予想アーカイブをご覧ください）")

    if pred_tab5 and pred_tab5.get("races"):
        races_t5 = pred_tab5.get("races", [])
        races_t5 = sort_races_by_number(races_t5)

        total_investment = 0
        bet_list = []

        for race in races_t5:
            race_num = race.get("race_num", 0)
            race_name = race.get("race_name", "")
            venue = race.get("venue", "")
            horses_t5 = race.get("horses", []) or race.get("predictions", [])

            if not horses_t5:
                continue

            # AI予測実行（キー正規化）
            norm_t5 = []
            for h in horses_t5:
                nh = dict(h)
                if "umaban" in nh and "馬番" not in nh:
                    nh["馬番"] = nh["umaban"]
                if "horse_name" in nh and "馬名" not in nh:
                    nh["馬名"] = nh["horse_name"]
                if "odds" not in nh and "オッズ" not in nh:
                    wp = float(nh.get("win_probability", 0) or 0)
                    nh["オッズ"] = round(1.0 / wp, 1) if wp > 0 else 0
                norm_t5.append(nh)
            race_for_ml_t5 = race.copy()
            race_for_ml_t5["all_results"] = norm_t5
            sorted_h, _ = ml_calc.predict_race(race_for_ml_t5)

            if not sorted_h:
                continue

            # 上位2頭の馬番で馬連買い目を生成
            top2_umaban = []
            for h in sorted_h[:2]:
                ub = h.get("umaban", h.get("馬番", ""))
                if ub:
                    top2_umaban.append(str(ub))
            quinella_str = f"馬連 {'-'.join(top2_umaban)}" if len(top2_umaban) == 2 else ""

            for idx, h in enumerate(sorted_h[:3]):
                odds_h = float(h.get("odds", 0) or 0)
                prob_h = float(h.get("prob_top3", 0) or 0)
                ev_h = float(h.get("expected_value", 0) or 0)
                umaban_h = h.get("umaban", h.get("馬番", ""))
                name_h = h.get("horse_name", h.get("馬名", ""))

                if odds_h <= 0:
                    continue
                if not (ev_h >= 0.90 or idx == 0):
                    continue

                if prob_h > 0:
                    b = odds_h - 1
                    kf = (b * prob_h - (1 - prob_h)) / b if b > 0 else 0
                    kf = max(0, kf) * 0.25
                    if kf > 0 and ev_h > 1.0:
                        bet_amt = max(200, min(500, int(bankroll * kf / 100) * 100))
                        mode_label = "推奨"
                    elif ev_h >= 0.90:
                        agg_rate = 0.005 + (ev_h - 0.90) * 0.05
                        bet_amt = max(200, min(1000, int(bankroll * agg_rate / 100) * 100))
                        mode_label = "積極"
                    else:
                        bet_amt = 200
                        mode_label = "注目"
                else:
                    if idx == 0:
                        bet_amt = 200
                        mode_label = "注目"
                    else:
                        continue

                total_investment += bet_amt
                bet_list.append({
                    "レース": f"{venue}{race_num}R",
                    "馬番": str(umaban_h),
                    "馬名": name_h,
                    "単勝オッズ": f"{odds_h:.1f}",
                    "勝率": f"{prob_h*100:.1f}%",
                    "EV": f"{ev_h:.2f}",
                    "モード": mode_label,
                    "推奨額": f"¥{bet_amt:,}",
                    "買い目": quinella_str if quinella_str else f"単勝 {umaban_h}",
                })

        # 注目馬テーブル（EV問わず全レースの上位1頭を必ず表示）
        if not bet_list:
            for race in races_t5:
                race_num = race.get("race_num", 0)
                venue = race.get("venue", "")
                horses_t5b = race.get("horses", []) or race.get("predictions", [])
                if not horses_t5b:
                    continue
                norm_t5b = []
                for hh in horses_t5b:
                    nh = dict(hh)
                    if "umaban" in nh and "馬番" not in nh:
                        nh["馬番"] = nh["umaban"]
                    if "horse_name" in nh and "馬名" not in nh:
                        nh["馬名"] = nh["horse_name"]
                    if "odds" not in nh and "オッズ" not in nh:
                        wp = float(nh.get("win_probability", 0) or 0)
                        nh["オッズ"] = round(1.0 / wp, 1) if wp > 0 else 0
                    norm_t5b.append(nh)
                race_for_ml_t5b = race.copy()
                race_for_ml_t5b["all_results"] = norm_t5b
                sorted_hb, _ = ml_calc.predict_race(race_for_ml_t5b)
                if sorted_hb:
                    bh = sorted_hb[0]
                    odds_bh = float(bh.get("odds", 0) or 0)
                    ub_bh = bh.get("umaban", bh.get("馬番", ""))
                    if odds_bh > 0:
                        bet_list.append({
                            "レース": f"{venue}{race_num}R",
                            "馬番": str(ub_bh),
                            "馬名": bh.get("horse_name", bh.get("馬名", "")),
                            "単勝オッズ": f"{odds_bh:.1f}",
                            "勝率": f"{float(bh.get('prob_top3', 0) or 0)*100:.1f}%",
                            "EV": f"{float(bh.get('expected_value', 0) or 0):.2f}",
                            "モード": "注目",
                            "推奨額": "¥200",
                            "買い目": f"単勝 {ub_bh}",
                        })
                        total_investment += 200

        if bet_list:
            # HTMLテーブルで深紺背景に純白Bold表示
            html_rows = ""
            for row in bet_list:
                mode_color = "#ffd700" if row["モード"] == "推奨" else "#f97316" if row["モード"] == "積極" else "#60a5fa"
                html_rows += f"""<tr>
                    <td style="font-weight:700;">{row['レース']}</td>
                    <td style="font-weight:700;color:#ffd700;">{row['馬番']}</td>
                    <td style="font-weight:700;">{row['馬名']}</td>
                    <td style="color:#34d399;font-weight:700;">{row['単勝オッズ']}</td>
                    <td>{row['勝率']}</td>
                    <td>{row['EV']}</td>
                    <td style="color:{mode_color};font-weight:700;">{row['モード']}</td>
                    <td style="color:#ffd700;font-weight:700;font-size:1.1rem;">{row['推奨額']}</td>
                    <td style="color:#FFFFFF;font-weight:700;">{row['買い目']}</td>
                </tr>"""
            
            st.markdown(f"""
            <div style="overflow-x:auto;">
            <table style="width:100%;border-collapse:collapse;background:#0a0f1a;border:1px solid rgba(255,215,0,0.3);border-radius:12px;">
            <thead><tr style="border-bottom:2px solid #ffd700;">
                <th style="padding:10px 8px;text-align:left;color:#ffd700;font-weight:700;font-size:0.95rem;">レース</th>
                <th style="padding:10px 8px;text-align:left;color:#ffd700;font-weight:700;">馬番</th>
                <th style="padding:10px 8px;text-align:left;color:#ffd700;font-weight:700;">馬名</th>
                <th style="padding:10px 8px;text-align:left;color:#ffd700;font-weight:700;">単勝オッズ</th>
                <th style="padding:10px 8px;text-align:left;color:#ffd700;font-weight:700;">勝率</th>
                <th style="padding:10px 8px;text-align:left;color:#ffd700;font-weight:700;">EV</th>
                <th style="padding:10px 8px;text-align:left;color:#ffd700;font-weight:700;">モード</th>
                <th style="padding:10px 8px;text-align:left;color:#ffd700;font-weight:700;">推奨額</th>
                <th style="padding:10px 8px;text-align:left;color:#ffd700;font-weight:700;">買い目</th>
            </tr></thead>
            <tbody style="color:#FFFFFF;font-weight:600;font-size:0.95rem;">
            {html_rows}
            </tbody></table></div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div style="background: #0a0f1a; border: 2px solid #ffd700; border-radius: 12px; padding: 1.2rem; margin-top: 1rem; text-align: center;">
                <span style="color: #FFFFFF; font-size: 1.1rem; font-weight: 700; text-shadow: 0 1px 3px rgba(0,0,0,0.5);">本日の推奨総投資額</span><br>
                <span style="color: #ffd700; font-size: 2.4rem; font-weight: 700; text-shadow: 0 0 12px rgba(255,215,0,0.3);">¥{total_investment:,}</span>
                <span style="color: #FFFFFF; font-size: 1rem; font-weight: 600;"> / 資金 ¥{bankroll:,}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div style="background:#0a0f1a;border:2px solid #ffd700;border-radius:12px;padding:1.2rem;text-align:center;"><span style="color:#FFFFFF;font-size:1.1rem;font-weight:700;text-shadow:0 1px 3px rgba(0,0,0,0.5);">📭 現在データ取得中です。再予想ボタンを押してください。</span></div>', unsafe_allow_html=True)
    else:
        st.info("本日開催のレースはありません（過去のデータは予想アーカイブをご覧ください）")

    st.markdown("---")

    # === 従来のシミュレーター ===
    st.markdown("### 📊 投資額シミュレーター（手動入力）")

    sim_col1, sim_col2 = st.columns(2)

    with sim_col1:
        sim_prob = st.slider("勝率 (%)", 5, 50, 20) / 100
        sim_odds = st.slider("オッズ", 1.5, 30.0, 5.0, 0.5)

    with sim_col2:
        sim_bankroll = st.number_input("資金 (円)", 10000, 10000000, bankroll, 10000)

    # ケリー計算
    b = sim_odds - 1
    p = sim_prob
    q = 1 - p
    kelly = (b * p - q) / b if b > 0 else 0
    kelly = max(0, kelly)

    half_kelly = kelly * 0.5
    full_kelly = kelly
    aggressive_kelly = kelly * 1.2

    st.markdown("### 📈 推奨投資額")

    result_col1, result_col2, result_col3 = st.columns(3)

    with result_col1:
        bet_half = int(sim_bankroll * half_kelly / 100) * 100
        st.metric("ハーフケリー", f"¥{bet_half:,}", f"{half_kelly*100:.2f}%")

    with result_col2:
        bet_full = int(sim_bankroll * full_kelly / 100) * 100
        st.metric("フルケリー", f"¥{bet_full:,}", f"{full_kelly*100:.2f}%")

    with result_col3:
        bet_agg = int(sim_bankroll * aggressive_kelly / 100) * 100
        st.metric("アグレッシブ", f"¥{bet_agg:,}", f"{aggressive_kelly*100:.2f}%")

    # 期待値
    expected_value = sim_prob * sim_odds
    st.markdown(f"**期待値**: {expected_value:.2f} {'✅ プラス期待値' if expected_value > 1 else '❌ マイナス期待値'}")


# === タブ6: AI学習状況 ===
with tab6:
    st.header("🧠 AI学習状況")
    
    ai_data = load_ai_weights()
    
    # 基本情報
    st.markdown("### 📊 現在のAI重み")
    
    weights = ai_data.get("weights", DEFAULT_WEIGHTS)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🔥 SpeedAgent", f"{weights.get('SpeedAgent', 0.35)*100:.0f}%")
    with col2:
        st.metric("🎯 AdaptabilityAgent", f"{weights.get('AdaptabilityAgent', 0.35)*100:.0f}%")
    with col3:
        st.metric("🧬 PedigreeFormAgent", f"{weights.get('PedigreeFormAgent', 0.30)*100:.0f}%")
    
    # --- 直近30日成績 + モデル情報 ---
    model_meta_path = DATA_DIR / "models" / "model_meta.json"
    if model_meta_path.exists():
        try:
            with open(model_meta_path, 'r', encoding='utf-8') as f:
                model_meta = json.load(f)
            
            st.markdown("---")
            st.markdown("### 📈 AI モデル性能")
            
            meta_c1, meta_c2, meta_c3 = st.columns(3)
            with meta_c1:
                st.metric("🎯 テストAUC", f"{model_meta.get('test_auc', 0):.4f}")
            with meta_c2:
                st.metric("📊 特徴量数", f"{model_meta.get('feature_count', 0)}")
            with meta_c3:
                ws = model_meta.get('weight_scheme', '均等')
                st.metric("⚖️ 重み付け", "直近重視" if "2026" in str(ws) else "均等")
            
            # 直近30日成績
            recent = model_meta.get("recent_stats", {})
            if recent:
                st.markdown("---")
                st.markdown("### 🔥 直近30日 AI成績")
                st.markdown(f'<p style="color:#94a3b8;font-size:0.85rem;">期間: {recent.get("recent_period", "")}</p>', unsafe_allow_html=True)
                
                r_c1, r_c2, r_c3, r_c4 = st.columns(4)
                with r_c1:
                    st.metric("📅 対象レース", f"{recent.get('recent_30d_races', 0)}R")
                with r_c2:
                    rate = recent.get('recent_30d_top3_rate', 0)
                    st.metric("🎯 複勝率", f"{rate}%", 
                             f"{'好調' if rate > 30 else '普通'}")
                with r_c3:
                    roi = recent.get('recent_30d_roi', 0)
                    st.metric("💰 推定回収率", f"{roi}%",
                             f"{'絶好調🔥' if roi > 100 else '好調' if roi > 80 else '調整中'}")
                with r_c4:
                    win_rate = recent.get('recent_30d_win_rate', 0)
                    st.metric("🏆 勝率", f"{win_rate}%")
                
                # ステータスバー
                if roi >= 100:
                    st.markdown("""
                    <div style="background:rgba(255,215,0,0.1);border:2px solid #ffd700;border-radius:10px;padding:0.8rem;text-align:center;margin-top:0.5rem;">
                        <span style="font-size:1.2rem;">🔥</span>
                        <span style="color:#ffd700;font-weight:700;font-size:1.1rem;">AIは絶好調！ 攻めの投資が有効です</span>
                    </div>
                    """, unsafe_allow_html=True)
                elif roi >= 80:
                    st.markdown("""
                    <div style="background:rgba(16,185,129,0.08);border:1px solid #10b981;border-radius:10px;padding:0.8rem;text-align:center;margin-top:0.5rem;">
                        <span style="color:#10b981;font-weight:700;">✅ AI好調 — 標準的な投資を推奨</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="background:rgba(96,165,250,0.08);border:1px solid #60a5fa;border-radius:10px;padding:0.8rem;text-align:center;margin-top:0.5rem;">
                        <span style="color:#60a5fa;font-weight:700;">🔄 モデル調整中 — 慎重な投資を推奨</span>
                    </div>
                    """, unsafe_allow_html=True)
        except Exception:
            pass
    
    st.markdown("---")
    
    # Train/Test分離の成績
    st.markdown("### 📈 バックテスト結果（Train/Test分離）")
    
    train_metrics = ai_data.get("train_metrics", {})
    test_metrics = ai_data.get("test_metrics", {})
    
    if train_metrics and test_metrics:
        train_col, test_col = st.columns(2)
        
        with train_col:
            st.markdown("#### 📚 学習データ（Train）")
            train_years = train_metrics.get("years", [])
            st.markdown(f"**対象年**: {', '.join(map(str, train_years)) if train_years else '不明'}")
            st.metric("対象レース数", f"{train_metrics.get('total_races', 0):,}")
            st.metric("的中率", f"{train_metrics.get('hit_rate', 0)*100:.2f}%")
            st.metric("回収率", f"{train_metrics.get('recovery_rate', 0)*100:.2f}%")
        
        with test_col:
            st.markdown("#### 🧪 テストデータ（Test）")
            test_years = test_metrics.get("years", [])
            st.markdown(f"**対象年**: {', '.join(map(str, test_years)) if test_years else '不明'}")
            st.metric("対象レース数", f"{test_metrics.get('total_races', 0):,}")
            st.metric("的中率", f"{test_metrics.get('hit_rate', 0)*100:.2f}%")
            st.metric("回収率", f"{test_metrics.get('recovery_rate', 0)*100:.2f}%")
        
        # 過学習チェック
        train_recovery = train_metrics.get("recovery_rate", 0)
        test_recovery = test_metrics.get("recovery_rate", 0)
        
        if train_recovery > 0 and test_recovery > 0:
            overfit_ratio = train_recovery / test_recovery if test_recovery > 0 else float('inf')
            
            st.markdown("---")
            st.markdown("### ⚠️ 過学習チェック")
            
            if overfit_ratio > 2.0:
                st.error(f"⚠️ **過学習の可能性あり**: Train回収率がTest回収率の{overfit_ratio:.1f}倍です。モデルの見直しを推奨します。")
            elif overfit_ratio > 1.5:
                st.warning(f"⚡ **軽度の過学習**: Train回収率がTest回収率の{overfit_ratio:.1f}倍です。注意が必要です。")
            else:
                st.success(f"✅ **良好**: Train/Test間の差異は許容範囲内です（比率: {overfit_ratio:.2f}）")
    else:
        # 旧形式のメトリクス
        metrics = ai_data.get("metrics", {})
        if metrics:
            st.markdown("#### 📊 全体成績")
            st.metric("対象レース数", f"{metrics.get('total_races', 0):,}")
            st.metric("的中率", f"{metrics.get('hit_rate', 0)*100:.2f}%")
            st.metric("回収率", f"{metrics.get('recovery_rate', 0)*100:.2f}%")
            
            st.warning("⚠️ Train/Test分離されていない旧形式のデータです。`ensemble_agents.py --optimize` を実行して更新してください。")
        else:
            st.info("📭 AI学習データがありません。`ensemble_agents.py --optimize` を実行してください。")
    
    st.markdown("---")
    
    # 更新情報
    updated_at = ai_data.get("updated_at", "")
    if updated_at:
        st.markdown(f"**最終更新**: {updated_at}")

    st.markdown("---")
    st.markdown("### 🔁 手動再学習（最新データ）")
    if st.button("🧠 最新データで再学習を実行", key="manual_retrain"):
        try:
            script_path = Path(__file__).parent / "scripts" / "train_model.py"
            if script_path.exists():
                result = subprocess.run([sys.executable, str(script_path)], check=False, capture_output=True, text=True, encoding='utf-8', errors='replace')
                out = (result.stdout or "")[:4000]
                err = (result.stderr or "")[:1000]
                if result.returncode == 0:
                    st.success("再学習が完了しました")
                    if out:
                        st.code(out)
                else:
                    st.error("再学習でエラーが発生しました")
                    if err:
                        st.code(err)
            else:
                st.warning("train_model.py が見つかりません")
        except Exception as e:
            st.error("再学習の実行に失敗しました")

# === タブ7: 予想アーカイブ ===
with tab7:
    st.header("📁 予想アーカイブ")
    st.markdown("過去の予想データを日付別に閲覧できます。全券種と予想ロジックを表示し、的中した場合は自動でマークが付きます。")
    st.info("ℹ️ アーカイブデータは土・日 7:00時点の出馬表＋初期オッズに基づく予想ロジックで自動保存されています。")

    # --- 日付選択 ---
    all_arch_files = sorted(HISTORY_DIR.glob(f"{PREDICTIONS_PREFIX}*.json"), reverse=True)
    arch_date_options = []
    for af in all_arch_files[:30]:
        ds = af.stem.replace(PREDICTIONS_PREFIX, "")
        if len(ds) == 8 and ds.isdigit():
            arch_date_options.append((f"{ds[:4]}/{ds[4:6]}/{ds[6:8]}", ds))

    if not arch_date_options:
        st.info("予想アーカイブデータがありません。")
        st.stop()

    arch_selected_display = st.selectbox(
        "📅 日付を選択",
        options=[o[0] for o in arch_date_options],
        index=0,
        key="archive_date_selector"
    )
    arch_selected_date = next(o[1] for o in arch_date_options if o[0] == arch_selected_display)

    # 予想データと結果データを両方読み込み
    arch_pred = load_predictions(arch_selected_date)
    arch_result = load_results(arch_selected_date)
    
    save_arch_col1, save_arch_col2 = st.columns(2)
    with save_arch_col1:
        if st.button("💾 この日の予想を保存（JSON）", key="save_arch_json"):
            ts = datetime.now().strftime("%H%M%S")
            outfile = HISTORY_DIR / f"{PREDICTIONS_PREFIX}{arch_selected_date}_snapshot_{ts}.json"
            if arch_pred:
                ok = save_json_file(outfile, arch_pred)
                if ok:
                    st.success(f"保存しました: {outfile.name}")
                else:
                    st.error("保存に失敗しました")
    with save_arch_col2:
        if st.button("💾 この日の買い目を保存（CSV）", key="save_arch_csv"):
            ts = datetime.now().strftime("%H%M%S")
            csvfile = HISTORY_DIR / f"bets_{arch_selected_date}_snapshot_{ts}.csv"
            try:
                with open(csvfile, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["date", "venue", "race_num", "race_name", "bet_type", "combo"])
                    for race in arch_pred.get("races", []):
                        bets_map = get_all_bet_types_display(race)
                        for bt, combo in bets_map.items():
                            writer.writerow([arch_selected_date, race.get("venue",""), race.get("race_num",0), race.get("race_name",""), bt, combo])
                st.success(f"保存しました: {csvfile.name}")
            except Exception:
                st.error("保存に失敗しました")

    if not arch_pred or not arch_pred.get("races"):
        st.warning(f"{arch_selected_display} の予想データが見つかりません。")
        st.stop()

    arch_races = sort_races_by_number(arch_pred.get("races", []))
    st.success(f"📊 {arch_selected_display} の予想データ ({len(arch_races)} レース)")

    # --- 競馬場フィルター ---
    def _get_venue_label(race: dict) -> str:
        v = race.get("venue", "")
        try:
            v.encode('utf-8').decode('utf-8')
            if v and not all(ord(c) < 128 or '\u3000' <= c <= '\u9fff' for c in v):
                raise ValueError("garbled")
            if v:
                return v
        except Exception:
            pass
        race_id = str(race.get("race_id", ""))
        VENUE_CODE = {
            "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
            "05": "東京", "06": "中山", "07": "中京", "08": "京都",
            "09": "阪神", "10": "小倉",
        }
        if len(race_id) >= 10:
            code = race_id[4:6]
            return VENUE_CODE.get(code, f"場コード{code}")
        return "不明"

    arch_venues = sorted(set(_get_venue_label(r) for r in arch_races))
    arch_selected_venue = st.selectbox("🏟️ 競馬場を選択", arch_venues, key="archive_venue_selector")

    arch_venue_races = [r for r in arch_races if _get_venue_label(r) == arch_selected_venue]

    # --- レースごとに詳細表示（全券種+的中判定） ---
    for race in arch_venue_races:
        race_id = race.get("race_id", "")
        race_num = race.get("race_num", 0)
        
        # レース名表示の改善
        raw_race_name = race.get("race_name", "")
        if not raw_race_name or raw_race_name.startswith("Race "):
            race_name_display = f"{race_num}R"
        else:
            race_name_display = raw_race_name

        distance = race.get("distance", 0)
        track_type = race.get("track_type", "")
        rank = race.get("rank", "")

        dist_str = f"({track_type}{distance}m)" if distance else ""
        
        result_race = None
        if arch_result and arch_result.get("races"):
            for r in arch_result["races"]:
                if str(r.get("race_id", "")) == str(race_id):
                    result_race = r
                    break
            if result_race is None:
                v_pred = _get_venue_label(race)
                rn_pred = race_num
                for r in arch_result["races"]:
                    v_res = r.get("venue", "")
                    rn_res = r.get("race_num", 0)
                    if v_res == v_pred and rn_res == rn_pred:
                        result_race = r
                        break
        
        # 的中判定
        hit_info = check_hit_result(race, result_race) if result_race else {"is_hit": False, "hit_types": []}
        
        # 全券種データ取得
        all_bets = get_all_bet_types_display(race)
        
        # AI評価コメントとロジックサマリー
        ai_evaluation = race.get("ai_evaluation", "")
        logic_summary = race.get("logic_summary", "")
        
        # 拡張子の決定（的中がある場合は自動展開）
        auto_expand = hit_info["is_hit"] or rank in ["S+", "S"]
        
        # ヘッダーに的中バッジを追加
        hit_badge = ""
        if hit_info["is_hit"]:
            hit_types_str = "+".join(hit_info["hit_types"])
            hit_badge = f" 🎯{hit_types_str}"
        
        with st.expander(
            f"🏇 {race_num}R {race_name_display} {dist_str} {get_rank_badge_html(rank) if rank else ''}{hit_badge}",
            expanded=auto_expand
        ):
            # 的中情報表示
            if hit_info["is_hit"]:
                st.success(f"🎯 的中しました！: {', '.join(hit_info['hit_types'])}")
                if hit_info.get("actual_order"):
                    st.info(f"着順：{'-'.join(map(str, hit_info['actual_order'][:3]))}")
            elif result_race:
                st.info("❌ 的中しませんでした")
                if hit_info.get("actual_order"):
                    st.info(f"着順：{'-'.join(map(str, hit_info['actual_order'][:3]))}")
            else:
                st.info("📊 結果データがありません")
            
            # 全券種表示
            st.subheader("🎯 全券種予想")
            
            # 8つの券種をグリッド表示
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("単勝", all_bets["tansho"])
                st.metric("複勝", all_bets["fukusho"])
            
            with col2:
                st.metric("枠連", all_bets["wakuren"])
                st.metric("馬連", all_bets["umaren"])
            
            with col3:
                st.metric("ワイド", all_bets["wide"])
                st.metric("馬単", all_bets["umatan"])
            
            with col4:
                st.metric("三連複", all_bets["sanrenpuku"])
                st.metric("三連単", all_bets["sanrentan"])
            
            if st.button("💾 このレースの買い目を保存（CSV）", key=f"save_race_csv_{race_id}"):
                ts = datetime.now().strftime("%H%M%S")
                csvfile = HISTORY_DIR / f"bets_{arch_selected_date}_{race_id}_{ts}.csv"
                try:
                    with open(csvfile, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["date", "venue", "race_id", "race_num", "race_name", "bet_type", "combo"])
                        for bt, combo in all_bets.items():
                            writer.writerow([arch_selected_date, race.get("venue",""), race_id, race_num, race_name_display, bt, combo])
                    st.success(f"保存しました: {csvfile.name}")
                except Exception:
                    st.error("保存に失敗しました")
            
            # AI評価とロジックサマリー
            if ai_evaluation or logic_summary:
                st.subheader("🤖 AI評価と予想ロジック")
                
                if ai_evaluation:
                    st.info(f"**AI評価**: {ai_evaluation}")
                
                if logic_summary:
                    st.info(f"**ロジックサマリー**: {logic_summary}")
            
            # 元の馬データ表示（簡略化）
            horses = race.get("horses", []) or race.get("predictions", [])
            if horses:
                st.subheader("🐎 注目馬")
                
                # 上位3頭のみ表示
                for i, horse in enumerate(horses[:3]):
                    umaban = horse.get("umaban", horse.get("馬番", ""))
                    name = horse.get("horse_name", horse.get("馬名", ""))
                    odds_val = float(horse.get("odds", horse.get("オッズ", 0)) or 0)
                    uma_index = horse.get("uma_index", 0)
                    
                    col_a, col_b, col_c = st.columns([1, 3, 2])
                    with col_a:
                        st.markdown(f"**{umaban}番**")
                    with col_b:
                        st.markdown(f"{name}")
                    with col_c:
                        if odds_val > 0:
                            st.markdown(f"{odds_val:.1f}倍")
                        if uma_index > 0:
                            st.markdown(f"指数: {uma_index:.1f}")



            # 馬ごとの行（Tab 1 と同じ列レイアウト）
            marks = ["◎", "○", "▲", "△", "☆"]
            for i, horse in enumerate(horses[:5]):
                umaban = horse.get("umaban", horse.get("馬番", ""))
                name = horse.get("horse_name", horse.get("馬名", ""))
                odds_val = float(horse.get("odds", horse.get("オッズ", 0)) or 0)
                uma_index = horse.get("uma_index", 0)
                rank_h = horse.get("rank", "C")
                ev = horse.get("expected_value", 0)
                prob = horse.get("prob_top3", horse.get("win_probability", 0)) or 0

                kelly_bet_str = ""
                if odds_val > 0 and prob > 0:
                    b = odds_val - 1
                    kelly_f = (b * prob - (1 - prob)) / b if b > 0 else 0
                    kelly_f = max(0, kelly_f) * 0.25
                    if kelly_f > 0 and ev > 1.0:
                        bet_amt = max(200, min(500, int(bankroll * kelly_f / 100) * 100))
                        kelly_bet_str = f"💰{bet_amt:,}円"
                    elif ev >= 0.90 and i < 3:
                        agg_rate = 0.005 + (ev - 0.90) * 0.05
                        agg_amt = max(200, min(1000, int(bankroll * agg_rate / 100) * 100))
                        kelly_bet_str = f"🔥{agg_amt:,}円"
                    elif i == 0:
                        kelly_bet_str = "🔸¥200"

                # 予想ロジックスコアを取得
                speed_s   = horse.get("speed_score", 0)
                adapt_s   = horse.get("adaptability_score", 0)
                pedigree_s = horse.get("pedigree_score", 0)
                confidence = horse.get("confidence", 0)
                stored_bet = horse.get("bet_amount", 0)

                mark = marks[i] if i < len(marks) else ""

                # 1行目: 印・馬番・馬名・ランク・指数・オッズ・推奨購入額
                col1, col2, col3, col4, col5, col6, col7 = st.columns([0.6, 0.6, 2.8, 1.2, 1.4, 1.4, 1.2])
                with col1:
                    st.markdown(f"<span style='font-size:1.1rem;font-weight:800;'>{mark}</span>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"<span style='font-size:1.1rem;font-weight:800;color:#ffd700;'>{umaban}</span>", unsafe_allow_html=True)
                with col3:
                    st.markdown(f"<span style='font-weight:700;'>{name}</span>", unsafe_allow_html=True)
                with col4:
                    st.markdown(get_rank_badge_html(rank_h), unsafe_allow_html=True)
                with col5:
                    if uma_index > 0:
                        st.markdown(f"<span style='color:#e2e8f0;font-size:0.9rem;'>指数 <strong style='color:#ffd700;'>{uma_index:.1f}</strong></span>", unsafe_allow_html=True)
                with col6:
                    if odds_val > 0:
                        st.markdown(f"<span style='color:#e2e8f0;font-size:0.9rem;'>倍率 <strong style='color:#60a5fa;'>{odds_val:.1f}</strong></span>", unsafe_allow_html=True)
                with col7:
                    if kelly_bet_str:
                        st.markdown(f'<span style="color:#ffd700;font-size:0.85rem;font-weight:700;">{kelly_bet_str}</span>', unsafe_allow_html=True)
                    elif stored_bet > 0:
                        st.markdown(f'<span style="color:#ffd700;font-size:0.85rem;font-weight:700;">💰{stored_bet:,}円</span>', unsafe_allow_html=True)

                # 2行目: 予想ロジックスコア（速さ・適性・血統・信頼度）
                if any([speed_s, adapt_s, pedigree_s, confidence]):
                    def _mini_bar(label: str, val: float, color: str) -> str:
                        pct = min(100, int(val * 100)) if val <= 1.0 else min(100, int(val))
                        return (
                            f'<div style="display:inline-flex;align-items:center;gap:4px;margin-right:10px;">'
                            f'<span style="color:#64748b;font-size:0.72rem;">{label}</span>'
                            f'<div style="width:40px;height:5px;background:#1e293b;border-radius:3px;overflow:hidden;">'
                            f'<div style="width:{pct}%;height:100%;background:{color};border-radius:3px;"></div>'
                            f'</div>'
                            f'<span style="color:{color};font-size:0.72rem;font-weight:700;">{pct}</span>'
                            f'</div>'
                        )
                    bars_html = (
                        _mini_bar("速", speed_s,    "#60a5fa") +
                        _mini_bar("適", adapt_s,   "#10b981") +
                        _mini_bar("血", pedigree_s, "#a78bfa") +
                        _mini_bar("信", confidence, "#ffd700")
                    )
                    st.markdown(
                        f'<div style="margin:-6px 0 4px 2.5rem;padding-left:0;">{bars_html}</div>',
                        unsafe_allow_html=True
                    )







# === タブ8: システム ===
with tab8:
    st.header("⚙️ システム情報")

    # データ統計
    st.markdown("### 📊 データ統計")

    pred_count = len(list(DATA_DIR.glob(f"{PREDICTIONS_PREFIX}*.json")))
    res_count = len(list(DATA_DIR.glob(f"{RESULTS_PREFIX}*.json")))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📝 予想ファイル", f"{pred_count}件")
    with col2:
        st.metric("📊 結果ファイル", f"{res_count}件")
    with col3:
        st.metric("📅 アーカイブ日数", f"{len(available_dates)}日")

    st.markdown("---")

    # アーカイブ統計
    st.markdown("### 📚 アーカイブ統計")

    index_data = load_archive_index()
    if index_data:
        years_data = index_data.get("years", {})
        for year in sorted(years_data.keys(), reverse=True):
            year_info = years_data[year]
            st.markdown(f"**{year}年**: {year_info.get('total_dates', 0)}日 / {year_info.get('total_races', 0)}レース")
    else:
        st.info("アーカイブインデックスがありません。`--rebuild-index` を実行してください。")

    st.markdown("---")

    # ワークフロー状態
    st.markdown("### 🔄 GitHub Actions ワークフロー")

    st.markdown("""
    | ワークフロー | スケジュール | 説明 |
    |-------------|-------------|------|
    | 予想データ取得 | 土日 7:00 JST | レースデータ取得+スコア計算 |
    | レース結果取得 | 土日 18:00 JST | 結果+払戻金取得 |
    | リアルタイムオッズ | 手動実行 | 直前オッズ取得+インサイダー検知 |
    | 過去データ一括取得 | 手動実行 | 過去2年分のデータ収集 |
    | AI学習 | 週1回(月曜) | 重み最適化+バックテスト |
    """)

    st.markdown("---")

    # システム情報
    st.markdown("### 📋 システム情報")

    system_info = "\n".join([
        "UMA-Logic PRO v2.1 (アンサンブル学習対応)",
        f"Python: {sys.version.split()[0]}",
        f"Streamlit: {st.__version__}",
        f"Plotly: {'Available' if PLOTLY_AVAILABLE else 'Not Available'}",
        f"AgGrid: {'Available' if AGGRID_AVAILABLE else 'Not Available'}",
        f"データディレクトリ: {DATA_DIR.absolute()}",
        f"アーカイブディレクトリ: {ARCHIVE_DIR.absolute()}",
        f"モデルディレクトリ: {MODELS_DIR.absolute()}",
        f"重みファイル: {WEIGHTS_FILE.absolute()}",
    ])
    st.code(system_info)
