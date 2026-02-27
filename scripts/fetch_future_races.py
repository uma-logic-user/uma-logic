import requests
from bs4 import BeautifulSoup
import json
import time
import re
import sys
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Windows文字化け対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# パス設定
DATA_DIR = Path("data")
HISTORY_DIR = DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# ユーティリティ
def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://race.netkeiba.com/"
    }

def fetch_with_retry(url, encoding='euc-jp'):
    for _ in range(3):
        try:
            time.sleep(1)
            response = requests.get(url, headers=get_headers(), timeout=10)
            response.encoding = encoding
            return response.text
        except Exception as e:
            print(f"  [RETRY] {e}")
            time.sleep(2)
    return None

JRA_VENUE_CODES = {"01","02","03","04","05","06","07","08","09","10"}

def is_jra_race_id(race_id: str) -> bool:
    """venue code 01-10 (JRA中央競馬) のみ Trueを返す"""
    s = str(race_id)
    return len(s) >= 10 and s[4:6] in JRA_VENUE_CODES

def get_future_race_ids(date_str: str) -> List[str]:
    """開催日から中央競馬のレースIDリストを取得"""
    url = f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date_str}"
    html = fetch_with_retry(url, 'utf-8')
    if not html:
        return []

    soup = BeautifulSoup(html, 'lxml')
    race_ids = []

    for link in soup.find_all('a', href=True):
        href = link['href']
        if "shutuba.html" in href and "race_id=" in href:
            match = re.search(r'race_id=(\d+)', href)
            if match:
                rid = match.group(1)
                if rid not in race_ids and is_jra_race_id(rid):  # JRAのみ
                    race_ids.append(rid)

    return sorted(race_ids)

def parse_shutuba_page(race_id: str) -> Dict:
    """出馬表ページをパース"""
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    html = fetch_with_retry(url, 'euc-jp')
    if not html:
        return None
        
    soup = BeautifulSoup(html, 'lxml')
    
    # レース情報抽出
    race_info = {}
    race_info["race_id"] = race_id
    
    # レース名、条件など
    data_intro = soup.find('div', class_='RaceData01')
    if data_intro:
        text = data_intro.get_text().strip()
        # "15:35発走 / 芝2400m (左 C) / 天候:晴 / 馬場:良" みたいな情報
        if "芝" in text:
            race_info["track_type"] = "芝"
        elif "ダ" in text:
            race_info["track_type"] = "ダート"
        else:
            race_info["track_type"] = "障害" # 簡易
            
        # 距離抽出
        dist_match = re.search(r'(\d+)m', text)
        race_info["distance"] = int(dist_match.group(1)) if dist_match else 1600
        
        # 天候・馬場（未来なので不明なことが多いが、直前ならあるかも）
        if "馬場:良" in text: race_info["track_condition"] = "良"
        elif "馬場:稍" in text: race_info["track_condition"] = "稍重"
        elif "馬場:重" in text: race_info["track_condition"] = "重"
        elif "馬場:不" in text: race_info["track_condition"] = "不良"
        else: race_info["track_condition"] = "良" # デフォルト

    race_name_elem = soup.find('div', class_='RaceName')
    race_info["race_name"] = race_name_elem.get_text().strip() if race_name_elem else f"Race {race_id}"
    
    # 開催地 (IDから推測可能)
    place_code = race_id[4:6]
    places = {"01":"札幌", "02":"函館", "03":"福島", "04":"新潟", "05":"東京", "06":"中山", "07":"中京", "08":"京都", "09":"阪神", "10":"小倉"}
    race_info["venue"] = places.get(place_code, "その他")
    race_info["race_num"] = int(race_id[10:12])

    # 馬データ抽出
    horses = []
    # ShutubaTable
    table = soup.find('table', class_='Shutuba_Table')
    if not table:
        return None
        
    rows = table.find_all('tr', class_='HorseList')
    for row in rows:
        h_data = {}
        
        # 枠番
        waku = row.find('td', class_=re.compile('Waku'))
        h_data["wakuban"] = int(waku.get_text().strip()) if waku else 0
        
        # 馬番
        umaban = row.find('td', class_=re.compile('Umaban'))
        h_data["umaban"] = int(umaban.get_text().strip()) if umaban else 0
        
        # 馬名
        name_div = row.find('span', class_='HorseName')
        h_data["horse_name"] = name_div.get_text().strip() if name_div else "Noname"
        
        # 性齢 ("牡3" など)
        sex_age = row.find('div', class_='Txt_C') # 構造依存強し
        if sex_age:
            txt = sex_age.get_text().strip()
            h_data["sex"] = txt[0] if txt else "牡"
            h_data["age"] = int(txt[1:]) if len(txt)>1 and txt[1:].isdigit() else 3
            
        # 斤量
        weight = row.find('td', class_='Txt_C', text=re.compile(r'\d+\.\d')) # 56.0とか
        # クラス指定が難しいので順番で取ることも多いが、今回は簡易的に
        w_cols = row.find_all('td', class_='Txt_C')
        # ...ちょっとDOM構造が複雑なので、専用classを持つ要素を探す
        jockey_td = row.find('td', class_='Jockey')
        h_data["jockey"] = jockey_td.find('a').get_text().strip() if jockey_td and jockey_td.find('a') else "不明"
        
        # オッズ (あれば)
        odds_td = row.find('td', class_='TxT_R') # 人気・オッズのクラス
        # netkeibaの出馬表はオッズが別ロードの場合がある
        # ここでは取得できなければデフォルト値を入れる
        h_data["odds"] = 0.0
        h_data["popularity"] = 0
        
        # 過去走のランク（簡易取得）
        # <div class="PastRank">1</div> ... みたいな構造を探す
        # netkeiba出馬表では、class="Kaisai"の中に着順が入っていたりする
        # とりあえず安全策で空リスト
        h_data["last_3_results"] = []
        
        # 血統（父）
        # 出馬表には父名が直接書かれていないことが多い（詳細クリックが必要）
        # ただし "HorseInfo" の中に title 属性などで隠れている場合も
        # 今回は「データなし」で進める（予測精度は下がるが、エラーにはならない）
        h_data["father"] = "不明"

        horses.append(h_data)

    race_info["horses"] = horses
    return race_info

