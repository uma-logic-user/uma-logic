#!/usr/bin/env python3
# scripts/notifier.py
# UMA-Logic PRO - 通知機能スクリプト（Discord/Slack対応）
# 修正完全版（Full Code）- そのままコピー＆ペーストで動作
# 環境変数が未設定でもエラーにならずスキップして正常終了

import os
import sys
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# --- 定数 ---
DATA_DIR = Path("data")
MODELS_DIR = DATA_DIR / "models"
WEIGHTS_FILE = MODELS_DIR / "weights.json"
ALERTS_FILE = DATA_DIR / "insider_alerts.json"


class Notifier:
    """
    通知送信クラス
    Discord, Slack に対応
    環境変数が未設定の場合はスキップして正常終了
    """

    def __init__(self):
        # 環境変数から取得（未設定の場合は空文字）
        self.discord_webhook = os.environ.get("DISCORD_WEBHOOK", "").strip()
        self.slack_webhook = os.environ.get("SLACK_WEBHOOK", "").strip()

        # 利用可能な通知サービスをチェック
        self.available_services = []
        if self.discord_webhook:
            self.available_services.append("Discord")
        if self.slack_webhook:
            self.available_services.append("Slack")

        if self.available_services:
            print(f"[INFO] 利用可能な通知サービス: {', '.join(self.available_services)}")
        else:
            print("[INFO] 通知サービスが設定されていません。通知はスキップされます。")

    def send_discord(self, title: str, message: str, color: int = 0x4ade80) -> bool:
        """Discord Webhookに通知を送信"""
        if not self.discord_webhook:
            print("[SKIP] Discord: Webhook URLが未設定")
            return False

        try:
            payload = {
                "embeds": [{
                    "title": title,
                    "description": message,
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat(),
                    "footer": {
                        "text": "UMA-Logic PRO"
                    }
                }]
            }

            response = requests.post(
                self.discord_webhook,
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 204]:
                print("[OK] Discord: 通知送信成功")
                return True
            else:
                print(f"[WARN] Discord: 送信失敗 (HTTP {response.status_code})")
                return False

        except Exception as e:
            print(f"[WARN] Discord: エラー - {e}")
            return False

    def send_slack(self, title: str, message: str) -> bool:
        """Slack Webhookに通知を送信"""
        if not self.slack_webhook:
            print("[SKIP] Slack: Webhook URLが未設定")
            return False

        try:
            payload = {
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": title
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"🐎 UMA-Logic PRO | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                            }
                        ]
                    }
                ]
            }

            response = requests.post(
                self.slack_webhook,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                print("[OK] Slack: 通知送信成功")
                return True
            else:
                print(f"[WARN] Slack: 送信失敗 (HTTP {response.status_code})")
                return False

        except Exception as e:
            print(f"[WARN] Slack: エラー - {e}")
            return False

    def send_all(self, title: str, message: str, color: int = 0x4ade80) -> int:
        """全ての利用可能なサービスに通知を送信"""
        success_count = 0

        if self.send_discord(title, message, color):
            success_count += 1
        if self.send_slack(title, message):
            success_count += 1

        return success_count

    def notify_optimize_result(self, status: str = "success") -> None:
        """AI学習結果を通知"""
        hit_rate = 0.0
        roi = 0.0
        weights = {}
        total_races = 0
        total_investment = 0
        total_return = 0

        if WEIGHTS_FILE.exists():
            try:
                with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # metrics または optimization_metrics を探す
                    metrics = data.get("metrics", data.get("optimization_metrics", {}))
                    
                    # hit_rate: 0-1形式なら100倍、既に%形式ならそのまま
                    raw_hit_rate = metrics.get("hit_rate", 0.0)
                    hit_rate = raw_hit_rate * 100 if raw_hit_rate <= 1 else raw_hit_rate
                    
                    # recovery_rate または roi
                    raw_roi = metrics.get("recovery_rate", metrics.get("roi", 0.0))
                    roi = raw_roi * 100 if raw_roi <= 10 else raw_roi
                    
                    # その他の統計
                    total_races = metrics.get("total_races", 0)
                    total_investment = metrics.get("total_investment", 0)
                    total_return = metrics.get("total_return", 0)
                    
                    weights = data.get("weights", {})
            except Exception as e:
                print(f"[WARN] weights.json 読み込みエラー: {e}")

        if status == "success":
            title = "🧠 AI学習完了"
            color = 0x4ade80  # 緑
        else:
            title = "❌ AI学習失敗"
            color = 0xef4444  # 赤

        # 重みのキー名を正規化（両方の形式に対応）
        speed = weights.get("SpeedAgent", weights.get("speed_agent", 0))
        adapt = weights.get("AdaptabilityAgent", weights.get("adaptability_agent", 0))
        pedigree = weights.get("PedigreeFormAgent", weights.get("pedigree_agent", 0))

        message = f"""✅ **ステータス**: {status.upper()}

📊 **学習結果**
・対象レース数: {total_races:,}レース
・的中率: {hit_rate:.2f}%
・回収率: {roi:.2f}%
・総投資額: ¥{total_investment:,}
・総払戻額: ¥{total_return:,.0f}

⚖️ **エージェント重み**
・Speed: {speed*100:.1f}%
・Adaptability: {adapt*100:.1f}%
・Pedigree: {pedigree*100:.1f}%

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        self.send_all(title, message, color)

    def notify_prediction(self, predictions: Optional[Dict] = None) -> None:
        """予想結果を通知"""
        title = "🐎 本日の予想"

        if predictions:
            races = predictions.get("races", [])
            date_str = predictions.get("date", "不明")
            
            message_lines = [f"📅 {date_str}", f"🏇 全{len(races)}レース", ""]

            for race in races[:5]:  # 最大5レースまで
                venue = race.get("venue", "")
                race_num = race.get("race_num", 0)
                race_name = race.get("race_name", "")
                top_picks = race.get("top_picks", [])
                top_pick = top_picks[0] if top_picks else "不明"
                
                message_lines.append(f"**{venue}{race_num}R** {race_name}")
                message_lines.append(f"◎ {top_pick}")
                message_lines.append("")

            if len(races) > 5:
                message_lines.append(f"...他 {len(races) - 5} レース")

            message = "\n".join(message_lines)
        else:
            message = "予想データがありません。"

        self.send_all(title, message)

    def notify_insider_alert(self) -> None:
        """インサイダーアラートを通知"""
        if not ALERTS_FILE.exists():
            print("[INFO] インサイダーアラートファイルなし")
            return

        try:
            with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                alerts = data.get("alerts", [])
        except Exception as e:
            print(f"[WARN] アラートファイル読み込みエラー: {e}")
            alerts = []

        if not alerts:
            print("[INFO] インサイダーアラートなし")
            return

        title = "🚨 インサイダーアラート検知"
        message_lines = [f"⚠️ {len(alerts)}件のアラートを検知", ""]

        for alert in alerts[:5]:
            venue = alert.get("venue", "")
            race_num = alert.get("race_num", 0)
            horse_name = alert.get("horse_name", "")
            umaban = alert.get("umaban", "")
            odds_before = alert.get("odds_before", 0)
            odds_after = alert.get("odds_after", 0)
            drop_rate = alert.get("drop_rate", 0)

            message_lines.append(f"**{venue}{race_num}R** {umaban}番 {horse_name}")
            message_lines.append(f"オッズ: {odds_before:.1f} → {odds_after:.1f} ({drop_rate*100:.1f}%↓)")
            message_lines.append("")

        if len(alerts) > 5:
            message_lines.append(f"...他 {len(alerts) - 5} 件")

        message = "\n".join(message_lines)
        self.send_all(title, message, color=0xfbbf24)  # 黄色

    def notify_results(self, results: Optional[Dict] = None) -> None:
        """レース結果を通知"""
        title = "📊 本日のレース結果"

        if results:
            date_str = results.get("date", "不明")
            races = results.get("races", [])

            message_lines = [f"📅 {date_str}", f"🏇 全{len(races)}レース完了", ""]

            # 上位3レースの結果を表示
            for race in races[:3]:
                venue = race.get("venue", "")
                race_num = race.get("race_num", 0)
                race_name = race.get("race_name", "")
                top3 = race.get("top3", [])
                
                message_lines.append(f"**{venue}{race_num}R** {race_name}")
                for i, horse in enumerate(top3[:3], 1):
                    horse_name = horse.get("馬名", horse.get("horse_name", ""))
                    message_lines.append(f"  {i}着: {horse_name}")
                message_lines.append("")

            if len(races) > 3:
                message_lines.append(f"...他 {len(races) - 3} レース")

            message = "\n".join(message_lines)
        else:
            message = "結果データがありません。"

        self.send_all(title, message)

    def notify_custom(self, title: str, message: str, color: int = 0x4ade80) -> None:
        """カスタムメッセージを通知"""
        self.send_all(title, message, color)


def main():
    """メイン関数"""
    print("=" * 50)
    print("🔔 UMA-Logic PRO - 通知システム")
    print("=" * 50)

    notifier = Notifier()

    # コマンドライン引数を解析
    args = sys.argv[1:]

    if not args:
        print("\n使用方法:")
        print("  python notifier.py --type <type> [--status <status>]")
        print("")
        print("タイプ:")
        print("  optimize   : AI学習結果を通知")
        print("  prediction : 予想結果を通知")
        print("  insider    : インサイダーアラートを通知")
        print("  results    : レース結果を通知")
        print("  test       : テスト通知を送信")
        print("")
        print("例:")
        print("  python notifier.py --type optimize --status success")
        print("  python notifier.py --type test")
        print("")

        # 引数なしでも正常終了
        print("[INFO] 引数が指定されていないため、通知をスキップします。")
        sys.exit(0)

    # 引数を解析
    notify_type = None
    status = "success"

    i = 0
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            notify_type = args[i + 1]
            i += 2
        elif args[i] == "--status" and i + 1 < len(args):
            status = args[i + 1]
            i += 2
        else:
            i += 1

    # 通知を送信
    if notify_type == "optimize":
        print("\n[INFO] AI学習結果を通知します...")
        notifier.notify_optimize_result(status)

    elif notify_type == "prediction":
        print("\n[INFO] 予想結果を通知します...")
        pred_files = sorted(DATA_DIR.glob("predictions_*.json"), reverse=True)
        if pred_files:
            try:
                with open(pred_files[0], 'r', encoding='utf-8') as f:
                    predictions = json.load(f)
                notifier.notify_prediction(predictions)
            except Exception as e:
                print(f"[WARN] 予想ファイル読み込みエラー: {e}")
                notifier.notify_prediction(None)
        else:
            notifier.notify_prediction(None)

    elif notify_type == "insider":
        print("\n[INFO] インサイダーアラートを通知します...")
        notifier.notify_insider_alert()

    elif notify_type == "results":
        print("\n[INFO] レース結果を通知します...")
        result_files = sorted(DATA_DIR.glob("results_*.json"), reverse=True)
        if result_files:
            try:
                with open(result_files[0], 'r', encoding='utf-8') as f:
                    results = json.load(f)
                notifier.notify_results(results)
            except Exception as e:
                print(f"[WARN] 結果ファイル読み込みエラー: {e}")
                notifier.notify_results(None)
        else:
            notifier.notify_results(None)

    elif notify_type == "test":
        print("\n[INFO] テスト通知を送信します...")
        notifier.notify_custom(
            "🧪 テスト通知",
            "UMA-Logic PRO の通知システムが正常に動作しています。\n\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            color=0x3b82f6  # 青
        )

    else:
        print(f"[WARN] 不明な通知タイプ: {notify_type}")
        print("[INFO] 通知をスキップします。")

    print("\n✅ 処理完了（正常終了）")
    sys.exit(0)


if __name__ == "__main__":
    main()
