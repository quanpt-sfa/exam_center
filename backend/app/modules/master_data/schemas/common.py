"""Shared schema contracts for master data services."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PaginationRequest(BaseModel):
    """Generic page/page-size request contract."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=1000)


class PaginationMetadata(BaseModel):
    """Standardized pagination metadata for list responses."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool


class SortRequest(BaseModel):
    """Generic sorting request contract."""

    model_config = ConfigDict(extra="forbid")

    sort_by: str | None = Field(default=None, max_length=100)
    sort_order: Literal["asc", "desc"] = "asc"


class StatusFilter(BaseModel):
    """Simple status filtering contract for list queries."""

    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(default=None, max_length=50)


class ValidationErrorItem(BaseModel):
    """Validation issue descriptor for service-layer checks."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)


class StandardListResponse(BaseModel):
    """Uniform list response contract for master data APIs."""

    items: list[dict[str, Any]] = Field(default_factory=list)
    pagination: PaginationMetadata


class StandardMutationResponse(BaseModel):
    """Uniform mutation response contract for master data APIs."""

    success: bool = True
    entity_id: int | None = None
    message: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ImportPreviewPlaceholderSchema(BaseModel):
    """Reserved schema for future import-preview worker responses."""

    status: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"
    worker_required: bool = True
    message: str = "Import preview worker is not implemented in MD-1 foundation"
