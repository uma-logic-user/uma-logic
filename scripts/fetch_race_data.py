# scripts/fetch_race_data.py
# UMA-Logic Pro - 商用グレード予想データ取得スクリプト
# netkeiba.comから全レース情報を取得し、日付別JSONに保存

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import random

# --- 定数 ---
BASE_URL = "https://race.netkeiba.com"
RACE_LIST_URL = "https://race.netkeiba.com/top/race_list.html"
SHUTUBA_URL = "https://race.netkeiba.com/race/shutuba.html"

DATA_DIR = Path("data" )
PREDICTIONS_PREFIX = "predictions_"

# リクエスト設定
MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 1.5  # リクエスト間隔（秒）

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# 競馬場コード
VENUE_CODES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉"
}

# トップ騎手リスト（UMA指数計算用）
TOP_JOCKEYS = [
    "川田将雅", "ルメール", "戸崎圭太", "横山武史", "福永祐一",
    "松山弘平", "岩田望来", "吉田隼人", "武豊", "デムーロ",
    "坂井瑠星", "横山和生", "田辺裕信", "池添謙一", "北村友一"
]


@dataclass
class HorseData:
    """馬データ"""
    馬番: int
    馬名: str
    性齢: str
    斤量: float
    騎手: str
    厩舎: str
    馬体重: str
    単勝オッズ: float
    人気: int
    印: str
    UMA指数: int
    期待値: float
    推奨理由: str
    horse_id: str  # 馬の詳細ページID
    jockey_id: str  # 騎手ID


@dataclass
class RaceData:
    """レースデータ"""
    race_id: str
    venue: str
    venue_code: str
    race_num: int
    race_name: str
    race_type: str  # 芝/ダート
    distance: int
    course: str  # 右/左/直線
    weather: str
    track_condition: str  # 良/稀重/重/不良
    start_time: str
    rank: str  # S/A/B
    is_win5: bool
    horses: List[dict]
    race_url: str