def fetch_future_predictions(date_str: str):
    """指定日の出馬表を取得・保存"""
    print(f"🎯 出馬表取得開始: {date_str}")
    
    race_ids = get_future_race_ids(date_str)
    if not race_ids:
        print("  [WARN] 開催レースが見つかりません（まだ公開されていないか、中止の可能性があります）")
        return False
        
    print(f"  {len(race_ids)}レース見つかりました。取得中...")
    
    races = []
    for rid in race_ids:
        try:
            r_data = parse_shutuba_page(rid)
            if r_data:
                races.append(r_data)
                print(f"    - {r_data['race_name']} ({len(r_data['horses'])}頭)")
            time.sleep(1)
        except Exception as e:
            print(f"    [ERROR] レース解析失敗 {rid}: {e}")
            
    if not races:
        print("  [ERROR] 有効なレースデータが取得できませんでした")
        return False
        
    # predictions_{date}.json として保存（result形式に近いが、predictions生成の種データとして使う）
    # calculator_pro.py は、"results_..." を入力とすることも "predictions_..."（再計算）もできるが、
    # ここでは "raw_entries_YYYYMMDD.json" として一時保存し、それを calculator に食わせるか、
    # あるいは calculator_pro.py 内で直接これを読み込める形式にする。
    # regenerate_predictions.py は "results_..." を読む仕様だった。
    
    # 互換性のため "predictions_YYYYMMDD.json" の形式（ただし結果スコアなし）で保存して、
    # calculator_pro.py --process で計算させるのがスムーズ。
    
    # ただし calculator_pro.py の --process は "predictions_..." を読んで "calculated_..." を出す仕様に見える。
    # ここでは "predictions_YYYYMMDD.json" に「未計算の状態」で保存する。
    
    output = {
        "date": date_str,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "races": races # ここには horses リストが含まれる
    }
    
    outfile = HISTORY_DIR / f"predictions_{date_str}.json"
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        
    print(f"  ✅ 出馬表保存完了: {outfile}")
    return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        d = sys.argv[1]
    else:
        # デフォルトは明日
        d = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        
    fetch_future_predictions(d)
