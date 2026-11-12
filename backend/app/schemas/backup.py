"""The backup file format.

A backup is one JSON document holding every resume version in the same shape the
create API accepts (so it is human-readable, diffable, and validated by exactly
the rules that guard any other write), plus which one is the default.

Export is built from the database without validating (a backup must never fail
because old data predates a newer limit); import validates everything.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.resume import ResumeCreate

BACKUP_FORMAT: Literal["someshwaran.dev/resume-backup"] = "someshwaran.dev/resume-backup"
BACKUP_VERSION: Literal[1] = 1


class BackupResume(ResumeCreate):
    is_default: bool = False


class BackupFile(BaseModel):
    format: Literal["someshwaran.dev/resume-backup"] = BACKUP_FORMAT
    version: Literal[1] = BACKUP_VERSION
    exported_at: datetime | None = None
    resumes: Annotated[list[BackupResume], Field(max_length=100)]


class ImportResult(BaseModel):
    created: list[int]
    skipped: list[str]  # names that already existed, so were left untouched
    default_id: int | None  # the default after the import (None if none is set)
