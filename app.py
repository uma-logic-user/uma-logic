# app_commercial.py
# UMA-Logic Pro - 商用グレード完成版（レース結果タブ強化版）

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path

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
    page_title="UMA-Logic Pro",
    page_icon="🐎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 定数 ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
PREDICTIONS_PREFIX = "predictions_"
RESULTS_PREFIX = "results_"

# --- CSSスタイル ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap' );

    html, body, [class*="st-"], .stApp {
        font-family: 'Noto Sans JP', sans-serif;
        background-color: #1A1A2E;
        color: #FFFFFF;
    }

    .stSidebar {
        background-color: #16213E;
    }

    h1, h2, h3 {
        color: #F6C953 !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #16213E;
        padding: 10px;
        border-radius: 10px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: #1A1A2E;
        border-radius: 8px;
        padding: 12px 24px;
        color: #FFFFFF;
        font-weight: bold;
    }

    .stTabs [aria-selected="true"] {
        background-color: #F6C953 !important;
        color: #1A1A2E !important;
    }

    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(246, 201, 83, 0.7); }
        70% { box-shadow: 0 0 0 15px rgba(246, 201, 83, 0); }
        100% { box-shadow: 0 0 0 0 rgba(246, 201, 83, 0); }
    }

    .pulse-s-rank {
        animation: pulse 2s infinite;
        border: 2px solid #F6C953;
        border-radius: 10px;
        padding: 15px;
        background-color: rgba(246, 201, 83, 0.1);
    }

    .rank-s { color: #F6C953; font-weight: bold; font-size: 1.2em; }
    .rank-a { color: #87CEEB; font-weight: bold; }
    .rank-b { color: #AAAAAA; }

    .gold-badge {
        display: inline-block;
        background-color: #F6C953;
        color: #1A1A2E;
        padding: 3px 10px;
        border-radius: 15px;
        font-weight: bold;
        font-size: 0.85em;
        margin-left: 8px;
    }

    .hit-badge {
        display: inline-block;
        background: linear-gradient(135deg, #4CAF50, #45a049);
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.9em;
        margin-left: 10px;
    }

    .venue-card {
        background: linear-gradient(135deg, #2a2a4e, #1A1A2E);
        padding: 15px 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        border-left: 4px solid #F6C953;
    }

    .race-card {
        background: linear-gradient(135deg, #252545, #1e1e3a);
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid #3c3c5a;
    }

    .race-card:hover {
        border-color: #F6C953;
    }

    .payout-table {
        background-color: #16213E;
        border-radius: 8px;
        padding: 10px;
    }

    .payout-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 12px;
        border-bottom: 1px solid #3c3c5a;
    }

    .payout-row:last-child {
        border-bottom: none;
    }

    .payout-label {
        color: #AAAAAA;
    }

    .payout-value {
        color: #F6C953;
        font-weight: bold;
    }

    .venue-button {
        background-color: #2a2a4e;
        color: white;
        border: 2px solid #3c3c5a;
        padding: 10px 20px;
        border-radius: 8px;
        margin-right: 8px;
        cursor: pointer;
    }

    .venue-button-active {
        background-color: #F6C953;
        color: #1A1A2E;
        border-color: #F6C953;
    }

    .result-header {
        background: linear-gradient(135deg, #F6C953, #e5b84a);
        color: #1A1A2E;
        padding: 10px 15px;
        border-radius: 8px 8px 0 0;
        font-weight: bold;
    }

    .result-body {
        background-color: #16213E;
        padding: 15px;
        border-radius: 0 0 8px 8px;
        border: 1px solid #3c3c5a;
        border-top: none;
    }
</style>
""", unsafe_allow_html=True)


# --- 安全なデータ読み込み関数 ---

def safe_load_json(filepath: Path) -> dict:
    """JSONファイルを安全に読み込む"""
    try:
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def get_available_dates_by_year() -> dict:
    """年ごとの利用可能な日付リストを取得"""
    dates_by_year = {}
    try:
        for filepath in DATA_DIR.glob(f"{RESULTS_PREFIX}*.json"):
            date_str = filepath.stem.replace(RESULTS_PREFIX, "")
            if len(date_str) == 8 and date_str.isdigit():
                try:
                    date = datetime.strptime(date_str, "%Y%m%d").date()
                    year = date.year
                    if year not in dates_by_year:
                        dates_by_year[year] = []
                    dates_by_year[year].append(date)
                except ValueError:
                    continue
        
        # 予想ファイルからも日付を取得
        for filepath in DATA_DIR.glob(f"{PREDICTIONS_PREFIX}*.json"):
            date_str = filepath.stem.replace(PREDICTIONS_PREFIX, "")
            if len(date_str) == 8 and date_str.isdigit():
                try:
                    date = datetime.strptime(date_str, "%Y%m%d").date()
                    year = date.year
                    if year not in dates_by_year:
                        dates_by_year[year] = []
                    if date not in dates_by_year[year]:
                        dates_by_year[year].append(date)
                except ValueError:
                    continue
        
        # 各年の日付をソート
        for year in dates_by_year:
            dates_by_year[year] = sorted(dates_by_year[year], reverse=True)
            
    except Exception:
        pass
    
    return dates_by_year


def get_available_dates() -> list:
    """利用可能な日付リストを取得"""
    dates = set()
    try:
        for filepath in DATA_DIR.glob(f"{PREDICTIONS_PREFIX}*.json"):
            date_str = filepath.stem.replace(PREDICTIONS_PREFIX, "")
            if len(date_str) == 8 and date_str.isdigit():
                try:
                    dates.add(datetime.strptime(date_str, "%Y%m%d").date())
                except ValueError:
                    continue
        for filepath in DATA_DIR.glob(f"{RESULTS_PREFIX}*.json"):
            date_str = filepath.stem.replace(RESULTS_PREFIX, "")
            if len(date_str) == 8 and date_str.isdigit():
                try:
                    dates.add(datetime.strptime(date_str, "%Y%m%d").date())
                except ValueError:
                    continue
    except Exception:
        pass
    return sorted(dates, reverse=True) if dates else [datetime.now().date()]


def load_predictions(date) -> dict:
    """指定日の予想データを読み込む"""
    date_str = date.strftime("%Y%m%d")
    filepath = DATA_DIR / f"{PREDICTIONS_PREFIX}{date_str}.json"
    data = safe_load_json(filepath)
    if data:
        return data
    latest_path = DATA_DIR / "latest_predictions.json"
    return safe_load_json(latest_path) or {"races": [], "date": date.strftime("%Y-%m-%d")}


def load_results(date) -> dict:
    """指定日の結果データを読み込む"""
    date_str = date.strftime("%Y%m%d")
    filepath = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
    return safe_load_json(filepath) or {"races": [], "date": date.strftime("%Y-%m-%d")}


def load_history() -> list:
    """的中履歴を読み込む"""
    filepath = DATA_DIR / "history.json"
    data = safe_load_json(filepath)
    return data if isinstance(data, list) else []


def check_hit(prediction: dict, result: dict) -> dict:
    """予想と結果を照合して的中判定"""
    hit_result = {
        "単勝": {"hit": False, "payout": 0},
        "複勝": {"hit": False, "payout": 0},
        "馬連": {"hit": False, "payout": 0},
        "三連複": {"hit": False, "payout": 0},
    }
    
    if not result or not prediction:
        return hit_result
    
    top3 = result.get("top3", [])
    if len(top3) < 3:
        return hit_result
    
    first = top3[0].get("馬番", 0)
    second = top3[1].get("馬番", 0)
    third = top3[2].get("馬番", 0)
    
    horses = prediction.get("horses", [])
    honmei = next((h["馬番"] for h in horses if h.get("印") == "◎"), 0)
    taikou = next((h["馬番"] for h in horses if h.get("印") == "○"), 0)
    tanpana = next((h["馬番"] for h in horses if h.get("印") == "▲"), 0)
    
    payouts = result.get("payouts", {})
    
    if honmei == first:
        hit_result["単勝"] = {"hit": True, "payout": payouts.get("単勝", 0)}
    
    if honmei in [first, second, third]:
        fukusho = payouts.get("複勝", {})
        payout = fukusho.get(str(honmei), 0) if isinstance(fukusho, dict) else 0
        hit_result["複勝"] = {"hit": True, "payout": payout}
    
    if {honmei, taikou} == {first, second}:
        hit_result["馬連"] = {"hit": True, "payout": payouts.get("馬連", 0)}
    
    if {honmei, taikou, tanpana} == {first, second, third}:
        hit_result["三連複"] = {"hit": True, "payout": payouts.get("三連複", 0)}
    
    return hit_result


def format_payout(value) -> str:
    """払戻金を表示用にフォーマット"""
    if isinstance(value, dict):
        return " / ".join([f"¥{v:,}" for v in value.values() if v])
    elif isinstance(value, (int, float)) and value > 0:
        return f"¥{int(value):,}"
    else:
        return "-"


# --- サイドバー ---
st.sidebar.markdown("# 🐎 UMA-Logic Pro")
st.sidebar.markdown("---")

st.sidebar.markdown("### 📅 アーカイブ")
available_dates = get_available_dates()

selected_date = st.sidebar.date_input(
    "表示する日付",
    value=available_dates[0] if available_dates else datetime.now().date(),
    format="YYYY/MM/DD"
)

st.sidebar.markdown("---")

st.sidebar.markdown("### 💰 投資設定")
total_budget = st.sidebar.slider("総予算", 1000, 100000, 10000, 1000, format="¥%d")
investment_style = st.sidebar.radio(
    "投資スタイル",
    ["A：バランス型", "B：高配当狙い"],
    captions=["単勝〜三連単まで分散", "馬連・三連系に集中"]
)

st.sidebar.markdown("---")
st.sidebar.caption("© 2026 UMA-Logic Pro v2.0")


# --- データ読み込み ---
predictions_data = load_predictions(selected_date)
results_data = load_results(selected_date)
history_data = load_history()


# --- メインコンテンツ（6タブ構成） ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎯 本日の予想",
    "🏁 レース結果",
    "🎉 的中実績",
    "📈 収支レポート",
    "💰 資金配分",
    "⚙️ システム状態"
])


# ========================================
# タブ1: 本日の予想
# ========================================
# app_commercial.py のタブ1（予想）に追加

# インサイダーアラート表示
def show_insider_alerts():
    """インサイダーアラートを表示"""
    alerts_file = DATA_DIR / "insider_alerts.json"
    
    if not alerts_file.exists():
        return
    
    try:
        with open(alerts_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        alerts = data.get("alerts", [])
        
        if alerts:
            st.markdown("### 🚨 インサイダーアラート")
            
            for alert in alerts:
                severity_color = {
                    "HIGH": "🔴",
                    "MEDIUM": "🟡",
                    "LOW": "🟢"
                }.get(alert.get("severity", "LOW"), "⚪")
                
                with st.expander(
                    f"{severity_color} {alert.get('venue', '')} {alert.get('race_name', '')} - "
                    f"{alert.get('umaban', '')}番 {alert.get('horse_name', '')}"
                ):
                    col1, col2, col3 = st.columns(3)
                    
                    col1.metric(
                        "オッズ変動",
                        f"{alert.get('current_odds', 0):.1f}",
                        f"{-alert.get('drop_rate', 0)*100:.1f}%"
                    )
                    col2.metric(
                        "信頼度",
                        f"{alert.get('confidence', 0)*100:.0f}%"
                    )
                    col3.metric(
                        "期待値ブースト",
                        f"{alert.get('expected_value_boost', 1.0):.2f}x"
                    )
                    
                    if alert.get("aggressive_mode"):
                        st.success("⚡ **Aggressiveモード有効** - ケリー基準が自動調整されています")
                    
                    st.caption(f"検出時刻: {alert.get('detected_at', '')}")
    
    except Exception as e:
        pass

# タブ1の先頭で呼び出し
with tab1:
    st.header("🎯 本日の予想")
    
    # インサイダーアラート表示
    show_insider_alerts()
with tab1:
    st.markdown(f"## 🎯 {selected_date.strftime('%Y年%m月%d日')} の予想")
    
    races = predictions_data.get("races", [])
    
    if not races:
        st.warning("この日の予想データがありません。")
    else:
        s_count = len([r for r in races if r.get("rank") == "S"])
        a_count = len([r for r in races if r.get("rank") == "A"])
        b_count = len([r for r in races if r.get("rank") == "B"])
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("総レース数", f"{len(races)}R")
        col2.metric("🥇 Sランク", f"{s_count}R")
        col3.metric("🥈 Aランク", f"{a_count}R")
        col4.metric("🥉 Bランク", f"{b_count}R")
        
        st.markdown("---")
        
        venues = sorted(set(r.get("venue", "不明") for r in races))
        
        for venue in venues:
            st.markdown(f'<div class="venue-card"><h3>🏇 {venue}競馬場</h3></div>', unsafe_allow_html=True)
            
            venue_races = sorted(
                [r for r in races if r.get("venue") == venue],
                key=lambda x: x.get("race_num", 0)
            )
            
            cols = st.columns(3)
            
            for idx, race in enumerate(venue_races):
                with cols[idx % 3]:
                    rank = race.get("rank", "B")
                    rank_class = f"rank-{rank.lower()}"
                    container_class = "pulse-s-rank" if rank == "S" else ""
                    
                    horses = race.get("horses", [])
                    honmei = next((h for h in horses if h.get("印") == "◎"), None)
                    
                    race_result = next(
                        (r for r in results_data.get("races", [])
                         if r.get("venue") == venue and r.get("race_num") == race.get("race_num")),
                        None
                    )
                    hit_info = check_hit(race, race_result) if race_result else None
                    
                    if container_class:
                        st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True)
                    
                    title_html = f"**{race.get('race_num', '')}R** <span class='{rank_class}'>[{rank}]</span>"
                    if honmei:
                        title_html += f" ◎{honmei.get('馬番', '')} {honmei.get('馬名', '')}"
                    
                    if hit_info:
                        total_payout = sum(h["payout"] for h in hit_info.values() if h["hit"])
                        if total_payout > 0:
                            title_html += f'<span class="hit-badge">🎯 +¥{total_payout:,}</span>'
                    
                    st.markdown(title_html, unsafe_allow_html=True)
                    
                    with st.expander("詳細", expanded=(rank == "S")):
                        for horse in horses[:5]:
                            mark = horse.get("印", "")
                            if not mark:
                                continue
                            
                            h_info = f"**{mark} {horse.get('馬番', '')} {horse.get('馬名', '')}**"
                            ev = horse.get("期待値", 0)
                            if ev >= 1.2:
                                h_info += f'<span class="gold-badge">EV {ev:.2f}</span>'
                            st.markdown(h_info, unsafe_allow_html=True)
                            
                            uma_idx = horse.get("UMA指数", 50)
                            st.progress(uma_idx / 100, text=f"UMA指数: {uma_idx}")
                            
                            odds = horse.get("単勝オッズ", 0)
                            reason = horse.get("推奨理由", "")
                            st.caption(f"単勝 {odds:.1f}倍 / {reason}")
                    
                    if container_class:
                        st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown("")


# ========================================
# タブ2: レース結果（大幅アップデート版）
# ========================================
with tab2:
    st.markdown("## 🏁 レース結果")
    
    # --- 階層化された検索・絞り込み機能 ---
    dates_by_year = get_available_dates_by_year()
    
    if not dates_by_year:
        st.warning("結果データがありません。")
    else:
        # 検索フィルター（3カラム）
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        # 年選択
        with filter_col1:
            available_years = sorted(dates_by_year.keys(), reverse=True)
            selected_year = st.selectbox(
                "📅 年を選択",
                available_years,
                index=0,
                key="result_year"
            )
        
       # 日付選択（選択した年の日付のみ表示）
        with filter_col2:
            year_dates = dates_by_year.get(selected_year, [])
            
            # 曜日を漢字で表示
            def format_date_jp(d):
                weekday_jp = ["月", "火", "水", "木", "金", "土", "日"]
                return f"{d.month}月{d.day}日 ({weekday_jp[d.weekday()]})"
            
            date_options = [format_date_jp(d) for d in year_dates]
            
            if date_options:
                selected_date_idx = st.selectbox(
                    "📆 開催日を選択",
                    range(len(date_options)),
                    format_func=lambda x: date_options[x],
                    index=0,
                    key="result_date"
                )
                result_target_date = year_dates[selected_date_idx]
            else:
                st.warning("この年のデータがありません")
                result_target_date = None
        
        # 結果データを読み込み
        if result_target_date:
            result_data_for_display = load_results(result_target_date)
            result_races = result_data_for_display.get("races", [])
            
            # 競馬場選択
            with filter_col3:
                if result_races:
                    venues_in_day = sorted(set(r.get("venue", "不明") for r in result_races))
                    selected_result_venue = st.selectbox(
                        "🏇 競馬場を選択",
                        venues_in_day,
                        index=0,
                        key="result_venue"
                    )
                else:
                    selected_result_venue = None
                    st.info("この日の結果データはまだありません")
            
            st.markdown("---")
            
            # --- 選択した競馬場のレース結果を表示 ---
            if result_races and selected_result_venue:
                venue_results = sorted(
                    [r for r in result_races if r.get("venue") == selected_result_venue],
                    key=lambda x: x.get("race_num", 0)
                )
                
                st.markdown(f'<div class="venue-card"><h3>🏇 {selected_result_venue}競馬場 - {result_target_date.strftime("%Y年%m月%d日")}</h3></div>', unsafe_allow_html=True)
                
                # レース数サマリー
                st.markdown(f"**全 {len(venue_results)} レース**")
                
                # 3カラムグリッドでレースカードを表示
                cols = st.columns(3)
                
                for idx, race in enumerate(venue_results):
                    with cols[idx % 3]:
                        race_num = race.get("race_num", "")
                        race_name = race.get("race_name", f"{race_num}R")
                        
                        # レースカードヘッダー
                        st.markdown(f"""
                        <div class="result-header">
                            🏆 {race_num}R {race_name}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 着順表示（簡易版）
                        top3 = race.get("top3", race.get("all_results", []))[:3]
                        if top3:
                            for i, horse in enumerate(top3):
                                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else ""
                                st.markdown(f"{medal} **{horse.get('馬番', '')}** {horse.get('馬名', '')}")
                        
                        # 詳細アコーディオン（絵文字なしでシンプルに）
                        with st.expander("詳細を見る"):
                            # --- 着順テーブル ---
                            st.markdown("**🏇 着順表**")
                            all_results = race.get("all_results", race.get("top3", []))
                            
                            if all_results:
                                result_df = pd.DataFrame([
                                    {
                                        "着順": h.get("着順", i + 1),
                                        "馬番": h.get("馬番", ""),
                                        "馬名": h.get("馬名", ""),
                                        "騎手": h.get("騎手", ""),
                                        "タイム": h.get("タイム", ""),
                                        "上がり3F": h.get("上がり3F", ""),
                                        "オッズ": h.get("オッズ", h.get("単勝オッズ", "-"))
                                    }
                                    for i, h in enumerate(all_results[:8])  # 上位8頭まで
                                ])
                                st.dataframe(result_df, use_container_width=True, hide_index=True)
                            
                            # --- 払戻金テーブル ---
                            st.markdown("**💰 払戻金**")
                            payouts = race.get("payouts", {})
                            
                            if payouts:
                                # 2カラムで払戻金を表示
                                payout_col1, payout_col2 = st.columns(2)
                                
                                # 単勝・複勝系
                                with payout_col1:
                                    st.markdown("**単勝・複勝**")
                                    payout_items_1 = [
                                        ("単勝", payouts.get("単勝", 0)),
                                        ("複勝", payouts.get("複勝", {})),
                                        ("枠連", payouts.get("枠連", 0)),
                                        ("馬連", payouts.get("馬連", 0)),
                                    ]
                                    for label, value in payout_items_1:
                                        display_val = format_payout(value)
                                        if display_val != "-":
                                            st.markdown(f"**{label}**: {display_val}")
                                
                                # 連複・連単系
                                with payout_col2:
                                    st.markdown("**連複・連単**")
                                    payout_items_2 = [
                                        ("馬単", payouts.get("馬単", 0)),
                                        ("ワイド", payouts.get("ワイド", {})),
                                        ("三連複", payouts.get("三連複", 0)),
                                        ("三連単", payouts.get("三連単", 0)),
                                    ]
                                    for label, value in payout_items_2:
                                        display_val = format_payout(value)
                                        if display_val != "-":
                                            st.markdown(f"**{label}**: {display_val}")
                            else:
                                st.info("払戻金データがありません")
                        
                        st.markdown("")  # スペーサー
            
            elif not result_races:
                st.info("この日の結果データはまだありません。レース終了後に自動取得されます。")


# ========================================
# タブ3: 的中実績
# ========================================
with tab3:
    st.markdown("## 🎉 的中実績")
    
    all_hits = []
    for date in available_dates:
        pred = load_predictions(date)
        res = load_results(date)
        
        for race in pred.get("races", []):
            race_result = next(
                (r for r in res.get("races", [])
                 if r.get("venue") == race.get("venue") and r.get("race_num") == race.get("race_num")),
                None
            )
            if race_result:
                hit_info = check_hit(race, race_result)
                for bet_type, info in hit_info.items():
                    if info["hit"] and info["payout"] > 0:
                        all_hits.append({
                            "日付": date.strftime("%Y-%m-%d"),
                            "会場": race.get("venue", ""),
                            "R": race.get("race_num", 0),
                            "券種": bet_type,
                            "配当": info["payout"],
                            "本命": next((h.get("馬名", "") for h in race.get("horses", []) if h.get("印") == "◎"), "")
                        })
    
    if all_hits:
        hit_df = pd.DataFrame(all_hits)
        
        total_payout = hit_df["配当"].sum()
        hit_count = len(hit_df)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("🎯 的中回数", f"{hit_count}回")
        c2.metric("💰 累計配当", f"¥{total_payout:,}")
        c3.metric("📊 平均配当", f"¥{total_payout // hit_count:,}" if hit_count > 0 else "¥0")
        
        st.markdown("---")
        st.markdown("### 的中一覧")
        st.dataframe(hit_df, use_container_width=True, hide_index=True)
        
        st.markdown("### 券種別集計")
        summary = hit_df.groupby("券種").agg({"配当": ["count", "sum", "mean"]}).round(0)
        summary.columns = ["回数", "合計", "平均"]
        st.dataframe(summary, use_container_width=True)
    else:
        st.info("まだ的中データがありません。")


# ========================================
# タブ4: 収支レポート
# ========================================
with tab4:
    st.markdown("## 📈 収支レポート")
    
    if history_data:
        hist_df = pd.DataFrame(history_data)
        
        if "投資額" in hist_df.columns and "的中配当金" in hist_df.columns:
            total_invest = hist_df["投資額"].sum()
            total_return = hist_df["的中配当金"].sum()
            profit = total_return - total_invest
            roi = (total_return / total_invest * 100) if total_invest > 0 else 0
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if PLOTLY_AVAILABLE:
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number+delta",
                        value=roi,
                        title={'text': "累計回収率", 'font': {'size': 20, 'color': 'white'}},
                        delta={'reference': 100, 'increasing': {'color': "#4CAF50"}, 'decreasing': {'color': "#f44336"}},
                        gauge={
                            'axis': {'range': [0, 200], 'tickcolor': "white"},
                            'bar': {'color': "#F6C953"},
                            'bgcolor': "#1A1A2E",
                            'borderwidth': 2,
                            'bordercolor': "#3c3c5a",
                            'steps': [
                                {'range': [0, 80], 'color': '#3c3c5a'},
                                {'range': [80, 120], 'color': '#5a5a7a'}
                            ],
                            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 100}
                        }
                    ))
                    fig.update_layout(paper_bgcolor="#1A1A2E", font_color="white", height=300)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.metric("累計回収率", f"{roi:.1f}%")
            
            with col2:
                st.metric("💰 純損益", f"¥{profit:,}")
                st.metric("📥 総投資", f"¥{total_invest:,}")
                st.metric("📤 総払戻", f"¥{total_return:,}")
        else:
            st.warning("履歴データの形式が正しくありません。")
    else:
        st.info("まだ収支データがありません。")


# ========================================
# タブ5: 資金配分
# ========================================
with tab5:
    st.markdown("## 💰 資金配分シミュレーター")
    
    st.info(f"総予算: **¥{total_budget:,}** / スタイル: **{investment_style}**")
    
    races = predictions_data.get("races", [])
    
    if not races:
        st.warning("予想データがありません。")
    else:
        race_options = [f"{r.get('venue', '')}{r.get('race_num', '')}R [{r.get('rank', 'B')}]" for r in races]
        selected_race_str = st.selectbox("対象レースを選択", race_options)
        
        idx = race_options.index(selected_race_str)
        selected_race = races[idx]
        
        st.markdown(f"### シミュレーション: {selected_race_str}")
        
        rank = selected_race.get("rank", "B")
        multiplier = {"S": 1.5, "A": 1.0, "B": 0.7}.get(rank, 1.0)
        
        if "バランス" in investment_style:
            config = {"単勝": 0.2, "馬連": 0.25, "馬単": 0.15, "三連複": 0.25, "三連単": 0.15}
        else:
            config = {"単勝": 0.05, "馬連": 0.3, "馬単": 0.2, "三連複": 0.3, "三連単": 0.15}
        
        allocations = {k: int(np.round(total_budget * v * multiplier / 100) * 100) for k, v in config.items()}
        
        alloc_cols = st.columns(5)
        for i, (bt, amt) in enumerate(allocations.items()):
            alloc_cols[i].metric(bt, f"¥{amt:,}")
        
        st.success(f"合計配分: ¥{sum(allocations.values()):,}")
        
        st.markdown("---")
        st.markdown("### 買い目構成案")
        
        horses = selected_race.get("horses", [])
        honmei = next((h for h in horses if h.get("印") == "◎"), None)
        taikou = next((h for h in horses if h.get("印") == "○"), None)
        tanpana = next((h for h in horses if h.get("印") == "▲"), None)
        
        if honmei:
            st.write(f"**単勝**: {honmei.get('馬番', '')}番")
        if honmei and taikou:
            st.write(f"**馬連**: {honmei.get('馬番', '')} - {taikou.get('馬番', '')}")
        if honmei and taikou and tanpana:
            st.write(f"**三連複**: {honmei.get('馬番', '')} - {taikou.get('馬番', '')} - {tanpana.get('馬番', '')}")


# ========================================
# タブ6: システム状態
# ========================================
with tab6:
    st.markdown("## ⚙️ システム状態")
    
    st.markdown("### 📁 データファイル状態")
    
    files_to_check = [
        ("latest_predictions.json", "最新予想"),
        ("history.json", "的中履歴"),
    ]
    
    for filename, label in files_to_check:
        filepath = DATA_DIR / filename
        if filepath.exists():
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            st.markdown(f'✅ **{label}** (`{filename}`) - 最終更新: {mtime.strftime("%Y-%m-%d %H:%M")}')
        else:
            st.markdown(f'❌ **{label}** (`{filename}`) - ファイルなし')
    
    st.markdown("---")
    
    st.markdown("### 📊 アーカイブ状況")
    pred_count = len(list(DATA_DIR.glob(f"{PREDICTIONS_PREFIX}*.json")))
    res_count = len(list(DATA_DIR.glob(f"{RESULTS_PREFIX}*.json")))
    
    c1, c2 = st.columns(2)
    c1.metric("予想ファイル数", f"{pred_count}件")
    c2.metric("結果ファイル数", f"{res_count}件")
    
    st.markdown("---")
    
    st.markdown("### 🔄 GitHub Actions ワークフロー")
    st.markdown("""
    | ワークフロー | スケジュール | 説明 |
    |-------------|-------------|------|
    | 🐎 予想データ取得 | 土日 07:00 JST | レースデータ取得＋スコア計算 |
    | 📊 レース結果取得 | 土日 18:00 JST | 結果＋払戻金取得 |
    | 💹 リアルタイムオッズ | 手動実行 | 直前オッズ取得 |
    """)
    
    st.markdown("---")
    st.markdown("### 📋 システム情報")
    st.code(f"""
UMA-Logic Pro v2.0
Streamlit: {st.__version__}
Plotly: {'Available' if PLOTLY_AVAILABLE else 'Not Available'}
AgGrid: {'Available' if AGGRID_AVAILABLE else 'Not Available'}
データディレクトリ: {DATA_DIR.absolute()}
    """)
