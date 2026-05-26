"""Private storage helpers for student-submitted answer files."""

from __future__ import annotations

import os
from pathlib import Path, PurePath
import re
from uuid import uuid4


DEFAULT_ANSWER_FILE_STORAGE_ROOT = "var/private/answer_files"
DEFAULT_ANSWER_FILE_MAX_BYTES = 25 * 1024 * 1024

DEFAULT_ALLOWED_EXTENSIONS = frozenset({".zip", ".pdf", ".docx", ".xlsx", ".csv", ".sql", ".txt", ".json"})

MIME_BY_EXTENSION: dict[str, frozenset[str]] = {
    ".zip": frozenset({"application/zip", "application/x-zip-compressed"}),
    ".pdf": frozenset({"application/pdf"}),
    ".docx": frozenset({"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
    ".xlsx": frozenset({"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}),
    ".csv": frozenset({"text/csv", "application/csv", "text/plain"}),
    ".sql": frozenset({"application/sql", "text/plain", "application/octet-stream"}),
    ".txt": frozenset({"text/plain"}),
    ".json": frozenset({"application/json", "text/json"}),
}

DEFAULT_ALLOWED_MIME_TYPES = frozenset(
    mime_type for mime_set in MIME_BY_EXTENSION.values() for mime_type in mime_set
)

DANGEROUS_EXTENSIONS = frozenset(
    {".exe", ".bat", ".cmd", ".ps1", ".msi", ".scr", ".js", ".vbs", ".jar", ".com", ".dll"}
)

STRICT_BINARY_SIGNATURE_EXTENSIONS = frozenset({".pdf", ".zip", ".docx", ".xlsx"})


def get_answer_file_storage_root() -> Path:
    configured = os.getenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", DEFAULT_ANSWER_FILE_STORAGE_ROOT).strip()
    candidate = Path(configured) if configured else Path(DEFAULT_ANSWER_FILE_STORAGE_ROOT)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def get_answer_file_max_bytes() -> int:
    raw = os.getenv("EXAM_SYS_ANSWER_FILE_MAX_BYTES", str(DEFAULT_ANSWER_FILE_MAX_BYTES)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_ANSWER_FILE_MAX_BYTES
    if value <= 0:
        return DEFAULT_ANSWER_FILE_MAX_BYTES
    return value


def sanitize_original_filename(filename: str | None) -> str:
    base_name = PurePath(str(filename or "").strip()).name
    if not base_name:
        return "answer_file"
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)
    return cleaned or "answer_file"


def file_extension(filename: str) -> str:
    return Path(filename).suffix.lower().strip()


def normalized_allowed_extensions(configured: list[str] | None = None) -> set[str]:
    source = configured if configured else list(DEFAULT_ALLOWED_EXTENSIONS)
    normalized = {str(item).strip().lower() for item in source if str(item).strip()}
    return {ext if ext.startswith(".") else f".{ext}" for ext in normalized}


def normalized_allowed_mimes(configured: list[str] | None = None) -> set[str]:
    source = configured if configured else list(DEFAULT_ALLOWED_MIME_TYPES)
    return {str(item).strip().lower() for item in source if str(item).strip()}


def is_dangerous_extension(extension: str) -> bool:
    return extension.lower() in DANGEROUS_EXTENSIONS


def stored_filename_for_upload(original_filename: str) -> str:
    extension = file_extension(original_filename)
    return f"{uuid4().hex}{extension}"


def internal_storage_key_for_upload(submission_id: int, question_id: int, stored_filename: str) -> str:
    return f"{int(submission_id)}/{int(question_id)}/{stored_filename}"


def resolve_answer_storage_path(internal_storage_key: str) -> Path:
    cleaned = str(internal_storage_key or "").strip().replace("\\", "/")
    if not cleaned:
        raise ValueError("internal_storage_key must not be empty")
    if cleaned.startswith("/"):
        raise ValueError("internal_storage_key must not be absolute")
    path = PurePath(cleaned)
    if any(part == ".." for part in path.parts):
        raise ValueError("internal_storage_key contains invalid traversal segment")
    root = get_answer_file_storage_root()
    resolved = (root / Path(*path.parts)).resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError("resolved path escapes storage root")
    return resolved


def detect_mime_type_by_signature(file_head: bytes) -> str | None:
    if file_head.startswith(b"%PDF-"):
        return "application/pdf"
    if file_head.startswith(b"PK\x03\x04") or file_head.startswith(b"PK\x05\x06") or file_head.startswith(b"PK\x07\x08"):
        return "application/zip"
    if file_head.startswith(b"{") or file_head.startswith(b"["):
        return "application/json"
    return None


def allowed_mimes_for_extension(extension: str) -> set[str]:
    return set(MIME_BY_EXTENSION.get(extension.lower(), frozenset()))


def preferred_mime_for_extension(extension: str) -> str | None:
    extension_mimes = allowed_mimes_for_extension(extension)
    if not extension_mimes:
        return None
    preferred_order = (
        "application/zip",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "application/csv",
        "application/sql",
        "text/plain",
        "application/json",
        "text/json",
        "application/octet-stream",
    )
    for candidate in preferred_order:
        if candidate in extension_mimes:
            return candidate
    return next(iter(extension_mimes))

