import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import datetime
import time
import joblib  # ★追加: 学習済みモデルの読み込み用

# ---------------------------------------------------------
# 1. 設定とユーティリティ関数
# ---------------------------------------------------------
st.set_page_config(page_title="競馬予想AI - 開催ステータス監視付き", layout="wide")

# --- (既存のスクレイピング関数はそのまま利用) ---
@st.cache_data(ttl=600)
def check_netkeiba_status(target_date_str, venue_name):
    # ... (あなたのコードのまま変更なし) ...
    try:
        dt = datetime.datetime.strptime(target_date_str, '%Y-%m-%d')
        formatted_date = dt.strftime('%Y%m%d')
    except ValueError:
        return "日付エラー", False

    url = f"https://race.netkeiba.com/top/race_list.html?kaisai_date={formatted_date}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'EUC-JP'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        race_data_list = soup.find('div', class_='RaceList_DataList')
        if not race_data_list:
            return "情報取得不可(通常想定)", False

        venue_found = False
        is_cancelled = False
        status_msg = "開催予定"

        venues_blocks = soup.find_all('div', class_='RaceList_Data')
        for block in venues_blocks:
            block_text = block.get_text()
            if venue_name in block_text:
                venue_found = True
                if "中止" in block_text or "延期" in block_text:
                    is_cancelled = True
                    status_msg = "開催中止・延期"
                elif "雪" in block_text and "影響" in block_text:
                    status_msg = "天候調査中"
                break
        
        if not venue_found:
            return "開催なし", False
            
        return status_msg, is_cancelled

    except Exception as e:
        return "接続エラー(手動確認推奨)", False

# ---------------------------------------------------------
# ★追加: AIモデルとデータ処理の関数
# ---------------------------------------------------------

# モデルの読み込み（キャッシュして高速化）
@st.cache_resource
def load_ai_model():
    # 本来はここで 'model.pkl' などを読み込みます
    # model = joblib.load('my_race_model.pkl')
    # return model
    return "DummyModel" # 今はファイルがないのでダミー文字列を返します

def get_real_predictions(venue, date_str):
    """
    ここで実際にその日の出馬表データを取得し、AIで予測を行います。
    今回は統合イメージを示すため、構造だけ作ります。
    """
    # 1. 出馬表データの取得 (スクレイピング or API)
    # data = scrape_race_card(venue, date_str)
    
    # 2. 前処理 (カテゴリ変数化など)
    # features = preprocess(data)
    
    # 3. 予測 (モデルの使用)
    # model = load_ai_model()
    # probs = model.predict_proba(features)
    
    # --- ここではまだモデルがないので、それっぽいデータを返します ---
    # ※ 実際はここが機械学習の推論結果になります
    df_predict = pd.DataFrame({
        'レース': [f'{i}R' for i in range(1, 13)],
        '本命馬': [f'AI選定馬-{i}' for i in range(1, 13)], # 実際は馬名
        'AI自信度': np.random.randint(50, 95, 12),       # 実際は予測確率
        'オッズ': np.round(np.random.uniform(1.5, 20.0, 12), 1) # 実際はリアルタイムオッズ
    })
    return df_predict

# ---------------------------------------------------------
# 2. メインアプリケーション
# ---------------------------------------------------------

def main():
    st.title("🏇 AI競馬予想システム Commercial Ver.")
    st.markdown("---")

    # --- サイドバー設定 ---
    st.sidebar.header("開催設定")
    today = datetime.date.today()
    target_date = st.sidebar.date_input("開催日選択", today)
    target_date_str = target_date.strftime('%Y-%m-%d')
    venue = st.sidebar.selectbox("開催会場", ["東京", "中山", "京都", "阪神", "新潟", "福島", "中京", "札幌", "函館", "小倉"])

    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠 デバッグ・テスト用")
    simulate_cancel = st.sidebar.checkbox("【テスト】強制的に『中止』状態にする")

    # --- 開催ステータスチェック ---
    if simulate_cancel:
        status_text = "テスト用：開催中止"
        is_cancelled = True
    else:
        with st.spinner(f'{venue}競馬場のステータスを確認中...'):
            status_text, is_cancelled = check_netkeiba_status(target_date_str, venue)

    # --- 画面表示制御 (ロック機能) ---
    ui_disabled = False 

    if is_cancelled:
        st.error(f"### ⚠️ {venue}競馬場は「{status_text}」です。機能はロックされます。")
        ui_disabled = True
    elif status_text == "開催なし":
        st.warning(f"{target_date_str} の {venue} 開催データが見つかりません。")
        ui_disabled = True
    else:
        st.success(f"ステータス確認OK: {venue} ({status_text})")

    # ---------------------------------------------------------
    # 5. アプリケーション本体
    # ---------------------------------------------------------

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📊 レース分析データ")
        
        # ★変更点: ロックされていない場合のみ、AI予測を実行して表示
        if not ui_disabled:
            # ここで自作関数を呼び出してデータを取得
            with st.spinner('AIがレースを分析中...'):
                df = get_real_predictions(venue, target_date_str)
            
            # データ表示（自信度が高い順に色付けなど）
            st.dataframe(
                df.style.background_gradient(subset=['AI自信度'], cmap='Greens'),
                use_container_width=True
            )
        else:
            st.info("開催中止またはデータなしのため、分析データは表示されません。")
            # 空のデータフレームを作成してエラーを防ぐ
            df = pd.DataFrame({'レース': [], '本命馬': []})

    with col2:
        st.subheader("💰 投資計算機")
        
        budget = st.number_input("総予算 (円)", min_value=1000, value=10000, step=1000, disabled=ui_disabled)
        
        # データがある場合のみ選択肢を表示
        race_options = df['レース'] if not df.empty else []
        target_race = st.selectbox("対象レース", race_options, disabled=ui_disabled)
        
        allocation_method = st.radio("資金配分ロジック", ["均等買い", "オッズ比例配分", "ケリー基準"], disabled=ui_disabled)

        if st.button("投資配分を計算する", type="primary", disabled=ui_disabled):
            
            # --- 実際の投資ロジックをここに書く ---
            st.markdown("### 推奨買い目")
            
            # 選択されたレースの情報を取得
            selected_race_info = df[df['レース'] == target_race].iloc[0]
            confidence = selected_race_info['AI自信度']
            odds = selected_race_info['オッズ']
            
            st.write(f"本命: **{selected_race_info['本命馬']}**")
            st.write(f"AI自信度: {confidence}% / オッズ: {odds}倍")
            
            # 簡易的な配分計算（ロジック例）
            if allocation_method == "ケリー基準":
                # 簡易ケリー計算
                win_prob = confidence / 100
                kelly_fraction = (win_prob * odds - 1) / (odds - 1)
                bet_amount = int(budget * max(0, kelly_fraction))
                msg = "ケリー基準による強気の配分"
            else:
                bet_amount = int(budget * 0.1) # 予算の10%
                msg = "安全策による定額配分"
                
            st.success(f"推奨投資額: **{bet_amount:,}円** ({msg})")

    if ui_disabled and is_cancelled:
        st.markdown("---")
        st.info("代替開催日が決定した場合、日付を選択し直してください。")

if __name__ == "__main__":
    main()
