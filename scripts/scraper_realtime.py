# scripts/scraper_realtime.py
# UMA-Logic PRO - リアルタイムスクレイパー＆インサイダー探知機
# オッズ変動監視 + インサイダーアラート + ケリー基準連動

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

# --- 定数 ---
DATA_DIR = Path("data")
ODDS_DIR = DATA_DIR / "odds"
ALERTS_FILE = DATA_DIR / "insider_alerts.json"
REALTIME_STATE_FILE = DATA_DIR / "realtime_state.json"

MAX_RETRIES = 3
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# インサイダー検知閾値
INSIDER_THRESHOLDS = {
    "odds_drop_rate": 0.20,      # 20%以上のオッズ低下
    "odds_drop_rate_fast": 0.15, # 15分以内に15%低下
    "volume_spike": 2.0,         # 通常の2倍以上の売れ行き
    "time_window_minutes": 30,   # 監視時間窓（分）
    "min_odds_for_alert": 3.0,   # アラート対象の最低オッズ
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
    popularity: int


@dataclass
class InsiderAlert:
    """インサイダーアラート"""
    alert_id: str
    race_id: str
    race_name: str
    venue: str
    umaban: int
    horse_name: str
    alert_type: str  # "ODDS_DROP", "VOLUME_SPIKE", "PATTERN_MATCH"
    severity: str    # "HIGH", "MEDIUM", "LOW"
    initial_odds: float
    current_odds: float
    drop_rate: float
    detected_at: str
    time_to_race_minutes: int
    confidence: float
    aggressive_mode: bool = True  # ケリー基準をAggressiveに変更
    expected_value_boost: float = 1.0  # 期待値ブースト係数
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RealtimeState:
    """リアルタイム状態管理"""
    last_update: str = ""
    active_alerts: List[Dict] = field(default_factory=list)
    odds_history: Dict[str, List[Dict]] = field(default_factory=dict)  # race_id -> [snapshots]
    aggressive_mode_horses: List[str] = field(default_factory=list)  # "race_id_umaban" のリスト


# --- インサイダー検知クラス ---

class InsiderDetector:
    """
    インサイダー取引検知エンジン
    オッズの急激な変動を監視し、不自然なパターンを検出
    """
    
    def __init__(self):
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
            except:
                pass
        return RealtimeState()
    
    def _save_state(self):
        """状態を保存"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
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
                    self.alerts = [
                        InsiderAlert(**alert) for alert in data.get("alerts", [])
                    ]
            except:
                self.alerts = []
    
    def _save_alerts(self):
        """アラートを保存"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        data = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            "odds": {str(h["umaban"]): h["odds"] for h in odds_data}
        }
        
        self.state.odds_history[race_id].append(snapshot)
        
        # 古いデータを削除（2時間以上前）
        cutoff = datetime.now() - timedelta(hours=2)
        self.state.odds_history[race_id] = [
            s for s in self.state.odds_history[race_id]
            if datetime.strptime(s["timestamp"], "%Y-%m-%d %H:%M:%S") > cutoff
        ]
        
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
        Returns: 検知されたアラートのリスト
        """
        detected_alerts = []
        
        # オッズ履歴がない場合は記録のみ
        if race_id not in self.state.odds_history or len(self.state.odds_history[race_id]) < 2:
            self.record_odds(race_id, current_odds)
            return detected_alerts
        
        history = self.state.odds_history[race_id]
        
        for horse in current_odds:
            umaban = horse.get("umaban", 0)
            horse_name = horse.get("horse_name", "")
            current = horse.get("odds", 0)
            
            if current <= 0 or current < INSIDER_THRESHOLDS["min_odds_for_alert"]:
                continue
            
            # 最初のオッズを取得
            initial_odds = None
            for snapshot in history:
                if str(umaban) in snapshot["odds"]:
                    initial_odds = snapshot["odds"][str(umaban)]
                    break
            
            if initial_odds is None or initial_odds <= 0:
                continue
            
            # オッズ低下率を計算
            drop_rate = (initial_odds - current) / initial_odds
            
            # 検知ロジック
            alert = None
            
            # パターン1: 急激なオッズ低下
            if drop_rate >= INSIDER_THRESHOLDS["odds_drop_rate"]:
                severity = "HIGH" if drop_rate >= 0.30 else "MEDIUM"
                confidence = min(0.95, 0.5 + drop_rate)
                
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
                    expected_value_boost=1.0 + drop_rate * 0.5  # 低下率に応じてブースト
                )
            
            # パターン2: 短時間での急落（15分以内）
            elif drop_rate >= INSIDER_THRESHOLDS["odds_drop_rate_fast"]:
                recent_cutoff = datetime.now() - timedelta(minutes=15)
                recent_snapshots = [
                    s for s in history
                    if datetime.strptime(s["timestamp"], "%Y-%m-%d %H:%M:%S") > recent_cutoff
                ]
                
                if recent_snapshots:
                    recent_initial = None
                    for s in recent_snapshots:
                        if str(umaban) in s["odds"]:
                            recent_initial = s["odds"][str(umaban)]
                            break
                    
                    if recent_initial and recent_initial > 0:
                        recent_drop = (recent_initial - current) / recent_initial
                        
                        if recent_drop >= INSIDER_THRESHOLDS["odds_drop_rate_fast"]:
                            alert = InsiderAlert(
                                alert_id=f"{race_id}_{umaban}_{datetime.now().strftime('%H%M%S')}",
                                race_id=race_id,
                                race_name=race_name,
                                venue=venue,
                                umaban=umaban,
                                horse_name=horse_name,
                                alert_type="RAPID_DROP",
                                severity="HIGH",
                                initial_odds=recent_initial,
                                current_odds=current,
                                drop_rate=recent_drop,
                                detected_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                time_to_race_minutes=time_to_race_minutes,
                                confidence=min(0.95, 0.6 + recent_drop),
                                aggressive_mode=True,
                                expected_value_boost=1.0 + recent_drop * 0.7
                            )
            
            # パターン3: 人気急上昇（順位変動）
            # TODO: 人気順位の変動も追跡
            
            if alert:
                # 重複チェック
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
                    print(f"   信頼度: {alert.confidence*100:.0f}% | 期待値ブースト: {alert.expected_value_boost:.2f}x")
        
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
        
        Returns:
            {
                "aggressive_mode": bool,
                "expected_value_boost": float,
                "kelly_multiplier": float,
                "confidence_boost": float,
                "alert_info": Optional[Dict]
            }
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
        
        Returns:
            {
                "kelly_fraction": float,
                "bet_amount": float,
                "mode": str,  # "CONSERVATIVE", "NORMAL", "AGGRESSIVE"
                "reason": str
            }
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
        adjusted_prob = min(0.95, adjusted_prob)  # 上限95%
        
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
        bet_amount = max(0, round(bet_amount / 100) * 100)  # 100円単位
        
        # モード判定
        if params["aggressive_mode"]:
            mode = "AGGRESSIVE"
            reason = f"インサイダー検知 (EV boost: {params['expected_value_boost']:.2f}x)"
        elif kelly_multiplier >= 1.0:
            mode = "NORMAL"
            reason = "通常モード"
        else:
            mode = "CONSERVATIVE"
            reason = "保守的モード"
        
        return {
            "kelly_fraction": final_kelly,
            "bet_amount": bet_amount,
            "mode": mode,
            "reason": reason,
            "adjusted_probability": adjusted_prob,
            "alert_info": params["alert_info"]
        }


# --- オッズスクレイパー ---

class OddsScraper:
    """リアルタイムオッズ取得"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.detector = InsiderDetector()
    
    def fetch_odds(self, race_id: str) -> Optional[List[Dict]]:
        """オッズを取得"""
        url = f"https://race.netkeiba.com/odds/index.html?race_id={race_id}"
        
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT )
            response.encoding = 'euc-jp'
            
            soup = BeautifulSoup(response.text, 'lxml')
            odds_data = []
            
            # オッズテーブルをパース
            for row in soup.select('table tr'):
                cells = row.select('td')
                if len(cells) >= 4:
                    try:
                        umaban = int(cells[1].get_text(strip=True))
                        horse_name = cells[2].get_text(strip=True)
                        odds_text = cells[3].get_text(strip=True)
                        odds = float(odds_text.replace(',', ''))
                        
                        odds_data.append({
                            "umaban": umaban,
                            "horse_name": horse_name,
                            "odds": odds
                        })
                    except:
                        continue
            
            return odds_data if odds_data else None
            
        except Exception as e:
            print(f"[ERROR] オッズ取得エラー: {e}")
            return None
    
    def monitor_race(
        self,
        race_id: str,
        race_name: str,
        venue: str,
        interval_seconds: int = 60,
        duration_minutes: int = 30
    ):
        """
        レースを監視してインサイダー検知
        """
        print(f"\n🔍 監視開始: {venue} {race_name}")
        print(f"   レースID: {race_id}")
        print(f"   監視間隔: {interval_seconds}秒")
        print(f"   監視時間: {duration_minutes}分")
        
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        
        while datetime.now() < end_time:
            odds_data = self.fetch_odds(race_id)
            
            if odds_data:
                time_to_race = int((end_time - datetime.now()).total_seconds() / 60)
                
                alerts = self.detector.detect_insider_activity(
                    race_id=race_id,
                    race_name=race_name,
                    venue=venue,
                    current_odds=odds_data,
                    time_to_race_minutes=time_to_race
                )
                
                if alerts:
                    print(f"\n⚠️ {len(alerts)}件の新規アラート検出")
            
            time.sleep(interval_seconds)
        
        print(f"\n✅ 監視終了: {venue} {race_name}")


