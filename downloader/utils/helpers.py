from __future__ import annotations

import json
import random
import re
from pathlib import Path
from urllib.parse import urlparse

ACCEPTED_PT_BR = {"pt-br", "pt", "pt_br", "brazilian-portuguese"}
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".avif")

CHROME_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


def normalize_language(lang: str | None) -> str:
    if not lang:
        return ""
    return lang.strip().lower().replace("_", "-")


def is_pt_br(lang: str | None) -> bool:
    return normalize_language(lang) in ACCEPTED_PT_BR


def sanitize_name(name: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return value or "unknown"


def infer_ext(url: str) -> str:
    lower = url.lower()
    for ext in IMAGE_EXTENSIONS:
        if ext in lower:
            return ext
    return ".jpg"


def random_user_agent() -> str:
    return random.choice(CHROME_UAS)


def host_from_url(url: str) -> str:
    return urlparse(url).netloc.lower()


def dump_summary(path: Path, payload: list[dict]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
