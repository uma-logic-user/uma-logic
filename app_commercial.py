# app_commercial.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from datetime import datetime, timedelta

# --- ページ設定と基本スタイル ---
st.set_page_config(
    page_title="UMA-Logic Pro",
    page_icon="🐎",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_css():
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap' );

        html, body, [class*="st-"], [class*="css-"] {{
            font-family: 'Noto Sans JP', sans-serif;
            background-color: #1A1A2E; /* 濃紺 */
            color: #FFFFFF;
        }}

        /* サイドバー */
        .css-1d391kg {{
            background-color: #1A1A2E;
            border-right: 1px solid #3c3c5a;
        }}

        /* メインコンテンツ */
        .main .block-container {{
            padding-top: 2rem;
        }}

        /* 見出し */
        h1, h2, h3 {{
            color: #F6C953; /* ゴールド */
        }}

        /* Sランクのパルスアニメーション */
        @keyframes pulse {{
            0% {{
                box-shadow: 0 0 0 0 rgba(246, 201, 83, 0.7);
            }}
            70% {{
                box-shadow: 0 0 0 15px rgba(246, 201, 83, 0);
            }}
            100% {{
                box-shadow: 0 0 0 0 rgba(246, 201, 83, 0);
            }}
        }}

        .pulse-s-rank {{
            animation: pulse 2s infinite;
            border-radius: 10px;
        }}

        /* 金バッジ */
        .gold-badge {{
            display: inline-block;
            background-color: #F6C953;
            color: #1A1A2E;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 0.8em;
            margin-left: 10px;
        }}

        /* プログレスバーのカスタム */
        .st-emotion-cache-10y5sf6 {{
            background-color: #3c3c5a;
        }}
        .st-emotion-cache-p5msec {{
            background-color: #F6C953;
        }}

    </style>
    """, unsafe_allow_html=True)

load_css()

# --- ダミーデータ生成 --- 
# 本来は各スクリプトから取得・計算されるデータ

def generate_dummy_predictions():
    venues = ["東京", "京都", "小倉"]
    races = []
    for venue in venues:
        for i in range(1, 13):
            race_rank = np.random.choice(['S', 'A', 'B'], p=[0.1, 0.4, 0.5])
            horses = []
            for j in range(1, 19):
                uma_index = np.random.randint(40, 100)
                expected_value = np.random.uniform(0.7, 1.8)
                horses.append({
                    "馬番": j,
                    "馬名": f"ダミーホース{j}",
                    "UMA指数": uma_index,
                    "推定勝率": uma_index / 200,
                    "単勝オッズ": np.random.uniform(1.5, 50.0),
                    "期待値": expected_value,
                    "推奨理由": np.random.choice(["血統背景あり", "追い切り抜群", "展開有利", "騎手得意コース"])
                })
            
            # UMA指数でソートして印を付ける
            sorted_horses = sorted(horses, key=lambda x: x['UMA指数'], reverse=True)
            for k, horse in enumerate(sorted_horses):
                if k == 0: horse['印'] = '◎'
                elif k == 1: horse['印'] = '○'
                elif k == 2: horse['印'] = '▲'
                elif k == 3: horse['印'] = '△'
                elif k == 4: horse['印'] = '△'
                else: horse['印'] = ''

            races.append({
                "日付": datetime.now().strftime("%Y-%m-%d"),
                "会場": venue,
                "レース名": f"{i}R",
                "ランク": race_rank,
                "馬リスト": sorted_horses
            })
    return races


def generate_dummy_history():
    data = []
    for i in range(100):
        date = (datetime.now() - timedelta(days=np.random.randint(1, 60))).strftime("%Y-%m-%d")
        bet_type = np.random.choice(["単勝", "馬連", "三連複", "三連単"])
        payout = np.random.randint(500, 50000) if np.random.rand() > 0.8 else 0
        investment = np.random.randint(100, 5000)
        data.append({
            "日付": date,
            "レース名": f"{np.random.choice(['東京', '京都', '阪神'])}{np.random.randint(1,13)}R",
            "的中券種": bet_type if payout > 0 else "-",
            "投資額": investment,
            "的中配当金": payout
        })
    return pd.DataFrame(data)

# --- サイドバー --- 
st.sidebar.title("U M A - L O G I C  P R O")
st.sidebar.markdown("--- ")

total_budget = st.sidebar.slider(
    "🎯 総予算設定",
    min_value=1000, 
    max_value=100000, 
    value=10000, 
    step=1000,
    format="¥%d"
)

investment_style = st.sidebar.radio(
    "💰 投資スタイル",
    ('A：総合バランス投資', 'B：連勝複式・一撃Ver'),
    captions=["単勝から三連単まで幅広く配分", "馬連/馬単/三連複/三連単に集中"]    
)

st.sidebar.markdown("--- ")
st.sidebar.info("これは商用グレードのデモアプリです。データはダミーであり、実際の投資を推奨するものではありません。")

# --- メインコンテンツ --- 

# タブ設定
tab1, tab2, tab3 = st.tabs(["🎯 今日の予想", "📈 的中実績レポート", "💰 資金配分シミュレーター"])

# --- タブ1: 今日の予想 ---
with tab1:
    st.header(f"{datetime.now().strftime('%Y年%m月%d日')} のAI予想")
    
    dummy_races = generate_dummy_predictions()
    venues = sorted(list(set([r['会場'] for r in dummy_races])))
    
    selected_venue = st.selectbox("競馬場を選択", venues)
    
    races_in_venue = [r for r in dummy_races if r['会場'] == selected_venue]

    cols = st.columns(3) # 3カラムグリッド
    col_idx = 0

    for race in races_in_venue:
        container_class = "pulse-s-rank" if race['ランク'] == 'S' else ""
        with cols[col_idx].container():
            st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True)
            
            # レースヘッダー
            honmei = next((h for h in race['馬リスト'] if h['印'] == '◎'), None)
            title = f"**{race['会場']}{race['レース名']}** <span style='color:#F6C953;'>[{race['ランク']}]</span> ◎ {honmei['馬番']} {honmei['馬名']}"
            st.markdown(title, unsafe_allow_html=True)

            with st.expander("詳細を見る", expanded=(race['ランク'] == 'S')):
                for horse in race['馬リスト'][:5]: # 上位5頭を表示
                    st.markdown(f"--- ")
                    horse_info = f"**{horse['印']} {horse['馬番']} {horse['馬名']}**"
                    if horse['期待値'] >= 1.2:
                        horse_info += f"<span class='gold-badge'>期待値 {horse['期待値']:.2f}</span>"
                    st.markdown(horse_info, unsafe_allow_html=True)
                    
                    # UMA指数プログレスバー
                    st.progress(horse['UMA指数'] / 100, text=f"UMA指数: {horse['UMA指数']}")
                    st.caption(f"単勝: {horse['単勝オッズ']:.1f}倍 / 推定勝率: {horse['推定勝率']:.1%} / 推奨理由: {horse['推奨理由']}")
            
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("&nbsp;") # スペーサー

        col_idx = (col_idx + 1) % 3

# --- タブ2: 的中実績レポート ---
with tab2:
    st.header("📈 的中実績レポート")
    history_df = generate_dummy_history()

    # --- リアルタイム収支メーター ---
    total_payout = history_df['的中配当金'].sum()
    total_investment = history_df['投資額'].sum()
    current_balance = total_payout - total_investment
    recovery_rate = (total_payout / total_investment * 100) if total_investment > 0 else 0

    meter_cols = st.columns(3)
    with meter_cols[0]:
        fig_meter = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = recovery_rate,
            title = {'text': "累計回収率", 'font': {'size': 20}},
            delta = {'reference': 100, 'increasing': {'color': "#F6C953"}, 'decreasing': {'color': "#3c3c5a"}},
            gauge = {
                'axis': {'range': [None, 200], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': "#F6C953"},
                'bgcolor': "#1A1A2E",
                'borderwidth': 2,
                'bordercolor': "#3c3c5a",
                'steps' : [
                    {'range': [0, 80], 'color': '#3c3c5a'},
                    {'range': [80, 120], 'color': '#5a5a7a'}
                ],
                'threshold' : {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 100}
            }
        ))
        fig_meter.update_layout(paper_bgcolor = "#1A1A2E", font = {'color': "white", 'family': "Noto Sans JP"})
        st.plotly_chart(fig_meter, use_container_width=True)
    
    with meter_cols[1]:
        st.metric("累計純損益", f"¥{current_balance:,}", delta=f"{current_balance - (history_df.iloc[-1]['的中配当金'] - history_df.iloc[-1]['投資額']):,}")
    with meter_cols[2]:
        st.metric("総投資額", f"¥{total_investment:,}")

    # --- 週次/月次推移グラフ ---
    history_df['日付'] = pd.to_datetime(history_df['日付'])
    history_df['純損益'] = history_df['的中配当金'] - history_df['投資額']
    
    # 月次集計
    monthly_summary = history_df.set_index('日付').resample('M').sum()
    monthly_summary['回収率'] = (monthly_summary['的中配当金'] / monthly_summary['投資額'] * 100).fillna(0)
    monthly_summary['累計純損益'] = monthly_summary['純損益'].cumsum()

    fig_trend = px.bar(monthly_summary, y='純損益', title='月次純損益 推移グラフ', labels={'純損益':'純損益 (円)'})
    fig_trend.add_scatter(y=monthly_summary['累計純損益'], mode='lines', name='累計純損益', yaxis='y2')
    fig_trend.update_layout(
        paper_bgcolor="#1A1A2E", 
        plot_bgcolor="#1A1A2E",
        font_color="white",
        yaxis2=dict(title='累計純損益 (円)', overlaying='y', side='right'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    # --- AgGrid 的中実績テーブル ---
    st.subheader("的中実績一覧")
    gb = GridOptionsBuilder.from_dataframe(history_df[['日付', 'レース名', '的中券種', '投資額', '的中配当金']])
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc='sum', editable=False)
    gb.configure_column("日付", type=["dateColumnFilter","customFilter"], custom_format_string='yyyy-MM-dd', pivot=True)
    
    # 数値のフォーマット
    jscode = JsCode("""
    function(params) {
        if (params.value === null || params.value === undefined) {
            return '';
        }
        return '¥' + params.value.toLocaleString();
    }
    """)
    gb.configure_column("投資額", valueFormatter=jscode)
    gb.configure_column("的中配当金", valueFormatter=jscode)

    gridOptions = gb.build()
    AgGrid(
        history_df, 
        gridOptions=gridOptions, 
        enable_enterprise_modules=False, 
        height=400, 
        width='100%',
        theme='streamlit-dark',
        reload_data=True
    )

# --- タブ3: 資金配分シミュレーター ---
with tab3:
    st.header("💰 資金配分シミュレーター")
    st.info("この機能は、選択したレースと投資スタイルに基づき、総予算を各券種にどう配分するかのシミュレーションを行います。")

    # レース選択
    race_options = [f"{r['会場']}{r['レース名']}" for r in dummy_races]
    selected_race_str = st.selectbox("シミュレーション対象レースを選択", race_options)
    selected_race_obj = next((r for r in dummy_races if f"{r['会場']}{r['レース名']}" == selected_race_str), None)

    if selected_race_obj:
        st.subheader(f"シミュレーション結果： {selected_race_str} ({selected_race_obj['ランク']}ランク)")
        
        # ランクとスタイルに応じた係数
        rank_multiplier = {'S': 1.5, 'A': 1.0, 'B': 0.7}[selected_race_obj['ランク']]
        style_config = {
            'A：総合バランス投資': {'単勝': 0.2, '馬連': 0.3, '馬単': 0.1, '三連複': 0.3, '三連単': 0.1},
            'B：連勝複式・一撃Ver': {'単勝': 0, '馬連': 0.4, '馬単': 0.2, '三連複': 0.3, '三連単': 0.1}
        }[investment_style]

        # 資金配分計算
        allocations = {}
        total_ratio = sum(style_config.values())
        for bet_type, ratio in style_config.items():
            base_alloc = (total_budget * ratio / total_ratio) * rank_multiplier
            # 100円単位に丸める
            allocations[bet_type] = int(np.round(base_alloc / 100) * 100)

        # 表示
        sim_cols = st.columns(5)
        bet_types = ['単勝', '馬連', '馬単', '三連複', '三連単']
        for i, bet_type in enumerate(bet_types):
            with sim_cols[i]:
                st.metric(bet_type, f"¥{allocations[bet_type]:,}")
        
        st.success(f"合計配分額: ¥{sum(allocations.values()):,}")

        st.markdown("--- ")
        st.write("**買い目構成案**")
        # ダミーの買い目表示
        honmei = next((h for h in selected_race_obj['馬リスト'] if h['印'] == '◎'), None)
        taikou = next((h for h in selected_race_obj['馬リスト'] if h['印'] == '○'), None)
        tanana = next((h for h in selected_race_obj['馬リスト'] if h['印'] == '▲'), None)

        st.write(f"- **単勝**: {honmei['馬番']} ({honmei['推奨理由']})")
        st.write(f"- **馬連**: {honmei['馬番']} - {taikou['馬番']}")
        st.write(f"- **三連複 (軸1頭流し)**: {honmei['馬番']} - {taikou['馬番']},{tanana['馬番']},{selected_race_obj['馬リスト'][3]['馬番']},{selected_race_obj['馬リスト'][4]['馬番']}")
        st.write(f"- **三連単 (フォーメーション)**: 1着: {honmei['馬番']} → 2着: {taikou['馬番']},{tanana['馬番']} → 3着: {taikou['馬番']},{tanana['馬番']},{selected_race_obj['馬リスト'][3]['馬番']},{selected_race_obj['馬リスト'][4]['馬番']}")

