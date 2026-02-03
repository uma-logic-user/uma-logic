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

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

# Plotlyのインポート
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

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

# --- 定数 ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR = DATA_DIR / "archive"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
PREDICTIONS_PREFIX = "predictions_"
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

# --- CSSスタイル ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');

    html, body, [class*="st-"], .stApp {
        font-family: 'Noto Sans JP', sans-serif;
        background-color: #0e1117;
    }

    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        border-left: 4px solid #e94560;
    }

    .main-header h1 {
        color: #ffffff;
        margin: 0;
        font-size: 2rem;
    }

    .main-header p {
        color: #a0a0a0;
        margin: 0.5rem 0 0 0;
    }

    .race-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        border: 1px solid #2a2a4a;
        transition: transform 0.2s, box-shadow 0.2s;
    }

    .race-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(233, 69, 96, 0.15);
    }

    .race-title {
        color: #e94560;
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }

    .race-info {
        color: #a0a0a0;
        font-size: 0.85rem;
    }

    .horse-row {
        display: flex;
        align-items: center;
        padding: 0.5rem 0;
        border-bottom: 1px solid #2a2a4a;
    }

    .horse-row:last-child {
        border-bottom: none;
    }

    .horse-number {
        background: #e94560;
        color: white;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        margin-right: 0.8rem;
        font-size: 0.9rem;
    }

    .horse-name {
        color: #ffffff;
        font-weight: 600;
        flex: 1;
    }

    .horse-odds {
        color: #4ade80;
        font-weight: 600;
    }

    .rank-badge {
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.8rem;
        margin-right: 0.5rem;
    }

    .rank-s-plus {
        background: linear-gradient(135deg, #ffd700, #ffaa00);
        color: #000;
    }

    .rank-s {
        background: linear-gradient(135deg, #e94560, #ff6b6b);
        color: #fff;
    }

    .rank-a {
        background: linear-gradient(135deg, #4ade80, #22c55e);
        color: #000;
    }

    .rank-b {
        background: #3b82f6;
        color: #fff;
    }

    .rank-c {
        background: #6b7280;
        color: #fff;
    }

    .insider-alert {
        background: linear-gradient(135deg, #ff6b6b, #e94560);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.8; }
    }

    .metric-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        border: 1px solid #2a2a4a;
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #4ade80;
    }

    .metric-label {
        color: #a0a0a0;
        font-size: 0.85rem;
    }

    .payout-table {
        width: 100%;
        border-collapse: collapse;
    }

    .payout-table th, .payout-table td {
        padding: 0.5rem;
        text-align: left;
        border-bottom: 1px solid #2a2a4a;
    }

    .payout-table th {
        color: #a0a0a0;
        font-weight: 600;
    }

    .payout-table td {
        color: #ffffff;
    }

    .payout-amount {
        color: #4ade80;
        font-weight: 700;
    }

    .venue-button {
        background: #2a2a4a;
        color: #ffffff;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        margin-right: 0.5rem;
        cursor: pointer;
        transition: background 0.2s;
    }

    .venue-button:hover {
        background: #e94560;
    }

    .venue-button.active {
        background: #e94560;
    }

    .ai-weights-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #4ade80;
    }

    .ai-weights-title {
        color: #4ade80;
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }

    .weight-bar {
        height: 8px;
        background: #2a2a4a;
        border-radius: 4px;
        margin: 0.3rem 0;
        overflow: hidden;
    }

    .weight-fill {
        height: 100%;
        border-radius: 4px;
    }

    .weight-speed {
        background: linear-gradient(90deg, #e94560, #ff6b6b);
    }

    .weight-adapt {
        background: linear-gradient(90deg, #3b82f6, #60a5fa);
    }

    .weight-pedigree {
        background: linear-gradient(90deg, #4ade80, #22c55e);
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
    """JSONファイルを読み込み"""
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"ファイル読み込みエラー: {e}")
    return {}


def load_predictions(date_str: str = None) -> dict:
    """予想データを読み込み"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
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

    # 利用可能なデータ数
    available_dates = get_available_dates()
    st.metric("📅 データ日数", f"{len(available_dates)}日")

    # 最終更新
    if available_dates:
        latest_date = available_dates[0]
        st.metric("🕐 最新データ", format_date_jp(latest_date))


# --- メインタブ ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🎯 本日の予想",
    "📊 レース結果",
    "🎉 的中実績",
    "📈 収支レポート",
    "💰 資金配分",
    "🧠 AI学習状況",
    "⚙️ システム"
])


# === タブ1: 本日の予想 ===
with tab1:
    st.header("🎯 本日の予想")

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

    # 予想データ読み込み
    today_str = datetime.now().strftime("%Y%m%d")
    predictions = load_predictions(today_str)

    if predictions and predictions.get("races"):
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

                with st.expander(f"🏇 {race_num}R {race_name} ({track_type}{distance}m)", expanded=False):
                    horses = race.get("horses", []) or race.get("predictions", [])

                    if horses:
                        # UMA指数を再計算（最新の重みを適用）
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
                            odds = horse.get("odds", horse.get("オッズ", 0))
                            uma_index = horse.get("uma_index", 0)
                            rank = horse.get("rank", "C")
                            ev = horse.get("expected_value", 0)

                            # 印を決定
                            marks = ["◎", "○", "▲", "△", "☆"]
                            mark = marks[i] if i < len(marks) else ""

                            col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 3, 2, 2, 1])
                            with col1:
                                st.markdown(f"**{mark}**")
                            with col2:
                                st.markdown(f"**{umaban}**")
                            with col3:
                                st.markdown(f"{name}")
                            with col4:
                                if uma_index > 0:
                                    st.markdown(f"指数: **{uma_index:.1f}**")
                            with col5:
                                if odds > 0:
                                    st.markdown(f"オッズ: **{odds:.1f}**")
                            with col6:
                                st.markdown(get_rank_badge_html(rank), unsafe_allow_html=True)
                    else:
                        st.info("出馬データがありません")
    else:
        st.info("📭 本日の予想データがありません。土日の朝に自動更新されます。")


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

                # 競馬場でグループ化
                venues = list(set(r.get("venue", "") for r in races if r.get("venue")))
                venues = sorted(venues)

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
                                st.markdown(f"""
                                <div class="race-card">
                                    <div class="race-title">{race_num}R {race_name}</div>
                                    <div class="race-info">{venue} / {race.get('distance', '')}m / {race.get('track_type', '')}</div>
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
                                            "odds": "オッズ"
                                        }

                                        result_df = result_df.rename(columns=column_mapping)

                                        # 表示するカラムを選択
                                        display_cols = ["着順", "馬番", "馬名", "騎手", "タイム", "上がり3F", "オッズ"]
                                        display_cols = [c for c in display_cols if c in result_df.columns]

                                        if display_cols:
                                            st.dataframe(
                                                result_df[display_cols],
                                                use_container_width=True,
                                                hide_index=True
                                            )
                                    else:
                                        st.info("着順データがありません")

                                    # 払戻金表
                                    st.markdown("#### 💰 払戻金")
                                    payouts = race.get("payouts", {})

                                    if payouts:
                                        # 2カラムで表示
                                        payout_col1, payout_col2 = st.columns(2)

                                        payout_items = list(payouts.items())
                                        mid = len(payout_items) // 2 + len(payout_items) % 2

                                        with payout_col1:
                                            for key, value in payout_items[:mid]:
                                                if isinstance(value, dict):
                                                    # 複勝・ワイドなど複数値
                                                    values_str = " / ".join([f"{k}: ¥{v:,}" for k, v in value.items()])
                                                    st.markdown(f"**{key}**: {values_str}")
                                                else:
                                                    st.markdown(f"**{key}**: ¥{value:,}")

                                        with payout_col2:
                                            for key, value in payout_items[mid:]:
                                                if isinstance(value, dict):
                                                    values_str = " / ".join([f"{k}: ¥{v:,}" for k, v in value.items()])
                                                    st.markdown(f"**{key}**: {values_str}")
                                                else:
                                                    st.markdown(f"**{key}**: ¥{value:,}")
                                    else:
                                        st.info("払戻金データがありません")

                                st.markdown("---")
                else:
                    st.warning("競馬場情報がありません")
            else:
                st.warning(f"{format_date_jp(selected_date)} のデータがありません")


# === タブ3: 的中実績 ===
with tab3:
    st.header("🎉 的中実績")

    history = load_history()

    if history:
        # 最新順にソート
        history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)

        # 統計
        total_hits = len(history)
        total_payout = sum(h.get("payout", 0) for h in history)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("🎯 総的中数", f"{total_hits}回")
        with col2:
            st.metric("💰 総払戻金", f"¥{total_payout:,}")

        st.markdown("---")

        # 的中履歴テーブル
        for hit in history[:20]:  # 最新20件
            date = hit.get("date", "")
            venue = hit.get("venue", "")
            race_num = hit.get("race_num", "")
            bet_type = hit.get("bet_type", "")
            payout = hit.get("payout", 0)
            horse = hit.get("horse_name", "")

            st.markdown(f"""
            <div class="race-card">
                <div class="race-title">🎉 {venue} {race_num}R - {bet_type}</div>
                <div class="race-info">
                    {format_date_jp(date) if date else ''} / {horse}<br>
                    <span class="payout-amount">払戻: ¥{payout:,}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("📭 まだ的中データがありません。")


# === タブ4: 収支レポート ===
with tab4:
    st.header("📈 収支レポート")

    history = load_history()

    if history:
        # データフレーム化
        df = pd.DataFrame(history)

        if "date" in df.columns and "payout" in df.columns:
            # 日付でグループ化
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
            daily = df.groupby(df["date"].dt.date).agg({
                "payout": "sum",
                "bet_amount": "sum" if "bet_amount" in df.columns else "count"
            }).reset_index()

            # 累積収支
            if "bet_amount" in daily.columns:
                daily["profit"] = daily["payout"] - daily["bet_amount"]
                daily["cumulative"] = daily["profit"].cumsum()

                # グラフ
                if PLOTLY_AVAILABLE:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=daily["date"],
                        y=daily["cumulative"],
                        mode="lines+markers",
                        name="累積収支",
                        line=dict(color="#4ade80", width=2)
                    ))
                    fig.update_layout(
                        title="累積収支推移",
                        xaxis_title="日付",
                        yaxis_title="収支 (円)",
                        template="plotly_dark",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # サマリー
            total_bet = df["bet_amount"].sum() if "bet_amount" in df.columns else 0
            total_payout = df["payout"].sum()
            profit = total_payout - total_bet
            roi = (total_payout / total_bet * 100) if total_bet > 0 else 0

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💸 総投資額", f"¥{total_bet:,}")
            with col2:
                st.metric("💰 総払戻額", f"¥{total_payout:,}")
            with col3:
                st.metric("📊 純損益", f"¥{profit:,}")
            with col4:
                st.metric("📈 回収率", f"{roi:.1f}%")
    else:
        st.info("📭 まだ収支データがありません。")


# === タブ5: 資金配分 ===
with tab5:
    st.header("💰 資金配分（ケリー基準）")

    st.markdown("""
    **ケリー基準**は、期待値がプラスの賭けに対して、長期的に資金を最大化する最適な投資比率を算出する数学的手法です。

    - **ハーフケリー**: 安全重視（推奨）
    - **フルケリー**: 標準
    - **アグレッシブ**: 積極的（インサイダー検知時に自動切替）
    """)

    st.markdown("---")

    # 計算シミュレーター
    st.markdown("### 📊 投資額シミュレーター")

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
    
    # --- 資産推移シミュレーション ---
    st.markdown("### 📈 資産推移シミュレーション（Equity Curve）")
    
    test_metrics = ai_data.get("test_metrics", {})
    metrics = ai_data.get("metrics", {})
    
    # シミュレーション用パラメータ
    sim_col1, sim_col2, sim_col3 = st.columns(3)
    with sim_col1:
        initial_capital = st.number_input("初期資金 (円)", 10000, 10000000, 100000, 10000, key="equity_capital")
    with sim_col2:
        bet_per_race = st.number_input("1レースあたり投資額 (円)", 100, 10000, 100, 100, key="equity_bet")
    with sim_col3:
        sim_races = st.number_input("シミュレーションレース数", 100, 10000, 1000, 100, key="equity_races")
    
    # 的中率と回収率を取得
    hit_rate = test_metrics.get("hit_rate", metrics.get("hit_rate", 0.2))
    recovery_rate = test_metrics.get("recovery_rate", metrics.get("recovery_rate", 0.8))
    
    if hit_rate > 0 and recovery_rate > 0:
        # 平均オッズを逆算（回収率 = 的中率 × 平均オッズ）
        avg_odds = recovery_rate / hit_rate if hit_rate > 0 else 5.0
        
        # モンテカルロシミュレーション
        import random
        random.seed(42)  # 再現性のため
        
        equity_curve = [initial_capital]
        drawdowns = []
        max_equity = initial_capital
        current_equity = initial_capital
        
        consecutive_losses = 0
        max_consecutive_losses = 0
        
        for i in range(sim_races):
            # 的中判定
            if random.random() < hit_rate:
                # 的中
                payout = int(bet_per_race * avg_odds)
                current_equity += payout - bet_per_race
                consecutive_losses = 0
            else:
                # 不的中
                current_equity -= bet_per_race
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            
            # 資金が0以下になったら終了
            if current_equity <= 0:
                current_equity = 0
                equity_curve.append(current_equity)
                break
            
            equity_curve.append(current_equity)
            
            # ドローダウン計算
            if current_equity > max_equity:
                max_equity = current_equity
            drawdown = (max_equity - current_equity) / max_equity if max_equity > 0 else 0
            drawdowns.append(drawdown)
        
        # 資産推移グラフ
        if PLOTLY_AVAILABLE:
            fig_equity = go.Figure()
            fig_equity.add_trace(go.Scatter(
                x=list(range(len(equity_curve))),
                y=equity_curve,
                mode="lines",
                name="資産推移",
                line=dict(color="#4ade80", width=2)
            ))
            fig_equity.add_hline(y=initial_capital, line_dash="dash", line_color="#fbbf24", annotation_text="初期資金")
            fig_equity.update_layout(
                title=f"資産推移シミュレーション（的中率: {hit_rate*100:.1f}%, 回収率: {recovery_rate*100:.1f}%）",
                xaxis_title="レース数",
                yaxis_title="資産 (円)",
                template="plotly_dark",
                height=400
            )
            st.plotly_chart(fig_equity, use_container_width=True)
        else:
            st.line_chart(equity_curve)
        
        # シミュレーション結果サマリー
        final_equity = equity_curve[-1]
        total_profit = final_equity - initial_capital
        profit_rate = (final_equity / initial_capital - 1) * 100
        max_drawdown = max(drawdowns) * 100 if drawdowns else 0
        
        result_col1, result_col2, result_col3, result_col4 = st.columns(4)
        with result_col1:
            st.metric("最終資産", f"¥{final_equity:,.0f}", f"{profit_rate:+.1f}%")
        with result_col2:
            st.metric("純損益", f"¥{total_profit:,.0f}")
        with result_col3:
            st.metric("最大ドローダウン", f"{max_drawdown:.1f}%")
        with result_col4:
            st.metric("最大連敗数", f"{max_consecutive_losses}連敗")
        
        st.markdown("---")
        
        # --- ドローダウン解析 ---
        st.markdown("### 📉 ドローダウン解析")
        
        if PLOTLY_AVAILABLE and drawdowns:
            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(
                x=list(range(len(drawdowns))),
                y=[d * 100 for d in drawdowns],
                mode="lines",
                name="ドローダウン",
                fill="tozeroy",
                line=dict(color="#ef4444", width=1)
            ))
            fig_dd.update_layout(
                title="ドローダウン推移（資産最高値からの下落率）",
                xaxis_title="レース数",
                yaxis_title="ドローダウン (%)",
                template="plotly_dark",
                height=300
            )
            st.plotly_chart(fig_dd, use_container_width=True)
        
        # ドローダウン統計
        st.markdown("#### 📊 ドローダウン統計")
        
        if drawdowns:
            avg_dd = sum(drawdowns) / len(drawdowns) * 100
            
            dd_col1, dd_col2, dd_col3 = st.columns(3)
            with dd_col1:
                st.metric("平均ドローダウン", f"{avg_dd:.2f}%")
            with dd_col2:
                st.metric("最大ドローダウン", f"{max_drawdown:.2f}%")
            with dd_col3:
                # 回復に必要な勝率
                recovery_needed = max_drawdown / (1 - max_drawdown/100) if max_drawdown < 100 else float('inf')
                st.metric("回復に必要な上昇率", f"{recovery_needed:.2f}%")
        
        # 連敗確率の解説
        st.markdown("#### 🎲 連敗確率の理論値")
        
        loss_rate = 1 - hit_rate
        st.markdown(f"""
        | 連敗数 | 確率 | 発生頻度（{sim_races}レース中） |
        |--------|------|-------------------------------|
        | 5連敗 | {(loss_rate**5)*100:.2f}% | 約{int(sim_races * (loss_rate**5))}回 |
        | 10連敗 | {(loss_rate**10)*100:.4f}% | 約{int(sim_races * (loss_rate**10))}回 |
        | 15連敗 | {(loss_rate**15)*100:.6f}% | 約{int(sim_races * (loss_rate**15))}回 |
        | 20連敗 | {(loss_rate**20)*100:.8f}% | 約{int(sim_races * (loss_rate**20))}回 |
        
        **解説**: 的中率{hit_rate*100:.1f}%の場合、{max_consecutive_losses}連敗は統計的に十分起こりうる範囲です。
        システムを信じて継続することが重要です。
        """)
    else:
        st.warning("AI学習データがないため、シミュレーションを実行できません。")
    
    st.markdown("---")
    
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


# === タブ7: システム ===
with tab7:
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
    | 🐎 予想データ取得 | 土日 07:00 JST | レースデータ取得＋スコア計算 |
    | 📊 レース結果取得 | 土日 18:00 JST | 結果＋払戻金取得 |
    | 💹 リアルタイムオッズ | 手動実行 | 直前オッズ取得＋インサイダー検知 |
    | 📚 過去データ一括取得 | 手動実行 | 過去2年分のデータ収集 |
    | 🧠 AI学習 | 週1回（月曜） | 重み最適化＋バックテスト |
    """)

    st.markdown("---")

    # システム情報
    st.markdown("### 📋 システム情報")

    st.code(f"""
UMA-Logic PRO v2.1 (アンサンブル学習対応)
Python: {sys.version.split()[0]}
Streamlit: {st.__version__}
Plotly: {'Available' if PLOTLY_AVAILABLE else 'Not Available'}
AgGrid: {'Available' if AGGRID_AVAILABLE else 'Not Available'}
データディレクトリ: {DATA_DIR.absolute()}
アーカイブディレクトリ: {ARCHIVE_DIR.absolute()}
モデルディレクトリ: {MODELS_DIR.absolute()}
重みファイル: {WEIGHTS_FILE.absolute()}
    """)
