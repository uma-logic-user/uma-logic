import requests
from bs4 import BeautifulSoup
import json
import time
import re
import sys
import io
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Windows文字化け対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DATA_DIR = Path("data")
RESULTS_PREFIX = "results_"

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
            # print(f"  [RETRY] {e}")
            time.sleep(2)
    return None

def fetch_race_details(race_id: str) -> Dict[str, Dict]:
    """
    レース詳細データを取得（血統、調教師など）
    戻り値: { "馬番": {DetailData} }
    """
    url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    html = fetch_with_retry(url)
    if not html:
        return {}
        
    soup = BeautifulSoup(html, 'lxml')
    details = {}
    
    # tr.HorseList を解析
    rows = soup.find_all('tr', class_='HorseList')
    for row in rows:
        try:
            # 馬番
            umaban_div = row.find('td', class_=re.compile('Umaban'))
            if not umaban_div: continue
            umaban = int(umaban_div.get_text().strip())
            
            detail = {}
            
            # 馬体重 ("480(+2)" 形式)
            weight_td = row.find('td', class_='Weight')
            if weight_td:
                w_text = weight_td.get_text().strip()
                match = re.search(r'(\d+)', w_text)
                if match:
                    detail["weight"] = int(match.group(1))
            
            # 調教師
            trainer_td = row.find('td', class_='Trainer')
            if trainer_td:
                detail["trainer"] = trainer_td.find('a').get_text().strip() if trainer_td.find('a') else trainer_td.get_text().strip()
                
            # ここから血統を取得するには、本来は馬の詳細ページに行く必要があるが、
            # resultページには血統情報は直接載っていないことが多い。
            # しかし、shutuba.html (出馬表) には簡易的な父名がある場合がある、
            # または horse/pedigree ページに行く必要がある。
            # 時間短縮のため、今回は「5代血統表」までは追わず、
            # もし `results_` データ生成時に取得漏れしていたなら、
            # 別途「馬データベース」を作るのが正攻法。
            # 
            # 暫定対応: resultページから馬IDを取得し、馬ページから父・母父を取る
            # これはリクエスト数が爆発するので、並列処理か、必要な馬のみに絞る。
            
            # 馬ID取得
            horse_link = row.find('span', class_='HorseName').find('a')
            if horse_link:
                href = horse_link['href']
                match = re.search(r'horse/(\d+)', href)
                if match:
                    detail["horse_id"] = match.group(1)
            
            details[umaban] = detail

        except Exception:
            continue
            
    return details

# 馬情報キャッシュ（メモリ内）
horse_cache = {}

def get_horse_pedigree(horse_id: str) -> Dict:
    """馬ページから血統情報を取得"""
    if horse_id in horse_cache:
        return horse_cache[horse_id]
        
    url = f"https://db.netkeiba.com/horse/{horse_id}/"
    html = fetch_with_retry(url)
    data = {"father": "不明", "mother_father": "不明"}
    
    if html:
        soup = BeautifulSoup(html, 'lxml')
        try:
            # db.netkeibaの構造依存
            # <dl class="fc"> ... </dl> の中に血統表へのリンクがあるが、
            # プロフィール欄の "血統" テーブルを見る
            # 通常は class="blood_table" がある
            blood_table = soup.find('table', class_='blood_table')
            if blood_table:
                # 父: 1行目
                father = blood_table.find_all('td')[0].get_text().strip()
                # 母父: 3行目の最後の方... 構造が複雑なので、
                # 簡易的に "父" だけでも十分効果はある
                # 母の父を取得するのは少し面倒（テーブル階層が深い）
                
                # 父の父、父の母...
                # 0: 父
                # 1: 父の父
                # 2: 父の母
                # 3: 母
                # 4: 母の父
                
                tds = blood_table.find_all('td', rowspan=True) 
                # この構造解析は壊れやすいので、テキスト検索などで補完も手
                
                if len(tds) > 0:
                   data["father"] = tds[0].get_text().strip().split("\n")[0]
                
                # 母父取得の試み (class="b_ml")
                b_ml = soup.find_all('td', class_='b_ml')
                if len(b_ml) >= 2:
                    data["mother_father"] = b_ml[1].get_text().strip().split("\n")[0]

        except Exception:
            pass
            
    horse_cache[horse_id] = data
    time.sleep(1) # サーバー負荷軽減
    return data

def process_file(file_path: Path):
    """1つのファイルに情報を付加"""
    print(f"Processing {file_path.name}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        modified = False
        races = data.get("races", [])
        
        for race in races:
            # 既に情報があればスキップ
            # サンプリングで最初の馬を見る
            if race.get("all_results") and "father" in race["all_results"][0]:
                continue
                
            race_id = race.get("race_id")
            if not race_id: continue
            
            # レース詳細（調教師など）を取得
            # 注: resultページには血統がないので、調教師データをメインに
            details = fetch_race_details(race_id)
            
            for horse in race.get("all_results", []):
                umaban = horse.get("馬番")
                if umaban in details:
                    d = details[umaban]
                    if "trainer" in d:
                        horse["trainer"] = d["trainer"]
                        modified = True
                    if "weight" in d:
                        horse["weight"] = d["weight"]
                        modified = True
                    
                    # 血統はAPI負荷が高すぎるので、今回は「主要種牡馬」判定ロジックを
                    # 馬名から推測するのは無理なので、
                    # 重要なのは「馬ID」を持たせておくこと。
                    # 必要ならば実行時にオンデマンドで取得するか、
                    # ここで頑張って取得するか。
                    # 商用レベルならちゃんと取るべきだが、スクレイピング制限に引っかかる。
                    # 妥協案: 上位人気馬や勝ち馬だけでも取る？
                    # いえ、全頭必要。
                    
                    # 今回は一旦、調教師と馬体重を付与することに注力し、
                    # 血統は「後でデータベースを作る」ための準備として horse_id を保存する
                    if "horse_id" in d:
                        horse["horse_id"] = d["horse_id"]
                        modified = True

        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  Updated {file_path.name}")
            
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def main():
    files = sorted(list(DATA_DIR.glob(f"{RESULTS_PREFIX}*.json")))
    # 最新のファイルから順に処理（テスト用）
    # 全件やるには時間がかかる
    
    # 並列処理はサーバーBANのリスクがあるので、直列でゆっくりやるか、
    # 必要な分だけやる。
    # 今回は直近10ファイルだけやってみるデモ
    target_files = files[-5:] 
    
    for p in target_files:
        process_file(p)

if __name__ == "__main__":
    main()
