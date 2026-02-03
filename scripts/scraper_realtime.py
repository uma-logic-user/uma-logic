# scripts/scraper_realtime.py
# UMA-Logic PRO - リアルタイムスクレイパー＆インサイダー探知機
# 完全版（Full Code）- そのままコピー＆ペーストで動作

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import math
import sys

# --- 定数 ---
DATA_DIR = Path("data")
ODDS_DIR = DATA_DIR / "odds"
ALERTS_FILE = DATA_DIR / "insider_alerts.json"
REALTIME_STATE_FILE = DATA_DIR / "realtime_state.json"

MAX_RETRIES = 3
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}

# インサイダー検知閾値
INSIDER_THRESHOLDS = {
    "odds_drop_rate": 0.20,
    "odds_drop_rate_fast": 0.15,
    "time_window_minutes": 30,
    "min_odds_for_alert": 3.0,
    "max_odds_for_alert": 50.0,
}


# --- データクラス ---

@dataclass
class OddsSnapshot:
    """オッズスナップショット"""
    timestamp: str
    race_id: str
    race_num: int
    venue: str
    horses: List[Dict] = field(default_factory=list)


@dataclass
class InsiderAlert:
    """インサイダーアラート"""
    alert_id: str
    race_id: str
    race_num: int
    venue: str
    umaban: int
    horse_name: str
    odds_before: float
    odds_after: float
    drop_rate: float
    time_span_minutes: int
    detected_at: str
    confidence: float
    expected_value_boost: float
    aggressive_mode: bool
    status: str = "active"

    def to_dict(self) -> Dict:
        return asdict(self)


# --- ヘルパー関数 ---

def get_jst_now() -> datetime:
    """日本時間の現在時刻を取得"""
    try:
        import pytz
        jst = pytz.timezone('Asia/Tokyo')
        return datetime.now(jst)
    except ImportError:
        return datetime.now() + timedelta(hours=9)


