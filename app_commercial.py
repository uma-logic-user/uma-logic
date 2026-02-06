#!/usr/bin/env python3
# UMA-Logic PRO v3.0 - 商用グレード完全版UI
# 多券種対応 + ケリー基準投資モデル + 堅牢化
# weights.json 自動適用 / レース番号昇順ソート / 階層型検索UI

import streamlit as st
import pandas as pd
import math
import random
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

# Plotlyのインポート（オプション）
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

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

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]

DEFAULT_WEIGHTS = {
    "SpeedAgent": 0.35,
    "AdaptabilityAgent": 0.35,
    "PedigreeFormAgent": 0.30
}

SIRE_BONUS = {
    "ディープインパクト": 15, "キングカメハメハ": 12, "ロードカナロア": 12,
    "ハーツクライ": 10, "エピファネイア": 10, "ドゥラメンテ": 10,
    "キタサンブラック": 10, "モーリス": 8, "オルフェーヴル": 8, "ゴールドシップ": 5,
}

TOP_JOCKEYS = ["ルメール", "川田将雅", "戸崎圭太", "横山武史", "福永祐一", "武豊"]

# netkeibaの競馬場コード（VV）→ 名前
VENUE_CODES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉",
}


# --- 安全な型変換ヘルパー ---

def safe_float(val, default=0.0):
    """安全にfloatに変換"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    """安全にintに変換"""
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def safe_str(val, default=""):
    """安全にstrに変換"""
    if val is None:
        return default
    return str(val)


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
        padding: 1.5rem; border-radius: 10px; margin-bottom: 1.5rem;
        border-left: 4px solid #e94560;
    }
    .main-header h1 { color: #ffffff; margin: 0; font-size: 2rem; }
    .main-header p { color: #a0a0a0; margin: 0.5rem 0 0 0; }
    .race-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem;
        border: 1px solid #2a2a4a;
    }
    .race-title { color: #e94560; font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem; }
    .race-info { color: #a0a0a0; font-size: 0.85rem; }
    .rank-badge { padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 700; font-size: 0.8rem; margin-right: 0.5rem; }
    .rank-s-plus { background: linear-gradient(135deg, #ffd700, #ffaa00); color: #000; }
    .rank-s { background: linear-gradient(135deg, #e94560, #ff6b6b); color: #fff; }
    .rank-a { background: linear-gradient(135deg, #4ade80, #22c55e); color: #000; }
    .rank-b { background: #3b82f6; color: #fff; }
    .rank-c { background: #6b7280; color: #fff; }
    .insider-alert {
        background: linear-gradient(135deg, #ff6b6b, #e94560);
        color: white; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;
    }
    .ai-weights-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border-radius: 12px; padding: 1rem; margin-bottom: 1rem; border: 1px solid #4ade80;
    }
    .ai-weights-title { color: #4ade80; font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem; }
    .weight-bar { height: 8px; background: #2a2a4a; border-radius: 4px; margin: 0.3rem 0; overflow: hidden; }
    .weight-fill { height: 100%; border-radius: 4px; }
    .weight-speed { background: linear-gradient(90deg, #e94560, #ff6b6b); }
    .weight-adapt { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
    .weight-pedigree { background: linear-gradient(90deg, #4ade80, #22c55e); }
    .ev-positive { color: #4ade80; font-weight: 700; }
    .ev-negative { color: #ef4444; font-weight: 700; }
    .ticket-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem;
        border-left: 3px solid #4ade80;
    }
    .ticket-card.no-bet {
        border-left: 3px solid #6b7280; opacity: 0.7;
    }
</style>
""", unsafe_allow_html=True)


# --- AI重み読み込み ---

@st.cache_data(ttl=300)
def load_ai_weights() -> dict:
    if WEIGHTS_FILE.exists():
        try:
            with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"weights": DEFAULT_WEIGHTS.copy(), "metrics": {}, "train_metrics": {}, "test_metrics": {}, "updated_at": ""}


def get_agent_weights() -> dict:
    data = load_ai_weights()
    return data.get("weights", DEFAULT_WEIGHTS.copy())


# --- スコア計算関数（アンサンブル） ---

def calculate_speed_score(horse: dict, race: dict, weight: float = 0.35) -> float:
    score = 50.0
    odds = safe_float(horse.get("オッズ", horse.get("odds", 0)))
    popularity = safe_int(horse.get("人気", horse.get("popularity", 0)))
    gate_num = safe_int(horse.get("枠番", horse.get("gate_num", 0)))
    distance = safe_int(race.get("distance", 0))

    if odds > 0:
        if odds < 2.0: score += 30
        elif odds < 5.0: score += 20
        elif odds < 10.0: score += 10
        elif odds < 20.0: score += 0
        else: score -= 10

    if popularity > 0:
        if popularity <= 3: score += 15
        elif popularity <= 6: score += 5
        else: score -= 5

    if distance > 0:
        if distance <= 1400:
            if gate_num <= 4: score += 5
        elif distance >= 2000:
            if popularity > 5 and odds < 30: score += 5

    return max(0, min(100, score)) * weight


