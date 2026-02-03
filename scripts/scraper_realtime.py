# scripts/scraper_realtime.py
# UMA-Logic PRO - リアルタイムオッズスクレイパー＆インサイダー探知機
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
import sys

# --- 定数 ---
DATA_DIR = Path("data")
ODDS_DIR = DATA_DIR / "odds"
ALERTS_FILE = DATA_DIR / "insider_alerts.json"
REALTIME_STATE_FILE = DATA_DIR / "realtime_state.json"

MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}

# インサイダー検知閾値
INSIDER_THRESHOLDS = {
    "odds_drop_rate": 0.20,           # 20%以上のオッズ低下でアラート
    "odds_drop_rate_fast": 0.15,      # 10分以内に15%低下でアラート
    "time_window_minutes": 10,        # 急落判定の時間窓（分）
    "min_odds_for_alert": 3.0,        # アラート対象の最低オッズ
    "max_odds_for_alert": 50.0,       # アラート対象の最高オッズ
}


# --- データクラス ---

@dataclass
class OddsSnapshot:
    """オッズスナップショット"""
    timestamp: str
    race_id: str
    umaban: int
    horse_name: str
    odds: float
    popularity: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class InsiderAlert:
    """インサイダーアラート"""
    alert_id: str
    race_id: str
    race_name: str
    venue: str
    umaban: int
    horse_name: str
    alert_type: str           # "ODDS_DROP", "RAPID_DROP", "VOLUME_SPIKE"
    severity: str             # "HIGH", "MEDIUM", "LOW"
    initial_odds: float
    current_odds: float
    drop_rate: float
    detected_at: str
    time_to_race_minutes: int
    confidence: float
    aggressive_mode: bool = True
    expected_value_boost: float = 1.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RealtimeState:
    """リアルタイム状態管理"""
    last_update: str = ""
    active_alerts: List[Dict] = field(default_factory=list)
    odds_history: Dict[str, List[Dict]] = field(default_factory=dict)
    aggressive_mode_horses: List[str] = field(default_factory=list)


# --- ヘルパー関数 ---

