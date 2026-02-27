# scripts/notifier.py
# UMA-Logic PRO - 通知機能（Discord/LINE/Slack対応）
# 完全版（Full Code）- そのままコピー＆ペーストで動作

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys

# --- 定数 ---
DATA_DIR = Path("data")
PREDICTIONS_PREFIX = "predictions_"
RESULTS_PREFIX = "results_"
ALERTS_FILE = DATA_DIR / "insider_alerts.json"
HISTORY_FILE = DATA_DIR / "history.json"
WEIGHTS_FILE = DATA_DIR / "models" / "weights.json"

# 環境変数から取得
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
LINE_NOTIFY_TOKEN = os.environ.get("LINE_NOTIFY_TOKEN", "")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", "")


# --- 通知クラス ---

class Notifier:
    """
    マルチプラットフォーム通知クラス
    Discord, LINE Notify, Slack に対応
    """

    def __init__(self):
        self.discord_webhook = DISCORD_WEBHOOK
        self.line_token = LINE_NOTIFY_TOKEN
        self.slack_webhook = SLACK_WEBHOOK
        self.available_platforms = self._check_platforms()

    def _check_platforms(self) -> List[str]:
        """利用可能なプラットフォームを確認"""
        platforms = []
        if self.discord_webhook:
            platforms.append("discord")
        if self.line_token:
            platforms.append("line")
        if self.slack_webhook:
            platforms.append("slack")
        return platforms

    def send_discord(self, title: str, message: str, color: int = 0x4ade80, fields: List[Dict] = None) -> bool:
        """Discordに通知を送信"""
        if not self.discord_webhook:
            return False

        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "UMA-Logic PRO"}
        }

        if fields:
            embed["fields"] = fields

        payload = {
            "embeds": [embed]
        }

        try:
            response = requests.post(
                self.discord_webhook,
                json=payload,
                timeout=10
            )
            return response.status_code == 204
        except Exception as e:
            print(f"[ERROR] Discord送信エラー: {e}")
            return False

    def send_line(self, message: str) -> bool:
        """LINE Notifyに通知を送信"""
        if not self.line_token:
            return False

        headers = {
            "Authorization": f"Bearer {self.line_token}"
        }

        payload = {
            "message": message
        }

        try:
            response = requests.post(
                "https://notify-api.line.me/api/notify",
                headers=headers,
                data=payload,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"[ERROR] LINE送信エラー: {e}")
            return False

    def send_slack(self, title: str, message: str, color: str = "#4ade80", fields: List[Dict] = None) -> bool:
        """Slackに通知を送信"""
        if not self.slack_webhook:
            return False

        attachment = {
            "color": color,
            "title": title,
            "text": message,
            "footer": "UMA-Logic PRO",
            "ts": int(datetime.now().timestamp())
        }

        if fields:
            attachment["fields"] = [
                {"title": f["name"], "value": f["value"], "short": True}
                for f in fields
            ]

        payload = {
            "attachments": [attachment]
        }

        try:
            response = requests.post(
                self.slack_webhook,
                json=payload,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"[ERROR] Slack送信エラー: {e}")
            return False

    def send_all(self, title: str, message: str, color: int = 0x4ade80, fields: List[Dict] = None):
        """全プラットフォームに通知を送信"""
        results = {}

        if "discord" in self.available_platforms:
            results["discord"] = self.send_discord(title, message, color, fields)

        if "line" in self.available_platforms:
            # LINEはシンプルなテキストのみ
            line_message = f"\n{title}\n\n{message}"
            if fields:
                for f in fields:
                    line_message += f"\n{f['name']}: {f['value']}"
            results["line"] = self.send_line(line_message)

        if "slack" in self.available_platforms:
            slack_color = f"#{color:06x}" if isinstance(color, int) else color
            results["slack"] = self.send_slack(title, message, slack_color, fields)

        return results


# --- 通知タイプ別関数 ---

