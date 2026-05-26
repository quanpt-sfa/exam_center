"""Logging setup for exam-sys-next API."""

from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    """Configure root logging once for local development."""

    log_level = os.getenv("EXAM_SYS_NEXT_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