def fetch_with_retry(url: str, encoding: str = 'euc-jp') -> Optional[str]:
    """リトライ機能付きHTTPリクエスト"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.encoding = encoding
            if response.status_code == 200:
                return response.text
            elif response.status_code == 404:
                return None
        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"[ERROR] リクエスト失敗: {url} - {e}")
    return None


def get_jst_now() -> datetime:
    """日本時間の現在時刻を取得"""
    try:
        import pytz
        jst = pytz.timezone('Asia/Tokyo')
        return datetime.now(jst)
    except ImportError:
        return datetime.now()


# --- インサイダー検知クラス ---

class InsiderDetector:
    """
    インサイダー取引検知エンジン
    オッズの急激な変動を監視し、不自然なパターンを検出
    """

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ODDS_DIR.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()
        self.alerts: List[InsiderAlert] = []
        self._load_alerts()

    def _load_state(self) -> RealtimeState:
        """状態を読み込み"""
        if REALTIME_STATE_FILE.exists():
            try:
                with open(REALTIME_STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    state = RealtimeState()
                    state.last_update = data.get("last_update", "")
                    state.active_alerts = data.get("active_alerts", [])
                    state.odds_history = data.get("odds_history", {})
                    state.aggressive_mode_horses = data.get("aggressive_mode_horses", [])
                    return state
            except Exception as e:
                print(f"[WARN] 状態ファイル読み込みエラー: {e}")
        return RealtimeState()

    def _save_state(self):
        """状態を保存"""
        data = {
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active_alerts": self.state.active_alerts,
            "odds_history": self.state.odds_history,
            "aggressive_mode_horses": self.state.aggressive_mode_horses
        }
        with open(REALTIME_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_alerts(self):
        """アラートを読み込み"""
        if ALERTS_FILE.exists():
            try:
                with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    alerts_data = data.get("alerts", [])
                    self.alerts = []
                    for alert in alerts_data:
                        try:
                            self.alerts.append(InsiderAlert(**alert))
                        except Exception:
                            continue
            except Exception as e:
                print(f"[WARN] アラートファイル読み込みエラー: {e}")
                self.alerts = []

    def _save_alerts(self):
        """アラートを保存"""
        data = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_alerts": len(self.alerts),
            "alerts": [alert.to_dict() for alert in self.alerts]
        }
        with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_odds(self, race_id: str, odds_data: List[Dict]):
        """オッズを記録"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if race_id not in self.state.odds_history:
            self.state.odds_history[race_id] = []

        snapshot = {
            "timestamp": timestamp,
            "odds": {}
        }

        for horse in odds_data:
            umaban = str(horse.get("umaban", 0))
            odds = horse.get("odds", 0)
            horse_name = horse.get("horse_name", "")
            if umaban and odds > 0:
                snapshot["odds"][umaban] = {
                    "odds": odds,
                    "horse_name": horse_name
                }

        self.state.odds_history[race_id].append(snapshot)

        # 古いデータを削除（2時間以上前）
        cutoff = datetime.now() - timedelta(hours=2)
        filtered_history = []
        for s in self.state.odds_history[race_id]:
            try:
                snap_time = datetime.strptime(s["timestamp"], "%Y-%m-%d %H:%M:%S")
                if snap_time > cutoff:
                    filtered_history.append(s)
            except Exception:
                continue
        self.state.odds_history[race_id] = filtered_history

        self._save_state()

    def detect_insider_activity(
        self,
        race_id: str,
        race_name: str,
        venue: str,
        current_odds: List[Dict],
        time_to_race_minutes: int = 60
    ) -> List[InsiderAlert]:
        """
        インサイダー活動を検知
        直近10分でオッズが20%以上急落した馬を検出
        """
        detected_alerts = []

        # オッズ履歴がない場合は記録のみ
        if race_id not in self.state.odds_history or len(self.state.odds_history[race_id]) < 2:
            self.record_odds(race_id, current_odds)
            return detected_alerts

        history = self.state.odds_history[race_id]

        # 10分前のスナップショットを取得
        time_window = datetime.now() - timedelta(minutes=INSIDER_THRESHOLDS["time_window_minutes"])
        baseline_snapshot = None

        for snapshot in history:
            try:
                snap_time = datetime.strptime(snapshot["timestamp"], "%Y-%m-%d %H:%M:%S")
                if snap_time <= time_window:
                    baseline_snapshot = snapshot
            except Exception:
                continue

        # 10分前のデータがない場合は最初のスナップショットを使用
        if baseline_snapshot is None and history:
            baseline_snapshot = history[0]

        if baseline_snapshot is None:
            self.record_odds(race_id, current_odds)
            return detected_alerts

        # 各馬のオッズ変動をチェック
        for horse in current_odds:
            umaban = horse.get("umaban", 0)
            horse_name = horse.get("horse_name", "")
            current = horse.get("odds", 0)

            # オッズ範囲チェック
            if current <= 0:
                continue
            if current < INSIDER_THRESHOLDS["min_odds_for_alert"]:
                continue
            if current > INSIDER_THRESHOLDS["max_odds_for_alert"]:
                continue

            # ベースラインオッズを取得
            umaban_str = str(umaban)
            if umaban_str not in baseline_snapshot.get("odds", {}):
                continue

            baseline_data = baseline_snapshot["odds"][umaban_str]
            initial_odds = baseline_data.get("odds", 0) if isinstance(baseline_data, dict) else baseline_data

            if initial_odds <= 0:
                continue

            # オッズ低下率を計算
            drop_rate = (initial_odds - current) / initial_odds

            # 検知ロジック
            alert = None

            # パターン1: 10分以内に20%以上のオッズ低下
            if drop_rate >= INSIDER_THRESHOLDS["odds_drop_rate"]:
                # 重大度判定
                if drop_rate >= 0.35:
                    severity = "HIGH"
                    confidence = min(0.95, 0.7 + drop_rate * 0.5)
                elif drop_rate >= 0.25:
                    severity = "HIGH"
                    confidence = min(0.90, 0.6 + drop_rate * 0.5)
                else:
                    severity = "MEDIUM"
                    confidence = min(0.85, 0.5 + drop_rate * 0.5)

                # 期待値ブースト係数（低下率に応じて1.1〜1.35）
                expected_value_boost = 1.0 + drop_rate * 0.5

                alert = InsiderAlert(
                    alert_id=f"{race_id}_{umaban}_{datetime.now().strftime('%H%M%S')}",
                    race_id=race_id,
                    race_name=race_name,
                    venue=venue,
                    umaban=umaban,
                    horse_name=horse_name,
                    alert_type="ODDS_DROP",
                    severity=severity,
                    initial_odds=initial_odds,
                    current_odds=current,
                    drop_rate=drop_rate,
                    detected_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    time_to_race_minutes=time_to_race_minutes,
                    confidence=confidence,
                    aggressive_mode=True,
                    expected_value_boost=expected_value_boost
                )

            # パターン2: 10分以内に15%以上の急落（より短時間）
            elif drop_rate >= INSIDER_THRESHOLDS["odds_drop_rate_fast"]:
                severity = "MEDIUM"
                confidence = min(0.80, 0.4 + drop_rate * 0.5)
                expected_value_boost = 1.0 + drop_rate * 0.4

                alert = InsiderAlert(
                    alert_id=f"{race_id}_{umaban}_{datetime.now().strftime('%H%M%S')}",
                    race_id=race_id,
                    race_name=race_name,
                    venue=venue,
                    umaban=umaban,
                    horse_name=horse_name,
                    alert_type="RAPID_DROP",
                    severity=severity,
                    initial_odds=initial_odds,
                    current_odds=current,
                    drop_rate=drop_rate,
                    detected_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    time_to_race_minutes=time_to_race_minutes,
                    confidence=confidence,
                    aggressive_mode=True,
                    expected_value_boost=expected_value_boost
                )

            if alert:
                # 重複チェック（同じレース・同じ馬のアラートは1つまで）
                existing = [a for a in self.alerts if a.race_id == race_id and a.umaban == umaban]
                if not existing:
                    self.alerts.append(alert)
                    detected_alerts.append(alert)

                    # Aggressiveモードリストに追加
                    key = f"{race_id}_{umaban}"
                    if key not in self.state.aggressive_mode_horses:
                        self.state.aggressive_mode_horses.append(key)

                    print(f"🚨 [INSIDER ALERT] {venue} {race_name}")
                    print(f"   {umaban}番 {horse_name}")
                    print(f"   オッズ: {initial_odds:.1f} → {current:.1f} ({drop_rate*100:.1f}%低下)")
                    print(f"   重大度: {severity} | 信頼度: {confidence*100:.0f}%")
                    print(f"   期待値ブースト: {expected_value_boost:.2f}x")
                else:
                    # 既存アラートを更新
                    for i, a in enumerate(self.alerts):
                        if a.race_id == race_id and a.umaban == umaban:
                            self.alerts[i].current_odds = current
                            self.alerts[i].drop_rate = drop_rate
                            break

        # オッズを記録
        self.record_odds(race_id, current_odds)

        # アラートを保存
        if detected_alerts:
            self._save_alerts()
            self._save_state()

        return detected_alerts

    def get_active_alerts(self, race_id: str = None) -> List[InsiderAlert]:
        """アクティブなアラートを取得"""
        if race_id:
            return [a for a in self.alerts if a.race_id == race_id]
        return self.alerts

    def is_aggressive_mode(self, race_id: str, umaban: int) -> bool:
        """指定馬がAggressiveモードかどうか"""
        key = f"{race_id}_{umaban}"
        return key in self.state.aggressive_mode_horses

    def get_expected_value_boost(self, race_id: str, umaban: int) -> float:
        """期待値ブースト係数を取得"""
        alerts = [a for a in self.alerts if a.race_id == race_id and a.umaban == umaban]
        if alerts:
            return max(a.expected_value_boost for a in alerts)
        return 1.0

    def clear_old_alerts(self, hours: int = 24):
        """古いアラートをクリア"""
        cutoff = datetime.now() - timedelta(hours=hours)
        self.alerts = [
            a for a in self.alerts
            if datetime.strptime(a.detected_at, "%Y-%m-%d %H:%M:%S") > cutoff
        ]
        self._save_alerts()