def fetch_with_retry(url: str, encoding: str = 'euc-jp') -> Optional[str]:
    """リトライ機能付きHTTPリクエスト"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.encoding = encoding
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"[WARN] リクエストエラー (attempt {attempt + 1}): {e}")
            time.sleep(2)
    return None


# --- オッズ取得クラス ---

class OddsScraper:
    """netkeibaからオッズを取得"""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ODDS_DIR.mkdir(parents=True, exist_ok=True)

    def get_today_race_ids(self) -> List[Dict]:
        """本日のレースID一覧を取得"""
        now = get_jst_now()
        date_str = now.strftime("%Y%m%d")

        url = f"https://race.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
        html = fetch_with_retry(url, encoding='utf-8')

        if not html:
            print("[WARN] レース一覧を取得できませんでした")
            return []

        soup = BeautifulSoup(html, 'lxml')
        races = []

        # レースリンクを探す
        for link in soup.find_all('a', href=re.compile(r'/race/\d+')):
            href = link.get('href', '')
            match = re.search(r'/race/(\d+)', href)
            if match:
                race_id = match.group(1)

                # 競馬場とレース番号を抽出
                venue = ""
                race_num = 0

                # 親要素からテキストを取得
                text = link.get_text(strip=True)
                num_match = re.search(r'(\d+)R', text)
                if num_match:
                    race_num = int(num_match.group(1))

                # 競馬場名を探す
                parent = link.find_parent('div', class_='RaceList_DataItem')
                if parent:
                    venue_elem = parent.find_previous('span', class_='RaceList_DataTitle')
                    if venue_elem:
                        venue = venue_elem.get_text(strip=True)

                if race_id not in [r['race_id'] for r in races]:
                    races.append({
                        'race_id': race_id,
                        'race_num': race_num,
                        'venue': venue
                    })

        print(f"[INFO] {len(races)}レースを検出")
        return races

    def fetch_odds(self, race_id: str) -> Optional[Dict]:
        """指定レースのオッズを取得"""
        url = f"https://race.netkeiba.com/odds/index.html?race_id={race_id}&type=b1"
        html = fetch_with_retry(url, encoding='utf-8')

        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')
        horses = []

        # オッズテーブルを探す
        odds_table = soup.find('table', class_='RaceOdds_HorseList_Table')
        if not odds_table:
            # 別の形式を試す
            odds_table = soup.find('table', id='odds_tan_block')

        if odds_table:
            for row in odds_table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    try:
                        # 馬番
                        umaban_cell = cells[0]
                        umaban_text = umaban_cell.get_text(strip=True)
                        if not umaban_text.isdigit():
                            continue
                        umaban = int(umaban_text)

                        # 馬名
                        horse_name = ""
                        name_cell = cells[1] if len(cells) > 1 else None
                        if name_cell:
                            horse_name = name_cell.get_text(strip=True)

                        # オッズ
                        odds = 0.0
                        for cell in cells:
                            text = cell.get_text(strip=True)
                            odds_match = re.search(r'(\d+\.?\d*)', text)
                            if odds_match and '.' in text:
                                odds = float(odds_match.group(1))
                                break

                        if umaban > 0 and odds > 0:
                            horses.append({
                                'umaban': umaban,
                                'horse_name': horse_name,
                                'odds': odds
                            })
                    except Exception:
                        continue

        # 別の方法でオッズを取得
        if not horses:
            odds_spans = soup.find_all('span', class_='Odds')
            for i, span in enumerate(odds_spans):
                try:
                    odds_text = span.get_text(strip=True)
                    odds = float(odds_text)
                    horses.append({
                        'umaban': i + 1,
                        'horse_name': f"馬{i+1}",
                        'odds': odds
                    })
                except Exception:
                    continue

        if horses:
            return {
                'race_id': race_id,
                'timestamp': get_jst_now().strftime("%Y-%m-%d %H:%M:%S"),
                'horses': horses
            }

        return None

    def fetch_all_odds(self) -> List[Dict]:
        """全レースのオッズを取得"""
        races = self.get_today_race_ids()
        all_odds = []

        for race in races:
            race_id = race['race_id']
            print(f"  取得中: {race_id}")

            odds_data = self.fetch_odds(race_id)
            if odds_data:
                odds_data['venue'] = race.get('venue', '')
                odds_data['race_num'] = race.get('race_num', 0)
                all_odds.append(odds_data)

            time.sleep(REQUEST_INTERVAL)

        return all_odds

    def save_odds_snapshot(self, odds_list: List[Dict]) -> Path:
        """オッズスナップショットを保存"""
        now = get_jst_now()
        filename = f"odds_{now.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = ODDS_DIR / filename

        data = {
            'timestamp': now.strftime("%Y-%m-%d %H:%M:%S"),
            'races': odds_list
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[SAVED] {filepath}")
        return filepath


# --- インサイダー検知クラス ---

class InsiderDetector:
    """インサイダー（急激なオッズ変動）を検知"""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.alerts = self._load_alerts()
        self.state = self._load_state()

    def _load_alerts(self) -> Dict:
        """アラートを読み込み"""
        if ALERTS_FILE.exists():
            try:
                with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"alerts": [], "updated_at": ""}

    def _save_alerts(self):
        """アラートを保存"""
        self.alerts["updated_at"] = get_jst_now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.alerts, f, ensure_ascii=False, indent=2)

    def _load_state(self) -> Dict:
        """状態を読み込み"""
        if REALTIME_STATE_FILE.exists():
            try:
                with open(REALTIME_STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_odds": {}, "updated_at": ""}

    def _save_state(self):
        """状態を保存"""
        self.state["updated_at"] = get_jst_now().strftime("%Y-%m-%d %H:%M:%S")
        with open(REALTIME_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def get_previous_odds(self) -> List[Dict]:
        """直前のオッズスナップショットを取得"""
        odds_files = sorted(ODDS_DIR.glob("odds_*.json"), reverse=True)

        if len(odds_files) < 2:
            return []

        # 2番目に新しいファイル（前回のスナップショット）
        prev_file = odds_files[1]

        try:
            with open(prev_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('races', [])
        except Exception:
            return []

    def detect_insider(self, current_odds: List[Dict], previous_odds: List[Dict]) -> List[InsiderAlert]:
        """インサイダー（急激なオッズ変動）を検知"""
        alerts = []
        now = get_jst_now()

        # 前回のオッズをrace_id + umabanでインデックス化
        prev_index = {}
        for race in previous_odds:
            race_id = race.get('race_id', '')
            for horse in race.get('horses', []):
                key = f"{race_id}_{horse.get('umaban', 0)}"
                prev_index[key] = {
                    'odds': horse.get('odds', 0),
                    'horse_name': horse.get('horse_name', ''),
                    'venue': race.get('venue', ''),
                    'race_num': race.get('race_num', 0)
                }

        # 現在のオッズと比較
        for race in current_odds:
            race_id = race.get('race_id', '')
            venue = race.get('venue', '')
            race_num = race.get('race_num', 0)

            for horse in race.get('horses', []):
                umaban = horse.get('umaban', 0)
                current_odds_val = horse.get('odds', 0)
                horse_name = horse.get('horse_name', '')

                key = f"{race_id}_{umaban}"

                if key not in prev_index:
                    continue

                prev_data = prev_index[key]
                prev_odds_val = prev_data['odds']

                # オッズが有効範囲内かチェック
                if current_odds_val < INSIDER_THRESHOLDS['min_odds_for_alert']:
                    continue
                if current_odds_val > INSIDER_THRESHOLDS['max_odds_for_alert']:
                    continue

                # オッズ低下率を計算
                if prev_odds_val > 0 and current_odds_val > 0:
                    drop_rate = (prev_odds_val - current_odds_val) / prev_odds_val

                    # 20%以上の急落を検知
                    if drop_rate >= INSIDER_THRESHOLDS['odds_drop_rate']:
                        # 信頼度を計算（低下率が大きいほど高い）
                        confidence = min(1.0, drop_rate / 0.4)

                        # 期待値ブースト係数を計算
                        ev_boost = 1.0 + (drop_rate * 0.5)
                        ev_boost = min(1.35, ev_boost)

                        # Aggressiveモードを判定（30%以上の急落）
                        aggressive_mode = drop_rate >= 0.30

                        alert = InsiderAlert(
                            alert_id=f"{race_id}_{umaban}_{now.strftime('%H%M%S')}",
                            race_id=race_id,
                            race_num=race_num,
                            venue=venue or prev_data.get('venue', ''),
                            umaban=umaban,
                            horse_name=horse_name or prev_data.get('horse_name', ''),
                            odds_before=prev_odds_val,
                            odds_after=current_odds_val,
                            drop_rate=drop_rate,
                            time_span_minutes=10,
                            detected_at=now.strftime("%Y-%m-%d %H:%M:%S"),
                            confidence=confidence,
                            expected_value_boost=ev_boost,
                            aggressive_mode=aggressive_mode,
                            status="active"
                        )

                        alerts.append(alert)

                        print(f"\n🚨 インサイダー検知!")
                        print(f"   {venue} {race_num}R - {horse_name} (馬番{umaban})")
                        print(f"   オッズ: {prev_odds_val:.1f} → {current_odds_val:.1f} ({drop_rate*100:.1f}%低下)")
                        print(f"   信頼度: {confidence*100:.0f}%")
                        print(f"   期待値ブースト: {ev_boost:.2f}x")
                        if aggressive_mode:
                            print(f"   ⚡ Aggressiveモード有効")

        return alerts

    def update_alerts(self, new_alerts: List[InsiderAlert]):
        """アラートを更新"""
        # 既存のアラートを古いものは非アクティブに
        now = get_jst_now()
        for alert in self.alerts.get("alerts", []):
            detected_at = datetime.strptime(alert["detected_at"], "%Y-%m-%d %H:%M:%S")
            if (now - detected_at).total_seconds() > 3600:  # 1時間以上前
                alert["status"] = "expired"

        # 新しいアラートを追加
        for alert in new_alerts:
            # 重複チェック
            existing_ids = [a["alert_id"] for a in self.alerts.get("alerts", [])]
            if alert.alert_id not in existing_ids:
                self.alerts["alerts"].append(alert.to_dict())

        # 保存
        self._save_alerts()

    def run_detection(self, current_odds: List[Dict]) -> List[InsiderAlert]:
        """検知を実行"""
        previous_odds = self.get_previous_odds()

        if not previous_odds:
            print("[INFO] 前回のオッズデータがありません。次回から検知を開始します。")
            return []

        alerts = self.detect_insider(current_odds, previous_odds)

        if alerts:
            self.update_alerts(alerts)
            print(f"\n[INFO] {len(alerts)}件のインサイダーアラートを検出しました")
        else:
            print("\n[INFO] インサイダーは検出されませんでした")

        return alerts


# --- メイン処理 ---

def main():
    print("=" * 60)
    print("💹 UMA-Logic PRO - リアルタイムオッズ＆インサイダー探知")
    print("=" * 60)

    scraper = OddsScraper()
    detector = InsiderDetector()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--fetch":
            # オッズ取得のみ
            print("\n[INFO] オッズを取得中...")
            odds_list = scraper.fetch_all_odds()
            if odds_list:
                scraper.save_odds_snapshot(odds_list)
                print(f"\n✅ {len(odds_list)}レースのオッズを取得しました")
            else:
                print("\n[WARN] オッズを取得できませんでした")

        elif command == "--detect":
            # 検知のみ（既存データを使用）
            print("\n[INFO] インサイダー検知を実行中...")
            odds_files = sorted(ODDS_DIR.glob("odds_*.json"), reverse=True)
            if odds_files:
                with open(odds_files[0], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    current_odds = data.get('races', [])
                detector.run_detection(current_odds)
            else:
                print("[WARN] オッズデータがありません")

        elif command == "--status":
            # 現在の状態を表示
            print("\n📊 現在の状態")
            print("-" * 40)

            alerts = detector.alerts.get("alerts", [])
            active_alerts = [a for a in alerts if a.get("status") == "active"]

            print(f"アクティブアラート: {len(active_alerts)}件")
            print(f"総アラート数: {len(alerts)}件")
            print(f"最終更新: {detector.alerts.get('updated_at', 'N/A')}")

            if active_alerts:
                print("\n🚨 アクティブアラート:")
                for alert in active_alerts[:5]:
                    print(f"  - {alert.get('venue', '')} {alert.get('race_num', '')}R")
                    print(f"    {alert.get('horse_name', '')} (馬番{alert.get('umaban', '')})")
                    print(f"    オッズ: {alert.get('odds_before', 0):.1f} → {alert.get('odds_after', 0):.1f}")

        elif command == "--clear":
            # アラートをクリア
            detector.alerts = {"alerts": [], "updated_at": ""}
            detector._save_alerts()
            print("✅ アラートをクリアしました")

        else:
            print(f"[ERROR] 不明なコマンド: {command}")
            print("\n使用方法:")
            print("  --fetch   : オッズを取得")
            print("  --detect  : インサイダー検知を実行")
            print("  --status  : 現在の状態を表示")
            print("  --clear   : アラートをクリア")
            print("  (引数なし): オッズ取得＋インサイダー検知")

    else:
        # デフォルト: オッズ取得 + インサイダー検知
        print("\n[INFO] オッズを取得中...")
        odds_list = scraper.fetch_all_odds()

        if odds_list:
            scraper.save_odds_snapshot(odds_list)
            print(f"\n✅ {len(odds_list)}レースのオッズを取得しました")

            print("\n[INFO] インサイダー検知を実行中...")
            detector.run_detection(odds_list)
        else:
            print("\n[WARN] オッズを取得できませんでした")

    print("\n✅ 処理完了")


if __name__ == "__main__":
    main()
