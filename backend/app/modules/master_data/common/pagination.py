"""Reusable pagination helpers for master data list APIs."""

from __future__ import annotations

from dataclasses import dataclass
import math


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
DEFAULT_MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class PaginationParams:
    """Normalized pagination values plus SQL-friendly offset/limit."""

    page: int
    page_size: int
    offset: int
    limit: int


def normalize_pagination(
    page: int | None,
    page_size: int | None,
    *,
    default_page: int = DEFAULT_PAGE,
    default_page_size: int = DEFAULT_PAGE_SIZE,
    max_page_size: int = DEFAULT_MAX_PAGE_SIZE,
) -> tuple[int, int]:
    """Normalize page and page_size with sane defaults and hard caps."""

    normalized_page = default_page if page is None else int(page)
    if normalized_page < 1:
        normalized_page = default_page

    normalized_page_size = default_page_size if page_size is None else int(page_size)
    if normalized_page_size < 1:
        normalized_page_size = default_page_size
    if normalized_page_size > max_page_size:
        normalized_page_size = max_page_size

    return normalized_page, normalized_page_size


def compute_offset_limit(page: int, page_size: int) -> tuple[int, int]:
    """Compute SQL offset/limit from normalized pagination values."""

    normalized_page = max(int(page), 1)
    normalized_page_size = max(int(page_size), 1)
    offset = (normalized_page - 1) * normalized_page_size
    return offset, normalized_page_size


def build_pagination_params(
    page: int | None,
    page_size: int | None,
    *,
    default_page: int = DEFAULT_PAGE,
    default_page_size: int = DEFAULT_PAGE_SIZE,
    max_page_size: int = DEFAULT_MAX_PAGE_SIZE,
) -> PaginationParams:
    """Build a compact object for repository list queries."""

    normalized_page, normalized_page_size = normalize_pagination(
        page=page,
        page_size=page_size,
        default_page=default_page,
        default_page_size=default_page_size,
        max_page_size=max_page_size,
    )
    offset, limit = compute_offset_limit(normalized_page, normalized_page_size)
    return PaginationParams(page=normalized_page, page_size=normalized_page_size, offset=offset, limit=limit)


def build_pagination_metadata(*, page: int, page_size: int, total: int) -> dict[str, int | bool]:
    """Return response metadata for paged list endpoints."""

    normalized_page = max(int(page), 1)
    normalized_page_size = max(int(page_size), 1)
    normalized_total = max(int(total), 0)

    total_pages = 0 if normalized_total == 0 else math.ceil(normalized_total / normalized_page_size)
    has_next = normalized_page < total_pages
    has_previous = normalized_page > 1 and total_pages > 0

    return {
        "page": normalized_page,
        "page_size": normalized_page_size,
        "total": normalized_total,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_previous": has_previous,
    }
