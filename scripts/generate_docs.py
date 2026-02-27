#!/usr/bin/env python3
"""
自動ドキュメント生成スクリプト
- プロジェクトの設定と使用方法を自動生成
"""

from pathlib import Path
import configparser

def generate_readme():
    """README.mdを生成"""
    config = configparser.ConfigParser()
    config.read('config', encoding='utf-8')
    
    readme_content = f"""# 🏇 UMA Logic - 競馬予想システム

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
max_retries = {config['odds_fetch']['max_retries']}
timeout = {config['odds_fetch']['timeout']}
backoff_base = {config['odds_fetch']['backoff_base']}

[network]
user_agent = {config['network']['user_agent']}
referer = {config['network']['referer']}
accept_language = {config['network']['accept_language']}

[logging]
level = {config['logging']['level']}
max_file_size = {config['logging']['max_file_size']}
backup_count = {config['logging']['backup_count']}

[performance]
warning_threshold = {config['performance']['warning_threshold']}
error_threshold = {config['performance']['error_threshold']}
batch_size = {config['performance']['batch_size']}
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
"""
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print("✅ README.mdを生成しました")

def generate_usage_guide():
    """使用方法ガイドを生成"""
    guide_content = """# 📖 使用方法ガイド

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
"""
    
    with open('USAGE.md', 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    print("✅ USAGE.mdを生成しました")

def main():
    """メイン関数"""
    print("📝 ドキュメントを生成中...")
    
    generate_readme()
    generate_usage_guide()
    
    print("🎉 ドキュメント生成が完了しました！")
    print("📖 README.md - プロジェクト概要")
    print("📚 USAGE.md - 詳細な使用方法")

if __name__ == "__main__":
    main()