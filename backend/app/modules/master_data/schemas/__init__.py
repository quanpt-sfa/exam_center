"""Common request/response schemas for master data services."""

from app.modules.master_data.schemas.common import (
    ImportPreviewPlaceholderSchema,
    PaginationMetadata,
    PaginationRequest,
    SortRequest,
    StandardListResponse,
    StandardMutationResponse,
    StatusFilter,
    ValidationErrorItem,
)
from app.modules.master_data.schemas.academic import ClassSectionCreateCommand
from app.modules.master_data.schemas.academic import ClassSectionDeactivateCommand
from app.modules.master_data.schemas.academic import ClassSectionUpdateCommand
from app.modules.master_data.schemas.academic import CourseCreateCommand
from app.modules.master_data.schemas.academic import CourseDeactivateCommand
from app.modules.master_data.schemas.academic import CourseUpdateCommand
from app.modules.master_data.schemas.academic import DepartmentCreateCommand
from app.modules.master_data.schemas.academic import DepartmentDeactivateCommand
from app.modules.master_data.schemas.academic import DepartmentUpdateCommand
from app.modules.master_data.schemas.academic import EnrollmentCreateCommand
from app.modules.master_data.schemas.academic import EnrollmentDeactivateCommand
from app.modules.master_data.schemas.identity import AddressInput
from app.modules.master_data.schemas.identity import ContactInput
from app.modules.master_data.schemas.identity import InstructorCreateCommand
from app.modules.master_data.schemas.identity import InstructorDeactivateCommand
from app.modules.master_data.schemas.identity import InstructorUpdateCommand
from app.modules.master_data.schemas.identity import StudentCreateCommand
from app.modules.master_data.schemas.identity import StudentDeactivateCommand
from app.modules.master_data.schemas.identity import StudentUpdateCommand
from app.modules.master_data.schemas.facility import DeviceCreateCommand
from app.modules.master_data.schemas.facility import DeviceDeactivateCommand
from app.modules.master_data.schemas.facility import DeviceUpdateCommand
from app.modules.master_data.schemas.facility import RoomCreateCommand
from app.modules.master_data.schemas.facility import RoomDeactivateCommand
from app.modules.master_data.schemas.facility import RoomUpdateCommand
from app.modules.master_data.schemas.facility import StationCreateCommand
from app.modules.master_data.schemas.facility import StationUpdateCommand
from app.modules.master_data.schemas.assessment import ExamArchiveCommand
from app.modules.master_data.schemas.assessment import ExamCreateCommand
from app.modules.master_data.schemas.assessment import ExamUpdateCommand
from app.modules.master_data.schemas.assessment import ExamVersionCreateCommand
from app.modules.master_data.schemas.assessment import ExamVersionRetireCommand
from app.modules.master_data.schemas.assessment import ExamVersionUpdateCommand
from app.modules.master_data.schemas.capture_grading import CaptureExtractorQueryCreateCommand
from app.modules.master_data.schemas.capture_grading import CaptureProfileCreateCommand
from app.modules.master_data.schemas.capture_grading import CaptureProfileDeactivateCommand
from app.modules.master_data.schemas.capture_grading import CaptureProfileUpdateCommand
from app.modules.master_data.schemas.capture_grading import GradingEngineCreateCommand
from app.modules.master_data.schemas.capture_grading import GradingEngineUpdateCommand
from app.modules.master_data.schemas.capture_grading import QuestionGradingProfileCreateCommand
from app.modules.master_data.schemas.capture_grading import QuestionGradingProfileUpdateCommand
from app.modules.master_data.schemas.import_foundation import ImportCommitRequest
from app.modules.master_data.schemas.import_foundation import ImportCommitResponse
from app.modules.master_data.schemas.import_foundation import ImportJobErrorItem
from app.modules.master_data.schemas.import_foundation import ImportJobCreateRequest
from app.modules.master_data.schemas.import_foundation import ImportJobResponse
from app.modules.master_data.schemas.import_foundation import ImportRowPreview
from app.modules.master_data.schemas.import_foundation import ImportStatusResponse
from app.modules.master_data.schemas.import_foundation import ImportValidationError

__all__ = [
    "PaginationRequest",
    "PaginationMetadata",
    "SortRequest",
    "StatusFilter",
    "StandardListResponse",
    "StandardMutationResponse",
    "ValidationErrorItem",
    "ImportPreviewPlaceholderSchema",
    "ClassSectionCreateCommand",
    "ClassSectionDeactivateCommand",
    "ClassSectionUpdateCommand",
    "CourseCreateCommand",
    "CourseDeactivateCommand",
    "CourseUpdateCommand",
    "DepartmentCreateCommand",
    "DepartmentDeactivateCommand",
    "DepartmentUpdateCommand",
    "EnrollmentCreateCommand",
    "EnrollmentDeactivateCommand",
    "AddressInput",
    "ContactInput",
    "InstructorCreateCommand",
    "InstructorDeactivateCommand",
    "InstructorUpdateCommand",
    "StudentCreateCommand",
    "StudentDeactivateCommand",
    "StudentUpdateCommand",
    "RoomCreateCommand",
    "RoomDeactivateCommand",
    "RoomUpdateCommand",
    "DeviceCreateCommand",
    "DeviceDeactivateCommand",
    "DeviceUpdateCommand",
    "StationCreateCommand",
    "StationUpdateCommand",
    "ExamCreateCommand",
    "ExamUpdateCommand",
    "ExamArchiveCommand",
    "ExamVersionCreateCommand",
    "ExamVersionUpdateCommand",
    "ExamVersionRetireCommand",
    "CaptureProfileCreateCommand",
    "CaptureProfileUpdateCommand",
    "CaptureProfileDeactivateCommand",
    "CaptureExtractorQueryCreateCommand",
    "GradingEngineCreateCommand",
    "GradingEngineUpdateCommand",
    "QuestionGradingProfileCreateCommand",
    "QuestionGradingProfileUpdateCommand",
    "ImportJobCreateRequest",
    "ImportJobErrorItem",
    "ImportJobResponse",
    "ImportRowPreview",
    "ImportStatusResponse",
    "ImportValidationError",
    "ImportCommitRequest",
    "ImportCommitResponse",
]
