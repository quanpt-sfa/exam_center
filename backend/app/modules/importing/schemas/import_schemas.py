"""Request/response schemas for Import API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ImportJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_code: str = Field(min_length=3, max_length=100)
    command_code: str | None = Field(default=None, max_length=100)


class ImportCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_code: str | None = Field(default="IMPORT_COMMIT", max_length=100)


class ImportRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=1000)


class ImportPreviewQuery(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ImportTemplatesResponse(BaseModel):
    templates: list[dict]