def calculate_adaptability_score(horse: dict, race: dict, weight: float = 0.35) -> float:
    score = 50.0
    gate_num = safe_int(horse.get("枠番", horse.get("gate_num", 0)))
    horse_weight = safe_float(horse.get("馬体重", horse.get("weight", 0)))
    weight_diff = safe_float(horse.get("増減", horse.get("weight_diff", 0)))
    distance = safe_int(race.get("distance", 0))
    track_condition = safe_str(race.get("track_condition", ""))

    if distance > 0 and gate_num > 0:
        if distance <= 1400:
            if gate_num <= 3: score += 15
            elif gate_num <= 5: score += 5
            elif gate_num >= 7: score -= 5
        elif distance > 1800:
            if gate_num >= 7: score -= 10

    if track_condition in ["重", "不良"]:
        if horse_weight >= 500: score += 10
        elif horse_weight <= 440: score -= 5

    if weight_diff != 0:
        if abs(weight_diff) > 20: score -= 10
        elif -10 <= weight_diff <= 10: score += 5

    return max(0, min(100, score)) * weight


def calculate_pedigree_score(horse: dict, race: dict, weight: float = 0.30) -> float:
    score = 50.0
    father = safe_str(horse.get("父", horse.get("father", "")))
    jockey = safe_str(horse.get("騎手", horse.get("jockey", "")))

    if father:
        score += SIRE_BONUS.get(father, 0)
    if jockey in TOP_JOCKEYS:
        score += 10

    return max(0, min(100, score)) * weight


def calculate_uma_index(horse: dict, race: dict) -> float:
    weights = get_agent_weights()
    speed = calculate_speed_score(horse, race, weights.get("SpeedAgent", 0.35))
    adapt = calculate_adaptability_score(horse, race, weights.get("AdaptabilityAgent", 0.35))
    pedigree = calculate_pedigree_score(horse, race, weights.get("PedigreeFormAgent", 0.30))
    return speed + adapt + pedigree


def get_rank_from_score(score: float) -> str:
    if score >= 75: return "S+"
    elif score >= 65: return "S"
    elif score >= 55: return "A"
    elif score >= 45: return "B"
    else: return "C"


# --- ケリー基準 ---

def estimate_win_probability(uma_index: float, num_horses: int = 16) -> float:
    if uma_index <= 0:
        return 0.01
    x = (uma_index - 50) / 10
    base_prob = 1.0 / (1.0 + math.exp(-x))
    horse_factor = 16.0 / max(num_horses, 5)
    return min(max(base_prob * horse_factor * 0.4, 0.01), 0.80)


def estimate_place_probability(uma_index: float, num_horses: int = 16) -> float:
    return min(estimate_win_probability(uma_index, num_horses) * 2.5, 0.90)


def kelly_fraction(win_prob: float, odds: float, cap: float = 0.25) -> float:
    if odds <= 1.0 or win_prob <= 0 or win_prob >= 1:
        return 0.0
    b = odds - 1.0
    f = (b * win_prob - (1 - win_prob)) / b
    if f <= 0:
        return 0.0
    return min(f * 0.5, cap)  # ハーフケリー


def expected_value(win_prob: float, odds: float) -> float:
    if odds <= 0 or win_prob <= 0:
        return 0.0
    return win_prob * odds


