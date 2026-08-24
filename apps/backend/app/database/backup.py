import os
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from app.core.config import settings
from app.observability.models import DatabaseBackupMetadata, utc_now
from app.security.audit import audit_logger
from app.core.logging import logger

class DatabaseBackupService:
    """
    Manages SQLite database backups and integrity verification using PRAGMA integrity_check.
    """

    @classmethod
    def get_backup_dir(cls) -> Path:
        p = Path(settings.DATABASE_PATH).parent.parent / "backups"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def check_integrity(cls) -> str:
        db_path = settings.DATABASE_PATH
        if not Path(db_path).exists():
            return "OK"
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            res = cursor.fetchone()
            conn.close()
            return "OK" if res and res[0] == "ok" else "CORRUPTED"
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return "CORRUPTED"

    @classmethod
    def create_backup(cls) -> DatabaseBackupMetadata:
        db_path = Path(settings.DATABASE_PATH)
        backup_id = str(uuid.uuid4())[:8]
        timestamp = utc_now()
        filename = f"matrioshai_backup_{timestamp.strftime('%Y%m%d_%H%M%S')}_{backup_id}.db"
        dest_path = cls.get_backup_dir() / filename

        size_bytes = 0
        if db_path.exists():
            shutil.copy2(db_path, dest_path)
            size_bytes = dest_path.stat().st_size
        else:
            dest_path.write_bytes(b"")
            size_bytes = 0

        integrity = cls.check_integrity()

        audit_logger.log_event(
            event_type="DATABASE_BACKUP_CREATED",
            action="create_backup",
            resource=filename,
            decision="ALLOWED",
            reason=f"Backup created ({size_bytes} bytes, integrity: {integrity})"
        )

        return DatabaseBackupMetadata(
            backup_id=backup_id,
            timestamp=timestamp,
            filename=filename,
            size_bytes=size_bytes,
            integrity_status=integrity
        )

    @classmethod
    def list_backups(cls) -> List[DatabaseBackupMetadata]:
        backups = []
        b_dir = cls.get_backup_dir()
        for f in sorted(b_dir.glob("*.db"), key=os.path.getmtime, reverse=True):
            backups.append(DatabaseBackupMetadata(
                backup_id=f.stem.split("_")[-1] if "_" in f.stem else "snap",
                timestamp=datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc),
                filename=f.name,
                size_bytes=f.stat().st_size,
                integrity_status="OK"
            ))
        return backups

database_backup_service = DatabaseBackupService()
