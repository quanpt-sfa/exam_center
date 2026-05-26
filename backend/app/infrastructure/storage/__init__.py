"""Storage utilities for backend runtime artifacts."""

from .answer_files import get_answer_file_storage_root
from .paper_assets import get_paper_storage_root

__all__ = ["get_answer_file_storage_root", "get_paper_storage_root"]
