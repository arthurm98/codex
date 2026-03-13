from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class Chapter:
    manga_title: str
    chapter_id: str
    chapter_title: str
    chapter_url: str
    language: str


@dataclass(slots=True)
class DownloadResult:
    manga_title: str
    chapter: str
    pages_downloaded: int
    failed_pages: int
    folder: Path
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
