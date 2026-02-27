import streamlit as st
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

# 1. 基本設定
st.set_page_config(page_title="UMA-Logic PRO", layout="wide")
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 2. ヘルパー関数
def load_json(path):
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

# 3. メインUI
st.title("🐎 UMA-Logic PRO v3.0")
st.caption("Sayaka様用 - 堅牢化モデル")

# サイドバー
with st.sidebar:
    bankroll = st.number_input("💰 総資金", value=100000)
    k_mode = st.selectbox("📊 投資モード", ["ハーフケリー", "フルケリー"])

# タブ
tab1, tab2, tab3 = st.tabs(["🎯 予想", "📊 結果", "💰 資金配分"])

with tab1:
    today = datetime.now().strftime("%Y%m%d")
    st.write(f"本日 ({today}) の予想データを確認中...")
    # ここに予想ロジック

with tab2:
    st.header("📊 レース結果 (netkeiba反映)")
    res_files = sorted(DATA_DIR.glob("results_*.json"), reverse=True)
    if res_files:
        sel = st.selectbox("日付選択", res_files)
        st.json(load_json(sel))
    else:
        st.info("dataフォルダに results_YYYYMMDD.json を入れてください")

with tab3:
    st.header("💰 ケリー基準計算")
    odds = st.number_input("オッズ", value=2.0, min_value=1.1)
    prob = st.slider("的中率", 0, 100, 50) / 100
    ev = odds * prob
    st.metric("期待値", f"{ev:.2f}")
    
    # 簡単なケリー計算
    f = ( (odds-1) * prob - (1-prob) ) / (odds-1) if odds > 1 else 0
    mult = 0.5 if k_mode == "ハーフケリー" else 1.0
    bet = max(0, int(bankroll * f * mult))
    st.metric("推奨投資額", f"¥{bet:,}")