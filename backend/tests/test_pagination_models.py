"""Tests for reusable pagination models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.pagination import PaginationRequest, PaginationResponse


def test_pagination_request_defaults() -> None:
    model = PaginationRequest()
    assert model.page == 1
    assert model.page_size == 20


def test_pagination_request_validates_bounds() -> None:
    with pytest.raises(ValidationError):
        PaginationRequest(page=0, page_size=20)

    with pytest.raises(ValidationError):
        PaginationRequest(page=1, page_size=0)


def test_pagination_response_fields() -> None:
    model = PaginationResponse(page=1, page_size=10, total=2, items=[{"id": 1}, {"id": 2}])

    assert model.page == 1
    assert model.page_size == 10
    assert model.total == 2
    assert len(model.items) == 2


def test_pagination_response_total_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        PaginationResponse(page=1, page_size=10, total=-1, items=[])