# --- メイン処理 ---

def main():
    import sys
    
    print("=" * 60)
    print("🔍 UMA-Logic PRO - インサイダー探知機")
    print("=" * 60)
    
    detector = InsiderDetector()
    integration = RealtimeIntegration()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--test":
            # テストデータでシミュレーション
            print("\n📊 インサイダー検知テスト")
            
            # 初期オッズを記録
            initial_odds = [
                {"umaban": 1, "horse_name": "テストホース1", "odds": 5.0},
                {"umaban": 2, "horse_name": "テストホース2", "odds": 8.0},
                {"umaban": 3, "horse_name": "テストホース3", "odds": 12.0},
            ]
            detector.record_odds("TEST001", initial_odds)
            
            time.sleep(1)
            
            # オッズ変動をシミュレート
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
            print("\n📈 ケリー基準計算テスト")
            for horse in changed_odds:
                result = integration.calculate_adjusted_kelly(
                    win_probability=0.2,
                    odds=horse["odds"],
                    race_id="TEST001",
                    umaban=horse["umaban"],
                    bankroll=100000
                )
                print(f"  {horse['umaban']}番 {horse['horse_name']}")
                print(f"    モード: {result['mode']}")
                print(f"    ケリー: {result['kelly_fraction']*100:.1f}%")
                print(f"    推奨額: ¥{result['bet_amount']:,}")
        
        elif command == "--status":
            alerts = detector.get_active_alerts()
            print(f"\n📋 アクティブアラート: {len(alerts)}件")
            for alert in alerts:
                print(f"  [{alert.severity}] {alert.venue} {alert.race_name}")
                print(f"    {alert.umaban}番 {alert.horse_name}")
                print(f"    オッズ: {alert.initial_odds:.1f} → {alert.current_odds:.1f}")
        
        elif command == "--clear":
            detector.clear_old_alerts(hours=0)
            print("✅ アラートをクリアしました")
    
    else:
        print("\n使用方法:")
        print("  --test   : テストモードで実行")
        print("  --status : アクティブアラートを表示")
        print("  --clear  : アラートをクリア")
    
    print("\n✅ 処理完了")


if __name__ == "__main__":
    main()
