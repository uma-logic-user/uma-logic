# 🏇 UMA Logic - 競馬予想システム

## 📋 システム概要

競馬のリアルタイムオッズ取得とAI予想を行う商用レベルのシステムです。

## 🚀 主な機能

- ✅ **リアルタイムオッズ取得**: netkeiba.comから全券種のオッズを自動取得
- ✅ **AI予想**: 機械学習モデルによる勝馬予想
- ✅ **商用レベルロギング**: 詳細な実行ログとパフォーマンス監視
- ✅ **自動依存関係管理**: ゼロコンフィグセットアップ
- ✅ **設定ファイルシステム**: 柔軟な構成管理
- ✅ **メトリクス収集**: 実行統計の自動記録
- ✅ **ヘルスチェック**: システム健全性の自動確認

## ⚙️ 設定

### 設定ファイル (`config`)

```ini
[odds_fetch]
max_retries = 3
timeout = 15
backoff_base = 2

[network]
user_agent = Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36
referer = https://race.netkeiba.com/
accept_language = ja,en-US;q=0.9,en;q=0.8

[logging]
level = INFO
max_file_size = 10
backup_count = 5

[performance]
warning_threshold = 30
error_threshold = 60
batch_size = 5
```

## 📁 ディレクトリ構造

```
uma-logic-new/
├── data/                 # データディレクトリ
│   ├── history/         # 履歴データ
│   └── processed/       # 処理済みデータ
├── logs/                # ログファイル
├── scripts/             # Pythonスクリプト
│   ├── fetch_realtime_odds.py  # メインスクリプト
│   ├── health_check.py         # ヘルスチェック
│   └── generate_docs.py        # ドキュメント生成
├── config               # 設定ファイル
└── README.md           # このファイル
```

## 🛠️ 使用方法

### 1. オッズ取得の実行

```bash
# 特定日のオッズを取得
python scripts/fetch_realtime_odds.py 20260222

# 強制再取得
python scripts/fetch_realtime_odds.py 20260222 --force
```

### 2. ヘルスチェックの実行

```bash
python scripts/health_check.py
```

### 3. ドキュメントの再生成

```bash
python scripts/generate_docs.py
```

## 📊 メトリクス

実行メトリクスは `logs/performance_metrics.csv` に自動保存されます：
- 実行日時
- 処理レース数
- 成功/失敗数
- 実行時間
- 成功率
- 1レースあたりの平均時間

## 🔧 カスタマイズ

### 設定の変更

`config` ファイルを編集して各種設定を変更できます：

```bash
# リトライ回数を5回に変更
max_retries = 5

# タイムアウト時間を30秒に変更
timeout = 30

# ログレベルをDEBUGに変更
level = DEBUG
```

### バッチサイズの調整

大量のレースを処理する場合、バッチサイズを調整して負荷を分散できます：

```ini
[performance]
batch_size = 3  # デフォルト: 5
```

## 🐛 トラブルシューティング

### 一般的な問題

1. **依存関係エラー**
   ```bash
   # 自動で解決されますが、手動でインストールする場合
   pip install requests beautifulsoup4
   ```

2. **ネットワークエラー**
   - 設定ファイルのタイムアウト値を増やす
   - リトライ回数を増やす

3. **ログファイルの肥大化**
   - 設定ファイルでログの最大サイズと保持数を調整

## 📈 パフォーマンスチューニング

### 推奨設定（高負荷環境）

```ini
[odds_fetch]
max_retries = 5
timeout = 20
backoff_base = 2

[performance]
batch_size = 3  # 負荷分散
warning_threshold = 45
error_threshold = 90
```

## 📝 ライセンス

このプロジェクトは独自開発の商用システムです。

## 🤝 サポート

問題が発生した場合は、以下の情報を確認してください：
1. `logs/fetch_realtime_odds.log` のエラーログ
2. `logs/performance_metrics.csv` の実行統計
3. ヘルスチェックの結果
