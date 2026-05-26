"""Reusable pagination models for future domain APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PaginationRequest(BaseModel):
    """Common pagination input model."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


class PaginationResponse(BaseModel):
    """Common pagination output model."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)
    items: list[Any] = Field(default_factory=list)
