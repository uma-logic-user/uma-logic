# app_commercial.py
# UMA-Logic Pro - 商用グレード完成版
# アーカイブ機能・全レース結果・的中照合機能を統合

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from datetime import datetime, timedelta
import json
import os
import glob
from pathlib import Path

# --- ページ設定と基本スタイル ---
st.set_page_config(
    page_title="UMA-Logic Pro",
    page_icon="🐎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 定数 ---
DATA_DIR = Path("data")
PREDICTIONS_PREFIX = "predictions_"
RESULTS_PREFIX = "results_"

# --- CSSスタイル ---
def load_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap' );

        html, body, [class*="st-"], [class*="css-"] {
            font-family: 'Noto Sans JP', sans-serif;
            background-color: #1A1A2E;
            color: #FFFFFF;
        }

        .css-1d391kg {
            background-color: #1A1A2E;
            border-right: 1px solid #3c3c5a;
        }

        .main .block-container {
            padding-top: 2rem;
        }

        h1, h2, h3 {
            color: #F6C953;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(246, 201, 83, 0.7); }
            70% { box-shadow: 0 0 0 15px rgba(246, 201, 83, 0); }
            100% { box-shadow: 0 0 0 0 rgba(246, 201, 83, 0); }
        }

        .pulse-s-rank {
            animation: pulse 2s infinite;
            border-radius: 10px;
            padding: 10px;
            background-color: rgba(246, 201, 83, 0.1);
            border: 1px solid #F6C953;
        }

        .gold-badge {
            display: inline-block;
            background-color: #F6C953;
            color: #1A1A2E;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 0.8em;
            margin-left: 10px;
        }

        .hit-badge {
            display: inline-block;
            background-color: #4CAF50;
            color: white;
            padding: 4px 12px;
            border-radius: 15px;
            font-weight: bold;
            font-size: 0.9em;
            margin-left: 10px;
        }

        .miss-badge {
            display: inline-block;
            background-color: #666;
            color: #ccc;
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.9em;
            margin-left: 10px;
        }

        .rank-s { color: #F6C953; font-weight: bold; }
        .rank-a { color: #87CEEB; font-weight: bold; }
        .rank-b { color: #AAAAAA; }

        .venue-header {
            background-color: #2a2a4e;
            padding: 10px 15px;
            border-radius: 8px;
            margin-bottom: 15px;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }

        .stTabs [data-baseweb="tab"] {
            background-color: #2a2a4e;
            border-radius: 8px 8px 0 0;
            padding: 10px 20px;
        }

        .stTabs [aria-selected="true"] {
            background-color: #F6C953;
            color: #1A1A2E;
        }
    </style>
    """, unsafe_allow_html=True)

load_css()


# --- データ読み込み関数 ---

def get_available_dates() -> list:
    """
    data/ディレクトリから利用可能な日付リストを取得
    """
    dates = set()
    
    # 予想ファイルから日付を抽出
    for filepath in DATA_DIR.glob(f"{PREDICTIONS_PREFIX}*.json"):
        date_str = filepath.stem.replace(PREDICTIONS_PREFIX, "")
        if len(date_str) == 8 and date_str.isdigit():
            try:
                date = datetime.strptime(date_str, "%Y%m%d").date()
                dates.add(date)
            except ValueError:
                continue
    
    # 結果ファイルからも日付を抽出
    for filepath in DATA_DIR.glob(f"{RESULTS_PREFIX}*.json"):
        date_str = filepath.stem.replace(RESULTS_PREFIX, "")
        if len(date_str) == 8 and date_str.isdigit():
            try:
                date = datetime.strptime(date_str, "%Y%m%d").date()
                dates.add(date)
            except ValueError:
                continue
    
    return sorted(dates, reverse=True)


def load_predictions(date: datetime.date) -> dict:
    """
    指定日の予想データを読み込む
    """
    date_str = date.strftime("%Y%m%d")
    filepath = DATA_DIR / f"{PREDICTIONS_PREFIX}{date_str}.json"
    
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # latest_predictions.jsonをフォールバック
    latest_path = DATA_DIR / "latest_predictions.json"
    if latest_path.exists():
        with open(latest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 日付が一致するか確認
            if data.get("date") == date.strftime("%Y-%m-%d"):
                return data
    
    return {"races": [], "date": date.strftime("%Y-%m-%d")}


def load_results(date: datetime.date) -> dict:
    """
    指定日の結果データを読み込む
    """
    date_str = date.strftime("%Y%m%d")
    filepath = DATA_DIR / f"{RESULTS_PREFIX}{date_str}.json"
    
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    return {"races": [], "date": date.strftime("%Y-%m-%d")}


def load_history() -> pd.DataFrame:
    """
    的中履歴データを読み込む
    """
    filepath = DATA_DIR / "history.json"
    
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return pd.DataFrame(data)
    
    return pd.DataFrame(columns=["日付", "レース名", "的中券種", "投資額", "的中配当金"])


def check_hit(prediction: dict, result: dict) -> dict:
    """
    予想と結果を照合して的中判定を行う
    
    Returns:
        {
            "単勝": {"hit": bool, "payout": int},
            "馬連": {"hit": bool, "payout": int},
            ...
        }
    """
    hit_result = {
        "単勝": {"hit": False, "payout": 0},
        "複勝": {"hit": False, "payout": 0},
        "馬連": {"hit": False, "payout": 0},
        "馬単": {"hit": False, "payout": 0},
        "三連複": {"hit": False, "payout": 0},
        "三連単": {"hit": False, "payout": 0}
    }
    
    if not result or not prediction:
        return hit_result
    
    # 結果から着順を取得
    top3 = result.get("top3", [])
    if len(top3) < 3:
        return hit_result
    
    first = top3[0].get("馬番", 0)
    second = top3[1].get("馬番", 0)
    third = top3[2].get("馬番", 0)
    
    # 予想から推奨馬を取得
    horses = prediction.get("horses", [])
    if not horses:
        return hit_result
    
    # 印ごとの馬番を取得
    honmei = next((h["馬番"] for h in horses if h.get("印") == "◎"), 0)
    taikou = next((h["馬番"] for h in horses if h.get("印") == "○"), 0)
    tanpana = next((h["馬番"] for h in horses if h.get("印") == "▲"), 0)
    
    # 払戻金を取得
    payouts = result.get("payouts", {})
    
    # 単勝的中判定（◎が1着）
    if honmei == first:
        hit_result["単勝"]["hit"] = True
        hit_result["単勝"]["payout"] = payouts.get("単勝", 0)
    
    # 複勝的中判定（◎が3着以内）
    if honmei in [first, second, third]:
        hit_result["複勝"]["hit"] = True
        hit_result["複勝"]["payout"] = payouts.get("複勝", {}).get(str(honmei), 0)
    
    # 馬連的中判定（◎○が1-2着、順不同）
    if set([honmei, taikou]) == set([first, second]):
        hit_result["馬連"]["hit"] = True
        hit_result["馬連"]["payout"] = payouts.get("馬連", 0)
    
    # 馬単的中判定（◎→○が1着→2着）
    if honmei == first and taikou == second:
        hit_result["馬単"]["hit"] = True
        hit_result["馬単"]["payout"] = payouts.get("馬単", 0)
    
    # 三連複的中判定（◎○▲が1-2-3着、順不同）
    if set([honmei, taikou, tanpana]) == set([first, second, third]):
        hit_result["三連複"]["hit"] = True
        hit_result["三連複"]["payout"] = payouts.get("三連複", 0)
    
    # 三連単的中判定（◎→○→▲が1着→2着→3着）
    if honmei == first and taikou == second and tanpana == third:
        hit_result["三連単"]["hit"] = True
        hit_result["三連単"]["payout"] = payouts.get("三連単", 0)
    
    return hit_result


# --- サイドバー ---
st.sidebar.title("🐎 UMA-Logic Pro")
st.sidebar.markdown("---")

# 日付選択（カレンダー形式）
st.sidebar.subheader("📅 日付選択")
available_dates = get_available_dates()

if available_dates:
    min_date = min(available_dates)
    max_date = max(available_dates)
    default_date = max_date
else:
    min_date = datetime(2026, 1, 31).date()
    max_date = datetime.now().date()
    default_date = datetime.now().date()

selected_date = st.sidebar.date_input(
    "表示する日付",
    value=default_date,
    min_value=min_date,
    max_value=max_date,
    format="YYYY/MM/DD"
)

st.sidebar.markdown("---")

# 予算設定
st.sidebar.subheader("💰 投資設定")
total_budget = st.sidebar.slider(
    "総予算",
    min_value=1000,
    max_value=100000,
    value=10000,
    step=1000,
    format="¥%d"
)

investment_style = st.sidebar.radio(
    "投資スタイル",
    ('A：総合バランス投資', 'B：連勝複式・一撃Ver'),
    captions=["単勝から三連単まで幅広く配分", "馬連/馬単/三連複/三連単に集中"]
)

st.sidebar.markdown("---")
st.sidebar.caption("© 2026 UMA-Logic Pro")


# --- メインコンテンツ ---

# データ読み込み
predictions_data = load_predictions(selected_date)
results_data = load_results(selected_date)
history_df = load_history()

# タブ設定
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎯 予想一覧",
    "📊 全レース結果",
    "🎉 的中実績",
    "📈 収支レポート",
    "💰 資金配分"
])


# --- タブ1: 予想一覧 ---
with tab1:
    st.header(f"🎯 {selected_date.strftime('%Y年%m月%d日')} の予想")
    
    races = predictions_data.get("races", [])
    
    if not races:
        st.warning("この日の予想データがありません。")
    else:
        # 会場でグループ化
        venues = sorted(list(set(r.get("venue", "不明") for r in races)))
        
        for venue in venues:
            st.markdown(f'<div class="venue-header"><h3>🏇 {venue}競馬場</h3></div>', unsafe_allow_html=True)
            
            venue_races = [r for r in races if r.get("venue") == venue]
            venue_races.sort(key=lambda x: x.get("race_num", 0))
            
            # 3カラムグリッド
            cols = st.columns(3)
            
            for idx, race in enumerate(venue_races):
                col_idx = idx % 3
                
                with cols[col_idx]:
                    rank = race.get("rank", "B")
                    rank_class = f"rank-{rank.lower()}"
                    container_class = "pulse-s-rank" if rank == "S" else ""
                    
                    # 本命馬を取得
                    horses = race.get("horses", [])
                    honmei = next((h for h in horses if h.get("印") == "◎"), None)
                    
                    # 結果との照合
                    race_result = next(
                        (r for r in results_data.get("races", [])
                         if r.get("venue") == venue and r.get("race_num") == race.get("race_num")),
                        None
                    )
                    hit_info = check_hit(race, race_result) if race_result else None
                    
                    # レースカード
                    st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True)
                    
                    # ヘッダー
                    race_title = f"**{race.get('race_num', '')}R** "
                    race_title += f"<span class='{rank_class}'>[{rank}]</span> "
                    if honmei:
                        race_title += f"◎ {honmei.get('馬番', '')} {honmei.get('馬名', '')}"
                    
                    # 的中バッジ
                    if hit_info:
                        total_payout = sum(h["payout"] for h in hit_info.values() if h["hit"])
                        if total_payout > 0:
                            race_title += f"<span class='hit-badge'>🎯 的中 +¥{total_payout:,}</span>"
                    
                    st.markdown(race_title, unsafe_allow_html=True)
                    
                    # 詳細
                    with st.expander("詳細を見る", expanded=(rank == "S")):
                        for horse in horses[:5]:
                            mark = horse.get("印", "")
                            if not mark:
                                continue
                            
                            horse_info = f"**{mark} {horse.get('馬番', '')} {horse.get('馬名', '')}**"
                            
                            # 期待値バッジ
                            ev = horse.get("期待値", 0)
                            if ev >= 1.2:
                                horse_info += f"<span class='gold-badge'>期待値 {ev:.2f}</span>"
                            
                            st.markdown(horse_info, unsafe_allow_html=True)
                            
                            # UMA指数プログレスバー
                            uma_index = horse.get("UMA指数", 50)
                            st.progress(uma_index / 100, text=f"UMA指数: {uma_index}")
                            
                            # 詳細情報
                            odds = horse.get("単勝オッズ", 0)
                            reason = horse.get("推奨理由", "")
                            st.caption(f"単勝: {odds:.1f}倍 / {reason}")
                        
                        # 結果表示
                        if race_result:
                            st.markdown("---")
                            st.markdown("**📋 結果**")
                            top3 = race_result.get("top3", [])
                            for i, horse in enumerate(top3[:3], 1):
                                st.write(f"{i}着: {horse.get('馬番', '')} {horse.get('馬名', '')}")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown("&nbsp;")


# --- タブ2: 全レース結果 ---
with tab2:
    st.header(f"📊 {selected_date.strftime('%Y年%m月%d日')} の全レース結果")
    
    result_races = results_data.get("races", [])
    
    if not result_races:
        st.warning("この日の結果データがありません。レース終了後に自動取得されます。")
    else:
        # 会場選択
        result_venues = sorted(list(set(r.get("venue", "不明") for r in result_races)))
        selected_venue = st.selectbox("競馬場を選択", result_venues, key="result_venue")
        
        venue_results = [r for r in result_races if r.get("venue") == selected_venue]
        venue_results.sort(key=lambda x: x.get("race_num", 0))
        
        for race in venue_results:
            st.subheader(f"{race.get('race_num', '')}R {race.get('race_name', '')}")
            
            # 着順テーブル
            top3 = race.get("top3", [])
            if top3:
                result_df = pd.DataFrame([
                    {
                        "着順": i + 1,
                        "馬番": h.get("馬番", ""),
                        "馬名": h.get("馬名", ""),
                        "騎手": h.get("騎手", ""),
                        "タイム": h.get("タイム", ""),
                        "上がり3F": h.get("上がり3F", "")
                    }
                    for i, h in enumerate(top3)
                ])
                
                # AgGrid設定
                gb = GridOptionsBuilder.from_dataframe(result_df)
                gb.configure_default_column(filterable=True, sortable=True)
                gb.configure_column("馬名", filter="agTextColumnFilter")
                gb.configure_column("騎手", filter="agTextColumnFilter")
                gridOptions = gb.build()
                
                AgGrid(
                    result_df,
                    gridOptions=gridOptions,
                    height=200,
                    theme='streamlit-dark',
                    enable_enterprise_modules=False
                )
            
            # 払戻金テーブル
            payouts = race.get("payouts", {})
            if payouts:
                st.markdown("**💰 払戻金**")
                
                payout_cols = st.columns(4)
                
                bet_types = [
                    ("単勝", "単勝"), ("複勝", "複勝"),
                    ("枠連", "枠連"), ("馬連", "馬連"),
                    ("馬単", "馬単"), ("ワイド", "ワイド"),
                    ("三連複", "三連複"), ("三連単", "三連単")
                ]
                
                for i, (label, key) in enumerate(bet_types):
                    col_idx = i % 4
                    with payout_cols[col_idx]:
                        payout_val = payouts.get(key, 0)
                        if isinstance(payout_val, dict):
                            # 複勝やワイドの場合（複数の払戻）
                            payout_str = " / ".join([f"¥{v:,}" for v in payout_val.values()])
                        elif payout_val > 0:
                            payout_str = f"¥{payout_val:,}"
                        else:
                            payout_str = "-"
                        st.metric(label, payout_str)
            
            st.markdown("---")


# --- タブ3: 的中実績 ---
with tab3:
    st.header("🎉 的中実績")
    
    # 的中レースの抽出
    hit_records = []
    
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
                        hit_records.append({
                            "日付": date.strftime("%Y-%m-%d"),
                            "会場": race.get("venue", ""),
                            "レース": f"{race.get('race_num', '')}R",
                            "券種": bet_type,
                            "配当金": info["payout"],
                            "本命馬": next((h.get("馬名", "") for h in race.get("horses", []) if h.get("印") == "◎"), "")
                        })
    
    if hit_records:
        hit_df = pd.DataFrame(hit_records)
        
        # サマリー
        total_payout = hit_df["配当金"].sum()
        hit_count = len(hit_df)
        
        summary_cols = st.columns(3)
        with summary_cols[0]:
            st.metric("🎯 的中回数", f"{hit_count}回")
        with summary_cols[1]:
            st.metric("💰 累計配当金", f"¥{total_payout:,}")
        with summary_cols[2]:
            avg_payout = total_payout / hit_count if hit_count > 0 else 0
            st.metric("📊 平均配当", f"¥{avg_payout:,.0f}")
        
        st.markdown("---")
        
        # 的中一覧テーブル
        st.subheader("的中一覧")
        
        gb = GridOptionsBuilder.from_dataframe(hit_df)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(filterable=True, sortable=True)
        gb.configure_column("日付", type=["dateColumnFilter"])
        gb.configure_column("配当金", valueFormatter=JsCode("""
            function(params) {
                return '¥' + params.value.toLocaleString();
            }
        """))
        gridOptions = gb.build()
        
        AgGrid(
            hit_df,
            gridOptions=gridOptions,
            height=400,
            theme='streamlit-dark',
            enable_enterprise_modules=False
        )
        
        # 券種別集計
        st.subheader("券種別的中集計")
        bet_type_summary = hit_df.groupby("券種").agg({
            "配当金": ["count", "sum", "mean"]
        }).round(0)
        bet_type_summary.columns = ["的中回数", "合計配当", "平均配当"]
        st.dataframe(bet_type_summary, use_container_width=True)
        
    else:
        st.info("まだ的中データがありません。レース終了後に自動で更新されます。")


# --- タブ4: 収支レポート ---
with tab4:
    st.header("📈 収支レポート")
    
    if not history_df.empty:
        # 日付型に変換
        history_df["日付"] = pd.to_datetime(history_df["日付"])
        history_df["純損益"] = history_df["的中配当金"] - history_df["投資額"]
        
        # 累計計算
        total_investment = history_df["投資額"].sum()
        total_payout = history_df["的中配当金"].sum()
        total_profit = total_payout - total_investment
        recovery_rate = (total_payout / total_investment * 100) if total_investment > 0 else 0
        
        # メーター表示
        meter_cols = st.columns(4)
        
        with meter_cols[0]:
            fig_meter = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=recovery_rate,
                title={'text': "累計回収率", 'font': {'size': 18, 'color': 'white'}},
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
            fig_meter.update_layout(
                paper_bgcolor="#1A1A2E",
                font={'color': "white", 'family': "Noto Sans JP"},
                height=250
            )
            st.plotly_chart(fig_meter, use_container_width=True)
        
        with meter_cols[1]:
            st.metric("💰 累計純損益", f"¥{total_profit:,}")
        with meter_cols[2]:
            st.metric("📥 総投資額", f"¥{total_investment:,}")
        with meter_cols[3]:
            st.metric("📤 総払戻額", f"¥{total_payout:,}")
        
        st.markdown("---")
        
        # 日別推移グラフ
        st.subheader("日別収支推移")
        
        daily_summary = history_df.set_index("日付").resample("D").agg({
            "投資額": "sum",
            "的中配当金": "sum",
            "純損益": "sum"
        }).reset_index()
        daily_summary["累計純損益"] = daily_summary["純損益"].cumsum()
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily_summary["日付"],
            y=daily_summary["純損益"],
            name="日別純損益",
            marker_color=np.where(daily_summary["純損益"] >= 0, "#4CAF50", "#f44336")
        ))
        fig.add_trace(go.Scatter(
            x=daily_summary["日付"],
            y=daily_summary["累計純損益"],
            name="累計純損益",
            line=dict(color="#F6C953", width=3),
            yaxis="y2"
        ))
        
        fig.update_layout(
            paper_bgcolor="#1A1A2E",
            plot_bgcolor="#1A1A2E",
            font_color="white",
            yaxis=dict(title="日別純損益 (円)", gridcolor="#3c3c5a"),
            yaxis2=dict(title="累計純損益 (円)", overlaying="y", side="right", gridcolor="#3c3c5a"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 月別集計
        st.subheader("月別集計")
        monthly_summary = history_df.set_index("日付").resample("M").agg({
            "投資額": "sum",
            "的中配当金": "sum",
            "純損益": "sum"
        })
        monthly_summary["回収率"] = (monthly_summary["的中配当金"] / monthly_summary["投資額"] * 100).round(1)
        monthly_summary.index = monthly_summary.index.strftime("%Y年%m月")
        st.dataframe(monthly_summary, use_container_width=True)
        
    else:
        st.info("まだ収支データがありません。")


# --- タブ5: 資金配分 ---
with tab5:
    st.header("💰 資金配分シミュレーター")
    
    st.info(f"総予算: ¥{total_budget:,} / スタイル: {investment_style}")
    
    races = predictions_data.get("races", [])
    
    if not races:
        st.warning("予想データがありません。")
    else:
        # レース選択
        race_options = [f"{r.get('venue', '')}{r.get('race_num', '')}R [{r.get('rank', 'B')}]" for r in races]
        selected_race_str = st.selectbox("シミュレーション対象レースを選択", race_options)
        
        selected_idx = race_options.index(selected_race_str)
        selected_race = races[selected_idx]
        
        st.subheader(f"シミュレーション結果: {selected_race_str}")
        
        # ランクとスタイルに応じた係数
        rank = selected_race.get("rank", "B")
        rank_multiplier = {"S": 1.5, "A": 1.0, "B": 0.7}.get(rank, 1.0)
        
        if investment_style == 'A：総合バランス投資':
            style_config = {"単勝": 0.2, "馬連": 0.25, "馬単": 0.15, "三連複": 0.25, "三連単": 0.15}
        else:
            style_config = {"単勝": 0, "馬連": 0.35, "馬単": 0.2, "三連複": 0.3, "三連単": 0.15}
        
        # 資金配分計算
        allocations = {}
        for bet_type, ratio in style_config.items():
            base_alloc = total_budget * ratio * rank_multiplier
            allocations[bet_type] = int(np.round(base_alloc / 100) * 100)
        
        # 表示
        alloc_cols = st.columns(5)
        for i, (bet_type, amount) in enumerate(allocations.items()):
            with alloc_cols[i]:
                st.metric(bet_type, f"¥{amount:,}")
        
        st.success(f"合計配分額: ¥{sum(allocations.values()):,}")
        
        st.markdown("---")
        
        # 買い目構成
        st.subheader("買い目構成案")
        
        horses = selected_race.get("horses", [])
        honmei = next((h for h in horses if h.get("印") == "◎"), None)
        taikou = next((h for h in horses if h.get("印") == "○"), None)
        tanpana = next((h for h in horses if h.get("印") == "▲"), None)
        himo1 = next((h for h in horses if h.get("印") == "△" and h != tanpana), None)
        himo2 = [h for h in horses if h.get("印") == "△"][-1] if len([h for h in horses if h.get("印") == "△"]) > 1 else None
        
        if honmei:
            st.write(f"**単勝**: {honmei.get('馬番', '')}番 ({honmei.get('推奨理由', '')})")
        
        if honmei and taikou:
            st.write(f"**馬連**: {honmei.get('馬番', '')} - {taikou.get('馬番', '')}")
            st.write(f"**馬単**: {honmei.get('馬番', '')} → {taikou.get('馬番', '')}")
        
        if honmei and taikou and tanpana:
            himo_nums = [h.get('馬番', '') for h in [taikou, tanpana, himo1, himo2] if h]
            st.write(f"**三連複 (軸1頭流し)**: {honmei.get('馬番', '')} - {','.join(map(str, himo_nums))}")
            
            # 三連単フォーメーション
            second_nums = [taikou.get('馬番', ''), tanpana.get('馬番', '')]
            third_nums = himo_nums
            st.write(f"**三連単 (フォーメーション)**: 1着: {honmei.get('馬番', '')} → 2着: {','.join(map(str, second_nums))} → 3着: {','.join(map(str, third_nums))}")
