"""
UMA-Logic PRO - スケジューラ + 自動更新システム
- 毎朝8:00: 予想データ自動更新
- 各レース発走15分前: リアルタイムオッズ取得＋EV再計算
- Windowsタスクスケジューラ or 常駐プロセスとして実行
"""
import subprocess
import sys
import io
import time
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

# Windows文字化け対策
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# パス設定
BASE_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
DATA_DIR = BASE_DIR / "data"
PREDICTIONS_PREFIX = "predictions_"
HISTORY_DIR = DATA_DIR / "history"


def run_script(script_name, args=[]):
    """スクリプトを実行するヘルパー関数"""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        print(f"[ERROR] スクリプトが見つかりません: {script_path}")
        return False
        
    cmd = [sys.executable, str(script_path)] + args
    print(f"\n>> Running: {script_name} {' '.join(args)}")
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.stdout:
            print(result.stdout)
        if result.returncode != 0 and result.stderr:
            print(f"[WARN] {result.stderr[:500]}")
        return result.returncode == 0
    except Exception as e:
        print(f"[ERROR] 実行失敗: {e}")
        return False


def get_race_start_times(date_str: str) -> list:
    """
    指定日の各レースの発走時刻を取得する。
    Returns: [(race_id, hour, minute), ...]
    """
    pred_file = HISTORY_DIR / f"{PREDICTIONS_PREFIX}{date_str}.json"
    if not pred_file.exists():
        return []
    
    try:
        with open(pred_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        start_times = []
        for race in data.get("races", []):
            race_id = race.get("race_id", "")
            start_time = race.get("start_time", "")
            if race_id and start_time:
                # 発走時刻パース: "15:40" 形式
                match = re.match(r"(\d{1,2}):(\d{2})", str(start_time))
                if match:
                    h, m = int(match.group(1)), int(match.group(2))
                    start_times.append((race_id, h, m))
        
        return sorted(start_times, key=lambda x: (x[1], x[2]))
    except Exception as e:
        print(f"[WARN] 発走時刻の読み込みエラー: {e}")
        return []


def morning_update():
    """毎朝8時の自動更新処理"""
    print("=" * 60)
    print(f"🌅 UMA-Logic PRO - 朝の自動更新")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. 過去の結果データを更新
    print("\n[Step 1] 過去レース結果の更新")
    run_script("update_results.py")
    
    # 2. 当日の予想データを更新
    today_str = datetime.now().strftime("%Y%m%d")
    print(f"\n[Step 2] 本日 ({today_str}) の予想データ更新")
    run_script("fetch_future_races.py", [today_str])
    run_script("calculator_pro.py", ["--process", today_str])
    
    # 3. 翌日の予想データを生成
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    print(f"\n[Step 3] 翌日 ({tomorrow_str}) の予想データ生成")
    run_script("fetch_future_races.py", [tomorrow_str])
    run_script("calculator_pro.py", ["--process", tomorrow_str])
    
    print("\n" + "=" * 60)
    print("✅ 朝の自動更新完了")
    print("=" * 60)


def pre_race_update(date_str: str):
    """各レース発走15分前のリアルタイムオッズ取得"""
    print(f"\n🏇 発走前オッズ更新: {date_str}")
    run_script("fetch_realtime_odds.py", [date_str])


def run_scheduler():
    """
    常駐スケジューラ
    - 毎朝8:00に morning_update() を実行
    - 各レース発走15分前に pre_race_update() を実行
    """
    print("=" * 60)
    print(f"🤖 UMA-Logic PRO - スケジューラ起動")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("   スケジュール:")
    print("     - 毎朝 08:00: 予想データ自動更新")
    print("     - 発走15分前: リアルタイムオッズ取得")
    print("=" * 60)
    
    morning_done_today = False
    weekly_done = False
    triggered_races = set()  # すでに取得済みのレース
    
    while True:
        now = datetime.now()
        today_str = now.strftime("%Y%m%d")
        
        # 日付が変わったらリセット
        if now.hour == 0 and now.minute == 0:
            morning_done_today = False
            triggered_races.clear()
            # 月曜日リセット
            if now.weekday() == 0:
                weekly_done = False
        
        # 毎週月曜日 06:00 - マスターDB自動更新
        if now.weekday() == 0 and now.hour == 6 and now.minute == 0 and not weekly_done:
            print("\n" + "=" * 60)
            print("📦 週次マスターDB自動更新 (毎週月曜)")
            print("=" * 60)
            # 過去1週間分のレースデータを再取得してDB肥大化
            for d in range(7):
                target = (now - timedelta(days=d)).strftime("%Y%m%d")
                run_script("fetch_future_races.py", [target])
            # 今後1週間分の出馬表を先取り
            for d in range(1, 8):
                target = (now + timedelta(days=d)).strftime("%Y%m%d")
                run_script("fetch_future_races.py", [target])
            print("✅ 週次マスターDB更新完了")
            weekly_done = True
        
        # 毎朝8:00の更新
        if now.hour == 8 and now.minute == 0 and not morning_done_today:
            morning_update()
            morning_done_today = True
        
        # 土日のみ発走前更新を実行
        if now.weekday() >= 5:  # 5=土, 6=日
            race_times = get_race_start_times(today_str)
            
            for race_id, race_hour, race_min in race_times:
                # 発走15分前を計算
                race_dt = now.replace(hour=race_hour, minute=race_min, second=0)
                trigger_dt = race_dt - timedelta(minutes=15)
                
                # 発走15分前±1分以内かつ未処理
                diff_seconds = abs((now - trigger_dt).total_seconds())
                if diff_seconds <= 60 and race_id not in triggered_races:
                    print(f"\n⏰ 発走15分前 ({race_hour}:{race_min:02d}発走)")
                    pre_race_update(today_str)
                    triggered_races.add(race_id)
                    break  # 1回のループで1レースのみ更新
        
        # 30秒間隔でチェック
        time.sleep(30)


def main():
    """エントリーポイント: --daemon でスケジューラ常駐、なしで朝の一括更新"""
    import argparse
    parser = argparse.ArgumentParser(description="UMA-Logic スケジューラ")
    parser.add_argument("--daemon", action="store_true",
                        help="常駐スケジューラモードで起動")
    parser.add_argument("--odds", action="store_true",
                        help="リアルタイムオッズのみ取得")
    args = parser.parse_args()
    
    if args.daemon:
        run_scheduler()
    elif args.odds:
        today_str = datetime.now().strftime("%Y%m%d")
        pre_race_update(today_str)
    else:
        morning_update()


if __name__ == "__main__":
    main()
