# 📖 使用方法ガイド

## 🎯 クイックスタート

### 1. 初期設定
```bash
# 設定ファイルが自動生成されます
# 必要に応じて config ファイルを編集
```

### 2. 初回実行
```bash
# 依存関係が自動インストールされます
python scripts/fetch_realtime_odds.py 20260222
```

### 3. システム確認
```bash
python scripts/health_check.py
```

## 🔄 日常的な運用

### 毎日のオッズ取得
```bash
# 当日のオッズを取得
python scripts/fetch_realtime_odds.py $(date +%Y%m%d)

# または特定の日付を指定
python scripts/fetch_realtime_odds.py 20260222
```

### 強制再取得
```bash
# オッズ取得エラー時や再取得が必要な場合
python scripts/fetch_realtime_odds.py 20260222 --force
```

## 📊 モニタリング

### ログの確認
```bash
# リアルタイムログの監視
tail -f logs/fetch_realtime_odds.log

# エラーログの確認
grep "ERROR" logs/fetch_realtime_odds.log
```

### パフォーマンス統計
```bash
# メトリクスの確認
cat logs/performance_metrics.csv
```

## ⚙️ 設定カスタマイズ

### ネットワーク設定
```ini
[network]
user_agent = あなたのカスタムUser-Agent
referer = https://race.netkeiba.com/
accept_language = ja,en-US;q=0.9,en;q=0.8
```

### パフォーマンス設定
```ini
[performance]
warning_threshold = 30  # 警告閾値（秒）
error_threshold = 60    # エラー閾値（秒）
batch_size = 5          # バッチ処理サイズ
```

## 🛡️ セキュリティ

### ベストプラクティス
1. 定期的にログを確認
2. パフォーマンス閾値を監視
3. 依存関係のバージョンを管理

## 🔍 トラブルシューティング

### よくある問題と解決策

**問題**: オッズ取得が頻繁に失敗する
**解決**: 
- タイムアウト時間を増やす
- リトライ回数を増やす
- ネットワーク接続を確認

**問題**: 実行時間が長い
**解決**:
- バッチサイズを小さくする
- ネットワーク速度を確認
