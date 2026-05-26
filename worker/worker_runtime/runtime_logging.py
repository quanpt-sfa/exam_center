"""Safe runtime logging helpers for worker orchestration loops."""

from __future__ import annotations

import json
import logging
import re
from typing import Any


_SENSITIVE_KEYWORDS = {
    "password",
    "dsn",
    "raw_answer",
    "answer_state",
    "sealed_answer",
    "capture_dataset_rows",
    "artifact_payload",
}


def _sanitize_text(value: str | None) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)postgres(?:ql)?://[^\s,;]+", "<redacted_dsn>", text)
    text = re.sub(r"(?i)(dsn\s*[:=]\s*)([^,\s;]+)", r"\1<redacted>", text)
    text = re.sub(r"(?i)(password\s*[:=]\s*)([^,\s;]+)", r"\1<redacted>", text)
    text = re.sub(r"(?i)\b(answer_state|raw_answer|sealed_answer)\b", "<redacted_field>", text)
    return text


def sanitize_log_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, raw in value.items():
            token = str(key).strip().lower()
            if token in _SENSITIVE_KEYWORDS:
                sanitized[str(key)] = "<redacted>"
            else:
                sanitized[str(key)] = sanitize_log_value(raw)
        return sanitized
    if isinstance(value, (list, tuple, set)):
        return [sanitize_log_value(item) for item in value]
    return _sanitize_text(str(value))


def log_runtime_cycle(
    logger: logging.Logger,
    *,
    role: str,
    worker_id: str,
    cycle_number: int,
    outcome: dict[str, Any],
) -> None:
    payload = {
        "role": str(role),
        "worker_id": str(worker_id),
        "cycle": int(cycle_number),
        "outcome": sanitize_log_value(outcome),
    }
    logger.info("runtime_loop_cycle %s", json.dumps(payload, sort_keys=True))