def calculate_multi_tickets(horses: list, race: dict, bankroll: float = 100000) -> list:
    """多券種の推奨馬券リストを生成"""
    recs = []
    num_horses = len(horses)
    if num_horses < 2:
        return recs

    sorted_h = sorted(horses, key=lambda x: safe_float(x.get("uma_index", 0)), reverse=True)

    # --- 単勝 ---
    for h in sorted_h[:5]:
        uma = safe_float(h.get("uma_index", 0))
        odds = safe_float(h.get("オッズ", h.get("odds", 0)))
        if odds <= 0:
            continue
        wp = estimate_win_probability(uma, num_horses)
        ev = expected_value(wp, odds)
        kf = kelly_fraction(wp, odds)
        bet = int(bankroll * kf / 100) * 100
        recs.append({
            "券種": "単勝", "馬番": safe_str(h.get("umaban", h.get("馬番", ""))),
            "馬名": safe_str(h.get("horse_name", h.get("馬名", ""))),
            "オッズ": odds, "的中確率": round(wp * 100, 1),
            "期待値": round(ev, 3), "ケリー比率": round(kf * 100, 2),
            "推奨投資額": max(bet, 0), "uma_index": uma,
        })

    # --- 複勝 ---
    for h in sorted_h[:5]:
        uma = safe_float(h.get("uma_index", 0))
        odds = safe_float(h.get("オッズ", h.get("odds", 0)))
        if odds <= 0:
            continue
        place_odds = max(odds * 0.35, 1.1)
        pp = estimate_place_probability(uma, num_horses)
        ev = expected_value(pp, place_odds)
        kf = kelly_fraction(pp, place_odds)
        bet = int(bankroll * kf / 100) * 100
        recs.append({
            "券種": "複勝", "馬番": safe_str(h.get("umaban", h.get("馬番", ""))),
            "馬名": safe_str(h.get("horse_name", h.get("馬名", ""))),
            "オッズ": round(place_odds, 1), "的中確率": round(pp * 100, 1),
            "期待値": round(ev, 3), "ケリー比率": round(kf * 100, 2),
            "推奨投資額": max(bet, 0), "uma_index": uma,
        })

    # --- 馬連・ワイド（上位3頭の組み合わせ） ---
    top3 = sorted_h[:3]
    for i in range(len(top3)):
        for j in range(i + 1, len(top3)):
            h1, h2 = top3[i], top3[j]
            uma1 = safe_float(h1.get("uma_index", 0))
            uma2 = safe_float(h2.get("uma_index", 0))
            odds1 = safe_float(h1.get("オッズ", h1.get("odds", 0)))
            odds2 = safe_float(h2.get("オッズ", h2.get("odds", 0)))
            if odds1 <= 0 or odds2 <= 0:
                continue

            ub1 = safe_str(h1.get("umaban", h1.get("馬番", "")))
            ub2 = safe_str(h2.get("umaban", h2.get("馬番", "")))
            nm1 = safe_str(h1.get("horse_name", h1.get("馬名", "")))
            nm2 = safe_str(h2.get("horse_name", h2.get("馬名", "")))

            # 馬連
            q_odds = max(math.sqrt(odds1 * odds2) * 1.5, 2.0)
            wp1 = estimate_win_probability(uma1, num_horses)
            wp2 = estimate_win_probability(uma2, num_horses)
            q_prob = wp1 * wp2 * 2 * 0.8
            ev_q = expected_value(q_prob, q_odds)
            kf_q = kelly_fraction(q_prob, q_odds)
            bet_q = int(bankroll * kf_q / 100) * 100
            recs.append({
                "券種": "馬連", "馬番": f"{ub1}-{ub2}", "馬名": f"{nm1} - {nm2}",
                "オッズ": round(q_odds, 1), "的中確率": round(q_prob * 100, 1),
                "期待値": round(ev_q, 3), "ケリー比率": round(kf_q * 100, 2),
                "推奨投資額": max(bet_q, 0), "uma_index": (uma1 + uma2) / 2,
            })

            # ワイド
            w_odds = max(math.sqrt(odds1 * odds2) * 0.5, 1.2)
            pp1 = estimate_place_probability(uma1, num_horses)
            pp2 = estimate_place_probability(uma2, num_horses)
            w_prob = pp1 * pp2 * 0.7
            ev_w = expected_value(w_prob, w_odds)
            kf_w = kelly_fraction(w_prob, w_odds)
            bet_w = int(bankroll * kf_w / 100) * 100
            recs.append({
                "券種": "ワイド", "馬番": f"{ub1}-{ub2}", "馬名": f"{nm1} - {nm2}",
                "オッズ": round(w_odds, 1), "的中確率": round(w_prob * 100, 1),
                "期待値": round(ev_w, 3), "ケリー比率": round(kf_w * 100, 2),
                "推奨投資額": max(bet_w, 0), "uma_index": (uma1 + uma2) / 2,
            })

    recs.sort(key=lambda x: x["期待値"], reverse=True)
    return recs


# --- ヘルパー関数 ---

def load_json_file(file_path: Path) -> dict:
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def load_predictions(date_str: str = None) -> dict:
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    return load_json_file(DATA_DIR / f"{PREDICTIONS_PREFIX}{date_str}.json")


