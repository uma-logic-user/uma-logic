#!/usr/bin/env python3
"""
ヘルスチェックスクリプト
- システムの健全性を確認するためのチェックポイント
- 定期的な監視やデプロイ前の確認に使用
"""

import json
import sys
from pathlib import Path
import logging

def setup_logging():
    """ロギング設定"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/health_check.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def check_dependencies():
    """依存関係のチェック"""
    logger.info("🔍 依存関係をチェック中...")
    
    required = ['requests', 'beautifulsoup4']
    missing = []
    
    for package in required:
        try:
            if package == 'beautifulsoup4':
                __import__('bs4')
            else:
                __import__(package)
            logger.info(f"✅ {package} が利用可能")
        except ImportError:
            missing.append(package)
            logger.warning(f"❌ {package} が見つかりません")
    
    return len(missing) == 0

def check_data_directories():
    """データディレクトリのチェック"""
    logger.info("📁 データディレクトリをチェック中...")
    
    directories = [
        Path('data'),
        Path('data/history'),
        Path('logs')
    ]
    
    all_ok = True
    for directory in directories:
        if directory.exists() and directory.is_dir():
            logger.info(f"✅ {directory} が存在")
        else:
            logger.warning(f"❌ {directory} が存在しません")
            all_ok = False
    
    return all_ok

def check_recent_predictions():
    """最近の予想ファイルのチェック"""
    logger.info("📊 最近の予想ファイルをチェック中...")
    
    history_dir = Path('data/history')
    if not history_dir.exists():
        logger.warning("履歴ディレクトリが存在しません")
        return False
    
    prediction_files = list(history_dir.glob('predictions_*.json'))
    if not prediction_files:
        logger.warning("予想ファイルが見つかりません")
        return False
    
    # 最新のファイルをチェック
    latest_file = max(prediction_files, key=lambda x: x.stat().st_mtime)
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        races = data.get('races', [])
        logger.info(f"✅ 最新の予想ファイル: {latest_file.name} ({len(races)}レース)")
        return True
    except Exception as e:
        logger.error(f"予想ファイルの読み込みに失敗: {e}")
        return False

def check_config_file():
    """設定ファイルのチェック"""
    logger.info("⚙️ 設定ファイルをチェック中...")
    
    config_file = Path('config')
    if not config_file.exists():
        logger.warning("設定ファイルが存在しません")
        return False
    
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read(config_file, encoding='utf-8')
        
        # 必須セクションのチェック
        required_sections = ['odds_fetch', 'network', 'logging']
        for section in required_sections:
            if not config.has_section(section):
                logger.warning(f"セクション '{section}' が存在しません")
                return False
        
        logger.info("✅ 設定ファイルが正常")
        return True
    except Exception as e:
        logger.error(f"設定ファイルの読み込みに失敗: {e}")
        return False

def main():
    """メインヘルスチェック"""
    logger.info("🚀 ヘルスチェックを開始します")
    
    checks = [
        ("依存関係", check_dependencies),
        ("データディレクトリ", check_data_directories),
        ("予想ファイル", check_recent_predictions),
        ("設定ファイル", check_config_file)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"{name} チェック中にエラー: {e}")
            results.append((name, False))
    
    # 結果の集計
    logger.info("\n📋 ヘルスチェック結果:")
    all_passed = True
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        logger.info("🎉 すべてのチェックが成功しました！システムは正常です。")
        return 0
    else:
        logger.error("⚠️ 一部のチェックが失敗しました。設定を確認してください。")
        return 1

if __name__ == "__main__":
    sys.exit(main())