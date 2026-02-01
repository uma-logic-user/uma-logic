# scripts/scraper_realtime.py
# UMA-Logic Pro - 高機能リアルタイムスクレイパー
# netkeiba.comから最新オッズ・脚質データを取得し、ペース予想を行う

import requests
from bs4 import BeautifulSoup
import time
import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# --- 定数 ---
BASE_URL = "https://race.netkeiba.com"
ODDS_URL = "https://race.netkeiba.com/odds/index.html"
SHUTUBA_URL = "https://race.netkeiba.com/race/shutuba.html"

# リトライ設定
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒
REQUEST_TIMEOUT = 10  # 秒

# User-Agent（ブロック回避用 ）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}


class RunningStyle(Enum):
    """脚質の列挙型"""
    NIGE = "逃げ"      # 逃げ
    SENKO = "先行"     # 先行
    SASHI = "差し"     # 差し
    OIKOMI = "追込"    # 追込
    UNKNOWN = "不明"


@dataclass
class HorseOdds:
    """馬のオッズ情報"""
    horse_number: int
    horse_name: str
    win_odds: float          # 単勝オッズ
    place_odds_min: float    # 複勝オッズ（下限）
    place_odds_max: float    # 複勝オッズ（上限）
    popularity: int          # 人気順


@dataclass
class WideOdds:
    """ワイドオッズ情報"""
    horse1: int
    horse2: int
    odds_min: float
    odds_max: float


@dataclass
class HorseRunningStyle:
    """馬の脚質情報"""
    horse_number: int
    horse_name: str
    style: RunningStyle
    style_score: Dict[str, int]  # 各脚質のスコア（過去レースから算出）


@dataclass
class PacePrediction:
    """ペース予想結果"""
    pace_type: str           # "ハイペース" / "ミドルペース" / "スローペース"
    confidence: float        # 信頼度（0-1）
    nige_count: int          # 逃げ馬の数
    senko_count: int         # 先行馬の数
    sashi_count: int         # 差し馬の数
    oikomi_count: int        # 追込馬の数
    analysis: str            # 分析コメント


