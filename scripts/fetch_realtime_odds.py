"""
リアルタイムオッズ取得スクリプト（全券種対応版）
- 単勝・複勝・馬連・ワイド・3連複・3連単オッズを netkeiba.com から取得
- 取得失敗時は odds_status="fetch_error" を設定してUIでエラー表示
- --force オプションで全レース即時強制取得
"""
import json
import sys
import io
import re
import time
import csv
from pathlib import Path
from datetime import datetime

# Windows文字化け対策
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ロギングシステムの設定
def _setup_logging():
    """ロギングシステムの設定"""
    import logging
    from pathlib import Path
    
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'fetch_realtime_odds.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# グローバルロガーインスタンス
logger = _setup_logging()

# 依存関係の自動インストール機能
def _install_dependencies():
    """必要な依存関係を自動インストール"""
    import subprocess
    import sys
    
    required_packages = ['requests', 'beautifulsoup4']
    
    for package in required_packages:
        try:
            if package == 'beautifulsoup4':
                __import__('bs4')
            else:
                __import__(package)
        except ImportError:
            logger.info(f"📦 {package} をインストール中...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                logger.info(f"✅ {package} のインストール成功")
            except subprocess.CalledProcessError:
                logger.error(f"❌ {package} のインストール失敗")
                return False
    return True

# 依存関係チェックと自動インストール
try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    if _install_dependencies():
        import requests
        from bs4 import BeautifulSoup
        HAS_REQUESTS = True
    else:
        HAS_REQUESTS = False

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PREDICTIONS_PREFIX = "predictions_"
HISTORY_DIR = DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# 設定ファイルの読み込み
def _load_config():
    """設定ファイルを読み込む"""
    import configparser
    from pathlib import Path
    
    config = configparser.ConfigParser()
    config_file = Path(__file__).parent.parent / "config"
    
    # デフォルト設定
    defaults = {
        'odds_fetch': {
            'max_retries': '3',
            'timeout': '15',
            'backoff_base': '2'
        },
        'network': {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'referer': 'https://race.netkeiba.com/',
            'accept_language': 'ja,en-US;q=0.9,en;q=0.8'
        },
        'logging': {
            'level': 'INFO',
            'max_file_size': '10',
            'backup_count': '5'
        },
        'performance': {
            'warning_threshold': '30',
            'error_threshold': '60',
            'batch_size': '5'
        },
        'email': {
            'enabled': 'false',
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': '587',
            'email_from': 'your_email@gmail.com',
            'email_password': 'your_app_password',
            'email_to': 'recipient@example.com',
            'use_tls': 'true'
        }
    }
    
    # デフォルト設定を適用
    config.read_dict(defaults)
    
    # 設定ファイルが存在すれば読み込み
    if config_file.exists():
        try:
            config.read(config_file, encoding='utf-8')
            logger.info("設定ファイルを読み込みました")
        except Exception as e:
            logger.warning(f"設定ファイルの読み込みに失敗しました: {e}")
    
    return config

def _send_email_notification(subject: str, body: str):
    """メール通知を送信"""
    try:
        enabled = CONFIG['email']['enabled'].lower() == 'true'
        if not enabled:
            return False
            
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # メール設定
        smtp_server = CONFIG['email']['smtp_server']
        smtp_port = int(CONFIG['email']['smtp_port'])
        email_from = CONFIG['email']['email_from']
        email_password = CONFIG['email']['email_password']
        email_to = CONFIG['email']['email_to'].split(',')
        use_tls = CONFIG['email']['use_tls'].lower() == 'true'
        
        # メール作成
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = ', '.join(email_to)
        msg['Subject'] = f"[UMA Logic] {subject}"
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # SMTP接続と送信
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if use_tls:
                server.starttls()
            server.login(email_from, email_password)
            server.send_message(msg)
        
        logger.info("📧 メール通知を送信しました")
        return True
        
    except Exception as e:
        logger.error(f"メール送信エラー: {e}")
        return False

def _save_metrics(target_date: str, execution_time: float):
    """メトリクスをCSVファイルに保存"""
    metrics_file = Path(__file__).parent.parent / "logs" / "performance_metrics.csv"
    
    # メトリクスデータ作成
    metrics_data = {
        'date': target_date,
        'timestamp': datetime.now().isoformat(),
        'total_races': METRICS['total_races'],
        'successful_fetches': METRICS['successful_fetches'],
        'failed_fetches': METRICS['failed_fetches'],
        'execution_time_seconds': round(execution_time, 2),
        'success_rate_percent': round(METRICS['successful_fetches'] / METRICS['total_races'] * 100, 1) if METRICS['total_races'] > 0 else 0,
        'avg_time_per_race': round(execution_time / METRICS['total_races'], 3) if METRICS['total_races'] > 0 else 0
    }
    
    # CSVファイルに追記
    file_exists = metrics_file.exists()
    
    with open(metrics_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=metrics_data.keys())
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(metrics_data)
    
    logger.info(f"📈 メトリクスを保存しました: {metrics_file}")

# グローバル設定
CONFIG = _load_config()

# メトリクス収集用グローバル変数
METRICS = {
    'total_races': 0,
    'successful_fetches': 0,
    'failed_fetches': 0,
    'total_execution_time': 0.0,
    'start_time': None
}

HEADERS = {
    "User-Agent": CONFIG['network']['user_agent'],
    "Accept-Language": CONFIG['network']['accept_language'],
    "Referer": CONFIG['network']['referer'],
}


def _get_html(url: str, encoding: str = "euc-jp", max_retries: int = None) -> BeautifulSoup | None:
    """
    URL取得ヘルパー（リトライ機能付き）。失敗時はNoneを返す。
    
    Args:
        url: 取得対象URL
        encoding: 文字エンコーディング（デフォルト: euc-jp）
        max_retries: 最大リトライ回数（Noneの場合は設定ファイルから読み込み）
    
    Returns:
        BeautifulSoupオブジェクトまたはNone
    """
    if not HAS_REQUESTS:
        logger.error("requestsモジュールが利用できません")
        return None
    
    if max_retries is None:
        max_retries = int(CONFIG['odds_fetch']['max_retries'])
    
    timeout = int(CONFIG['odds_fetch']['timeout'])
    backoff_base = int(CONFIG['odds_fetch']['backoff_base'])
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger.warning(f"リトライ中 ({attempt + 1}/{max_retries})")
                time.sleep(backoff_base ** attempt)  # Exponential backoff
            
            logger.info(f"オッズ取得中: {url}")
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.encoding = encoding
            logger.info(f"HTTPステータス: {resp.status_code}")
            
            if resp.status_code != 200:
                logger.error(f"HTTPエラー: {resp.status_code}")
                continue
                
            return BeautifulSoup(resp.text, "html.parser")
            
        except requests.exceptions.Timeout:
            logger.warning(f"タイムアウト (試行 {attempt + 1}/{max_retries})")
        except requests.exceptions.ConnectionError:
            logger.error(f"接続エラー (試行 {attempt + 1}/{max_retries})")
        except requests.exceptions.RequestException as e:
            logger.error(f"ネットワークエラー: {e} (試行 {attempt + 1}/{max_retries})")
        except Exception as e:
            logger.exception(f"予期せぬエラー: {e}")
            break
    
    logger.error(f"最大リトライ回数({max_retries})を超えました")
    return None


def fetch_win_odds(race_id: str) -> dict:
    """単勝オッズ → {馬番(int): odds(float)}"""
    soup = _get_html(f"https://race.netkeiba.com/odds/index.html?race_id={race_id}&type=b1")
    if soup is None:
        return {}
    result = {}
    # 複数セレクタを試行
    for sel_ub, sel_od in [
        ("td.Umaban", "td.Odds span.Odds"),
        ("td.Umaban", "td.Odds span"),
        (".HorseList td:nth-child(1)", ".HorseList td.Odds span"),
    ]:
        rows = soup.select("tr.HorseList")
        if rows:
            for row in rows:
                try:
                    ub = row.select_one("td.Umaban")
                    od = row.select_one("td.Odds span") or row.select_one("td.Odds")
                    if ub and od:
                        txt = od.get_text(strip=True).replace(",", "")
                        if txt and txt != "---":
                            result[int(ub.get_text(strip=True))] = float(txt)
                except Exception:
                    continue
            break
        # フォールバック: JSON埋め込みを探す
        scripts = soup.find_all("script")
        for sc in scripts:
            txt = sc.get_text()
            m = re.findall(r'"umaban":(\d+).*?"odds":([\d.]+)', txt)
            if m:
                for um, od in m:
                    result[int(um)] = float(od)
                break
    return result


def fetch_quinella_odds(race_id: str) -> dict:
    """馬連オッズ → {(馬番1, 馬番2): odds}  (馬番1 < 馬番2)"""
    soup = _get_html(f"https://race.netkeiba.com/odds/index.html?race_id={race_id}&type=b6")
    if soup is None:
        return {}
    result = {}
    try:
        # データテーブルからパース
        table = soup.select_one("table#odds_wide_b6") or soup.select_one("table.Odds_Table")
        if table:
            for td in table.select("td[id]"):
                cell_id = td.get("id", "")
                m = re.match(r"b6_(\d+)_(\d+)", cell_id)
                if m:
                    a, b = int(m.group(1)), int(m.group(2))
                    txt = td.get_text(strip=True).replace(",", "")
                    if txt and txt not in ("---", ""):
                        k = (min(a, b), max(a, b))
                        result[k] = float(txt)
    except Exception as e:
        print(f"  [WARN] 馬連パースエラー: {e}")
    return result


def fetch_wide_odds(race_id: str) -> dict:
    """ワイドオッズ → {(馬番1, 馬番2): (odds_min, odds_max)}"""
    soup = _get_html(f"https://race.netkeiba.com/odds/index.html?race_id={race_id}&type=b5")
    if soup is None:
        return {}
    result = {}
    try:
        table = soup.select_one("table#odds_wide_b5") or soup.select_one("table.Odds_Table")
        if table:
            for td in table.select("td[id]"):
                cell_id = td.get("id", "")
                m = re.match(r"b5_(\d+)_(\d+)", cell_id)
                if m:
                    a, b = int(m.group(1)), int(m.group(2))
                    txt = td.get_text(strip=True).replace(",", "")
                    # "1.2-3.4" 形式
                    parts = txt.split("-")
                    if len(parts) == 2:
                        try:
                            k = (min(a, b), max(a, b))
                            result[k] = (float(parts[0]), float(parts[1]))
                        except Exception:
                            pass
    except Exception as e:
        print(f"  [WARN] ワイドパースエラー: {e}")
    return result


def fetch_trio_odds(race_id: str) -> dict:
    """3連複オッズ → {(馬番1, 馬番2, 馬番3): odds} (昇順)"""
    soup = _get_html(f"https://race.netkeiba.com/odds/index.html?race_id={race_id}&type=b8")
    if soup is None:
        return {}
    result = {}
    try:
        for td in soup.select("td[id^='b8_']"):
            cell_id = td.get("id", "")
            m = re.match(r"b8_(\d+)_(\d+)_(\d+)", cell_id)
            if m:
                nums = sorted([int(m.group(1)), int(m.group(2)), int(m.group(3))])
                txt = td.get_text(strip=True).replace(",", "")
                if txt and txt != "---":
                    result[tuple(nums)] = float(txt)
    except Exception as e:
        print(f"  [WARN] 3連複パースエラー: {e}")
    return result


def fetch_trifecta_odds(race_id: str) -> dict:
    """3連単オッズ → {(1着, 2着, 3着): odds}"""
    soup = _get_html(f"https://race.netkeiba.com/odds/index.html?race_id={race_id}&type=b7")
    if soup is None:
        return {}
    result = {}
    try:
        for td in soup.select("td[id^='b7_']"):
            cell_id = td.get("id", "")
            m = re.match(r"b7_(\d+)_(\d+)_(\d+)", cell_id)
            if m:
                key = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                txt = td.get_text(strip=True).replace(",", "")
                if txt and txt != "---":
                    result[key] = float(txt)
    except Exception as e:
        print(f"  [WARN] 3連単パースエラー: {e}")
    return result


def fetch_all_odds(race_id: str) -> dict:
    """
    全券種オッズを取得して辞書に格納。

    Returns:
        {
            "win":       {umaban: float},
            "place":     {umaban: float},
            "quinella":  {(a,b): float},
            "wide":      {(a,b): (min, max)},
            "trio":      {(a,b,c): float},
            "trifecta":  {(a,b,c): float},
            "fetched_at": "YYYY-MM-DD HH:MM:SS",
            "fetch_success": bool,
        }
    """
    print(f"  📡 全券種オッズ取得: {race_id}")
    win   = fetch_win_odds(race_id)
    time.sleep(0.8)
    place = {}  # 複勝は単勝ページに含まれることが多い
    quinella = fetch_quinella_odds(race_id)
    time.sleep(0.8)
    wide = fetch_wide_odds(race_id)
    time.sleep(0.8)
    trio = fetch_trio_odds(race_id)
    time.sleep(0.8)
    tri_str  = {str(k): v for k, v in fetch_trifecta_odds(race_id).items()}
    time.sleep(0.8)

    fetch_success = bool(win)

    # JSON serializable に変換
    result = {
        "win":      {str(k): v for k, v in win.items()},
        "place":    {str(k): v for k, v in place.items()},
        "quinella": {f"{k[0]}-{k[1]}": v for k, v in quinella.items()},
        "wide":     {f"{k[0]}-{k[1]}": list(v) for k, v in wide.items()},
        "trio":     {f"{k[0]}-{k[1]}-{k[2]}": v for k, v in trio.items()},
        "trifecta": tri_str,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fetch_success": fetch_success,
    }

    if fetch_success:
        print(f"    ✅ 単勝{len(win)}頭 / 馬連{len(quinella)}組 / ワイド{len(wide)}組 / 3連複{len(trio)}組")
    else:
        print(f"    ❌ 単勝オッズ取得失敗 (schedule外または取得できず)")

    return result


def update_predictions_with_live_odds(target_date: str, force: bool = False) -> dict:
    """指定日の予想データをリアルタイムオッズで更新"""
    logger.info(f"📊 {target_date}のオッズ更新を開始します...")
    
    # メトリクス計測開始
    METRICS['start_time'] = time.time()
    METRICS['total_races'] = 0
    METRICS['successful_fetches'] = 0
    METRICS['failed_fetches'] = 0
    
    pred_file = HISTORY_DIR / f"{PREDICTIONS_PREFIX}{target_date}.json"
    
    if not pred_file.exists():
        logger.error(f"❌ 予想ファイルが見つかりません: {pred_file}")
        return {"status": "error", "message": "予想ファイルが存在しません"}
    
    with open(pred_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    races = data.get("races", [])
    updated_count = 0
    error_count = 0
    METRICS['total_races'] = len(races)
    
    # バッチサイズ設定
    batch_size = int(CONFIG['performance']['batch_size'])
    
    for i, race in enumerate(races):
        race_id = race.get("race_id", "")
        if not race_id:
            continue
            
        all_odds = fetch_all_odds(race_id)

        if all_odds["fetch_success"]:
            race["odds_status"] = "realtime"
            race["odds_all"] = all_odds
            race["odds_updated_at"] = all_odds["fetched_at"]

            # 各馬の単勝オッズを更新
            horses = race.get("horses", []) or race.get("predictions", [])
            win_odds = all_odds["win"]
            for horse in horses:
                umaban = str(horse.get("umaban", horse.get("馬番", "")))
                if umaban in win_odds:
                    old = horse.get("odds", horse.get("オッズ", None))
                    new = win_odds[umaban]
                    horse["odds"] = new
                    horse["オッズ"] = new
                    horse["odds_prev"] = old
                    horse["odds_status"] = "realtime"
                    updated_count += 1
                else:
                    horse["odds"] = None
                    horse["オッズ"] = None
                    horse["odds_status"] = "fetch_error"
            
            METRICS['successful_fetches'] += 1
            logger.info(f"✅ {race_id} のオッズを更新しました")
        else:
            # 取得失敗 → エラーフラグを設定
            race["odds_status"] = "fetch_error"
            race["odds_error_msg"] = "オッズ取得エラー（netkeiba接続失敗またはレース未公開）"
            horses = race.get("horses", []) or race.get("predictions", [])
            for horse in horses:
                horse["odds"] = None
                horse["オッズ"] = None
                horse["odds_status"] = "fetch_error"
            error_count += 1
            METRICS['failed_fetches'] += 1
            logger.warning(f"⚠️ {race_id} のオッズ取得に失敗しました")
        
        # バッチ処理の間隔調整
        if batch_size > 0 and (i + 1) % batch_size == 0:
            logger.info(f"⏸️ バッチ処理中... ({i + 1}/{len(races)})")
            time.sleep(1)  # 1秒間隔

    if updated_count > 0:
        data["odds_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["odds_source"] = "realtime"

        with open(pred_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"[OK] {updated_count}件を更新 → {pred_file.name}")
    else:
        logger.info("[INFO] 更新対象なし（レースIDなしまたは全取得失敗）")
    
    # メトリクス計測終了
    execution_time = time.time() - METRICS['start_time']
    METRICS['total_execution_time'] = execution_time
    
    result = {
        "status": "success",
        "updated": updated_count,
        "errors": error_count,
        "total": len(races),
        "execution_time": round(execution_time, 2),
        "success_rate": round(updated_count / len(races) * 100, 1) if races else 0
    }
    
    logger.info(f"🎯 オッズ更新完了: {updated_count}成功, {error_count}失敗, 合計{len(races)}レース, 実行時間: {execution_time:.2f}秒")
    
    # メール通知の送信
    if updated_count > 0 or error_count > 0:
        subject = f"オッズ更新完了 - {target_date}"
        body = f"""オッズ更新が完了しました

日付: {target_date}
成功: {updated_count}レース
失敗: {error_count}レース
合計: {len(races)}レース
実行時間: {execution_time:.2f}秒
成功率: {result['success_rate']}%

詳細はログファイルをご確認ください。
"""
        _send_email_notification(subject, body)
    
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="リアルタイムオッズ取得（全券種）")
    parser.add_argument("date", nargs="?", default=datetime.now().strftime("%Y%m%d"),
                        help="対象日 YYYYMMDD (default: today)")
    parser.add_argument("--force", action="store_true", help="強制全レース取得")
    args = parser.parse_args()

    logger.info(f"🔄 リアルタイムオッズ取得（全券種）: {args.date}")
    logger.info(f"📁 作業ディレクトリ: {Path.cwd()}")
    
    # パフォーマンスモニタリング
    start_time = time.time()
    result = update_predictions_with_live_odds(args.date, force=args.force)
    end_time = time.time()
    
    execution_time = end_time - start_time
    logger.info(f"✅ 処理完了: {result}, 実行時間: {execution_time:.2f}秒")
    
    # パフォーマンス統計の記録
    if execution_time > 30:
        logger.warning(f"実行時間が長いです: {execution_time:.2f}秒")
    elif execution_time > 60:
        logger.error(f"実行時間が異常に長いです: {execution_time:.2f}秒")
