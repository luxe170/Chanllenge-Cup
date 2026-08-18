"""In-memory task store for resume parsing.

Resume analysis is fully deterministic today (catalog rules + regex on the raw
text), so we finish the work synchronously inside ``create_task`` but still
expose the async task shape the frontend contract requires: the client
uploads once, receives ``taskId``, and polls ``GET /resume-tasks/{taskId}``.

Persisting resume tasks in Postgres is out of scope for this module — the
resume is user-uploaded, may contain PII, and the graph backend contract
explicitly places resume/matching data outside the graph database.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .resume import ResumeProfile, ResumeSkill, parse_resume_text
from .resume_text import ResumeTextError, extract_resume_text


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB, matches the frontend copy


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ResumeTask:
    id: str
    filename: str
    fileSize: int
    status: str  # queued | processing | succeeded | failed
    progress: int  # 0-100
    createdAt: datetime
    updatedAt: datetime
    error: str | None = None
    profile: ResumeProfile | None = None
    userEdits: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "filename": self.filename,
            "fileSize": self.fileSize,
            "status": self.status,
            "progress": self.progress,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
            "error": self.error,
        }
        if self.profile is not None:
            data = self.profile.as_dict()
            # Merge user-side edits (skill CRUD) on top of the extractor output.
            if self.userEdits.get("skills"):
                data["skills"] = list(self.userEdits["skills"])
            payload["result"] = data
        return payload


class ResumeTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, ResumeTask] = {}
        self._lock = threading.Lock()

    def create(self, filename: str, data: bytes) -> ResumeTask:
        if not filename:
            raise ValueError("filename is required")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError(f"resume file exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
        task_id = f"resume_{uuid.uuid4().hex}"
        now = _now()
        task = ResumeTask(
            id=task_id,
            filename=filename,
            fileSize=len(data),
            status="processing",
            progress=10,
            createdAt=now,
            updatedAt=now,
        )
        with self._lock:
            self._tasks[task_id] = task
        try:
            text = extract_resume_text(filename, data)
            task.progress = 60
            profile = parse_resume_text(text)
            task.profile = profile
            task.status = "succeeded"
            task.progress = 100
        except ResumeTextError as exc:
            task.status = "failed"
            task.progress = 100
            task.error = str(exc)
        except ValueError as exc:
            task.status = "failed"
            task.progress = 100
            task.error = str(exc)
        task.updatedAt = _now()
        return task

    def get(self, task_id: str) -> ResumeTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def apply_skill_edits(
        self,
        task_id: str,
        added: list[dict[str, Any]] | None,
        removed: list[str] | None,
        updated: list[dict[str, Any]] | None,
    ) -> ResumeTask | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.profile is None:
                return task
            # Start from either the last-edited state or the original extractor output.
            current = list(task.userEdits.get("skills") or [item.as_dict() for item in task.profile.skills])
            if removed:
                remove_set = set(removed)
                current = [item for item in current if item["id"] not in remove_set and item["name"] not in remove_set]
            if updated:
                by_id = {item["id"]: item for item in current}
                for change in updated:
                    key = change.get("id") or change.get("name")
                    if key in by_id:
                        by_id[key].update({k: v for k, v in change.items() if k in {"name", "level", "source", "confidence"}})
                current = list(by_id.values())
            if added:
                existing_ids = {item["id"] for item in current}
                for skill in added:
                    skill_id = skill.get("id") or f"custom_{uuid.uuid4().hex[:8]}"
                    if skill_id in existing_ids:
                        continue
                    current.append(
                        ResumeSkill(
                            id=skill_id,
                            name=skill.get("name", "").strip() or skill_id,
                            level=skill.get("level", "掌握"),
                            source=skill.get("source", "用户补充"),
                            confidence=float(skill.get("confidence", 1.0)),
                        ).as_dict()
                    )
                    existing_ids.add(skill_id)
            task.userEdits["skills"] = current
            task.updatedAt = _now()
            return task


_store = ResumeTaskStore()


def get_resume_task_store() -> ResumeTaskStore:
    return _store