# --- オッズスクレイパークラス ---

class OddsScraper:
    """netkeibaからリアルタイムオッズを取得"""

    def __init__(self):
        self.detector = InsiderDetector()

    def get_today_race_ids(self) -> List[Dict]:
        """本日のレースID一覧を取得"""
        url = "https://race.netkeiba.com/top/race_list.html"
        html = fetch_with_retry(url, encoding='euc-jp')

        if not html:
            print("[ERROR] レースリストの取得に失敗しました")
            return []

        soup = BeautifulSoup(html, 'lxml')
        races = []

        # レースリストをパース
        for race_item in soup.select('.RaceList_DataItem'):
            try:
                link = race_item.select_one('a')
                if not link:
                    continue

                href = link.get('href', '')
                race_id_match = re.search(r'race_id=(\d+)', href)
                if not race_id_match:
                    continue

                race_id = race_id_match.group(1)

                # レース名を取得
                race_name_elem = race_item.select_one('.RaceName')
                race_name = race_name_elem.get_text(strip=True) if race_name_elem else ""

                # レース番号を取得
                race_num_elem = race_item.select_one('.RaceNum')
                race_num_text = race_num_elem.get_text(strip=True) if race_num_elem else ""
                race_num_match = re.search(r'(\d+)', race_num_text)
                race_num = int(race_num_match.group(1)) if race_num_match else 0

                # 競馬場を取得（レースIDから判定）
                venue_code = race_id[4:6] if len(race_id) >= 6 else ""
                venue_map = {
                    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
                    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
                    "09": "阪神", "10": "小倉"
                }
                venue = venue_map.get(venue_code, "不明")

                races.append({
                    "race_id": race_id,
                    "race_name": race_name,
                    "race_num": race_num,
                    "venue": venue
                })

            except Exception as e:
                continue

        return races

    def fetch_odds(self, race_id: str) -> Optional[List[Dict]]:
        """指定レースのオッズを取得"""
        url = f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}"
        html = fetch_with_retry(url, encoding='euc-jp')

        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')
        odds_data = []

        # オッズテーブルをパース
        for row in soup.select('table.RaceOdds_HorseList_Table tr'):
            try:
                cells = row.select('td')
                if len(cells) < 4:
                    continue

                # 馬番
                umaban_elem = cells[0].select_one('.Umaban, .Waku_Txt')
                if not umaban_elem:
                    continue
                umaban_text = umaban_elem.get_text(strip=True)
                umaban_match = re.search(r'(\d+)', umaban_text)
                if not umaban_match:
                    continue
                umaban = int(umaban_match.group(1))

                # 馬名
                horse_name_elem = row.select_one('.HorseName a, .Horse_Name a')
                horse_name = horse_name_elem.get_text(strip=True) if horse_name_elem else ""

                # オッズ
                odds_elem = row.select_one('.Odds, .Popular_Odds')
                if not odds_elem:
                    continue
                odds_text = odds_elem.get_text(strip=True)
                odds_text = re.sub(r'[^\d.]', '', odds_text)
                if not odds_text:
                    continue
                odds = float(odds_text)

                # 人気
                popularity = 0
                pop_elem = row.select_one('.Popular, .Ninki')
                if pop_elem:
                    pop_text = pop_elem.get_text(strip=True)
                    pop_match = re.search(r'(\d+)', pop_text)
                    if pop_match:
                        popularity = int(pop_match.group(1))

                odds_data.append({
                    "umaban": umaban,
                    "horse_name": horse_name,
                    "odds": odds,
                    "popularity": popularity
                })

            except Exception as e:
                continue

        return odds_data if odds_data else None

    def scan_all_races(self) -> Dict:
        """全レースをスキャンしてインサイダー検知"""
        print("\n" + "=" * 60)
        print("🔍 UMA-Logic PRO - リアルタイムオッズスキャン")
        print("=" * 60)

        races = self.get_today_race_ids()

        if not races:
            print("[INFO] 本日のレースがありません")
            return {"status": "no_races", "alerts": []}

        print(f"[INFO] {len(races)}レースを検出")

        all_alerts = []
        all_odds = {}

        for i, race in enumerate(races):
            race_id = race["race_id"]
            race_name = race["race_name"]
            venue = race["venue"]
            race_num = race["race_num"]

            print(f"\n[{i+1}/{len(races)}] {venue} {race_num}R {race_name}")

            odds_data = self.fetch_odds(race_id)

            if odds_data:
                print(f"  {len(odds_data)}頭のオッズを取得")

                # インサイダー検知
                alerts = self.detector.detect_insider_activity(
                    race_id=race_id,
                    race_name=race_name,
                    venue=venue,
                    current_odds=odds_data,
                    time_to_race_minutes=60
                )

                if alerts:
                    all_alerts.extend(alerts)

                # オッズを保存
                all_odds[race_id] = {
                    "race_name": race_name,
                    "venue": venue,
                    "race_num": race_num,
                    "odds": odds_data,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                print(f"  [WARN] オッズ取得失敗")

            time.sleep(REQUEST_INTERVAL)

        # オッズデータを保存
        today_str = datetime.now().strftime("%Y%m%d")
        odds_file = ODDS_DIR / f"odds_{today_str}.json"
        with open(odds_file, 'w', encoding='utf-8') as f:
            json.dump(all_odds, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 60)
        print(f"✅ スキャン完了")
        print(f"   取得レース: {len(all_odds)}件")
        print(f"   検出アラート: {len(all_alerts)}件")
        print("=" * 60)

        return {
            "status": "completed",
            "races_scanned": len(all_odds),
            "alerts": [a.to_dict() for a in all_alerts]
        }


# --- IntegratedCalculator連携クラス ---

class RealtimeIntegration:
    """
    IntegratedCalculatorとの連携
    インサイダー検知結果を期待値計算に反映
    """

    def __init__(self):
        self.detector = InsiderDetector()

    def get_adjusted_parameters(self, race_id: str, umaban: int, base_odds: float) -> Dict:
        """
        インサイダー検知に基づいて調整されたパラメータを取得
        """
        is_aggressive = self.detector.is_aggressive_mode(race_id, umaban)
        ev_boost = self.detector.get_expected_value_boost(race_id, umaban)

        alerts = self.detector.get_active_alerts(race_id)
        horse_alert = next((a for a in alerts if a.umaban == umaban), None)

        # ケリー乗数の決定
        if is_aggressive:
            if horse_alert and horse_alert.severity == "HIGH":
                kelly_multiplier = 1.5  # フルケリーの1.5倍
            else:
                kelly_multiplier = 1.2  # フルケリーの1.2倍
        else:
            kelly_multiplier = 0.5  # 通常はハーフケリー

        # 信頼度ブースト
        confidence_boost = 1.0
        if horse_alert:
            confidence_boost = 1.0 + horse_alert.confidence * 0.2

        return {
            "aggressive_mode": is_aggressive,
            "expected_value_boost": ev_boost,
            "kelly_multiplier": kelly_multiplier,
            "confidence_boost": confidence_boost,
            "alert_info": horse_alert.to_dict() if horse_alert else None
        }

    def calculate_adjusted_kelly(
        self,
        win_probability: float,
        odds: float,
        race_id: str,
        umaban: int,
        bankroll: float = 100000
    ) -> Dict:
        """
        インサイダー検知を考慮したケリー基準計算
        """
        params = self.get_adjusted_parameters(race_id, umaban, odds)

        # 基本ケリー計算
        if odds <= 1 or win_probability <= 0:
            return {
                "kelly_fraction": 0,
                "bet_amount": 0,
                "mode": "SKIP",
                "reason": "オッズまたは勝率が不正"
            }

        b = odds - 1
        q = 1 - win_probability

        # インサイダー検知による勝率調整
        adjusted_prob = win_probability * params["confidence_boost"]
        adjusted_prob = min(0.95, adjusted_prob)

        # ケリー基準
        kelly = (b * adjusted_prob - q) / b
        kelly = max(0, kelly)

        # モード別の乗数適用
        kelly_multiplier = params["kelly_multiplier"]
        final_kelly = kelly * kelly_multiplier

        # 上限設定（最大25%）
        final_kelly = min(0.25, final_kelly)

        # 賭け金計算
        bet_amount = bankroll * final_kelly
        bet_amount = max(0, round(bet_amount / 100) * 100)

        # モード判定
        if params["aggressive_mode"]:
            mode = "AGGRESSIVE"
            reason = f"インサイダー検知 (EV boost: {params['expected_value_boost']:.2f}x)"
        elif kelly_multiplier >= 1.0:
            mode = "NORMAL"
            reason = "通常モード"
        else:
            mode = "CONSERVATIVE"
            reason = "保守的モード（ハーフケリー）"

        return {
            "kelly_fraction": final_kelly,
            "bet_amount": bet_amount,
            "mode": mode,
            "reason": reason,
            "adjusted_probability": adjusted_prob,
            "alert_info": params["alert_info"]
        }


# --- メイン処理 ---

def main():
    print("=" * 60)
    print("🔍 UMA-Logic PRO - リアルタイムオッズスクレイパー")
    print("=" * 60)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--scan":
            # 全レーススキャン
            scraper = OddsScraper()
            result = scraper.scan_all_races()
            print(f"\n結果: {result['status']}")

        elif command == "--test":
            # テストモード
            print("\n📊 インサイダー検知テスト")
            detector = InsiderDetector()
            integration = RealtimeIntegration()

            # 初期オッズを記録
            initial_odds = [
                {"umaban": 1, "horse_name": "テストホース1", "odds": 5.0},
                {"umaban": 2, "horse_name": "テストホース2", "odds": 8.0},
                {"umaban": 3, "horse_name": "テストホース3", "odds": 12.0},
            ]
            detector.record_odds("TEST001", initial_odds)

            print("  初期オッズを記録しました")
            time.sleep(1)

            # オッズ変動をシミュレート（20%以上の低下）
            changed_odds = [
                {"umaban": 1, "horse_name": "テストホース1", "odds": 3.5},  # 30%低下
                {"umaban": 2, "horse_name": "テストホース2", "odds": 7.5},  # 6%低下
                {"umaban": 3, "horse_name": "テストホース3", "odds": 9.0},  # 25%低下
            ]

            alerts = detector.detect_insider_activity(
                race_id="TEST001",
                race_name="テストレース",
                venue="東京",
                current_odds=changed_odds,
                time_to_race_minutes=30
            )

            print(f"\n検出されたアラート: {len(alerts)}件")

            # ケリー基準テスト
            print("\n📈 ケリー基準計算テスト（資金10万円）")
            for horse in changed_odds:
                result = integration.calculate_adjusted_kelly(
                    win_probability=0.2,
                    odds=horse["odds"],
                    race_id="TEST001",
                    umaban=horse["umaban"],
                    bankroll=100000
                )
                print(f"\n  {horse['umaban']}番 {horse['horse_name']} (オッズ: {horse['odds']})")
                print(f"    モード: {result['mode']}")
                print(f"    ケリー: {result['kelly_fraction']*100:.1f}%")
                print(f"    推奨額: ¥{result['bet_amount']:,}")
                print(f"    理由: {result['reason']}")

        elif command == "--status":
            # アラート状態表示
            detector = InsiderDetector()
            alerts = detector.get_active_alerts()
            print(f"\n📋 アクティブアラート: {len(alerts)}件")
            for alert in alerts:
                print(f"\n  [{alert.severity}] {alert.venue} {alert.race_name}")
                print(f"    {alert.umaban}番 {alert.horse_name}")
                print(f"    オッズ: {alert.initial_odds:.1f} → {alert.current_odds:.1f} ({alert.drop_rate*100:.1f}%低下)")
                print(f"    検出時刻: {alert.detected_at}")

        elif command == "--clear":
            # アラートクリア
            detector = InsiderDetector()
            detector.clear_old_alerts(hours=0)
            print("✅ アラートをクリアしました")

        else:
            print(f"[ERROR] 不明なコマンド: {command}")
            print("\n使用方法:")
            print("  --scan   : 全レースをスキャンしてインサイダー検知")
            print("  --test   : テストモードで実行")
            print("  --status : アクティブアラートを表示")
            print("  --clear  : アラートをクリア")

    else:
        # デフォルト: スキャン実行
        scraper = OddsScraper()
        result = scraper.scan_all_races()

    print("\n✅ 処理完了")


if __name__ == "__main__":
    main()
