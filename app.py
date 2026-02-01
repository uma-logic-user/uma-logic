#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UMA-Logic 商用グレード完成版 app.py v14.0
- 今週の予想タブ
- WIN5専用タブ
- 全レース結果タブ
- 的中実績レポートタブ
- 動的資金配分（総合バランス/一撃Ver）
- スマホ最適化UI
"""

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

# ページ設定
st.set_page_config(
    page_title="UMA-Logic 競馬AI予想",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS（スマホ最適化）
st.markdown("""
<style>
    /* スマホ最適化 */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem 0.5rem;
        }
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.2rem !important; }
        h3 { font-size: 1rem !important; }
    }
    
    /* ランクバッジ */
    .rank-s { 
        background: linear-gradient(135deg, #ff6b6b, #ee5a5a);
        color: white; padding: 4px 12px; border-radius: 20px;
        font-weight: bold; font-size: 0.9rem;
    }
    .rank-a { 
        background: linear-gradient(135deg, #ffd93d, #f0c000);
        color: #333; padding: 4px 12px; border-radius: 20px;
        font-weight: bold; font-size: 0.9rem;
    }
    .rank-b { 
        background: linear-gradient(135deg, #6bcb77, #4caf50);
        color: white; padding: 4px 12px; border-radius: 20px;
        font-weight: bold; font-size: 0.9rem;
    }
    
    /* カード */
    .race-card {
        background: white;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    /* 本命馬ハイライト */
    .honmei-highlight {
        background: linear-gradient(135deg, #fff3cd, #ffeeba);
        border-left: 4px solid #ffc107;
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
    }
    
    /* 的中バッジ */
    .hit-badge {
        background: #28a745;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    
    /* 統計カード */
    .stat-card {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin: 8px;
    }
    .stat-value {
        font-size: 2rem;
        font-weight: bold;
    }
    .stat-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
</style>
""", unsafe_allow_html=True)


def load_predictions():
    """予想データを読み込み"""
    try:
        path = Path(__file__).parent / "data" / "latest_predictions.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        st.error(f"予想データ読み込みエラー: {e}")
    return None


def load_history():
    """履歴データを読み込み"""
    try:
        path = Path(__file__).parent / "data" / "history.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        pass
    return []


def load_stats():
    """統計データを読み込み"""
    try:
        path = Path(__file__).parent / "data" / "stats.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        pass
    return {
        "total_bets": 0,
        "total_wins": 0,
        "total_payout": 0,
        "total_investment": 0
    }


def get_rank_badge(rank):
    """ランクバッジのHTML"""
    if rank == "S":
        return '<span class="rank-s">🔥 Sランク</span>'
    elif rank == "A":
        return '<span class="rank-a">⭐ Aランク</span>'
    else:
        return '<span class="rank-b">Bランク</span>'


def render_predictions_tab(data, budget, style):
    """予想タブを描画"""
    st.header("🎯 今週の予想")
    
    if not data:
        st.warning("予想データがありません")
        return
    
    races = data.get("races", [])
    if not races:
        st.warning("レースデータがありません")
        return
    
    # 生成日時
    st.caption(f"📅 生成日時: {data.get('generated_at', '不明')}")
    
    # ランクサマリー
    rank_summary = data.get("rank_summary", {})
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("総レース数", f"{len(races)}R")
    with col2:
        st.metric("🔥 Sランク", f"{rank_summary.get('S', 0)}R")
    with col3:
        st.metric("⭐ Aランク", f"{rank_summary.get('A', 0)}R")
    with col4:
        st.metric("Bランク", f"{rank_summary.get('B', 0)}R")
    
    st.divider()
    
    # 会場ごとにグループ化
    venues = {}
    for race in races:
        venue = race.get("venue", "不明")
        if venue not in venues:
            venues[venue] = []
        venues[venue].append(race)
    
    # 会場タブ
    if venues:
        venue_tabs = st.tabs(list(venues.keys()))
        
        for tab, (venue_name, venue_races) in zip(venue_tabs, venues.items()):
            with tab:
                # レース番号順にソート
                venue_races.sort(key=lambda x: x.get("race_num", 0))
                
                for race in venue_races:
                    render_race_card(race, budget, style)


def render_race_card(race, budget, style):
    """レースカードを描画"""
    rank = race.get("rank", "B")
    race_num = race.get("race_num", 0)
    race_name = race.get("race_name", "")
    venue = race.get("venue", "")
    
    # 本命馬情報
    honmei = race.get("honmei", {})
    honmei_name = honmei.get("horse_name", "未定")
    honmei_umaban = honmei.get("umaban", 0)
    honmei_mark = honmei.get("mark", "◎")
    
    # WIN5対象
    is_win5 = race.get("is_win5", False)
    win5_badge = " 🎯WIN5" if is_win5 else ""
    
    # タイトル作成
    rank_emoji = {"S": "🔥", "A": "⭐", "B": "📌"}.get(rank, "📌")
    title = f"{venue} {race_num}R [{rank}]{rank_emoji} {honmei_mark}{honmei_umaban}番 {honmei_name}{win5_badge}"
    
    # Sランクは自動展開
    expanded = rank == "S"
    
    with st.expander(title, expanded=expanded):
        st.markdown(f"**{race_name}**")
        
        # 本命馬ハイライト
        if honmei:
            uma_index = honmei.get("uma_index", 0)
            reasons = honmei.get("reasons", [])
            horse_type = honmei.get("horse_type", "標準")
            
            st.markdown(f"""
            <div class="honmei-highlight">
                <strong>◎ 本命: {honmei_umaban}番 {honmei_name}</strong><br>
                UMA指数: <strong>{uma_index}</strong> | タイプ: {horse_type}<br>
                推奨理由: {', '.join(reasons) if reasons else '総合評価'}
            </div>
            """, unsafe_allow_html=True)
        
        # 推奨馬一覧（上位5頭）
        horses = race.get("horses", [])
        if horses:
            sorted_horses = sorted(horses, key=lambda x: x.get("uma_index", 0), reverse=True)[:5]
            
            st.markdown("**📋 推奨馬（上位5頭）**")
            
            for i, horse in enumerate(sorted_horses):
                mark = ["◎", "○", "▲", "△", "△"][i]
                umaban = horse.get("umaban", 0)
                name = horse.get("horse_name", "")
                jockey = horse.get("jockey", "")
                uma_index = horse.get("uma_index", 0)
                odds = horse.get("odds", 0)
                
                st.markdown(f"{mark} **{umaban}番** {name} ({jockey}) - UMA指数:{uma_index} オッズ:{odds:.1f}")
        
        # 買い目
        bets = race.get("bets", {})
        if bets:
            st.markdown("**🎫 買い目（馬番表示）**")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"- 単勝: **{bets.get('tansho_display', '-')}**")
                st.markdown(f"- 馬連: **{bets.get('umaren_display', '-')}**")
                st.markdown(f"- 馬単: **{bets.get('umatan_display', '-')}**")
            with col2:
                st.markdown(f"- 三連複: **{bets.get('sanrenpuku_display', '-')}**")
                formation = bets.get("sanrentan_formation", {})
                if formation:
                    st.markdown(f"- 三連単: **{formation.get('display', '-')}**")
                    st.caption(f"  ({formation.get('point_count', 0)}点)")
        
        # 資金配分
        st.markdown("**💰 推奨資金配分**")
        
        if style == "総合バランス投資":
            allocation = race.get("budget_balanced", {})
        else:
            allocation = race.get("budget_aggressive", {})
        
        if allocation:
            # 予算に応じて調整
            ratio = budget / 10000
            
            cols = st.columns(5)
            bet_names = ["単勝", "馬連", "馬単", "三連複", "三連単"]
            bet_keys = ["tansho", "umaren", "umatan", "sanrenpuku", "sanrentan"]
            
            for col, name, key in zip(cols, bet_names, bet_keys):
                amount = int(allocation.get(key, 0) * ratio / 100) * 100
                with col:
                    st.metric(name, f"¥{amount:,}")


def render_win5_tab(data):
    """WIN5タブを描画"""
    st.header("🎯 WIN5予想")
    
    if not data:
        st.warning("予想データがありません")
        return
    
    win5 = data.get("win5_strategies", {})
    
    if not win5.get("is_valid", False):
        st.info(win5.get("message", "WIN5は日曜日のみ発売です"))
        return
    
    st.success(f"WIN5対象レース: {win5.get('target_race_count', 0)}レース")
    
    # 3つのプラン
    plans = ["conservative", "balanced", "aggressive"]
    plan_tabs = st.tabs(["🛡️ 堅実プラン", "⚖️ バランスプラン", "🚀 高配当プラン"])
    
    for tab, plan_key in zip(plan_tabs, plans):
        with tab:
            plan = win5.get(plan_key, {})
            
            st.markdown(f"**{plan.get('name', '')}**")
            st.caption(plan.get("description", ""))
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("購入点数", f"{plan.get('point_count', 0)}点")
            with col2:
                st.metric("購入金額", f"¥{plan.get('estimated_cost', 0):,}")
            with col3:
                st.metric("的中確率目安", plan.get("hit_probability", "-"))
            
            st.divider()
            
            # 各レースの選択馬
            selections = plan.get("selections", [])
            for i, sel in enumerate(selections):
                venue = sel.get("venue", "")
                race_num = sel.get("race_num", 0)
                race_name = sel.get("race_name", "")
                horses = sel.get("horses", [])
                
                horse_str = " / ".join([f"{h.get('umaban', 0)}番{h.get('name', '')}" for h in horses])
                
                st.markdown(f"**第{i+1}レース**: {venue}{race_num}R {race_name}")
                st.markdown(f"→ {horse_str}")


def render_results_tab(history):
    """全レース結果タブを描画"""
    st.header("📊 全レース結果")
    
    if not history:
        st.info("まだ結果データがありません。レース終了後に自動更新されます。")
        return
    
    # 日付でソート（新しい順）
    sorted_history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)
    
    for day in sorted_history:
        date = day.get("date", "")
        results = day.get("results", [])
        
        with st.expander(f"📅 {date} ({len(results)}レース)", expanded=(day == sorted_history[0])):
            if not results:
                st.caption("結果データなし")
                continue
            
            for result in results:
                venue = result.get("venue", "")
                race_num = result.get("race_num", 0)
                race_name = result.get("race_name", "")
                
                first = result.get("result_1st", {})
                second = result.get("result_2nd", {})
                third = result.get("result_3rd", {})
                
                payouts = result.get("payouts", {})
                hits = result.get("hits", {})
                
                # 的中があればハイライト
                has_hit = any(h.get("is_hit", False) for h in hits.values())
                
                st.markdown(f"**{venue} {race_num}R {race_name}**")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"🥇 1着: {first.get('umaban', '-')}番 {first.get('name', '-')}")
                    st.markdown(f"🥈 2着: {second.get('umaban', '-')}番 {second.get('name', '-')}")
                    st.markdown(f"🥉 3着: {third.get('umaban', '-')}番 {third.get('name', '-')}")
                
                with col2:
                    if payouts:
                        st.markdown(f"単勝: ¥{payouts.get('tansho', 0):,}")
                        st.markdown(f"馬連: ¥{payouts.get('umaren', 0):,}")
                        st.markdown(f"三連複: ¥{payouts.get('sanrenpuku', 0):,}")
                
                if has_hit:
                    hit_types = [k for k, v in hits.items() if v.get("is_hit", False)]
                    st.success(f"✅ 的中: {', '.join(hit_types)}")
                
                st.divider()


def render_hit_report_tab(history, stats):
    """的中実績レポートタブを描画"""
    st.header("🏆 的中実績レポート")
    
    # 統計カード
    col1, col2, col3, col4 = st.columns(4)
    
    total_payout = stats.get("total_payout", 0)
    total_investment = stats.get("total_investment", 0)
    total_wins = stats.get("total_wins", 0)
    recovery = (total_payout / total_investment * 100) if total_investment > 0 else 0
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">¥{total_payout:,}</div>
            <div class="stat-label">累計配当</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{recovery:.1f}%</div>
            <div class="stat-label">回収率</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{total_wins}</div>
            <div class="stat-label">的中数</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        profit = total_payout - total_investment
        color = "#28a745" if profit >= 0 else "#dc3545"
        st.markdown(f"""
        <div class="stat-card" style="background: {color};">
            <div class="stat-value">¥{profit:,}</div>
            <div class="stat-label">収支</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # 券種別成績
    st.subheader("📊 券種別成績")
    
    bet_types = [
        ("単勝", "tansho_stats"),
        ("馬連", "umaren_stats"),
        ("馬単", "umatan_stats"),
        ("三連複", "sanrenpuku_stats"),
        ("三連単", "sanrentan_stats")
    ]
    
    cols = st.columns(5)
    for col, (name, key) in zip(cols, bet_types):
        with col:
            bet_stats = stats.get(key, {})
            bets = bet_stats.get("bets", 0)
            hits = bet_stats.get("hits", 0)
            payout = bet_stats.get("payout", 0)
            investment = bet_stats.get("investment", 0)
            
            hit_rate = (hits / bets * 100) if bets > 0 else 0
            bet_recovery = (payout / investment * 100) if investment > 0 else 0
            
            st.metric(name, f"{hits}/{bets}")
            st.caption(f"的中率: {hit_rate:.1f}%")
            st.caption(f"回収率: {bet_recovery:.1f}%")
    
    st.divider()
    
    # 的中履歴
    st.subheader("🎯 的中履歴")
    
    if not history:
        st.info("まだ的中履歴がありません")
        return
    
    hit_records = []
    for day in history:
        date = day.get("date", "")
        for result in day.get("results", []):
            hits = result.get("hits", {})
            for bet_type, hit_info in hits.items():
                if hit_info.get("is_hit", False):
                    hit_records.append({
                        "date": date,
                        "venue": result.get("venue", ""),
                        "race_num": result.get("race_num", 0),
                        "race_name": result.get("race_name", ""),
                        "bet_type": bet_type,
                        "payout": hit_info.get("payout", 0)
                    })
    
    if hit_records:
        # 新しい順にソート
        hit_records.sort(key=lambda x: (x["date"], x["race_num"]), reverse=True)
        
        for record in hit_records[:20]:  # 最新20件
            st.markdown(f"""
            **{record['date']}** {record['venue']}{record['race_num']}R {record['race_name']}
            - 的中券種: {record['bet_type']} → **¥{record['payout']:,}**
            """)
    else:
        st.info("まだ的中がありません")


def main():
    """メイン関数"""
    # サイドバー
    st.sidebar.title("🏇 UMA-Logic")
    st.sidebar.caption("競馬AI予想システム v14.0")
    
    st.sidebar.divider()
    
    # 予算設定
    st.sidebar.subheader("💰 予算設定")
    budget = st.sidebar.slider(
        "軍資金（1日あたり）",
        min_value=1000,
        max_value=50000,
        value=10000,
        step=1000,
        format="¥%d"
    )
    
    # 投資スタイル
    style = st.sidebar.radio(
        "投資スタイル",
        ["総合バランス投資", "連勝複式・一撃Ver"],
        help="総合バランス: 全券種に分散投資\n一撃Ver: 連勝式に集中投資"
    )
    
    st.sidebar.divider()
    st.sidebar.caption("© 2026 UMA-Logic")
    
    # データ読み込み
    predictions = load_predictions()
    history = load_history()
    stats = load_stats()
    
    # メインタブ
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 今週の予想",
        "🎰 WIN5予想",
        "📊 全レース結果",
        "🏆 的中実績"
    ])
    
    with tab1:
        render_predictions_tab(predictions, budget, style)
    
    with tab2:
        render_win5_tab(predictions)
    
    with tab3:
        render_results_tab(history)
    
    with tab4:
        render_hit_report_tab(history, stats)


if __name__ == "__main__":
    main()
