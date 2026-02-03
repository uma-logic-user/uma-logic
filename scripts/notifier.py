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
    """AI学習完了通知"""
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
                weights = json.load(f)
            
            agent_weights = weights.get("weights", {})
            for agent, weight in agent_weights.items():
                agent_name = agent.replace("_agent", "").title()
                fields.append({"name": f"⚖️ {agent_name}", "value": f"{weight:.2%}", "inline": True})

            metrics = weights.get("optimization_metrics", {})
            if metrics:
                fields.append({"name": "📈 的中率", "value": f"{metrics.get('hit_rate', 0):.1%}", "inline": True})
                fields.append({"name": "💰 回収率", "value": f"{metrics.get('roi', 0):.1%}", "inline": True})

        except Exception as e:
            print(f"[WARN] 重みファイル読み込みエラー: {e}")

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
        total_files = len(list(archive_dir.glob("**/*.json")))
        fields.append({"name": "📁 ファイル数", "value": f"{total_files}件", "inline": True})

    results = notifier.send_all(title, message, color, fields)
    print(f"[INFO] 通知送信結果: {results}")


def notify_hit(hit_info: Dict):
    """的中通知（即座に送信）"""
    notifier = Notifier()

    if not notifier.available_platforms:
        return

    title = "🎉 的中！"
    venue = hit_info.get("venue", "")
    race_num = hit_info.get("race_num", "")
    bet_type = hit_info.get("bet_type", "")
    payout = hit_info.get("payout", 0)
    horse_name = hit_info.get("horse_name", "")

    message = f"{venue} {race_num}R で的中しました！"
    color = 0x4ade80
    fields = [
        {"name": "🏇 馬名", "value": horse_name, "inline": True},
        {"name": "🎫 券種", "value": bet_type, "inline": True},
        {"name": "💰 払戻金", "value": f"¥{payout:,}", "inline": True}
    ]

    notifier.send_all(title, message, color, fields)


# --- メイン関数 ---

def main():
    """メイン関数"""
    print("=" * 60)
    print("📱 UMA-Logic PRO - 通知システム")
    print("=" * 60)

    # 利用可能なプラットフォームを表示
    notifier = Notifier()
    print(f"\n[INFO] 利用可能なプラットフォーム: {notifier.available_platforms or 'なし'}")

    if len(sys.argv) < 2:
        print("\n使用方法:")
        print("  python notifier.py --type [predictions|results|optimize|odds|historical]")
        print("  python notifier.py --type odds --insider-count 3")
        print("  python notifier.py --test")
        return

    args = sys.argv[1:]

    if "--test" in args:
        # テスト通知
        print("\n[INFO] テスト通知を送信します...")
        results = notifier.send_all(
            "🔔 テスト通知",
            "UMA-Logic PRO からのテスト通知です。",
            0x4ade80,
            [{"name": "📊 ステータス", "value": "正常", "inline": True}]
        )
        print(f"[INFO] 送信結果: {results}")
        return

    # 引数を解析
    notify_type = None
    status = "success"
    insider_count = 0

    i = 0
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            notify_type = args[i + 1]
            i += 2
        elif args[i] == "--status" and i + 1 < len(args):
            status = args[i + 1]
            i += 2
        elif args[i] == "--insider-count" and i + 1 < len(args):
            try:
                insider_count = int(args[i + 1])
            except ValueError:
                insider_count = 0
            i += 2
        else:
            i += 1

    # 通知タイプに応じて送信
    if notify_type == "predictions":
        notify_predictions(status)
    elif notify_type == "results":
        notify_results(status)
    elif notify_type == "optimize":
        notify_optimize(status)
    elif notify_type == "odds":
        notify_odds(insider_count)
    elif notify_type == "historical":
        notify_historical(status)
    else:
        print(f"[ERROR] 不明な通知タイプ: {notify_type}")

    print("\n✅ 処理完了")


if __name__ == "__main__":
    main()
