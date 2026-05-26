"""Schemas for master-data facility APIs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic import model_validator


class RoomCreateCommand(BaseModel):
    """Create payload for one room."""

    model_config = ConfigDict(extra="forbid")

    room_code: str = Field(min_length=1, max_length=100)
    room_name: str = Field(min_length=1, max_length=255)
    building: str | None = Field(default=None, max_length=255)
    floor_no: str | None = Field(default=None, max_length=50)
    capacity: int | None = Field(default=None, ge=0)
    room_type: str = Field(default="LAB", min_length=1, max_length=50)
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)


class RoomUpdateCommand(BaseModel):
    """Patch payload for one room."""

    model_config = ConfigDict(extra="forbid")

    room_code: str | None = Field(default=None, min_length=1, max_length=100)
    room_name: str | None = Field(default=None, min_length=1, max_length=255)
    building: str | None = Field(default=None, max_length=255)
    floor_no: str | None = Field(default=None, max_length=50)
    capacity: int | None = Field(default=None, ge=0)
    room_type: str | None = Field(default=None, min_length=1, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=30)


class RoomDeactivateCommand(BaseModel):
    """Deactivate payload for one room."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
    force: bool = False


class DeviceCreateCommand(BaseModel):
    """Create payload for one device."""

    model_config = ConfigDict(extra="forbid")

    device_code: str | None = Field(default=None, min_length=1, max_length=100)
    asset_tag: str | None = Field(default=None, min_length=1, max_length=100)
    device_name: str | None = Field(default=None, max_length=255)
    device_type: str = Field(default="LAB_PC", min_length=1, max_length=50)
    serial_no: str | None = Field(default=None, max_length=255)
    current_station_id: int | None = None
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)


class DeviceUpdateCommand(BaseModel):
    """Patch payload for one device."""

    model_config = ConfigDict(extra="forbid")

    device_code: str | None = Field(default=None, min_length=1, max_length=100)
    asset_tag: str | None = Field(default=None, min_length=1, max_length=100)
    device_name: str | None = Field(default=None, max_length=255)
    device_type: str | None = Field(default=None, min_length=1, max_length=50)
    serial_no: str | None = Field(default=None, max_length=255)
    current_station_id: int | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)


class DeviceDeactivateCommand(BaseModel):
    """Deactivate payload for one device."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class StationCreateCommand(BaseModel):
    """Create payload for one station."""

    model_config = ConfigDict(extra="forbid")

    room_id: int
    station_code: str = Field(min_length=1, max_length=100)
    seat_no: str | None = Field(default=None, max_length=50)
    row_no: str | None = Field(default=None, max_length=50)
    column_no: str | None = Field(default=None, max_length=50)
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)
    device_id: int | None = None


class StationUpdateCommand(BaseModel):
    """Patch payload for one station."""

    model_config = ConfigDict(extra="forbid")

    room_id: int | None = None
    station_code: str | None = Field(default=None, min_length=1, max_length=100)
    seat_no: str | None = Field(default=None, max_length=50)
    row_no: str | None = Field(default=None, max_length=50)
    column_no: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=30)
    device_id: int | None = None


class StationDeactivateCommand(BaseModel):
    """Deactivate payload for one station."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class StationBulkGenerateCommand(BaseModel):
    """Bulk generator payload for room stations."""

    model_config = ConfigDict(extra="forbid")

    row_labels: list[str] | None = None
    start_number: int = Field(ge=0)
    end_number: int = Field(ge=0)
    zero_pad: int = Field(default=0, ge=0, le=10)
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_number < self.start_number:
            raise ValueError("end_number must be greater than or equal to start_number")
        return self


class DeviceAssignStationCommand(BaseModel):
    """Assign one device to a station."""

    model_config = ConfigDict(extra="forbid")

    station_id: int


class DeviceRegistrationCreateCommand(BaseModel):
    """Create payload for one device registration."""

    model_config = ConfigDict(extra="forbid")

    registration_type: str = Field(min_length=1, max_length=50)
    registration_value: str = Field(min_length=1, max_length=500)
    valid_from: str | None = None
    valid_to: str | None = None


class DeviceRegistrationRevokeCommand(BaseModel):
    """Revoke payload for one device registration."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
    revoked_at: str | None = None


class DeviceCheckinCreateCommand(BaseModel):
    """Create payload for one device check-in."""

    model_config = ConfigDict(extra="forbid")

    registration_type: str = Field(min_length=1, max_length=50)
    registration_value: str = Field(min_length=1, max_length=500)
    station_id: int | None = None
    ip_address: str | None = Field(default=None, max_length=100)
    hostname: str | None = Field(default=None, max_length=255)
    client_fingerprint: str | None = Field(default=None, max_length=500)
    health_status: str = Field(min_length=1, max_length=30)
    metadata_json: dict | None = None
