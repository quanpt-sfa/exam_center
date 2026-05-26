"""Private storage helpers for exam-version visual paper assets."""

from __future__ import annotations

import os
from pathlib import Path, PurePath
import re
from uuid import uuid4


DEFAULT_PAPER_STORAGE_ROOT = "var/private/exam_papers"
DEFAULT_PAPER_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

ALLOWED_PAPER_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
    }
)

_MIME_TO_EXTENSION = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def get_paper_max_file_size_bytes() -> int:
    raw = os.getenv("EXAM_SYS_PAPER_ASSET_MAX_BYTES", str(DEFAULT_PAPER_MAX_FILE_SIZE_BYTES)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_PAPER_MAX_FILE_SIZE_BYTES
    if value <= 0:
        return DEFAULT_PAPER_MAX_FILE_SIZE_BYTES
    return value


def get_paper_storage_root() -> Path:
    configured = os.getenv("EXAM_SYS_PAPER_STORAGE_ROOT", DEFAULT_PAPER_STORAGE_ROOT).strip()
    candidate = Path(configured) if configured else Path(DEFAULT_PAPER_STORAGE_ROOT)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def sanitize_original_filename(filename: str | None) -> str:
    base_name = PurePath(str(filename or "").strip()).name
    if not base_name:
        return "paper_asset"
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)
    return cleaned or "paper_asset"


def extension_for_mime_type(mime_type: str) -> str:
    return _MIME_TO_EXTENSION.get(str(mime_type).strip().lower(), "")


def build_stored_filename(mime_type: str) -> str:
    return f"{uuid4().hex}{extension_for_mime_type(mime_type)}"


def detect_mime_type_by_signature(file_bytes: bytes) -> str | None:
    if file_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None


def normalize_relative_storage_path(relative_path: str) -> str:
    cleaned = str(relative_path or "").strip().replace("\\", "/")
    if not cleaned:
        raise ValueError("relative_path must not be empty")
    if cleaned.startswith("/"):
        raise ValueError("relative_path must not be absolute")
    path = PurePath(cleaned)
    if any(part == ".." for part in path.parts):
        raise ValueError("relative_path contains invalid traversal segment")
    return "/".join(path.parts)


def resolve_storage_path(relative_path: str) -> Path:
    root = get_paper_storage_root()
    normalized = normalize_relative_storage_path(relative_path)
    target = (root / normalized).resolve()
    if root != target and root not in target.parents:
        raise ValueError("resolved path escapes storage root")
    return target