def notify_predictions(status: str = "success"):
    """予想データ取得完了通知"""
    notifier = Notifier()

    if not notifier.available_platforms:
        print("[INFO] 通知プラットフォームが設定されていません")
        return

    # 本日の予想を読み込み
    today_str = datetime.now().strftime("%Y%m%d")
    pred_file = DATA_DIR / f"{PREDICTIONS_PREFIX}{today_str}.json"

    title = "🐎 予想データ取得完了"
    message = f"本日 ({datetime.now().strftime('%m/%d')}) の予想データを取得しました。"
    color = 0x4ade80 if status == "success" else 0xef4444
    fields = []

    if pred_file.exists():
        try:
            with open(pred_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            races = data.get("races", [])
            fields.append({"name": "📊 レース数", "value": f"{len(races)}レース", "inline": True})

            # 推奨馬をピックアップ
            top_picks = []
            for race in races[:3]:
                venue = race.get("venue", "")
                race_num = race.get("race_num", 0)
                top3 = race.get("top3", [])
                if top3:
                    horse = top3[0]
                    horse_name = horse.get("horse_name", horse.get("馬名", ""))
                    top_picks.append(f"{venue}{race_num}R: {horse_name}")

            if top_picks:
                fields.append({"name": "🎯 注目馬", "value": "\n".join(top_picks), "inline": False})

        except Exception as e:
            print(f"[WARN] 予想データ読み込みエラー: {e}")

    results = notifier.send_all(title, message, color, fields)
    print(f"[INFO] 通知送信結果: {results}")


def notify_results(status: str = "success"):
    """レース結果取得完了通知"""
    notifier = Notifier()

    if not notifier.available_platforms:
        print("[INFO] 通知プラットフォームが設定されていません")
        return

    today_str = datetime.now().strftime("%Y%m%d")
    results_file = DATA_DIR / f"{RESULTS_PREFIX}{today_str}.json"

    title = "📊 レース結果取得完了"
    message = f"本日 ({datetime.now().strftime('%m/%d')}) のレース結果を取得しました。"
    color = 0x60a5fa
    fields = []

    if results_file.exists():
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            races = data.get("races", [])
            fields.append({"name": "📊 レース数", "value": f"{len(races)}レース", "inline": True})
        except Exception:
            pass

    # 的中情報を確認
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
            today_hits = [h for h in history if h.get("date") == today_str]
            if today_hits:
                total_payout = sum(h.get("payout", 0) for h in today_hits)
                fields.append({"name": "🎉 本日の的中", "value": f"{len(today_hits)}件", "inline": True})
                fields.append({"name": "💰 払戻金", "value": f"¥{total_payout:,}", "inline": True})
                color = 0x4ade80  # 的中があれば緑色
        except Exception:
            pass

    results = notifier.send_all(title, message, color, fields)
    print(f"[INFO] 通知送信結果: {results}")


def notify_optimize(status: str = "success"):
    """
    AI学習完了通知
    weights.json の正しい階層構造を読み取る
    
    weights.json の構造:
    {
        "weights": { "SpeedAgent": 0.35, ... },
        "train_metrics": { "hit_rate": 0.46, "recovery_rate": 1.26, ... },
        "test_metrics": { "hit_rate": 0.44, "recovery_rate": 1.21, ... },
        "metrics": { ... }
    }
    """
    notifier = Notifier()

    if not notifier.available_platforms:
        print("[INFO] 通知プラットフォームが設定されていません")
        return

    title = "🧠 AI学習完了"
    message = "エージェントの重み最適化が完了しました。"
    color = 0xa855f7 if status == "success" else 0xef4444
    fields = []

    # 新しい重みを読み込み
    if WEIGHTS_FILE.exists():
        try:
            with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
                weights_data = json.load(f)
            
            # エージェントの重みを表示
            agent_weights = weights_data.get("weights", {})
            for agent, weight in agent_weights.items():
                # "SpeedAgent" -> "Speed" に変換
                agent_name = agent.replace("Agent", "")
                fields.append({
                    "name": f"⚖️ {agent_name}",
                    "value": f"{weight:.2%}",
                    "inline": True
                })
            
            # Train メトリクスを表示
            train_metrics = weights_data.get("train_metrics", {})
            if train_metrics:
                train_years = train_metrics.get("years", [])
                train_hit_rate = train_metrics.get("hit_rate", 0)
                train_recovery = train_metrics.get("recovery_rate", 0)
                
                fields.append({
                    "name": f"📊 Train ({', '.join(map(str, train_years))})",
                    "value": f"的中率: {train_hit_rate:.1%}\n回収率: {train_recovery:.1%}",
                    "inline": True
                })
            
            # Test メトリクスを表示
            test_metrics = weights_data.get("test_metrics", {})
            if test_metrics:
                test_years = test_metrics.get("years", [])
                test_hit_rate = test_metrics.get("hit_rate", 0)
                test_recovery = test_metrics.get("recovery_rate", 0)
                
                fields.append({
                    "name": f"📈 Test ({', '.join(map(str, test_years))})",
                    "value": f"的中率: {test_hit_rate:.1%}\n回収率: {test_recovery:.1%}",
                    "inline": True
                })
            
            # 過学習チェック
            if train_metrics and test_metrics:
                train_recovery = train_metrics.get("recovery_rate", 0)
                test_recovery = test_metrics.get("recovery_rate", 0)
                
                if test_recovery > 0:
                    overfit_ratio = train_recovery / test_recovery
                    if overfit_ratio > 2.0:
                        overfit_status = "⚠️ 過学習の可能性"
                        color = 0xef4444  # 赤
                    elif overfit_ratio > 1.5:
                        overfit_status = "⚡ 軽度の過学習"
                        color = 0xfbbf24  # 黄
                    else:
                        overfit_status = "✅ 良好"
                    
                    fields.append({
                        "name": "🔍 過学習チェック",
                        "value": f"{overfit_status}\n(Train/Test比: {overfit_ratio:.2f})",
                        "inline": True
                    })
            
            # 更新日時
            updated_at = weights_data.get("updated_at", "")
            if updated_at:
                fields.append({
                    "name": "🕐 更新日時",
                    "value": updated_at,
                    "inline": True
                })

        except Exception as e:
            print(f"[WARN] 重みファイル読み込みエラー: {e}")
            fields.append({
                "name": "⚠️ エラー",
                "value": str(e),
                "inline": False
            })

    results = notifier.send_all(title, message, color, fields)
    print(f"[INFO] 通知送信結果: {results}")


def notify_odds(insider_count: int = 0):
    """オッズ取得・インサイダー検知通知"""
    notifier = Notifier()

    if not notifier.available_platforms:
        print("[INFO] 通知プラットフォームが設定されていません")
        return

    title = "💹 オッズ更新"
    message = f"リアルタイムオッズを取得しました。"
    color = 0xfbbf24
    fields = []

    # インサイダーアラートを確認
    if ALERTS_FILE.exists():
        try:
            with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
                alerts_data = json.load(f)
            active_alerts = [a for a in alerts_data.get("alerts", []) if a.get("status") == "active"]

            if active_alerts:
                color = 0xef4444  # アラートがあれば赤色
                title = "🚨 インサイダーアラート検知！"
                message = f"{len(active_alerts)}件のインサイダーアラートを検知しました！"

                for alert in active_alerts[:3]:
                    venue = alert.get("venue", "")
                    race_num = alert.get("race_num", "")
                    horse_name = alert.get("horse_name", "")
                    odds_before = alert.get("odds_before", 0)
                    odds_after = alert.get("odds_after", 0)
                    drop_rate = alert.get("drop_rate", 0)

                    fields.append({
                        "name": f"⚠️ {venue} {race_num}R",
                        "value": f"{horse_name}\n{odds_before:.1f} → {odds_after:.1f} ({drop_rate*100:.1f}%↓)",
                        "inline": True
                    })

        except Exception as e:
            print(f"[WARN] アラートファイル読み込みエラー: {e}")

    results = notifier.send_all(title, message, color, fields)
    print(f"[INFO] 通知送信結果: {results}")


def notify_historical(status: str = "success"):
    """過去データ取得完了通知"""
    notifier = Notifier()

    if not notifier.available_platforms:
        print("[INFO] 通知プラットフォームが設定されていません")
        return

    title = "📚 過去データ取得完了"
    message = "過去データの一括取得が完了しました。"
    color = 0x06b6d4 if status == "success" else 0xef4444
    fields = []

    # アーカイブ統計を取得
    archive_dir = DATA_DIR / "archive"
    if archive_dir.exists():
        try:
            years = [d.name for d in archive_dir.iterdir() if d.is_dir() and d.name.isdigit()]
            if years:
                fields.append({
                    "name": "📅 取得年",
                    "value": ", ".join(sorted(years)),
                    "inline": True
                })
        except Exception:
            pass

    results = notifier.send_all(title, message, color, fields)
    print(f"[INFO] 通知送信結果: {results}")


def notify_error(error_type: str, error_message: str):
    """エラー通知"""
    notifier = Notifier()

    if not notifier.available_platforms:
        print("[INFO] 通知プラットフォームが設定されていません")
        return

    title = f"❌ エラー発生: {error_type}"
    message = error_message
    color = 0xef4444
    fields = [
        {"name": "🕐 発生時刻", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "inline": True}
    ]

    results = notifier.send_all(title, message, color, fields)
    print(f"[INFO] 通知送信結果: {results}")


# --- メイン ---

def main():
    """コマンドライン引数に基づいて通知を送信"""
    import argparse

    parser = argparse.ArgumentParser(description="UMA-Logic PRO 通知システム")
    parser.add_argument("--type", choices=["predictions", "results", "optimize", "odds", "historical", "error"],
                        required=True, help="通知タイプ")
    parser.add_argument("--status", default="success", help="ステータス（success/failure）")
    parser.add_argument("--error-message", default="", help="エラーメッセージ（typeがerrorの場合）")

    args = parser.parse_args()

    if args.type == "predictions":
        notify_predictions(args.status)
    elif args.type == "results":
        notify_results(args.status)
    elif args.type == "optimize":
        notify_optimize(args.status)
    elif args.type == "odds":
        notify_odds()
    elif args.type == "historical":
        notify_historical(args.status)
    elif args.type == "error":
        notify_error("Unknown", args.error_message)


if __name__ == "__main__":
    main()
