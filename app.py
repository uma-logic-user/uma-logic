#!/usr/bin/env python3
"""
UMA-Logic シンプル版アプリ
"""
import json
import streamlit as st
from pathlib import Path
import pandas as pd

# ページ設定
st.set_page_config(
    page_title="🏇 UMA-Logic",
    page_icon="🏇",
    layout="wide"
)

# タイトル
st.title("🏇 UMA-Logic | AI競馬予想システム")
st.caption("回収率重視の科学的予想")

# データ読み込み
DATA_DIR = Path(__file__).parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"
STATS_FILE = DATA_DIR / "stats.json"

# 履歴読み込み
if HISTORY_FILE.exists():
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
else:
    history = []

# 統計読み込み
if STATS_FILE.exists():
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        stats = json.load(f)
else:
    stats = {
        "total_profit": 0,
        "recovery_rate": 0,
        "hit_rate": 0,
        "hit_count": 0,
        "total_races": 0
    }

# サイドバー
st.sidebar.header("📊 累計収支")
st.sidebar.metric("損益", f"{stats.get('total_profit', 0):+,}円")
st.sidebar.metric("回収率", f"{stats.get('recovery_rate', 0)}%")
st.sidebar.metric("的中率", f"{stats.get('hit_rate', 0)}%")

# メインエリア
if not history:
    st.warning("📭 まだレースデータがありません")
    st.info("以下のコマンドでデータを取得してください:")
    st.code("python scripts/fetch_race_data_enhanced.py", language="bash")
else:
    st.success(f"✅ {len(history)}件のレースデータを読み込みました")
    
    # タブ作成
    tab1, tab2 = st.tabs(["📅 最新の予想", "📊 全レース一覧"])
    
    with tab1:
        st.subheader("最新5レースの予想")
        
        # 最新5レースを表示
        for race in history[:5]:
            with st.expander(
                f"🏁 {race.get('venue', '不明')} 第{race.get('race_num', '?')}R - {race.get('race_name', '不明')}",
                expanded=True
            ):
                # 本命馬情報
                honmei = race.get("honmei", {})
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("本命馬", f"◎{honmei.get('umaban', '?')}番")
                    st.caption(honmei.get('horse_name', '不明'))
                
                with col2:
                    st.metric("UMA指数", honmei.get('uma_index', 0))
                    rank = honmei.get('rank', 'C')
                    if rank == 'S':
                        st.error(f"ランク: {rank} 🔥")
                    elif rank == 'A':
                        st.warning(f"ランク: {rank}")
                    else:
                        st.info(f"ランク: {rank}")
                
                with col3:
                    confidence = honmei.get('confidence', 0)
                    st.metric("信頼度", f"{confidence * 100:.0f}%")
                
                with col4:
                    expected = honmei.get('expected_value', 0)
                    st.metric("期待値", f"{expected:.2f}")
                    if expected >= 1.2:
                        st.success("期待値◎")
                    elif expected >= 1.0:
                        st.warning("期待値○")
                    else:
                        st.info("期待値△")
                
                # レース情報
                st.caption(
                    f"📍 {race.get('surface', '不明')}{race.get('distance', '不明')} | "
                    f"天候: {race.get('weather', '晴')} | "
                    f"馬場: {race.get('track_condition', '良')}"
                )
                
                # 結果表示
                result = race.get("result")
                if result:
                    hits = result.get("hits", {})
                    profit = result.get("profit", 0)
                    
                    hit_list = [k for k, v in hits.items() if v]
                    
                    if hit_list:
                        st.success(f"✅ 的中！ {', '.join(hit_list)} → {profit:+,}円")
                    else:
                        st.error(f"❌ 不的中 → {profit:,}円")
                
                # 買い目表示
                st.markdown("**🎯 推奨買い目:**")
                bets = race.get("bets", {})
                
                bet_text = []
                if "単勝" in bets and bets["単勝"]:
                    bet_text.append(f"単勝: {', '.join(map(str, bets['単勝']))}番")
                if "ワイド" in bets and bets["ワイド"]:
                    wide_list = [f"{b[0]}-{b[1]}" for b in bets["ワイド"][:3]]
                    bet_text.append(f"ワイド: {', '.join(wide_list)}")
                if "馬連" in bets and bets["馬連"]:
                    umaren_list = [f"{b[0]}-{b[1]}" for b in bets["馬連"][:3]]
                    bet_text.append(f"馬連: {', '.join(umaren_list)}")
                
                if bet_text:
                    for text in bet_text:
                        st.write(f"- {text}")
                
                st.divider()
    
    with tab2:
        st.subheader("全レース一覧")
        
        # データフレーム作成
        df_data = []
        for race in history:
            honmei = race.get("honmei", {})
            result = race.get("result")
            
            df_data.append({
                "日付": race.get("date", ""),
                "会場": race.get("venue", ""),
                "R": race.get("race_num", ""),
                "レース名": race.get("race_name", ""),
                "本命": f"{honmei.get('umaban', '?')}番",
                "馬名": honmei.get("horse_name", ""),
                "指数": honmei.get("uma_index", 0),
                "ランク": honmei.get("rank", ""),
                "期待値": f"{honmei.get('expected_value', 0):.2f}",
                "結果": "的中" if (result and any(result.get("hits", {}).values())) else ("不的中" if result else "未確定"),
                "収支": f"{result.get('profit', 0):+,}円" if result else "-"
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

# フッター
st.divider()
st.caption("💡 土日 7:00に予想取得 / 17:00に結果更新")