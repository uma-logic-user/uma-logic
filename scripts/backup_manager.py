#!/usr/bin/env python3
import json
import shutil
import gzip
import tarfile
from pathlib import Path
from datetime import datetime, timedelta
import logging

def setup_logging():
    """ロギング設定"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/backup.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class BackupManager:
    def __init__(self, backup_dir="backups", max_backups=30):
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_backup(self, source_dir="data"):
        source_path = Path(source_dir)
        if not source_path.exists():
            logger.error(f"ソースディレクトリが存在しません: {source_dir}")
            return False
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        try:
            if source_path.is_dir():
                shutil.copytree(source_path, backup_path)
                logger.info(f"✅ バックアップを作成しました: {backup_name}")
            else:
                shutil.copy2(source_path, backup_path)
                logger.info(f"✅ ファイルをバックアップしました: {backup_name}")
            
            self._compress_backup(backup_path)
            
            self._cleanup_old_backups()
            
            return True
            
        except Exception as e:
            logger.error(f"バックアップ作成エラー: {e}")
            return False
    
    def create_project_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        backup_name = f"project_{timestamp}"
        temp_dir = self.backup_dir / backup_name
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
            root_files = ["app.py", "main.py", "start_app.bat"]
            for rf in root_files:
                src = Path(__file__).resolve().parent.parent / rf
                if src.exists():
                    shutil.copy2(src, temp_dir / rf)
            scripts_dir = Path(__file__).resolve().parent
            scripts_out = temp_dir / "scripts"
            scripts_out.mkdir(parents=True, exist_ok=True)
            for p in scripts_dir.glob("*.py"):
                shutil.copy2(p, scripts_out / p.name)
            data_dir = Path(__file__).resolve().parent.parent / "data"
            data_out = temp_dir / "data_json"
            data_out.mkdir(parents=True, exist_ok=True)
            for p in data_dir.glob("*.json"):
                shutil.copy2(p, data_out / p.name)
            tar_path = temp_dir.with_suffix(".tar.gz")
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(temp_dir, arcname=temp_dir.name)
            shutil.rmtree(temp_dir)
            logger.info(f"📦 プロジェクトバックアップを作成しました: {tar_path.name}")
            self._cleanup_old_backups()
            return True
        except Exception as e:
            logger.error(f"プロジェクトバックアップ作成エラー: {e}")
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except Exception:
                pass
            return False
    
    def _compress_backup(self, backup_path):
        try:
            if backup_path.is_dir():
                tar_path = backup_path.with_suffix('.tar.gz')
                with tarfile.open(tar_path, 'w:gz') as tar:
                    tar.add(backup_path, arcname=backup_path.name)
                
                shutil.rmtree(backup_path)
                logger.info(f"📦 バックアップを圧縮しました: {tar_path.name}")
            
        except Exception as e:
            logger.warning(f"圧縮に失敗しました: {e}")
    
    def _cleanup_old_backups(self):
        try:
            backups = list(self.backup_dir.glob("backup_*"))
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            if len(backups) > self.max_backups:
                for old_backup in backups[self.max_backups:]:
                    if old_backup.is_dir():
                        shutil.rmtree(old_backup)
                    else:
                        old_backup.unlink()
                    logger.info(f"🗑️ 古いバックアップを削除: {old_backup.name}")
        
        except Exception as e:
            logger.error(f"バックアップ削除エラー: {e}")
    
    def list_backups(self):
        backups = list(self.backup_dir.glob("backup_*"))
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        logger.info("📋 バックアップ一覧:")
        for i, backup in enumerate(backups, 1):
            size = backup.stat().st_size
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            logger.info(f"  {i}. {backup.name} ({size/1024/1024:.1f}MB, {mtime:%Y-%m-%d %H:%M})")
        
        return backups
    
    def restore_backup(self, backup_name, target_dir="data"):
        backup_path = self.backup_dir / backup_name
        target_path = Path(target_dir)
        
        if not backup_path.exists():
            logger.error(f"バックアップが存在しません: {backup_name}")
            return False
        
        try:
            if target_path.exists():
                temp_backup = self.backup_dir / f"restore_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copytree(target_path, temp_backup)
                logger.info(f"🔒 現在のデータを一時バックアップ: {temp_backup.name}")
            
            if target_path.exists():
                shutil.rmtree(target_path)
            
            if backup_path.suffix == '.gz':
                with tarfile.open(backup_path, 'r:gz') as tar:
                    tar.extractall(target_path.parent)
            else:
                if backup_path.is_dir():
                    shutil.copytree(backup_path, target_path)
                else:
                    shutil.copy2(backup_path, target_path)
            
            logger.info(f"🔄 バックアップから復元しました: {backup_name} → {target_dir}")
            return True
            
        except Exception as e:
            logger.error(f"復元エラー: {e}")
            return False
    
    def auto_backup(self):
        logger.info("🤖 自動バックアップを開始します")
        
        success = self.create_backup("data")
        success_proj = self.create_project_backup()
        
        if success_data or success_proj:
            logger.info("✅ 自動バックアップが正常終了しました")
        else:
            logger.error("❌ 自動バックアップが失敗しました")
        
        return success_data or success_proj

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="バックアップ管理ツール")
    parser.add_argument('action', choices=['create', 'list', 'restore', 'auto', 'project'], 
                       help='実行するアクション')
    parser.add_argument('--name', help='復元するバックアップ名')
    parser.add_argument('--target', default='data', help='復元先ディレクトリ')
    
    args = parser.parse_args()
    
    manager = BackupManager()
    
    if args.action == 'create':
        manager.create_backup()
    elif args.action == 'list':
        manager.list_backups()
    elif args.action == 'restore':
        if not args.name:
            logger.error("復元するバックアップ名を指定してください")
            return
        manager.restore_backup(args.name, args.target)
    elif args.action == 'auto':
        manager.auto_backup()
    elif args.action == 'project':
        manager.create_project_backup()

if __name__ == "__main__":
    main()
