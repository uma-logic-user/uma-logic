import threading
import time
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# パス設定
BASE_DIR = Path(__file__).parent
SCRIPTS_DIR = BASE_DIR / "scripts"

def run_sync():
    """5分おきにデータ同期を行うバックグラウンドループ"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 Auto-Sync Scheduler Started.")
    
    while True:
        try:
            today_str = datetime.now().strftime("%Y%m%d")
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔄 Syncing data for {today_str}...")
            
            # 1. 結果の更新
            subprocess.run([sys.executable, str(SCRIPTS_DIR / "update_results.py"), "--date", today_str], check=False)
            
            # 2. オッズの更新
            subprocess.run([sys.executable, str(SCRIPTS_DIR / "fetch_realtime_odds.py"), today_str], check=False)
            
            # 3. 資金配分用計算 (calculated_...更新)
            subprocess.run([sys.executable, str(SCRIPTS_DIR / "calculator_pro.py")], check=False)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Sync completed. Next sync in 5 minutes.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Sync error: {e}")
        
        time.sleep(300)  # 5分待機

def run_streamlit():
    """Streamlitアプリを起動"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Launching UMA-Logic PRO (0.0.0.0:8501)...")
    cmd = [
        "streamlit", "run", "app.py",
        "--server.address", "0.0.0.0",
        "--server.port", "8501"
    ]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    # 同期スレッドの開始
    sync_thread = threading.Thread(target=run_sync, daemon=True)
    sync_thread.start()
    
    # Streamlitの起動
    try:
        run_streamlit()
    except KeyboardInterrupt:
        print("\n👋 UMA-Logic PRO Stopped.")