def _make_request(url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
    """
    リトライ・タイムアウト処理付きのHTTPリクエスト
    
    Args:
        url: リクエスト先URL
        params: クエリパラメータ
    
    Returns:
        レスポンスオブジェクト（失敗時はNone）
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
        except requests.exceptions.Timeout:
            print(f"[WARN] タイムアウト発生 (試行 {attempt + 1}/{MAX_RETRIES}): {url}")
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] HTTPエラー: {e}")
            if response.status_code == 404:
                return None  # 404は即座に終了
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] リクエストエラー (試行 {attempt + 1}/{MAX_RETRIES}): {e}")
        
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
    
    print(f"[ERROR] 最大リトライ回数に達しました: {url}")
    return None


def _decode_html(response: requests.Response) -> str:
    """
    netkeibaのHTMLをデコード（EUC-JP対応）
    
    Args:
        response: HTTPレスポンス
    
    Returns:
        デコードされたHTML文字列
    """
    try:
        return response.content.decode('euc-jp', errors='replace')
    except Exception:
        return response.text


def get_live_odds(race_id: str) -> Dict[str, any]:
    """
    レース直前の単複・ワイドオッズを取得
    
    Args:
        race_id: レースID（例: "202605010101"）
    
    Returns:
        {
            "race_id": str,
            "timestamp": str,
            "win_place_odds": List[HorseOdds],
            "wide_odds": List[WideOdds],
            "error": Optional[str]
        }
    """
    result = {
        "race_id": race_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "win_place_odds": [],
        "wide_odds": [],
        "error": None
    }

    # --- 単勝・複勝オッズ取得 ---
    win_place_url = f"{ODDS_URL}?type=b1&race_id={race_id}&rf=shutuba_submenu"
    response = _make_request(win_place_url)
    
    if response is None:
        result["error"] = "単複オッズの取得に失敗しました"
        return result
    
    html = _decode_html(response)
    soup = BeautifulSoup(html, 'lxml')
    
    try:
        # 単勝・複勝テーブルを解析
        odds_table = soup.select_one('table.RaceOdds_HorseList_Table')
        if odds_table:
            rows = odds_table.select('tr.HorseList')
            for row in rows:
                try:
                    # 馬番
                    umaban_td = row.select_one('td[class*="Umaban"]')
                    horse_number = int(umaban_td.get_text(strip=True)) if umaban_td else 0
                    
                    # 馬名
                    horse_name_td = row.select_one('span.HorseName')
                    horse_name = horse_name_td.get_text(strip=True) if horse_name_td else ""
                    
                    # 単勝オッズ
                    win_odds_td = row.select_one('td.Odds.Txt_R')
                    win_odds_text = win_odds_td.get_text(strip=True) if win_odds_td else "0"
                    win_odds = float(win_odds_text.replace(',', '')) if win_odds_text not in ['---', ''] else 0.0
                    
                    # 複勝オッズ（範囲）
                    place_odds_tds = row.select('td.Odds.Txt_R')
                    place_odds_min = 0.0
                    place_odds_max = 0.0
                    if len(place_odds_tds) >= 3:
                        place_min_text = place_odds_tds[1].get_text(strip=True)
                        place_max_text = place_odds_tds[2].get_text(strip=True)
                        place_odds_min = float(place_min_text.replace(',', '')) if place_min_text not in ['---', ''] else 0.0
                        place_odds_max = float(place_max_text.replace(',', '')) if place_max_text not in ['---', ''] else 0.0
                    
                    # 人気
                    popularity_td = row.select_one('td.Popular')
                    popularity = int(popularity_td.get_text(strip=True)) if popularity_td else 0
                    
                    if horse_number > 0:
                        result["win_place_odds"].append(HorseOdds(
                            horse_number=horse_number,
                            horse_name=horse_name,
                            win_odds=win_odds,
                            place_odds_min=place_odds_min,
                            place_odds_max=place_odds_max,
                            popularity=popularity
                        ))
                except Exception as e:
                    print(f"[WARN] 馬データのパースエラー: {e}")
                    continue
    except Exception as e:
        result["error"] = f"単複オッズのパースエラー: {e}"
        return result

    # --- ワイドオッズ取得 ---
    wide_url = f"{ODDS_URL}?type=b5&race_id={race_id}&rf=shutuba_submenu"
    response = _make_request(wide_url)
    
    if response:
        html = _decode_html(response)
        soup = BeautifulSoup(html, 'lxml')
        
        try:
            # ワイドオッズテーブルを解析
            wide_table = soup.select_one('table.Wide_Odds_Table')
            if wide_table:
                cells = wide_table.select('td.Odds')
                for cell in cells:
                    try:
                        # セルのdata属性から馬番の組み合わせを取得
                        data_id = cell.get('data-odds-id', '')
                        if '-' in data_id:
                            parts = data_id.split('-')
                            horse1 = int(parts[0])
                            horse2 = int(parts[1])
                            
                            odds_text = cell.get_text(strip=True)
                            # "1.5 - 2.0" のような形式を解析
                            odds_match = re.search(r'([\d.]+)\s*-\s*([\d.]+)', odds_text)
                            if odds_match:
                                odds_min = float(odds_match.group(1))
                                odds_max = float(odds_match.group(2))
                                
                                result["wide_odds"].append(WideOdds(
                                    horse1=horse1,
                                    horse2=horse2,
                                    odds_min=odds_min,
                                    odds_max=odds_max
                                ))
                    except Exception as e:
                        continue
        except Exception as e:
            print(f"[WARN] ワイドオッズのパースエラー: {e}")

    # 人気順でソート
    result["win_place_odds"].sort(key=lambda x: x.popularity if x.popularity > 0 else 999)
    
    return result


def get_running_styles(race_id: str) -> List[HorseRunningStyle]:
    """
    出走馬の脚質データを取得
    
    Args:
        race_id: レースID
    
    Returns:
        各馬の脚質情報リスト
    """
    result = []
    
    # 出馬表ページから脚質情報を取得
    shutuba_url = f"{SHUTUBA_URL}?race_id={race_id}"
    response = _make_request(shutuba_url)
    
    if response is None:
        return result
    
    html = _decode_html(response)
    soup = BeautifulSoup(html, 'lxml')
    
    try:
        # 出馬表テーブルを解析
        horse_rows = soup.select('tr.HorseList')
        
        for row in horse_rows:
            try:
                # 馬番
                umaban_td = row.select_one('td[class*="Umaban"]')
                horse_number = int(umaban_td.get_text(strip=True)) if umaban_td else 0
                
                # 馬名
                horse_name_elem = row.select_one('span.HorseName a')
                horse_name = horse_name_elem.get_text(strip=True) if horse_name_elem else ""
                
                # 脚質情報（netkeibaでは直接表示されないため、過去成績から推定）
                # ここでは馬の詳細ページにアクセスして過去の位置取りから推定
                horse_link = horse_name_elem.get('href', '') if horse_name_elem else ''
                
                style_score = {"逃げ": 0, "先行": 0, "差し": 0, "追込": 0}
                
                if horse_link:
                    # 馬の詳細ページから過去成績を取得（簡易版）
                    horse_id_match = re.search(r'/horse/(\d+)', horse_link)
                    if horse_id_match:
                        horse_id = horse_id_match.group(1)
                        style_score = _get_horse_running_style_score(horse_id)
                
                # 最も高いスコアの脚質を採用
                if max(style_score.values()) > 0:
                    dominant_style = max(style_score, key=style_score.get)
                    style = RunningStyle(dominant_style)
                else:
                    style = RunningStyle.UNKNOWN
                
                if horse_number > 0:
                    result.append(HorseRunningStyle(
                        horse_number=horse_number,
                        horse_name=horse_name,
                        style=style,
                        style_score=style_score
                    ))
                    
            except Exception as e:
                print(f"[WARN] 脚質データのパースエラー: {e}")
                continue
                
    except Exception as e:
        print(f"[ERROR] 脚質データ取得エラー: {e}")
    
    return result


def _get_horse_running_style_score(horse_id: str) -> Dict[str, int]:
    """
    馬の過去成績から脚質スコアを算出
    
    Args:
        horse_id: 馬ID
    
    Returns:
        脚質ごとのスコア
    """
    style_score = {"逃げ": 0, "先行": 0, "差し": 0, "追込": 0}
    
    # 馬の過去成績ページ
    horse_url = f"https://db.netkeiba.com/horse/{horse_id}"
    response = _make_request(horse_url )
    
    if response is None:
        return style_score
    
    html = _decode_html(response)
    soup = BeautifulSoup(html, 'lxml')
    
    try:
        # 過去成績テーブルから通過順位を取得
        result_table = soup.select_one('table.db_h_race_results')
        if result_table:
            rows = result_table.select('tr')[1:11]  # 直近10レース
            
            for row in rows:
                try:
                    # 通過順位（例: "1-1-1-1" や "5-5-3-2"）
                    corner_td = row.select('td')
                    if len(corner_td) >= 11:
                        corner_text = corner_td[10].get_text(strip=True)
                        if corner_text and '-' in corner_text:
                            positions = [int(p) for p in corner_text.split('-') if p.isdigit()]
                            if positions:
                                first_corner = positions[0]
                                # 頭数を取得（同じ行から）
                                field_size = 18  # デフォルト
                                
                                # 位置取りから脚質を判定
                                position_ratio = first_corner / field_size
                                
                                if position_ratio <= 0.15:
                                    style_score["逃げ"] += 3
                                elif position_ratio <= 0.35:
                                    style_score["先行"] += 3
                                elif position_ratio <= 0.65:
                                    style_score["差し"] += 3
                                else:
                                    style_score["追込"] += 3
                except Exception:
                    continue
                    
    except Exception as e:
        print(f"[WARN] 過去成績のパースエラー: {e}")
    
    return style_score


def get_pace_prediction(race_id: str) -> PacePrediction:
    """
    出走馬の脚質分布からハイ/スローペースを予測
    
    Args:
        race_id: レースID
    
    Returns:
        ペース予想結果
    """
    # 脚質データを取得
    running_styles = get_running_styles(race_id)
    
    if not running_styles:
        return PacePrediction(
            pace_type="不明",
            confidence=0.0,
            nige_count=0,
            senko_count=0,
            sashi_count=0,
            oikomi_count=0,
            analysis="脚質データを取得できませんでした"
        )
    
    # 脚質ごとの頭数をカウント
    nige_count = sum(1 for h in running_styles if h.style == RunningStyle.NIGE)
    senko_count = sum(1 for h in running_styles if h.style == RunningStyle.SENKO)
    sashi_count = sum(1 for h in running_styles if h.style == RunningStyle.SASHI)
    oikomi_count = sum(1 for h in running_styles if h.style == RunningStyle.OIKOMI)
    
    total_horses = len(running_styles)
    front_runners = nige_count + senko_count  # 前に行きたい馬の数
    
    # ペース予測ロジック
    front_ratio = front_runners / total_horses if total_horses > 0 else 0
    
    if nige_count >= 3 or front_ratio >= 0.5:
        # 逃げ馬が3頭以上、または前に行きたい馬が半数以上 → ハイペース
        pace_type = "ハイペース"
        confidence = min(0.9, 0.5 + (nige_count * 0.1) + (front_ratio * 0.3))
        analysis = f"逃げ馬{nige_count}頭、先行馬{senko_count}頭と前に行きたい馬が多く、ペースが上がりやすい展開。差し・追込馬に有利。"
    elif nige_count == 0 or front_ratio <= 0.25:
        # 逃げ馬がいない、または前に行きたい馬が少ない → スローペース
        pace_type = "スローペース"
        confidence = min(0.9, 0.5 + ((1 - front_ratio) * 0.4))
        analysis = f"逃げ馬{nige_count}頭と少なく、ペースが落ち着きやすい展開。逃げ・先行馬に有利。"
    else:
        # 中間 → ミドルペース
        pace_type = "ミドルペース"
        confidence = 0.6
        analysis = f"逃げ馬{nige_count}頭、先行馬{senko_count}頭とバランスが取れた構成。展開は読みにくいが、実力馬が力を発揮しやすい。"
    
    return PacePrediction(
        pace_type=pace_type,
        confidence=round(confidence, 2),
        nige_count=nige_count,
        senko_count=senko_count,
        sashi_count=sashi_count,
        oikomi_count=oikomi_count,
        analysis=analysis
    )


def get_all_race_data(race_id: str) -> Dict:
    """
    レースの全データ（オッズ・脚質・ペース予想）を一括取得
    
    Args:
        race_id: レースID
    
    Returns:
        統合されたレースデータ
    """
    print(f"[INFO] レースデータ取得開始: {race_id}")
    
    # オッズ取得
    odds_data = get_live_odds(race_id)
    
    # 脚質データ取得
    running_styles = get_running_styles(race_id)
    
    # ペース予想
    pace_prediction = get_pace_prediction(race_id)
    
    # 統合
    result = {
        "race_id": race_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "odds": {
            "win_place": [
                {
                    "horse_number": o.horse_number,
                    "horse_name": o.horse_name,
                    "win_odds": o.win_odds,
                    "place_odds_min": o.place_odds_min,
                    "place_odds_max": o.place_odds_max,
                    "popularity": o.popularity
                } for o in odds_data["win_place_odds"]
            ],
            "wide": [
                {
                    "horse1": w.horse1,
                    "horse2": w.horse2,
                    "odds_min": w.odds_min,
                    "odds_max": w.odds_max
                } for w in odds_data["wide_odds"]
            ],
            "error": odds_data.get("error")
        },
        "running_styles": [
            {
                "horse_number": rs.horse_number,
                "horse_name": rs.horse_name,
                "style": rs.style.value,
                "style_score": rs.style_score
            } for rs in running_styles
        ],
        "pace_prediction": {
            "pace_type": pace_prediction.pace_type,
            "confidence": pace_prediction.confidence,
            "nige_count": pace_prediction.nige_count,
            "senko_count": pace_prediction.senko_count,
            "sashi_count": pace_prediction.sashi_count,
            "oikomi_count": pace_prediction.oikomi_count,
            "analysis": pace_prediction.analysis
        }
    }
    
    print(f"[INFO] レースデータ取得完了: {race_id}")
    return result


# --- メイン実行（テスト用） ---
if __name__ == "__main__":
    # テスト用レースID（実際のレースIDに置き換えてください）
    test_race_id = "202605010101"
    
    print("=" * 60)
    print("UMA-Logic Pro - リアルタイムスクレイパー テスト")
    print("=" * 60)
    
    # 全データ取得
    race_data = get_all_race_data(test_race_id)
    
    # 結果表示
    print("\n--- オッズ情報 ---")
    for odds in race_data["odds"]["win_place"][:5]:
        print(f"  {odds['popularity']}番人気: {odds['horse_number']}番 {odds['horse_name']} "
              f"単勝{odds['win_odds']}倍 複勝{odds['place_odds_min']}-{odds['place_odds_max']}倍")
    
    print("\n--- 脚質分布 ---")
    for rs in race_data["running_styles"][:5]:
        print(f"  {rs['horse_number']}番 {rs['horse_name']}: {rs['style']}")
    
    print("\n--- ペース予想 ---")
    pace = race_data["pace_prediction"]
    print(f"  予想: {pace['pace_type']} (信頼度: {pace['confidence']:.0%})")
    print(f"  逃げ{pace['nige_count']}頭 / 先行{pace['senko_count']}頭 / "
          f"差し{pace['sashi_count']}頭 / 追込{pace['oikomi_count']}頭")
    print(f"  分析: {pace['analysis']}")
    
    # JSON出力
    print("\n--- JSON出力 ---")
    print(json.dumps(race_data, ensure_ascii=False, indent=2))