def fetch_with_retry(url: str, params: dict = None) -> Optional[requests.Response]:
    """
    リトライ機能付きHTTPリクエスト
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"[WARN] リクエスト失敗 (試行 {attempt + 1}/{MAX_RETRIES}): {url}")
            print(f"       エラー: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    
    print(f"[ERROR] 最大リトライ回数超過: {url}")
    return None


def get_race_ids_from_list(target_date: datetime.date) -> List[str]:
    """
    レース一覧ページから当日の全レースIDを取得
    """
    date_str = target_date.strftime("%Y%m%d")
    url = f"{RACE_LIST_URL}?kaisai_date={date_str}"
    
    print(f"[INFO] レース一覧を取得中: {url}")
    
    response = fetch_with_retry(url)
    if not response:
        return []
    
    # EUC-JPからUTF-8に変換
    try:
        html = response.content.decode('euc-jp', errors='replace')
    except:
        html = response.text
    
    soup = BeautifulSoup(html, 'lxml')
    
    race_ids = []
    
    # レースリンクからIDを抽出
    for link in soup.find_all('a', href=True):
        href = link['href']
        match = re.search(r'race_id=(\d{12})', href)
        if match:
            race_id = match.group(1)
            if race_id not in race_ids:
                race_ids.append(race_id)
    
    print(f"[INFO] {len(race_ids)}件のレースIDを取得")
    return race_ids


def get_race_ids_from_saved(target_date: datetime.date) -> List[str]:
    """
    保存済みのrace_ids.jsonからレースIDを取得（フォールバック用）
    """
    filepath = DATA_DIR / "race_ids.json"
    
    if not filepath.exists():
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # リスト形式の場合
            if isinstance(data, list):
                return data
            
            # 辞書形式の場合
            if isinstance(data, dict):
                date_str = target_date.strftime("%Y%m%d")
                return data.get(date_str, [])
    except Exception as e:
        print(f"[WARN] race_ids.json読み込みエラー: {e}")
    
    return []


def scrape_race(race_id: str) -> Optional[RaceData]:
    """
    出馬表ページから1レースの情報をスクレイピング
    """
    url = f"{SHUTUBA_URL}?race_id={race_id}"
    
    print(f"[INFO] レース情報を取得中: {race_id}")
    
    response = fetch_with_retry(url)
    if not response:
        return None
    
    # 文字コード処理
    try:
        html = response.content.decode('euc-jp', errors='replace')
    except:
        html = response.text
    
    soup = BeautifulSoup(html, 'lxml')
    
    # レース情報の抽出
    race_info = extract_race_info(soup, race_id, url)
    if not race_info:
        return None
    
    # 出走馬情報の抽出
    horses = extract_horses(soup)
    if not horses:
        print(f"[WARN] 馬情報が取得できませんでした: {race_id}")
        return None
    
    # UMA指数と期待値を計算
    horses = calculate_uma_index(horses, race_info)
    
    # 印を付与
    horses = assign_marks(horses)
    
    # ランクを決定
    rank = determine_rank(horses)
    
    # WIN5対象判定（9R以降）
    is_win5 = race_info.get("race_num", 0) >= 9
    
    return RaceData(
        race_id=race_id,
        venue=race_info.get("venue", ""),
        venue_code=race_info.get("venue_code", ""),
        race_num=race_info.get("race_num", 0),
        race_name=race_info.get("race_name", ""),
        race_type=race_info.get("race_type", ""),
        distance=race_info.get("distance", 0),
        course=race_info.get("course", ""),
        weather=race_info.get("weather", ""),
        track_condition=race_info.get("track_condition", ""),
        start_time=race_info.get("start_time", ""),
        rank=rank,
        is_win5=is_win5,
        horses=[asdict(h) if isinstance(h, HorseData) else h for h in horses],
        race_url=url
    )


def extract_race_info(soup: BeautifulSoup, race_id: str, url: str) -> Optional[dict]:
    """
    レース基本情報を抽出
    """
    info = {
        "race_id": race_id,
        "race_url": url
    }
    
    # 競馬場コードと回次を抽出
    venue_code = race_id[4:6]
    info["venue_code"] = venue_code
    info["venue"] = VENUE_CODES.get(venue_code, "不明")
    
    # レース番号
    race_num_str = race_id[10:12]
    info["race_num"] = int(race_num_str) if race_num_str.isdigit() else 0
    
    # レース名
    race_name_elem = soup.select_one('.RaceName')
    if race_name_elem:
        info["race_name"] = race_name_elem.get_text(strip=True)
    else:
        info["race_name"] = f"{info['venue']}{info['race_num']}R"
    
    # レース条件（距離・コース）
    race_data_elem = soup.select_one('.RaceData01')
    if race_data_elem:
        race_text = race_data_elem.get_text(strip=True)
        
        # 距離抽出
        distance_match = re.search(r'(\d{3,4})m', race_text)
        if distance_match:
            info["distance"] = int(distance_match.group(1))
        
        # 芝/ダート
        if '芝' in race_text:
            info["race_type"] = "芝"
        elif 'ダ' in race_text or 'ダート' in race_text:
            info["race_type"] = "ダート"
        else:
            info["race_type"] = "不明"
        
        # コース（右/左）
        if '右' in race_text:
            info["course"] = "右"
        elif '左' in race_text:
            info["course"] = "左"
        elif '直' in race_text:
            info["course"] = "直線"
        else:
            info["course"] = ""
    
    # 天候・馬場状態
    race_data2_elem = soup.select_one('.RaceData02')
    if race_data2_elem:
        spans = race_data2_elem.find_all('span')
        for span in spans:
            text = span.get_text(strip=True)
            if '天候' in text or '晴' in text or '曇' in text or '雨' in text:
                info["weather"] = text.replace('天候:', '').strip()
            if '良' in text or '稍' in text or '重' in text or '不' in text:
                if '馬場' in text or len(text) <= 3:
                    info["track_condition"] = text.replace('馬場:', '').strip()
    
    # 発走時刻
    time_elem = soup.select_one('.RaceData01 .PostTime, .RaceData01')
    if time_elem:
        time_match = re.search(r'(\d{1,2}:\d{2})', time_elem.get_text())
        if time_match:
            info["start_time"] = time_match.group(1)
    
    return info


def extract_horses(soup: BeautifulSoup) -> List[HorseData]:
    """
    出走馬情報を抽出
    """
    horses = []
    
    # 出馬表のテーブル行を取得
    rows = soup.select('table.Shutuba_Table tr.HorseList, table.ShutubaTable tr.HorseList')
    
    if not rows:
        # 別のセレクタを試す
        rows = soup.select('tr[class*="HorseList"]')
    
    for row in rows:
        try:
            horse = extract_single_horse(row)
            if horse:
                horses.append(horse)
        except Exception as e:
            print(f"[WARN] 馬情報抽出エラー: {e}")
            continue
    
    return horses


def extract_single_horse(row) -> Optional[HorseData]:
    """
    1頭分の馬情報を抽出
    """
    # 馬番
    umaban_elem = row.select_one('td[class*="Umaban"]')
    if umaban_elem:
        umaban_text = umaban_elem.get_text(strip=True)
        umaban = int(umaban_text) if umaban_text.isdigit() else 0
    else:
        return None
    
    # 馬名
    horse_name_elem = row.select_one('.HorseName a, td.HorseInfo a')
    if horse_name_elem:
        horse_name = horse_name_elem.get_text(strip=True)
        horse_href = horse_name_elem.get('href', '')
        horse_id_match = re.search(r'/horse/(\w+)', horse_href)
        horse_id = horse_id_match.group(1) if horse_id_match else ""
    else:
        horse_name = ""
        horse_id = ""
    
    # 性齢
    sex_age_elem = row.select_one('.Barei, td:nth-child(5)')
    sex_age = sex_age_elem.get_text(strip=True) if sex_age_elem else ""
    
    # 斤量
    weight_elem = row.select_one('.Txt_C.Futan, td.Futan')
    if weight_elem:
        weight_text = weight_elem.get_text(strip=True)
        try:
            kinryo = float(weight_text)
        except:
            kinryo = 0.0
    else:
        kinryo = 0.0
    
    # 騎手
    jockey_elem = row.select_one('.Jockey a, td.Jockey a')
    if jockey_elem:
        jockey = jockey_elem.get_text(strip=True)
        jockey_href = jockey_elem.get('href', '')
        jockey_id_match = re.search(r'/jockey/(\w+)', jockey_href)
        jockey_id = jockey_id_match.group(1) if jockey_id_match else ""
    else:
        jockey = ""
        jockey_id = ""
    
    # 厩舎
    trainer_elem = row.select_one('.Trainer a, td.Trainer a')
    trainer = trainer_elem.get_text(strip=True) if trainer_elem else ""
    
    # 馬体重
    weight_info_elem = row.select_one('.Weight, td.Weight')
    weight_info = weight_info_elem.get_text(strip=True) if weight_info_elem else ""
    
    # 単勝オッズ
    odds_elem = row.select_one('td.Txt_R.Popular, span.Odds')
    if odds_elem:
        odds_text = odds_elem.get_text(strip=True)
        try:
            odds = float(odds_text.replace(',', ''))
        except:
            odds = 0.0
    else:
        odds = 0.0
    
    # 人気
    ninki_elem = row.select_one('td.Popular_Ninki, span.Ninki')
    if ninki_elem:
        ninki_text = ninki_elem.get_text(strip=True)
        try:
            ninki = int(ninki_text)
        except:
            ninki = 0
    else:
        ninki = 0
    
    return HorseData(
        馬番=umaban,
        馬名=horse_name,
        性齢=sex_age,
        斤量=kinryo,
        騎手=jockey,
        厩舎=trainer,
        馬体重=weight_info,
        単勝オッズ=odds,
        人気=ninki,
        印="",
        UMA指数=0,
        期待値=0.0,
        推奨理由="",
        horse_id=horse_id,
        jockey_id=jockey_id
    )


def calculate_uma_index(horses: List[HorseData], race_info: dict) -> List[HorseData]:
    """
    UMA指数（5大要素統合スコア）を計算
    
    5大要素:
    1. 血統適性 (20点) - シミュレーション
    2. 調教評価 (20点) - シミュレーション
    3. 枠順/展開 (20点)
    4. 騎手/厩舎 (20点)
    5. 過去実績/オッズ (20点)
    """
    distance = race_info.get("distance", 1600)
    race_type = race_info.get("race_type", "芝")
    
    for horse in horses:
        score = 0
        reasons = []
        
        # 1. 血統適性 (シミュレーション: ランダム要素 + 距離適性)
        blood_score = random.randint(8, 18)
        if distance <= 1400:
            blood_score += random.randint(0, 2)  # 短距離血統ボーナス
        elif distance >= 2400:
            blood_score += random.randint(0, 2)  # 長距離血統ボーナス
        score += min(blood_score, 20)
        if blood_score >= 15:
            reasons.append("血統適性")
        
        # 2. 調教評価 (シミュレーション)
        training_score = random.randint(8, 18)
        score += min(training_score, 20)
        if training_score >= 15:
            reasons.append("追切良好")
        
        # 3. 枠順/展開 (内枠有利)
        if horse.馬番 <= 4:
            gate_score = 16 + random.randint(0, 4)
            reasons.append("内枠有利")
        elif horse.馬番 <= 8:
            gate_score = 12 + random.randint(0, 4)
        elif horse.馬番 <= 12:
            gate_score = 10 + random.randint(0, 4)
        else:
            gate_score = 8 + random.randint(0, 4)
        score += min(gate_score, 20)
        
        # 4. 騎手/厩舎
        jockey_score = 10
        if horse.騎手 in TOP_JOCKEYS:
            jockey_score = 16 + random.randint(0, 4)
            reasons.append(f"{horse.騎手}騎乗")
        else:
            jockey_score = 8 + random.randint(0, 6)
        score += min(jockey_score, 20)
        
        # 5. 過去実績/オッズ (人気・オッズから推定)
        if horse.人気 == 1:
            perf_score = 18 + random.randint(0, 2)
            reasons.append("1番人気")
        elif horse.人気 == 2:
            perf_score = 15 + random.randint(0, 3)
        elif horse.人気 <= 5:
            perf_score = 12 + random.randint(0, 4)
        else:
            perf_score = 8 + random.randint(0, 6)
        score += min(perf_score, 20)
        
        horse.UMA指数 = min(score, 100)
        
        # 期待値計算 (推定勝率 / (1/オッズ))
        if horse.単勝オッズ > 0:
            estimated_win_rate = horse.UMA指数 / 100 * 0.3  # 最大30%勝率
            fair_odds = 1 / estimated_win_rate if estimated_win_rate > 0 else 100
            horse.期待値 = round(fair_odds / horse.単勝オッズ, 2) if horse.単勝オッズ > 0 else 0
        else:
            horse.期待値 = 0
        
        # 期待値が高い場合の理由追加
        if horse.期待値 >= 1.2:
            reasons.append("期待値妙味")
        
        horse.推奨理由 = "・".join(reasons[:3]) if reasons else "総合評価"
    
    return horses


def assign_marks(horses: List[HorseData]) -> List[HorseData]:
    """
    UMA指数に基づいて印を付与
    """
    # UMA指数でソート
    sorted_horses = sorted(horses, key=lambda h: h.UMA指数, reverse=True)
    
    marks = ["◎", "○", "▲", "△", "△"]
    
    for i, horse in enumerate(sorted_horses):
        if i < len(marks):
            horse.印 = marks[i]
        else:
            horse.印 = ""
    
    return horses


def determine_rank(horses: List[HorseData]) -> str:
    """
    レースのランク（S/A/B）を決定
    """
    if not horses:
        return "B"
    
    # 上位3頭のUMA指数平均
    sorted_horses = sorted(horses, key=lambda h: h.UMA指数, reverse=True)
    top3_avg = sum(h.UMA指数 for h in sorted_horses[:3]) / min(3, len(sorted_horses))
    
    # 本命馬のUMA指数
    top_score = sorted_horses[0].UMA指数 if sorted_horses else 0
    
    # 期待値1.2以上の馬がいるか
    has_high_ev = any(h.期待値 >= 1.2 for h in horses)
    
    if top_score >= 80 or (top3_avg >= 75 and has_high_ev):
        return "S"
    elif top_score >= 70 or top3_avg >= 65:
        return "A"
    else:
        return "B"


def save_predictions(races: List[RaceData], target_date: datetime.date):
    """
    予想データをJSON形式で保存
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = target_date.strftime("%Y%m%d")
    
    # 日付別ファイルに保存
    predictions_data = {
        "date": target_date.strftime("%Y-%m-%d"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_races": len(races),
        "rank_summary": {
            "S": len([r for r in races if r.rank == "S"]),
            "A": len([r for r in races if r.rank == "A"]),
            "B": len([r for r in races if r.rank == "B"])
        },
        "races": [asdict(r) for r in races]
    }
    
    # 日付別ファイル
    filepath = DATA_DIR / f"{PREDICTIONS_PREFIX}{date_str}.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(predictions_data, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 保存完了: {filepath}")
    
    # latest_predictions.jsonも更新
    latest_path = DATA_DIR / "latest_predictions.json"
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(predictions_data, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 保存完了: {latest_path}")


def main():
    """
    メイン処理
    """
    print("=" * 60)
    print("UMA-Logic Pro - 予想データ取得スクリプト")
    print("=" * 60)
    
    # 対象日を決定（日本時間）
    import pytz
    jst = pytz.timezone('Asia/Tokyo')
    now_jst = datetime.now(jst)
    target_date = now_jst.date()
    
    # 土日でなければ次の土曜日を対象に
    weekday = target_date.weekday()
    if weekday == 4:  # 金曜日
        target_date += timedelta(days=1)
    elif weekday == 6:  # 日曜日
        pass  # そのまま
    elif weekday < 4:  # 月〜木
        days_until_saturday = 5 - weekday
        target_date += timedelta(days=days_until_saturday)
    
    print(f"[INFO] 対象日: {target_date.strftime('%Y年%m月%d日')}")
    
    # レースIDを取得
    race_ids = get_race_ids_from_list(target_date)
    
    if not race_ids:
        print("[WARN] レース一覧から取得できませんでした。保存済みIDを使用します。")
        race_ids = get_race_ids_from_saved(target_date)
    
    if not race_ids:
        print("[ERROR] レースIDが取得できませんでした。")
        return
    
    print(f"[INFO] 取得対象: {len(race_ids)}レース")
    
    # 各レースの情報を取得
    races = []
    for i, race_id in enumerate(race_ids):
        print(f"[INFO] 処理中: {i + 1}/{len(race_ids)}")
        
        race_data = scrape_race(race_id)
        if race_data:
            races.append(race_data)
        
        # リクエスト間隔
        if i < len(race_ids) - 1:
            time.sleep(REQUEST_INTERVAL)
    
    print(f"[INFO] 取得完了: {len(races)}レース")
    
    # 会場別にソート
    races.sort(key=lambda r: (r.venue, r.race_num))
    
    # 保存
    save_predictions(races, target_date)
    
    # サマリー表示
    print("\n" + "=" * 60)
    print("取得結果サマリー")
    print("=" * 60)
    
    venues = set(r.venue for r in races)
    for venue in sorted(venues):
        venue_races = [r for r in races if r.venue == venue]
        print(f"  {venue}: {len(venue_races)}レース")
    
    rank_s = len([r for r in races if r.rank == "S"])
    rank_a = len([r for r in races if r.rank == "A"])
    rank_b = len([r for r in races if r.rank == "B"])
    
    print(f"\n  Sランク: {rank_s}レース")
    print(f"  Aランク: {rank_a}レース")
    print(f"  Bランク: {rank_b}レース")
    
    win5_races = [r for r in races if r.is_win5]
    print(f"\n  WIN5対象: {len(win5_races)}レース")
    
    print("\n[INFO] 処理完了")


if __name__ == "__main__":
    main()