def load_results(date_str: str = None) -> dict:
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    year, month, day = date_str[:4], date_str[4:6], date_str[6:8]
    archive_path = ARCHIVE_DIR / year / month / day / f"{RESULTS_PREFIX}{date_str}.json"
    if archive_path.exists():
        return load_json_file(archive_path)
    return load_json_file(DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json")


def load_insider_alerts() -> dict:
    return load_json_file(ALERTS_FILE)


def load_history() -> list:
    return load_json_file(HISTORY_FILE).get("history", [])


def get_available_dates() -> list:
    dates = set()
    for f in DATA_DIR.glob(f"{RESULTS_PREFIX}*.json"):
        match = f.stem.replace(RESULTS_PREFIX, "")
        if len(match) == 8 and match.isdigit():
            dates.add(match)
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
                    dates.add(f"{year_dir.name}{month_dir.name}{day_dir.name}")
    return sorted(dates, reverse=True)


def format_date_jp(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        return f"{dt.month}月{dt.day}日 ({WEEKDAY_JP[dt.weekday()]})"
    except Exception:
        return date_str


def get_rank_badge_html(rank: str) -> str:
    classes = {"S+": "rank-s-plus", "S": "rank-s", "A": "rank-a", "B": "rank-b", "C": "rank-c"}
    return f'<span class="rank-badge {classes.get(rank, "rank-c")}">{rank}</span>'


def sort_races_by_number(races: list) -> list:
    def get_num(race):
        rn = race.get("race_num", 0)
        if isinstance(rn, str):
            digits = ''.join(filter(str.isdigit, rn))
            return int(digits) if digits else 0
        return rn if rn else 0
    return sorted(races, key=get_num)


def resolve_venue(race: dict) -> str:
    """レースのvenueを確実に解決する"""
    venue = safe_str(race.get("venue", ""))
    if venue and venue != "不明":
        return venue
    rid = safe_str(race.get("race_id", ""))
    if len(rid) >= 6:
        # netkeibaのrace_id形式: YYYY VV CC DD RR → VV は位置4-5
        vv = rid[4:6]
        return VENUE_CODES.get(vv, "不明")
    return "不明"


# --- メインヘッダー ---
st.markdown("""
<div class="main-header">
    <h1>🐎 UMA-Logic PRO</h1>
    <p>AI競馬予想システム v3.0 - 多券種対応 / ケリー基準投資モデル</p>
</div>
""", unsafe_allow_html=True)


# --- サイドバー ---
with st.sidebar:
    st.markdown("### ⚙️ 設定")

    bankroll = st.number_input("💰 総資金 (円)", min_value=10000, max_value=10000000, value=100000, step=10000)

    kelly_mode = st.selectbox("📊 投資モード", ["ハーフケリー（安全）", "フルケリー（標準）", "アグレッシブ（積極的）"])

    min_ev_filter = st.slider("📈 最低期待値フィルタ", 0.5, 2.0, 1.0, 0.05)

    st.markdown("---")

    st.markdown("### 🧠 AI重み（自動適用）")
    ai_data = load_ai_weights()
    weights = ai_data.get("weights", DEFAULT_WEIGHTS)
    test_metrics = ai_data.get("test_metrics", {})
    updated_at = ai_data.get("updated_at", "未更新")

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

    if test_metrics:
        thr = safe_float(test_metrics.get("hit_rate", 0)) * 100
        trr = safe_float(test_metrics.get("recovery_rate", 0)) * 100
        st.markdown(f"**テスト成績**: 的中率 {thr:.1f}% / 回収率 {trr:.1f}%")
    else:
        metrics = ai_data.get("metrics", {})
        if metrics:
            hr = safe_float(metrics.get("hit_rate", 0)) * 100
            rr = safe_float(metrics.get("recovery_rate", 0)) * 100
            st.markdown(f"**成績**: 的中率 {hr:.1f}% / 回収率 {rr:.1f}%")

    st.markdown(f"<small>更新: {updated_at}</small>", unsafe_allow_html=True)

    if st.button("🔄 重み再読み込み"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### 📈 システム状態")
    available_dates = get_available_dates()
    st.metric("📅 データ日数", f"{len(available_dates)}日")
    if available_dates:
        st.metric("🕐 最新データ", format_date_jp(available_dates[0]))


# --- メインタブ ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎯 本日の予想",
    "📊 レース結果",
    "🎉 的中実績",
    "💰 資金配分",
    "🧠 AI学習状況",
    "⚙️ システム"
])


# === タブ1: 本日の予想（多券種対応） ===
with tab1:
    st.header("🎯 本日の予想")

    # インサイダーアラート
    alerts_data = load_insider_alerts()
    active_alerts = [a for a in alerts_data.get("alerts", []) if a.get("status") == "active"]
    if active_alerts:
        st.markdown("### 🚨 インサイダーアラート")
        for alert in active_alerts[:3]:
            st.markdown(f"""
            <div class="insider-alert">
                <strong>⚡ {alert.get('venue', '')} {alert.get('race_num', '')}R - {alert.get('horse_name', '')}</strong><br>
                オッズ急落検知: {safe_float(alert.get('odds_before', 0)):.1f} → {safe_float(alert.get('odds_after', 0)):.1f}
                （{safe_float(alert.get('drop_rate', 0))*100:.1f}%低下）
            </div>
            """, unsafe_allow_html=True)

    # 予想データ読み込み
    today_str = datetime.now().strftime("%Y%m%d")
    predictions = load_predictions(today_str)

    if predictions and predictions.get("races"):
        races = sort_races_by_number(predictions.get("races", []))
        venues = sorted(set(resolve_venue(r) for r in races))

        if venues:
            selected_venue = st.selectbox("🏟️ 競馬場を選択", venues, key="pred_venue")
            venue_races = sort_races_by_number([r for r in races if resolve_venue(r) == selected_venue])

            for race in venue_races:
                race_num = safe_int(race.get("race_num", 0))
                race_name = safe_str(race.get("race_name", ""))
                distance = safe_int(race.get("distance", 0))
                track_type = safe_str(race.get("track_type", ""))

                with st.expander(f"🏇 {race_num}R {race_name} ({track_type}{distance}m)", expanded=False):
                    horses = race.get("horses", []) or race.get("predictions", [])
                    if not horses:
                        st.info("出馬データがありません")
                        continue

                    # UMA指数を再計算
                    for horse in horses:
                        horse["uma_index"] = calculate_uma_index(horse, race)
                        horse["rank"] = get_rank_from_score(horse["uma_index"])

                    horses = sorted(horses, key=lambda x: safe_float(x.get("uma_index", 0)), reverse=True)

                    # --- 印付き上位5頭 ---
                    st.markdown("#### 📋 予想印")
                    marks = ["◎", "○", "▲", "△", "☆"]
                    for i, horse in enumerate(horses[:5]):
                        umaban = safe_str(horse.get("umaban", horse.get("馬番", "")))
                        name = safe_str(horse.get("horse_name", horse.get("馬名", "")))
                        odds = safe_float(horse.get("オッズ", horse.get("odds", 0)))
                        uma = safe_float(horse.get("uma_index", 0))
                        rank = horse.get("rank", "C")
                        mark = marks[i] if i < len(marks) else ""

                        c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 3, 2, 2, 1])
                        with c1: st.markdown(f"**{mark}**")
                        with c2: st.markdown(f"**{umaban}**")
                        with c3: st.markdown(name)
                        with c4: st.markdown(f"指数: **{uma:.1f}**" if uma > 0 else "")
                        with c5: st.markdown(f"オッズ: **{odds:.1f}**" if odds > 0 else "")
                        with c6: st.markdown(get_rank_badge_html(rank), unsafe_allow_html=True)

                    # --- 多券種推奨馬券リスト ---
                    st.markdown("---")
                    st.markdown("#### 💰 推奨馬券（ケリー基準）")

                    tickets = calculate_multi_tickets(horses, race, bankroll)
                    positive_tickets = [t for t in tickets if t["期待値"] >= min_ev_filter]

                    if positive_tickets:
                        total_bet = sum(t["推奨投資額"] for t in positive_tickets)
                        st.markdown(f"**期待値 {min_ev_filter:.2f} 以上の推奨馬券: {len(positive_tickets)}点 / 合計投資額: ¥{total_bet:,}**")

                        ticket_df = pd.DataFrame(positive_tickets)
                        display_cols = ["券種", "馬番", "馬名", "オッズ", "的中確率", "期待値", "推奨投資額"]
                        display_cols = [c for c in display_cols if c in ticket_df.columns]
                        st.dataframe(ticket_df[display_cols], use_container_width=True, hide_index=True)
                    else:
                        st.info("期待値フィルタを満たす推奨馬券はありません。フィルタを下げてみてください。")
    else:
        st.info("📭 本日の予想データがありません。土日の朝に自動更新されます。")

        # 直近の予想データを表示
        st.markdown("---")
        st.markdown("### 📅 直近の予想データ")
        pred_files = sorted(DATA_DIR.glob(f"{PREDICTIONS_PREFIX}*.json"), reverse=True)
        if pred_files:
            recent_dates = []
            for pf in pred_files[:10]:
                ds = pf.stem.replace(PREDICTIONS_PREFIX, "")
                if len(ds) == 8 and ds.isdigit():
                    recent_dates.append(ds)
            if recent_dates:
                selected_past = st.selectbox("📆 日付を選択", recent_dates, format_func=format_date_jp, key="past_pred")
                past_pred = load_predictions(selected_past)
                if past_pred and past_pred.get("races"):
                    past_races = sort_races_by_number(past_pred.get("races", []))
                    past_venues = sorted(set(resolve_venue(r) for r in past_races))
                    if past_venues:
                        pv = st.selectbox("🏟️ 競馬場", past_venues, key="past_pred_venue")
                        pv_races = sort_races_by_number([r for r in past_races if resolve_venue(r) == pv])
                        for race in pv_races:
                            rn = safe_int(race.get("race_num", 0))
                            rname = safe_str(race.get("race_name", ""))
                            horses = race.get("horses", []) or race.get("predictions", [])
                            if horses:
                                for h in horses:
                                    h["uma_index"] = calculate_uma_index(h, race)
                                horses = sorted(horses, key=lambda x: safe_float(x.get("uma_index", 0)), reverse=True)
                                top = horses[0]
                                st.markdown(f"**{rn}R** {rname} → ◎ {safe_str(top.get('horse_name', top.get('馬名', '')))} (指数: {safe_float(top.get('uma_index', 0)):.1f})")


