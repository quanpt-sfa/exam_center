"""Tests for master data pagination helpers."""

from __future__ import annotations

from app.modules.master_data.common.pagination import (
    build_pagination_metadata,
    build_pagination_params,
    normalize_pagination,
)


def test_normalize_pagination_defaults() -> None:
    page, page_size = normalize_pagination(page=None, page_size=None)

    assert page == 1
    assert page_size == 20


def test_normalize_pagination_enforces_max_page_size() -> None:
    page, page_size = normalize_pagination(page=2, page_size=9999, max_page_size=200)

    assert page == 2
    assert page_size == 200


def test_build_pagination_params_computes_offset_and_limit() -> None:
    params = build_pagination_params(page=3, page_size=25)

    assert params.page == 3
    assert params.page_size == 25
    assert params.offset == 50
    assert params.limit == 25


def test_build_pagination_metadata_values() -> None:
    metadata = build_pagination_metadata(page=2, page_size=20, total=45)

    assert metadata["page"] == 2
    assert metadata["page_size"] == 20
    assert metadata["total"] == 45
    assert metadata["total_pages"] == 3
    assert metadata["has_next"] is True
    assert metadata["has_previous"] is True
