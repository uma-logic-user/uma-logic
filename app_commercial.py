# app_commercial.py
# UMA-Logic Pro - 商用グレード完成版（6タブ構成 + 自動バックアップ機能）

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import shutil  # ファイルコピー用
from pathlib import Path

# --- ページ設定 (必ず最初に記述) ---
st.set_page_config(
    page_title="UMA-Logic Pro",
    page_icon="🐎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 定数設定 ---
DATA_DIR = Path("data")
BACKUP_DIR = DATA_DIR / "backups"
PREDICTIONS_PREFIX = "predictions_"
RESULTS_PREFIX = "results_"

# --- 自動バックアップ機能 ---
def create_self_backup():
    """
    起動時に自身のソースコードを data/backups/ にコピーして保存する
    """
    try:
        # ディレクトリがなければ作成
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        # 現在実行中のファイルのパスを取得
        current_file = Path(__file__).resolve()
        
        # タイムスタンプ付きのファイル名を生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"app_backup_{timestamp}.py"
        destination = BACKUP_DIR / backup_filename
        
        # コピー実行
        shutil.copy2(current_file, destination)
        
        # (デバッグ用) コンソールに出力
        print(f"Backup created: {destination}")
        
    except Exception as e:
        # バックアップ失敗時もアプリは止めず、ログだけ出す
        print(f"Backup failed: {e}")

# バックアップを実行
create_self_backup()

# --- ライブラリの安全なインポート ---
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    from st_aggrid import AgGrid, GridOptionsBuilder
    AGGRID_AVAILABLE = True
except ImportError:
    AGGRID_AVAILABLE = False

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
</style>
""", unsafe_allow_html=True)

# --- ヘルパー関数 ---

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
    except Exception:
        pass
    return sorted(dates, reverse=True) if dates else [datetime.now().date()]

def load_predictions(date) -> dict:
    """指定日の予想データを読み込む"""
    filename = f"{PREDICTIONS_PREFIX}{date.strftime('%Y%m%d')}.json"
    filepath = DATA_DIR / filename
    data = safe_load_json(filepath)
    if data:
        return data
    # フォールバック
    latest_path = DATA_DIR / "latest_predictions.json"
    return safe_load_json(latest_path) or {"races": [], "date": date.strftime("%Y-%m-%d")}

def load_results(date) -> dict:
    """指定日の結果データを読み込む"""
    filename = f"{RESULTS_PREFIX}{date.strftime('%Y%m%d')}.json"
    filepath = DATA_DIR / filename
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
    
    try:
        first = int(top3[0].get("馬番", 0))
        second = int(top3[1].get("馬番", 0))
        third = int(top3[2].get("馬番", 0))
    except (ValueError, TypeError):
        return hit_result
    
    horses = prediction.get("horses", [])
    
    # 馬番の取得ヘルパー
    def get_umaban(mark):
        h = next((h for h in horses if h.get("印") == mark), None)
        try:
            return int(h["馬番"]) if h else 0
        except:
            return 0

    honmei = get_umaban("◎")
    taikou = get_umaban("○")
    tanpana = get_umaban("▲")
    
    payouts = result.get("payouts", {})
    
    # 単勝
    if honmei == first:
        p = payouts.get("単勝", 0)
        hit_result["単勝"] = {"hit": True, "payout": p if isinstance(p, (int, float)) else 0}
    
    # 複勝 (簡易判定: 本命が3着以内)
    if honmei in [first, second, third]:
        fukusho = payouts.get("複勝", {})
        # 複勝は複数配当があるため、辞書かリストで来る想定
        payout = 0
        if isinstance(fukusho, dict):
            payout = fukusho.get(str(honmei), 0)
        elif isinstance(fukusho, list):
            # リストの場合は簡易的に平均などを取るか、本来は馬番でマッチングが必要
            payout = fukusho[0] if fukusho else 0 
        hit_result["複勝"] = {"hit": True, "payout": payout}
    
    # 馬連
    if {honmei, taikou} == {first, second}:
        p = payouts.get("馬連", 0)
        hit_result["馬連"] = {"hit": True, "payout": p if isinstance(p, (int, float)) else 0}
    
    # 三連複
    if {honmei, taikou, tanpana} == {first, second, third}:
        p = payouts.get("三連複", 0)
        hit_result["三連複"] = {"hit": True, "payout": p if isinstance(p, (int, float)) else 0}
    
    return hit_result

# --- サイドバー ---
st.sidebar.markdown("# 🐎 UMA-Logic Pro")
st.sidebar.markdown("---")

available_dates = get_available_dates()
selected_date = st.sidebar.selectbox(
    "日付選択",
    available_dates,
    format_func=lambda d: d.strftime("%Y/%m/%d (%a)")
)

# データ読み込み
predictions_data = load_predictions(selected_date)
results_data = load_results(selected_date)
history_data = load_history()

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

# --- メインコンテンツ ---
st.title("🐎 UMA-Logic Pro")

# 6タブ構成
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
                    
                    # 結果との照合
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
# タブ2: レース結果
# ========================================
with tab2:
    st.markdown(f"## 🏁 {selected_date.strftime('%Y年%m月%d日')} のレース結果")

    result_races = results_data.get("races", [])

    if not result_races:
        st.info("この日の結果データはまだありません。レース終了後に自動取得されます。")
    else:
        result_venues = sorted(set(r.get("venue", "不明") for r in result_races))
        selected_venue = st.selectbox("競馬場を選択", result_venues)
        
        venue_results = sorted(
            [r for r in result_races if r.get("venue") == selected_venue],
            key=lambda x: x.get("race_num", 0)
        )
        
        for race in venue_results:
            st.markdown(f"### {race.get('race_num', '')}R {race.get('race_name', '')}")

            top3 = race.get("top3", [])
            if top3:
                df = pd.DataFrame([
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
                st.dataframe(df, use_container_width=True, hide_index=True)
            
            payouts = race.get("payouts", {})
            if payouts:
                st.markdown("**💰 払戻金**")
                p_cols = st.columns(4)
                bet_types = ["単勝", "複勝", "馬連", "馬単", "ワイド", "三連複", "三連単", "枠連"]
                for i, bt in enumerate(bet_types):
                    if bt in payouts:
                        val = payouts[bt]
                        if isinstance(val, dict):
                            display = " / ".join([f"¥{v:,}" for v in val.values()])
                        elif isinstance(val, (int, float)) and val > 0:
                            display = f"¥{int(val):,}"
                        else:
                            display = "-"
                        p_cols[i % 4].metric(bt, display)
            
            st.markdown("---")

# ========================================
# タブ3: 的中実績
# ========================================
with tab3:
    st.markdown("## 🎉 的中実績")

    # 現在選択されている日のデータから的中を計算（簡易版）
    # 本来は全履歴データをスキャンするが、ここではデモとして現在選択日を使用
    all_hits = []
    
    # 選択されている日のレースでループ
    pred = predictions_data
    res = results_data
    
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
                        "日付": selected_date.strftime("%Y-%m-%d"),
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
        c1.metric("🎯 的中回数 (本日)", f"{hit_count}回")
        c2.metric("💰 累計配当 (本日)", f"¥{total_payout:,}")
        c3.metric("📊 平均配当", f"¥{total_payout // hit_count:,}" if hit_count > 0 else "¥0")
        
        st.markdown("---")
        st.markdown("### 的中一覧")
        st.dataframe(hit_df, use_container_width=True, hide_index=True)
        
        st.markdown("### 券種別集計")
        summary = hit_df.groupby("券種").agg({"配当": ["count", "sum", "mean"]}).round(0)
        summary.columns = ["回数", "合計", "平均"]
        st.dataframe(summary, use_container_width=True)
    else:
        st.info("本日分の的中データはまだありません。")

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
        
        # 予算配分計算（100円単位）
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
    backup_count = len(list(BACKUP_DIR.glob("*.py"))) if BACKUP_DIR.exists() else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("予想ファイル数", f"{pred_count}件")
    c2.metric("結果ファイル数", f"{res_count}件")
    c3.metric("バックアップ数", f"{backup_count}件")
    
    st.markdown("---")
    st.markdown("### 📋 システム情報")
    st.code(f"""
UMA-Logic Pro v2.0
Streamlit: {st.__version__}
Plotly: {'Available' if PLOTLY_AVAILABLE else 'Not Available'}
AgGrid: {'Available' if AGGRID_AVAILABLE else 'Not Available'}
データディレクトリ: {DATA_DIR.absolute()}
バックアップ先: {BACKUP_DIR.absolute()}
    """)
