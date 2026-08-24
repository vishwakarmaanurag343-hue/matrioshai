import os
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import logger
from app.models.db_models import Note

class NotesService:
    def __init__(self, db: Session):
        self.db = db
        self.notes_dir = Path(settings.NOTES_PATH).resolve()
        self.notes_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_slug(self, title: str) -> str:
        slug = re.sub(r'[^a-zA-Z0-9_\-]+', '-', title.lower()).strip('-')
        return slug or "untitled-note"

    def _get_relative_path(self, title: str) -> Path:
        now = datetime.now(timezone.utc)
        year_str = now.strftime("%Y")
        month_str = now.strftime("%m")
        dir_path = self.notes_dir / year_str / month_str
        dir_path.mkdir(parents=True, exist_ok=True)
        
        slug = self._sanitize_slug(title)
        filename = f"{slug}.md"
        target_path = dir_path / filename

        # De-duplicate filename if it already exists
        counter = 1
        while target_path.exists():
            target_path = dir_path / f"{slug}-{counter}.md"
            counter += 1

        return target_path

    def _validate_safe_path(self, file_path_str: str) -> Path:
        p = Path(file_path_str).resolve()
        # Ensure symlinks cannot escape the base directory
        real_p = Path(os.path.realpath(str(p)))
        real_notes_dir = Path(os.path.realpath(str(self.notes_dir)))
        if not str(real_p).startswith(str(real_notes_dir)):
            raise ValueError(f"Security error: Path traversal or symlink escape detected. Access to '{file_path_str}' is forbidden.")
        return real_p

    def create_note(self, title: str, content: str, tags: Optional[List[str]] = None) -> Note:
        tags = tags or []
        target_path = self._get_relative_path(title)
        self._validate_safe_path(str(target_path))

        # Write Markdown file
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Index in SQLite
        rel_file_path = str(target_path.relative_to(self.notes_dir))
        note = Note(
            title=title,
            file_path=rel_file_path,
            source="user",
            tags_json=json.dumps(tags)
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        logger.info(f"Created note '{title}' at {rel_file_path}")
        return note

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        note = self.db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return None

        abs_path = (self.notes_dir / note.file_path).resolve()
        self._validate_safe_path(str(abs_path))

        content = ""
        if abs_path.exists():
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

        tags = json.loads(note.tags_json) if note.tags_json else []
        return {
            "id": note.id,
            "file_path": note.file_path,
            "title": note.title,
            "content": content,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "source": note.source,
            "tags": tags
        }

    def update_note(self, note_id: str, title: Optional[str] = None, content: Optional[str] = None, tags: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        note = self.db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return None

        abs_path = (self.notes_dir / note.file_path).resolve()
        self._validate_safe_path(str(abs_path))

        if title and title != note.title:
            note.title = title
        if tags is not None:
            note.tags_json = json.dumps(tags)

        if content is not None and abs_path.exists():
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)

        self.db.commit()
        self.db.refresh(note)
        return self.get_note(note_id)

    def delete_note(self, note_id: str) -> bool:
        note = self.db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return False

        abs_path = (self.notes_dir / note.file_path).resolve()
        try:
            self._validate_safe_path(str(abs_path))
            if abs_path.exists():
                os.remove(abs_path)
        except ValueError as e:
            logger.error(f"Path safety error on note delete: {e}")
            return False

        self.db.delete(note)
        self.db.commit()
        logger.info(f"Deleted note [{note_id}]")
        return True

    def list_notes(self, query: Optional[str] = None, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        q = self.db.query(Note)
        if query:
            q = q.filter(Note.title.ilike(f"%{query}%"))
        
        notes = q.order_by(Note.updated_at.desc()).all()
        results = []
        for n in notes:
            tags = json.loads(n.tags_json) if n.tags_json else []
            if tag and tag not in tags:
                continue
            
            abs_path = (self.notes_dir / n.file_path).resolve()
            content_snippet = ""
            if abs_path.exists():
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        content_snippet = "".join(lines[:3])
                except Exception:
                    pass

            results.append({
                "id": n.id,
                "file_path": n.file_path,
                "title": n.title,
                "content": content_snippet,
                "created_at": n.created_at,
                "updated_at": n.updated_at,
                "source": n.source,
                "tags": tags
            })
        return results
