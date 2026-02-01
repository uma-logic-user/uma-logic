# app_commercial.py
# UMA-Logic Pro - エラーハンドリング強化版

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

# Plotlyのインポート（エラー時はフォールバック）
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("Plotlyが利用できません。一部のグラフが表示されません。")

# AgGridのインポート（エラー時はフォールバック）
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
DATA_DIR.mkdir(parents=True, exist_ok=True)  # ディレクトリがなければ作成

PREDICTIONS_PREFIX = "predictions_"
RESULTS_PREFIX = "results_"

# --- 安全なデータ読み込み関数 ---

def safe_load_json(filepath: Path) -> dict:
    """JSONファイルを安全に読み込む"""
    try:
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        st.error(f"ファイル読み込みエラー: {filepath} - {e}")
    return {}


def get_available_dates() -> list:
    """利用可能な日付リストを取得"""
    dates = set()
    try:
        if DATA_DIR.exists():
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
    except Exception as e:
        st.error(f"日付取得エラー: {e}")
    return sorted(dates, reverse=True) if dates else [datetime.now().date()]


def load_predictions(date) -> dict:
    """指定日の予想データを読み込む"""
    date_str = date.strftime("%Y%m%d")
    filepath = DATA_DIR / f"{PREDICTIONS_PREFIX}{date_str}.json"
    data = safe_load_json(filepath)
    if data:
        return data
    # フォールバック
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

st.sidebar.markdown("---")
st.sidebar.caption("© 2026 UMA-Logic Pro v2.0")


# --- データ読み込み ---
predictions_data = load_predictions(selected_date)
results_data = load_results(selected_date)
history_data = load_history()


# --- メインコンテンツ ---
st.title("🐎 UMA-Logic Pro")

tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 本日の予想",
    "🏁 レース結果",
    "🎉 的中実績",
    "📈 収支レポート"
])

# タブ1: 予想
with tab1:
    st.header(f"🎯 {selected_date.strftime('%Y年%m月%d日')} の予想")
    
    races = predictions_data.get("races", [])
    
    if not races:
        st.info("この日の予想データがありません。")
    else:
        for race in races[:10]:  # 最大10レース表示
            rank = race.get("rank", "B")
            venue = race.get("venue", "")
            race_num = race.get("race_num", "")
            
            st.subheader(f"{venue} {race_num}R [{rank}]")
            
            horses = race.get("horses", [])
            if horses:
                df = pd.DataFrame([
                    {
                        "印": h.get("印", ""),
                        "馬番": h.get("馬番", ""),
                        "馬名": h.get("馬名", ""),
                        "UMA指数": h.get("UMA指数", 0),
                        "単勝オッズ": h.get("単勝オッズ", 0)
                    }
                    for h in horses[:5]
                ])
                st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown("---")

# タブ2: 結果
with tab2:
    st.header(f"🏁 {selected_date.strftime('%Y年%m月%d日')} の結果")
    
    result_races = results_data.get("races", [])
    
    if not result_races:
        st.info("この日の結果データはまだありません。")
    else:
        for race in result_races[:10]:
            st.subheader(f"{race.get('venue', '')} {race.get('race_num', '')}R")
            
            top3 = race.get("top3", [])
            if top3:
                df = pd.DataFrame([
                    {"着順": i+1, "馬番": h.get("馬番", ""), "馬名": h.get("馬名", "")}
                    for i, h in enumerate(top3[:3])
                ])
                st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown("---")

# タブ3: 的中実績
with tab3:
    st.header("🎉 的中実績")
    
    if history_data:
        st.dataframe(pd.DataFrame(history_data), use_container_width=True)
    else:
        st.info("まだ的中データがありません。")

# タブ4: 収支
with tab4:
    st.header("📈 収支レポート")
    
    if history_data:
        hist_df = pd.DataFrame(history_data)
        if "投資額" in hist_df.columns and "的中配当金" in hist_df.columns:
            total_invest = hist_df["投資額"].sum()
            total_return = hist_df["的中配当金"].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("総投資額", f"¥{total_invest:,}")
            col2.metric("総払戻額", f"¥{total_return:,}")
            col3.metric("純損益", f"¥{total_return - total_invest:,}")
    else:
        st.info("まだ収支データがありません。")
