import sys
import io
import time
import json
import argparse
from datetime import datetime, timedelta, timezone, date as date_type
import re as _re
from pathlib import Path

# Windows環境文字化け対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# パス設定 & モジュールインポート
sys.path.append(str(Path(__file__).parent))
try:
    from fetch_historical_data import get_race_dates_from_calendar, get_race_ids_for_date, fetch_race_result
    from data_processor import DataProcessor
except ImportError:
    print("[ERROR] 必要なモジュールが見つかりません (fetch_historical_data.py, data_processor.py)")
    sys.exit(1)

processor = DataProcessor()
DATA_DIR = Path("data")

def update_by_month(year, month, force=False):
    print(f"📅 {year}年{month}月のレース結果を確認中...")
    try:
        dates = get_race_dates_from_calendar(year, month)
    except Exception as e:
        print(f"  [ERROR] カレンダー取得失敗: {e}")
        return

    if not dates:
        print("  開催日なし")
        return

    print(f"  開催日: {dates}")
    for date_str in dates:
        # 未来はスキップ
        try:
            if datetime.strptime(date_str, "%Y%m%d") > datetime.now():
                continue
        except: continue
        
        update_by_date(date_str, force=force)

# === 日付バリデーション ===
VALID_DATE_RE = _re.compile(r'^\d{8}$')

def validate_date_str(date_str: str) -> bool:
    """YYYYMMDD形式かつ実在する日付か検証する"""
    if not VALID_DATE_RE.match(str(date_str)):
        return False
    try:
        datetime.strptime(date_str, "%Y%m%d")
        return True
    except ValueError:
        return False

# === JST タイムゾーン ===
JST = timezone(timedelta(hours=9))

def now_jst() -> str:
    """現在時刻を日本時間 (JST) で返す"""
    return datetime.now(tz=JST).strftime("%Y-%m-%d %H:%M:%S+09:00")

def update_by_date(date_str, force=False):
    # === バリデーション ===
    if not validate_date_str(str(date_str)):
        print(f"  [ERROR] 不正な日付フォーマット: {repr(date_str)} (YYYYMMDD形式が必要)")
        return

    fpath = DATA_DIR / f"results_{date_str}.json"

    # 既存データチェック
    if fpath.exists() and not force:
        # 15KB以上なら正常データとみなしてスキップ
        if fpath.stat().st_size > 15000:
            print(f"  [SKIP] 既存データあり: {date_str} ({fpath.stat().st_size} bytes)")
            return
        else:
            print(f"  [RETRY] 既存データ不完全または空: {date_str}")
    
    print(f"  🚀 データ取得開始: {date_str}")
    try:
        race_ids = get_race_ids_for_date(date_str)
    except:
        print(f"    [ERROR] レースID取得失敗")
        return
        
    if not race_ids:
        print(f"    [WARN] レースIDなし (開催中止?)")
        processor.log("WARN", f"レースIDなし: {date_str}")
        return
        
    results = []
    print(f"    {len(race_ids)}レース取得中...")
    for race_id in race_ids:
        data = fetch_race_result(race_id)
        if data:
            processed = processor.process_race_data(data)
            results.append(processed)
        time.sleep(1.0)
        
    if results:
        save_path = fpath
        output = {
            "date": date_str,  # YYYYMMDD 固定 (JST)
            "updated_at": now_jst(),
            "races": results
        }
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"    ✅ 保存完了: {len(results)}レース -> {save_path.name}")
        processor.log("INFO", f"データ保存: {date_str}", {"count": len(results)})
    else:
        print(f"    [WARN] 結果データなし")

def main():
    parser = argparse.ArgumentParser(description="UMA-Logic Pro - 結果データ更新マネージャー")
    parser.add_argument("--date", type=str, help="指定日のみ更新 (YYYYMMDD)")
    parser.add_argument("--month", type=str, help="指定月のみ更新 (YYYYMM)")
    parser.add_argument("--range", type=str, help="範囲指定更新 (YYYYMMDD-YYYYMMDD)")
    parser.add_argument("--force", action="store_true", help="既存データを強制上書き")
    
    args = parser.parse_args()
    
    print("="*60)
    print("🏇 UMA-Logic Pro - 結果データ更新マネージャー")
    print("="*60)
    
    if args.date:
        update_by_date(args.date, force=args.force)
    elif args.range:
        try:
            start_str, end_str = args.range.split("-")
            start_date = datetime.strptime(start_str, "%Y%m%d")
            end_date = datetime.strptime(end_str, "%Y%m%d")
            delta = (end_date - start_date).days
            for i in range(delta + 1):
                d = (start_date + timedelta(days=i)).strftime("%Y%m%d")
                update_by_date(d, force=args.force)
        except Exception as e:
            print(f"[ERROR] 範囲指定エラー: {e}")
    elif args.month:
        if len(args.month) == 6:
            y = int(args.month[:4])
            m = int(args.month[4:])
            update_by_month(y, m, force=args.force)
        else:
            print("[ERROR] 月指定は YYYYMM 形式でお願いします")
    else:
        # 引数なしの場合: 今月と先月をチェック
        now = datetime.now()
        this_month = (now.year, now.month)
        
        # 先月計算
        last_month_date = now.replace(day=1) - timedelta(days=1)
        last_month = (last_month_date.year, last_month_date.month)
        
        print(f"[INFO] 直近2ヶ月 ({last_month[0]}/{last_month[1]} - {this_month[0]}/{this_month[1]}) をチェックします")
        update_by_month(last_month[0], last_month[1], force=args.force)
        update_by_month(this_month[0], this_month[1], force=args.force)
    
    print("\n" + "="*60)
    print("✅ 処理完了")

if __name__ == "__main__":
    main()