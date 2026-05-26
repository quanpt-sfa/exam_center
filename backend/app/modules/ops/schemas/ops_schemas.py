"""Request/response schemas for Ops API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OpsCommandRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_code: str = Field(min_length=2, max_length=100)
    command_text: str | None = Field(default=None, max_length=4000)
    event_payload: dict | None = None
