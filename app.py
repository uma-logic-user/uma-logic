"""
UMA-Logic 商用グレード完成版 v14.0
土日別タブ・全レース結果・的中実績レポート対応
"""
import streamlit as st
import json
import os

st.set_page_config(page_title="UMA-Logic AI競馬予想", page_icon="🏇", layout="wide")

st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: bold; text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; margin-bottom: 1rem; }
    .rank-s { background: #ee5a24; color: white; padding: 0.2rem 0.6rem; border-radius: 15px; font-weight: bold; }
    .rank-a { background: #ff9f43; color: white; padding: 0.2rem 0.6rem; border-radius: 15px; font-weight: bold; }
    .rank-b { background: #2e86de; color: white; padding: 0.2rem 0.6rem; border-radius: 15px; font-weight: bold; }
    .stat-card { background: white; padding: 1rem; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }
    .profit-positive { color: #27ae60; font-weight: bold; }
    .profit-negative { color: #e74c3c; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def load_json(filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return None

st.sidebar.markdown("## ⚙️ 設定")
budget = st.sidebar.slider("💰 軍資金", 1000, 50000, 10000, 1000)
style = st.sidebar.radio("📊 投資スタイル", ["総合バランス投資", "連勝複式・一撃Ver"])

st.markdown('<div class="main-header">🏇 UMA-Logic AI競馬予想システム</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎯 土曜予想", "🎯 日曜予想", "🏆 WIN5", "📋 結果", "📊 実績"])

def render_predictions(data, date_label):
    if not data or "races" not in data:
        st.info(f"{date_label}の予想データがありません")
        return
    races = data["races"]
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("総レース", f"{len(races)}R")
    with col2: st.metric("Sランク", f"{sum(1 for r in races if r.get('rank')=='S')}R")
    with col3: st.metric("Aランク", f"{sum(1 for r in races if r.get('rank')=='A')}R")
    with col4: st.metric("WIN5対象", f"{sum(1 for r in races if r.get('is_win5'))}R")
    st.markdown("---")
    venues = {}
    for race in races:
        v = race.get("venue", "不明")
        if v not in venues: venues[v] = []
        venues[v].append(race)
    for venue_name, venue_races in venues.items():
        st.markdown(f"### 📍 {venue_name}")
        for race in sorted(venue_races, key=lambda x: x.get("race_num", 0)):
            rank = race.get("rank", "B")
            rnum = race.get("race_num", 0)
            rname = race.get("race_name", "")
            is_win5 = race.get("is_win5", False)
            honmei = race.get("honmei", {})
            hnum = honmei.get("umaban", honmei.get("number", 0))
            hname = honmei.get("horse_name", honmei.get("name", ""))
            rank_badge = {"S": "🔥S", "A": "⭐A", "B": "📊B"}.get(rank, "B")
            win5_mark = " 🎯WIN5" if is_win5 else ""
            with st.expander(f"**{venue_name}{rnum}R** [{rank_badge}] ◎{hnum}番 {hname}{win5_mark}", expanded=(rank=="S")):
                st.markdown(f"**{rname}** | 発走: {race.get('start_time', '')} | {race.get('course', '')}")
                st.markdown("#### 🐴 推奨馬")
                horses = race.get("horses", [])
                marks = ["◎", "○", "▲", "△", "△"]
                for i, h in enumerate(horses[:5]):
                    m = marks[i] if i < len(marks) else "△"
                    st.markdown(f"{m} **{h.get('umaban', h.get('number', 0))}番** {h.get('horse_name', h.get('name', ''))} | オッズ: {h.get('odds', 0)} | UMA指数: {h.get('uma_index', 0)}")
                st.markdown("#### 💰 買い目")
                bets = race.get("bets", {})
                st.markdown(f"単勝: {bets.get('tansho_display', '-')} | 馬連: {bets.get('umaren_display', '-')} | 三連複: {bets.get('sanrenpuku_display', '-')}")

with tab1:
    st.markdown("## 📅 1月31日（土）の予想")
    render_predictions(load_json("data/predictions_20260131.json"), "土曜日")

with tab2:
    st.markdown("## 📅 2月1日（日）の予想")
    render_predictions(load_json("data/predictions_20260201.json"), "日曜日")

with tab3:
    st.markdown("## 🏆 WIN5予想")
    data = load_json("data/predictions_20260201.json")
    if data and "win5" in data:
        win5 = data["win5"]
        st.markdown("### 📋 対象レース")
        for i, r in enumerate(win5.get("target_races", []), 1):
            st.markdown(f"{i}. {r.get('venue', '')} {r.get('race_num', '')}R {r.get('race_name', '')}")
        st.markdown("---")
        plans = win5.get("plans", {})
        cols = st.columns(3)
        for col, (key, name) in zip(cols, [("solid", "🛡️堅実"), ("balanced", "⚖️バランス"), ("high_return", "🚀高配当")]):
            with col:
                p = plans.get(key, {})
                st.markdown(f"#### {name}")
                st.metric("購入金額", f"¥{p.get('cost', 0):,}")
                for s in p.get("selections", []):
                    st.markdown(f"- {s.get('venue', '')} {s.get('race_num', '')}R: **{', '.join(map(str, s.get('horses', [])))}番**")
    else:
        st.info("WIN5データなし（日曜のみ）")

with tab4:
    st.markdown("## 📋 全レース結果")
    results = load_json("data/results_20260131.json")
    if results and "results" in results:
        summary = results.get("summary", {})
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("本命的中", f"{summary.get('honmei_hits', 0)}/{summary.get('total_predictions', 0)}")
        with col2: st.metric("単勝的中", f"{summary.get('tansho_hits', 0)}回")
        with col3: st.metric("収支", f"¥{summary.get('profit', 0):+,}")
        with col4: st.metric("回収率", f"{summary.get('roi', 0):.1f}%")
        for r in results["results"]:
            with st.expander(f"{r.get('venue', '')}{r.get('race_num', '')}R {r.get('race_name', '')}"):
                res = r.get("result", {})
                st.markdown(f"1着: {res.get('1st', {}).get('umaban', '')}番 {res.get('1st', {}).get('horse_name', '')}")
                payouts = r.get("payouts", {})
                st.markdown(f"単勝: ¥{payouts.get('tansho', {}).get('payout', 0):,} | 馬連: ¥{payouts.get('umaren', {}).get('payout', 0):,}")
    else:
        st.info("結果データなし")

with tab5:
    st.markdown("## 📊 的中実績レポート")
    history = load_json("data/history.json")
    if history and isinstance(history, dict):
        total = history.get("total_stats", {})
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("累計収支", f"¥{total.get('profit', 0):+,}")
        with col2: st.metric("回収率", f"{total.get('roi', 0):.1f}%")
        with col3: st.metric("総投資", f"¥{total.get('total_investment', 0):,}")
        with col4: st.metric("総払戻", f"¥{total.get('total_return', 0):,}")
        st.markdown("---")
        st.markdown("### 🎫 券種別成績")
        by_ticket = history.get("by_ticket_type", {})
        for key, name in [("tansho", "単勝"), ("umaren", "馬連"), ("umatan", "馬単"), ("sanrenpuku", "三連複"), ("sanrentan", "三連単")]:
            d = by_ticket.get(key, {})
            st.markdown(f"**{name}**: 回収率 {d.get('roi', 0):.1f}% | 的中 {d.get('hits', 0)}/{d.get('races', 0)}")
        st.markdown("---")
        st.markdown("### 📝 的中ログ")
        for hit in history.get("hit_log", [])[:10]:
            st.markdown(f"- {hit.get('date', '')} {hit.get('race', '')} | {hit.get('ticket', '')} | ¥{hit.get('payout', 0):,}")
    else:
        st.info("実績データなし")

st.markdown("---")
st.caption("UMA-Logic v14.0 | データは毎週自動更新 | 投資は自己責任で")