# === タブ2: レース結果 ===
with tab2:
    st.header("📊 レース結果")

    available_dates = get_available_dates()

    if not available_dates:
        st.info("📭 レース結果データがありません。")
    else:
        dates_by_year = {}
        for ds in available_dates:
            y = ds[:4]
            dates_by_year.setdefault(y, []).append(ds)

        fc1, fc2 = st.columns(2)
        with fc1:
            years = sorted(dates_by_year.keys(), reverse=True)
            selected_year = st.selectbox("📅 年を選択", years, key="result_year")
        with fc2:
            year_dates = dates_by_year.get(selected_year, [])
            date_options = [(d, format_date_jp(d)) for d in year_dates]
            if date_options:
                sel_idx = st.selectbox("📆 開催日を選択", range(len(date_options)),
                                       format_func=lambda x: date_options[x][1], key="result_date")
                selected_date = date_options[sel_idx][0]
            else:
                selected_date = None

        if selected_date:
            results_data = load_results(selected_date)

            if results_data and results_data.get("races"):
                races = results_data.get("races", [])
                races = sort_races_by_number(races)

                # venueを確実に解決
                for race in races:
                    race["venue"] = resolve_venue(race)

                venues = sorted(set(r.get("venue", "不明") for r in races))

                if venues:
                    venue_tabs = st.tabs(venues)
                    for venue_tab, venue in zip(venue_tabs, venues):
                        with venue_tab:
                            v_races = sort_races_by_number([r for r in races if r.get("venue") == venue])

                            for race in v_races:
                                rn = safe_int(race.get("race_num", 0))
                                rname = safe_str(race.get("race_name", ""))

                                st.markdown(f"""
                                <div class="race-card">
                                    <div class="race-title">{rn}R {rname}</div>
                                    <div class="race-info">{venue} / {safe_int(race.get('distance', 0))}m / {safe_str(race.get('track_type', ''))}</div>
                                </div>
                                """, unsafe_allow_html=True)

                                with st.expander(f"📋 詳細を見る", expanded=False):
                                    st.markdown("#### 🏆 着順")
                                    top3 = race.get("top3", [])
                                    all_results = race.get("all_results", top3)

                                    if all_results:
                                        result_df = pd.DataFrame(all_results)
                                        col_map = {
                                            "rank": "着順", "umaban": "馬番", "horse_name": "馬名",
                                            "jockey": "騎手", "time": "タイム", "last_3f": "上がり3F",
                                            "odds": "オッズ",
                                        }
                                        result_df = result_df.rename(columns=col_map)
                                        show_cols = ["着順", "馬番", "馬名", "騎手", "タイム", "上がり3F", "オッズ"]
                                        show_cols = [c for c in show_cols if c in result_df.columns]
                                        if show_cols:
                                            st.dataframe(result_df[show_cols], use_container_width=True, hide_index=True)
                                    else:
                                        st.info("着順データがありません")

                                    st.markdown("#### 💰 払戻金")
                                    payouts = race.get("payouts", {})
                                    if payouts:
                                        pc1, pc2 = st.columns(2)
                                        items = list(payouts.items())
                                        mid = len(items) // 2 + len(items) % 2
                                        for col, chunk in [(pc1, items[:mid]), (pc2, items[mid:])]:
                                            with col:
                                                for key, value in chunk:
                                                    if isinstance(value, dict):
                                                        vs = " / ".join([f"{k}: ¥{v:,}" for k, v in value.items()])
                                                        st.markdown(f"**{key}**: {vs}")
                                                    elif isinstance(value, (int, float)):
                                                        st.markdown(f"**{key}**: ¥{value:,}")
                                                    else:
                                                        st.markdown(f"**{key}**: {value}")
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
        history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)
        total_hits = len(history)
        total_payout = sum(safe_int(h.get("payout", 0)) for h in history)

        c1, c2 = st.columns(2)
        with c1: st.metric("🎯 総的中数", f"{total_hits}回")
        with c2: st.metric("💰 総払戻金", f"¥{total_payout:,}")

        st.markdown("---")

        for hit in history[:20]:
            date = safe_str(hit.get("date", ""))
            venue = safe_str(hit.get("venue", ""))
            rn = safe_str(hit.get("race_num", ""))
            bt = safe_str(hit.get("bet_type", ""))
            po = safe_int(hit.get("payout", 0))
            hn = safe_str(hit.get("horse_name", ""))
            st.markdown(f"""
            <div class="race-card">
                <div class="race-title">🎉 {venue} {rn}R - {bt}</div>
                <div class="race-info">{format_date_jp(date) if date else ''} / {hn}<br>
                <span class="ev-positive">払戻: ¥{po:,}</span></div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("📭 まだ的中データがありません。")


# === タブ4: 資金配分（ケリー基準シミュレーター） ===
with tab4:
    st.header("💰 資金配分（ケリー基準）")

    st.markdown("""
    **ケリー基準** `f* = (bp - q) / b` は、期待値がプラスの賭けに対して長期的に資金を最大化する最適な投資比率です。

    - **ハーフケリー**: リスクを半減（推奨）
    - **フルケリー**: 理論上の最適値
    - **アグレッシブ**: フルケリーの1.2倍
    """)

    st.markdown("---")
    st.markdown("### 📊 投資額シミュレーター")

    sc1, sc2 = st.columns(2)
    with sc1:
        sim_prob = st.slider("勝率 (%)", 5, 50, 20, key="kelly_prob") / 100
        sim_odds = st.slider("オッズ", 1.5, 30.0, 5.0, 0.5, key="kelly_odds")
    with sc2:
        sim_bankroll = st.number_input("資金 (円)", 10000, 10000000, bankroll, 10000, key="kelly_bank")

    b = sim_odds - 1
    p = sim_prob
    q = 1 - p
    k = max(0, (b * p - q) / b) if b > 0 else 0

    st.markdown("### 📈 推奨投資額")
    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        hk = k * 0.5
        st.metric("ハーフケリー", f"¥{int(sim_bankroll * hk / 100) * 100:,}", f"{hk*100:.2f}%")
    with rc2:
        st.metric("フルケリー", f"¥{int(sim_bankroll * k / 100) * 100:,}", f"{k*100:.2f}%")
    with rc3:
        ak = k * 1.2
        st.metric("アグレッシブ", f"¥{int(sim_bankroll * ak / 100) * 100:,}", f"{ak*100:.2f}%")

    ev_sim = sim_prob * sim_odds
    if ev_sim > 1:
        st.markdown(f'**期待値**: <span class="ev-positive">{ev_sim:.2f} ✅ プラス期待値</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'**期待値**: <span class="ev-negative">{ev_sim:.2f} ❌ マイナス期待値</span>', unsafe_allow_html=True)


# === タブ5: AI学習状況 ===
with tab5:
    st.header("🧠 AI学習状況")

    ai_data = load_ai_weights()
    test_metrics = ai_data.get("test_metrics", {})
    train_metrics = ai_data.get("train_metrics", {})
    metrics = ai_data.get("metrics", {})

    # --- 資産推移シミュレーション ---
    st.markdown("### 📈 資産推移シミュレーション")

    ec1, ec2, ec3 = st.columns(3)
    with ec1: initial_capital = st.number_input("初期資金 (円)", 10000, 10000000, 100000, 10000, key="eq_cap")
    with ec2: bet_per_race = st.number_input("1レース投資額 (円)", 100, 10000, 100, 100, key="eq_bet")
    with ec3: sim_races = st.number_input("シミュレーションレース数", 100, 10000, 1000, 100, key="eq_races")

    hit_rate = safe_float(test_metrics.get("hit_rate", metrics.get("hit_rate", 0.2)))
    recovery_rate = safe_float(test_metrics.get("recovery_rate", metrics.get("recovery_rate", 0.8)))

    if hit_rate > 0 and recovery_rate > 0:
        avg_odds = recovery_rate / hit_rate if hit_rate > 0 else 5.0
        random.seed(42)

        equity_curve = [initial_capital]
        drawdowns = []
        max_equity = initial_capital
        current_equity = initial_capital
        max_consecutive_losses = 0
        consecutive_losses = 0

        for _ in range(sim_races):
            if random.random() < hit_rate:
                current_equity += int(bet_per_race * avg_odds) - bet_per_race
                consecutive_losses = 0
            else:
                current_equity -= bet_per_race
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            if current_equity <= 0:
                current_equity = 0
                equity_curve.append(0)
                break
            equity_curve.append(current_equity)
            if current_equity > max_equity:
                max_equity = current_equity
            drawdowns.append((max_equity - current_equity) / max_equity if max_equity > 0 else 0)

        if PLOTLY_AVAILABLE:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=list(range(len(equity_curve))), y=equity_curve,
                                      mode="lines", name="資産推移", line=dict(color="#4ade80", width=2)))
            fig.add_hline(y=initial_capital, line_dash="dash", line_color="#fbbf24", annotation_text="初期資金")
            fig.update_layout(title=f"資産推移（的中率: {hit_rate*100:.1f}%, 回収率: {recovery_rate*100:.1f}%）",
                              xaxis_title="レース数", yaxis_title="資産 (円)", template="plotly_dark", height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.line_chart(equity_curve)

        final_eq = equity_curve[-1]
        profit = final_eq - initial_capital
        profit_rate = (final_eq / initial_capital - 1) * 100
        max_dd = max(drawdowns) * 100 if drawdowns else 0

        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1: st.metric("最終資産", f"¥{final_eq:,.0f}", f"{profit_rate:+.1f}%")
        with mc2: st.metric("純損益", f"¥{profit:,.0f}")
        with mc3: st.metric("最大DD", f"{max_dd:.1f}%")
        with mc4: st.metric("最大連敗", f"{max_consecutive_losses}")
    else:
        st.warning("AI学習データがないため、シミュレーションを実行できません。")

    st.markdown("---")

    # 現在のAI重み
    st.markdown("### 📊 現在のAI重み")
    w = ai_data.get("weights", DEFAULT_WEIGHTS)
    wc1, wc2, wc3 = st.columns(3)
    with wc1: st.metric("🔥 Speed", f"{safe_float(w.get('SpeedAgent', 0.35))*100:.0f}%")
    with wc2: st.metric("🎯 Adapt", f"{safe_float(w.get('AdaptabilityAgent', 0.35))*100:.0f}%")
    with wc3: st.metric("🧬 Pedigree", f"{safe_float(w.get('PedigreeFormAgent', 0.30))*100:.0f}%")

    st.markdown("---")

    # Train/Test分離の成績
    st.markdown("### 📈 バックテスト結果")
    if train_metrics and test_metrics:
        tc, tc2 = st.columns(2)
        with tc:
            st.markdown("#### 📚 Train")
            ty = train_metrics.get("years", [])
            st.markdown(f"**対象年**: {', '.join(map(str, ty)) if ty else '不明'}")
            st.metric("レース数", f"{safe_int(train_metrics.get('total_races', 0)):,}")
            st.metric("的中率", f"{safe_float(train_metrics.get('hit_rate', 0))*100:.2f}%")
            st.metric("回収率", f"{safe_float(train_metrics.get('recovery_rate', 0))*100:.2f}%")
        with tc2:
            st.markdown("#### 🧪 Test")
            tey = test_metrics.get("years", [])
            st.markdown(f"**対象年**: {', '.join(map(str, tey)) if tey else '不明'}")
            st.metric("レース数", f"{safe_int(test_metrics.get('total_races', 0)):,}")
            st.metric("的中率", f"{safe_float(test_metrics.get('hit_rate', 0))*100:.2f}%")
            st.metric("回収率", f"{safe_float(test_metrics.get('recovery_rate', 0))*100:.2f}%")

        # 過学習チェック
        tr_r = safe_float(train_metrics.get("recovery_rate", 0))
        te_r = safe_float(test_metrics.get("recovery_rate", 0))
        if tr_r > 0 and te_r > 0:
            ratio = tr_r / te_r
            st.markdown("---")
            st.markdown("### ⚠️ 過学習チェック")
            if ratio > 2.0:
                st.error(f"⚠️ 過学習の可能性あり（Train/Test比: {ratio:.1f}倍）")
            elif ratio > 1.5:
                st.warning(f"⚡ 軽度の過学習（Train/Test比: {ratio:.1f}倍）")
            else:
                st.success(f"✅ 良好（Train/Test比: {ratio:.2f}倍）")
    elif metrics:
        st.metric("レース数", f"{safe_int(metrics.get('total_races', 0)):,}")
        st.metric("的中率", f"{safe_float(metrics.get('hit_rate', 0))*100:.2f}%")
        st.metric("回収率", f"{safe_float(metrics.get('recovery_rate', 0))*100:.2f}%")
        st.warning("⚠️ Train/Test分離されていない旧形式です。")
    else:
        st.info("📭 AI学習データがありません。")

    up = ai_data.get("updated_at", "")
    if up:
        st.markdown(f"**最終更新**: {up}")


# === タブ6: システム ===
with tab6:
    st.header("⚙️ システム情報")

    st.markdown("### 📊 データ統計")
    pred_count = len(list(DATA_DIR.glob(f"{PREDICTIONS_PREFIX}*.json")))
    res_count = len(list(DATA_DIR.glob(f"{RESULTS_PREFIX}*.json")))
    sc1, sc2, sc3 = st.columns(3)
    with sc1: st.metric("📝 予想ファイル", f"{pred_count}件")
    with sc2: st.metric("📊 結果ファイル", f"{res_count}件")
    with sc3: st.metric("📅 アーカイブ日数", f"{len(available_dates)}日")

    st.markdown("---")
    st.markdown("### 📚 アーカイブ統計")
    index_data = load_json_file(INDEX_FILE)
    if index_data:
        for year in sorted(index_data.get("years", {}).keys(), reverse=True):
            yi = index_data["years"][year]
            st.markdown(f"**{year}年**: {yi.get('total_dates', 0)}日 / {yi.get('total_races', 0)}レース")
    else:
        st.info("アーカイブインデックスがありません。")

    st.markdown("---")
    st.markdown("### 🔄 GitHub Actions ワークフロー")
    st.markdown("""
    | ワークフロー | スケジュール | 説明 |
    |-------------|-------------|------|
    | 🐎 予想データ取得 | 手動実行 | レースデータ取得＋スコア計算 |
    | 📊 レース結果取得 | 手動実行 | 結果＋払戻金取得 |
    | 📚 過去データ一括取得 | 手動実行 | 過去データ収集 |
    | 🧠 AI学習 | 手動実行 | 重み最適化＋バックテスト |
    """)

    st.markdown("---")
    st.code(f"""
UMA-Logic PRO v3.0 (多券種対応 + ケリー基準)
Python: {sys.version.split()[0]}
Streamlit: {st.__version__}
Plotly: {'Available' if PLOTLY_AVAILABLE else 'Not Available'}
データ: {DATA_DIR.absolute()}
モデル: {MODELS_DIR.absolute()}
    """)
