"""Master data foundation API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.responses import success_response
from app.modules.master_data.common.error_mapper import raise_as_api_error
from app.modules.master_data.common.errors import MasterDataError
from app.modules.master_data.common.permissions import require_facility_or_master_data_write
from app.modules.master_data.common.permissions import require_capture_config_write
from app.modules.master_data.common.permissions import require_grading_config_write
from app.modules.master_data.common.permissions import require_master_data_publish
from app.modules.master_data.common.permissions import require_master_data_read
from app.modules.master_data.common.permissions import require_master_data_read_or_import
from app.modules.master_data.common.permissions import require_master_data_or_facility_read
from app.modules.master_data.common.permissions import require_master_data_import
from app.modules.master_data.common.permissions import require_master_data_write
from app.modules.master_data.schemas.assessment import ExamArchiveCommand
from app.modules.master_data.schemas.assessment import ExamCreateCommand
from app.modules.master_data.schemas.assessment import ExamUpdateCommand
from app.modules.master_data.schemas.assessment import ExamVersionCreateCommand
from app.modules.master_data.schemas.assessment import ExamVersionQuestionAuthoringUpsertCommand
from app.modules.master_data.schemas.assessment import ExamVersionRetireCommand
from app.modules.master_data.schemas.assessment import ExamVersionUpdateCommand
from app.modules.master_data.schemas.capture_grading import CaptureExtractorQueryCreateCommand
from app.modules.master_data.schemas.capture_grading import CaptureProfileCreateCommand
from app.modules.master_data.schemas.capture_grading import CaptureProfileDeactivateCommand
from app.modules.master_data.schemas.capture_grading import CaptureProfileUpdateCommand
from app.modules.master_data.schemas.capture_grading import ExamVersionDeliveryProfileUpsertCommand
from app.modules.master_data.schemas.capture_grading import GradingEngineCreateCommand
from app.modules.master_data.schemas.capture_grading import GradingEngineUpdateCommand
from app.modules.master_data.schemas.capture_grading import QuestionGradingProfileCreateCommand
from app.modules.master_data.schemas.capture_grading import ConfigureFileUploadManualGradingCommand
from app.modules.master_data.schemas.capture_grading import FileUploadPlaceholderQuestionCommand
from app.modules.master_data.schemas.capture_grading import QuestionGradingProfileRetireCommand
from app.modules.master_data.schemas.capture_grading import QuestionGradingProfileUpdateCommand
from app.modules.master_data.schemas.import_foundation import ImportCommitRequest
from app.modules.master_data.schemas.import_foundation import ImportJobCreateRequest
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
from app.modules.master_data.schemas.facility import DeviceCreateCommand
from app.modules.master_data.schemas.facility import DeviceAssignStationCommand
from app.modules.master_data.schemas.facility import DeviceCheckinCreateCommand
from app.modules.master_data.schemas.facility import DeviceDeactivateCommand
from app.modules.master_data.schemas.facility import DeviceRegistrationCreateCommand
from app.modules.master_data.schemas.facility import DeviceRegistrationRevokeCommand
from app.modules.master_data.schemas.facility import DeviceUpdateCommand
from app.modules.master_data.schemas.facility import RoomCreateCommand
from app.modules.master_data.schemas.facility import RoomDeactivateCommand
from app.modules.master_data.schemas.facility import RoomUpdateCommand
from app.modules.master_data.schemas.facility import StationBulkGenerateCommand
from app.modules.master_data.schemas.facility import StationCreateCommand
from app.modules.master_data.schemas.facility import StationDeactivateCommand
from app.modules.master_data.schemas.facility import StationUpdateCommand
from app.modules.master_data.schemas.identity import InstructorCreateCommand
from app.modules.master_data.schemas.identity import InstructorDeactivateCommand
from app.modules.master_data.schemas.identity import InstructorUpdateCommand
from app.modules.master_data.schemas.identity import StudentCreateCommand
from app.modules.master_data.schemas.identity import StudentDeactivateCommand
from app.modules.master_data.schemas.identity import StudentUpdateCommand
from app.modules.master_data.services.class_section_service import ClassSectionService
from app.modules.master_data.services.class_section_service import build_class_section_service
from app.modules.master_data.services.course_service import CourseService
from app.modules.master_data.services.course_service import build_course_service
from app.modules.master_data.services.department_service import DepartmentService
from app.modules.master_data.services.department_service import build_department_service
from app.modules.master_data.services.assessment_type_service import AssessmentTypeService
from app.modules.master_data.services.assessment_type_service import build_assessment_type_service
from app.modules.master_data.services.device_service import DeviceService
from app.modules.master_data.services.device_service import build_device_service
from app.modules.master_data.services.device_registration_service import DeviceRegistrationService
from app.modules.master_data.services.device_registration_service import build_device_registration_service
from app.modules.master_data.services.device_checkin_service import DeviceCheckinService
from app.modules.master_data.services.device_checkin_service import build_device_checkin_service
from app.modules.master_data.services.enrollment_service import EnrollmentService
from app.modules.master_data.services.enrollment_service import build_enrollment_service
from app.modules.master_data.services.exam_service import ExamService
from app.modules.master_data.services.exam_service import build_exam_service
from app.modules.master_data.services.exam_version_delivery_profile_service import ExamVersionDeliveryProfileService
from app.modules.master_data.services.exam_version_delivery_profile_service import build_exam_version_delivery_profile_service
from app.modules.master_data.services.exam_version_service import ExamVersionService
from app.modules.master_data.services.exam_version_service import build_exam_version_service
from app.modules.master_data.services.exam_version_question_authoring_service import ExamVersionQuestionAuthoringService
from app.modules.master_data.services.exam_version_question_authoring_service import build_exam_version_question_authoring_service
from app.modules.master_data.services.capture_extractor_query_service import CaptureExtractorQueryService
from app.modules.master_data.services.capture_extractor_query_service import build_capture_extractor_query_service
from app.modules.master_data.services.capture_profile_service import CaptureProfileService
from app.modules.master_data.services.capture_profile_service import build_capture_profile_service
from app.modules.master_data.services.expected_answer_metadata_service import ExpectedAnswerMetadataService
from app.modules.master_data.services.expected_answer_metadata_service import build_expected_answer_metadata_service
from app.modules.master_data.services.grading_engine_service import GradingEngineService
from app.modules.master_data.services.grading_engine_service import build_grading_engine_service
from app.modules.master_data.services.import_status_service import ImportStatusService
from app.modules.master_data.services.import_status_service import build_import_status_service
from app.modules.master_data.services.import_template_service import ImportTemplateService
from app.modules.master_data.services.import_template_service import build_import_template_service
from app.modules.master_data.services.instructor_service import InstructorService
from app.modules.master_data.services.instructor_service import build_instructor_service
from app.modules.master_data.services.master_data_import_service import MasterDataImportService
from app.modules.master_data.services.master_data_import_service import build_master_data_import_service
from app.modules.master_data.services.question_grading_profile_service import QuestionGradingProfileService
from app.modules.master_data.services.question_grading_profile_service import build_question_grading_profile_service
from app.modules.master_data.services.program_service import ProgramService
from app.modules.master_data.services.program_service import build_program_service
from app.modules.master_data.services.registry_service import list_available_services
from app.modules.master_data.services.room_service import RoomService
from app.modules.master_data.services.room_service import build_room_service
from app.modules.master_data.services.station_service import StationService
from app.modules.master_data.services.station_service import build_station_service
from app.modules.master_data.services.student_service import StudentService
from app.modules.master_data.services.student_service import build_student_service


router = APIRouter(prefix="/master-data", tags=["master_data"])


@router.get("/health")
def master_data_health(_: dict = Depends(require_master_data_read)) -> dict:
    """Health endpoint for master data foundation readiness."""

    return success_response(
        data={
            "module": "master_data",
            "status": "ok",
            "available_services": list_available_services(),
        }
    )


@router.get("/import-templates")
def list_master_data_import_templates(
    current_user: dict = Depends(require_master_data_read_or_import),
    service: ImportTemplateService = Depends(build_import_template_service),
) -> dict:
    result = service.list_import_templates(actor=current_user)
    return success_response(data=result)


@router.get("/students")
def list_students(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    program_id: int | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: StudentService = Depends(build_student_service),
) -> dict:
    try:
        result = service.list_students(
            filters={"query": query, "status": status, "program_id": program_id},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/students/{student_id}")
def get_student(
    student_id: int,
    include_sensitive: bool = Query(default=False),
    current_user: dict = Depends(require_master_data_read),
    service: StudentService = Depends(build_student_service),
) -> dict:
    try:
        result = service.get_student(
            student_id=student_id,
            actor=current_user,
            include_sensitive=include_sensitive,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/students")
def create_student(
    payload: StudentCreateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: StudentService = Depends(build_student_service),
) -> dict:
    try:
        result = service.create_student(command=payload.model_dump(exclude_none=True), actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/students/{student_id}")
def update_student(
    student_id: int,
    payload: StudentUpdateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: StudentService = Depends(build_student_service),
) -> dict:
    try:
        result = service.update_student(
            student_id=student_id,
            command=payload.model_dump(exclude_none=False),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/students/{student_id}/deactivate")
def deactivate_student(
    student_id: int,
    payload: StudentDeactivateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: StudentService = Depends(build_student_service),
) -> dict:
    try:
        result = service.deactivate_student(student_id=student_id, reason=payload.reason, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/instructors")
def list_instructors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: InstructorService = Depends(build_instructor_service),
) -> dict:
    try:
        result = service.list_instructors(
            filters={"query": query, "status": status, "department_id": department_id},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/instructors/{instructor_id}")
def get_instructor(
    instructor_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: InstructorService = Depends(build_instructor_service),
) -> dict:
    try:
        result = service.get_instructor(instructor_id=instructor_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/instructors")
def create_instructor(
    payload: InstructorCreateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: InstructorService = Depends(build_instructor_service),
) -> dict:
    try:
        result = service.create_instructor(command=payload.model_dump(exclude_none=True), actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/instructors/{instructor_id}")
def update_instructor(
    instructor_id: int,
    payload: InstructorUpdateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: InstructorService = Depends(build_instructor_service),
) -> dict:
    try:
        result = service.update_instructor(
            instructor_id=instructor_id,
            command=payload.model_dump(exclude_none=False),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/instructors/{instructor_id}/deactivate")
def deactivate_instructor(
    instructor_id: int,
    payload: InstructorDeactivateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: InstructorService = Depends(build_instructor_service),
) -> dict:
    try:
        result = service.deactivate_instructor(
            instructor_id=instructor_id,
            reason=payload.reason,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/departments")
def list_departments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: DepartmentService = Depends(build_department_service),
) -> dict:
    try:
        result = service.list_departments(
            filters={"query": query, "status": status},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/departments")
def create_department(
    payload: DepartmentCreateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: DepartmentService = Depends(build_department_service),
) -> dict:
    try:
        result = service.create_department(command=payload.model_dump(exclude_none=True), actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/departments/{department_id}")
def update_department(
    department_id: int,
    payload: DepartmentUpdateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: DepartmentService = Depends(build_department_service),
) -> dict:
    try:
        result = service.update_department(
            department_id=department_id,
            command=payload.model_dump(exclude_none=False),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/departments/{department_id}/deactivate")
def deactivate_department(
    department_id: int,
    payload: DepartmentDeactivateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: DepartmentService = Depends(build_department_service),
) -> dict:
    try:
        result = service.deactivate_department(
            department_id=department_id,
            reason=payload.reason,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/programs")
def list_programs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: ProgramService = Depends(build_program_service),
) -> dict:
    try:
        result = service.list_programs(
            filters={"query": query, "status": status, "department_id": department_id},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/courses")
def list_courses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: CourseService = Depends(build_course_service),
) -> dict:
    try:
        result = service.list_courses(
            filters={"query": query, "status": status, "department_id": department_id},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/courses")
def create_course(
    payload: CourseCreateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: CourseService = Depends(build_course_service),
) -> dict:
    try:
        result = service.create_course(command=payload.model_dump(exclude_none=True), actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/courses/{course_id}")
def get_course(
    course_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: CourseService = Depends(build_course_service),
) -> dict:
    try:
        result = service.get_course(course_id=course_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/courses/{course_id}")
def update_course(
    course_id: int,
    payload: CourseUpdateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: CourseService = Depends(build_course_service),
) -> dict:
    try:
        result = service.update_course(
            course_id=course_id,
            command=payload.model_dump(exclude_none=False),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/courses/{course_id}/deactivate")
def deactivate_course(
    course_id: int,
    payload: CourseDeactivateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: CourseService = Depends(build_course_service),
) -> dict:
    try:
        result = service.deactivate_course(
            course_id=course_id,
            reason=payload.reason,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/assessment-types")
def list_assessment_types(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: AssessmentTypeService = Depends(build_assessment_type_service),
) -> dict:
    try:
        result = service.list_assessment_types(
            filters={"query": query, "is_active": is_active},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/exams")
def list_exams(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    class_section_id: int | None = Query(default=None),
    assessment_type_id: int | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: ExamService = Depends(build_exam_service),
) -> dict:
    try:
        result = service.list_exams(
            filters={
                "query": query,
                "status": status,
                "class_section_id": class_section_id,
                "assessment_type_id": assessment_type_id,
            },
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exams")
def create_exam(
    payload: ExamCreateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: ExamService = Depends(build_exam_service),
) -> dict:
    try:
        result = service.create_exam(command=payload.model_dump(exclude_none=True), actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/exams/{exam_id}")
def get_exam(
    exam_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: ExamService = Depends(build_exam_service),
) -> dict:
    try:
        result = service.get_exam(exam_id=exam_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/exams/{exam_id}")
def update_exam(
    exam_id: int,
    payload: ExamUpdateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: ExamService = Depends(build_exam_service),
) -> dict:
    try:
        result = service.update_exam(
            exam_id=exam_id,
            command=payload.model_dump(exclude_unset=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exams/{exam_id}/archive")
def archive_exam(
    exam_id: int,
    payload: ExamArchiveCommand | None = None,
    current_user: dict = Depends(require_master_data_write),
    service: ExamService = Depends(build_exam_service),
) -> dict:
    try:
        result = service.archive_exam(
            exam_id=exam_id,
            reason=(payload.reason if payload is not None else None),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/exams/{exam_id}/versions")
def list_exam_versions(
    exam_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    status: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: ExamVersionService = Depends(build_exam_version_service),
) -> dict:
    try:
        result = service.list_exam_versions(
            exam_id=exam_id,
            filters={"status": status},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exams/{exam_id}/versions")
def create_exam_version(
    exam_id: int,
    payload: ExamVersionCreateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: ExamVersionService = Depends(build_exam_version_service),
) -> dict:
    try:
        result = service.create_exam_version(
            exam_id=exam_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/exam-versions/{exam_version_id}")
def get_exam_version(
    exam_version_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: ExamVersionService = Depends(build_exam_version_service),
) -> dict:
    try:
        result = service.get_exam_version(exam_version_id=exam_version_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/exam-versions/{exam_version_id}")
def update_exam_version(
    exam_version_id: int,
    payload: ExamVersionUpdateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: ExamVersionService = Depends(build_exam_version_service),
) -> dict:
    try:
        result = service.update_exam_version(
            exam_version_id=exam_version_id,
            command=payload.model_dump(exclude_none=False),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exam-versions/{exam_version_id}/validate")
def validate_exam_version(
    exam_version_id: int,
    current_user: dict = Depends(require_master_data_publish),
    service: ExamVersionService = Depends(build_exam_version_service),
) -> dict:
    try:
        result = service.validate_exam_version_for_publish(
            exam_version_id=exam_version_id,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exam-versions/{exam_version_id}/publish")
def publish_exam_version(
    exam_version_id: int,
    current_user: dict = Depends(require_master_data_publish),
    service: ExamVersionService = Depends(build_exam_version_service),
) -> dict:
    try:
        result = service.publish_exam_version(exam_version_id=exam_version_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exam-versions/{exam_version_id}/retire")
def retire_exam_version(
    exam_version_id: int,
    payload: ExamVersionRetireCommand | None = None,
    current_user: dict = Depends(require_master_data_publish),
    service: ExamVersionService = Depends(build_exam_version_service),
) -> dict:
    try:
        result = service.retire_exam_version(
            exam_version_id=exam_version_id,
            reason=(payload.reason if payload is not None else None),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/facilities/rooms")
def list_facility_rooms(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    room_type: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: RoomService = Depends(build_room_service),
) -> dict:
    try:
        result = service.list_rooms(
            filters={"query": query, "status": status, "room_type": room_type},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/facilities/rooms")
def create_facility_room(
    payload: RoomCreateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: RoomService = Depends(build_room_service),
) -> dict:
    try:
        result = service.create_room(command=payload.model_dump(exclude_none=True), actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/facilities/rooms/{room_id}")
def get_facility_room(
    room_id: int,
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: RoomService = Depends(build_room_service),
) -> dict:
    try:
        result = service.get_room(room_id=room_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/facilities/rooms/{room_id}")
def update_facility_room(
    room_id: int,
    payload: RoomUpdateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: RoomService = Depends(build_room_service),
) -> dict:
    try:
        result = service.update_room(
            room_id=room_id,
            command=payload.model_dump(exclude_none=False),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/facilities/rooms/{room_id}/deactivate")
def deactivate_facility_room(
    room_id: int,
    payload: RoomDeactivateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: RoomService = Depends(build_room_service),
) -> dict:
    try:
        result = service.deactivate_room(
            room_id=room_id,
            reason=payload.reason,
            force=payload.force,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/facilities/devices")
def list_facility_devices(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    room_id: int | None = Query(default=None),
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    try:
        result = service.list_devices(
            filters={"query": query, "status": status, "room_id": room_id},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/facilities/devices")
def create_facility_device(
    payload: DeviceCreateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    try:
        result = service.create_device(command=payload.model_dump(exclude_none=True), actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/facilities/devices/{device_id}")
def get_facility_device(
    device_id: int,
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    try:
        result = service.get_device(device_id=device_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/facilities/devices/{device_id}")
def update_facility_device(
    device_id: int,
    payload: DeviceUpdateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    try:
        result = service.update_device(
            device_id=device_id,
            command=payload.model_dump(exclude_none=False),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/facilities/devices/{device_id}/deactivate")
def deactivate_facility_device(
    device_id: int,
    payload: DeviceDeactivateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    try:
        result = service.deactivate_device(
            device_id=device_id,
            reason=payload.reason,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/facilities/stations")
def list_facility_stations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    room_id: int | None = Query(default=None),
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: StationService = Depends(build_station_service),
) -> dict:
    try:
        result = service.list_stations(
            filters={"query": query, "status": status, "room_id": room_id},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/facilities/stations")
def create_facility_station(
    payload: StationCreateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: StationService = Depends(build_station_service),
) -> dict:
    try:
        result = service.create_station(command=payload.model_dump(exclude_none=True), actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/facilities/stations/{station_id}")
def update_facility_station(
    station_id: int,
    payload: StationUpdateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: StationService = Depends(build_station_service),
) -> dict:
    try:
        result = service.update_station(
            station_id=station_id,
            command=payload.model_dump(exclude_none=False),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/class-sections")
def list_class_sections(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    term_id: int | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: ClassSectionService = Depends(build_class_section_service),
) -> dict:
    try:
        result = service.list_class_sections(
            filters={
                "query": query,
                "status": status,
                "department_id": department_id,
                "course_id": course_id,
                "term_id": term_id,
            },
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/class-sections")
def create_class_section(
    payload: ClassSectionCreateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: ClassSectionService = Depends(build_class_section_service),
) -> dict:
    try:
        result = service.create_class_section(command=payload.model_dump(exclude_none=True), actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/class-sections/{class_section_id}")
def get_class_section(
    class_section_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: ClassSectionService = Depends(build_class_section_service),
) -> dict:
    try:
        result = service.get_class_section(class_section_id=class_section_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/class-sections/{class_section_id}")
def update_class_section(
    class_section_id: int,
    payload: ClassSectionUpdateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: ClassSectionService = Depends(build_class_section_service),
) -> dict:
    try:
        result = service.update_class_section(
            class_section_id=class_section_id,
            command=payload.model_dump(exclude_none=False),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/class-sections/{class_section_id}/deactivate")
def deactivate_class_section(
    class_section_id: int,
    payload: ClassSectionDeactivateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: ClassSectionService = Depends(build_class_section_service),
) -> dict:
    try:
        result = service.deactivate_class_section(
            class_section_id=class_section_id,
            reason=payload.reason,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/enrollments")
def list_enrollments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    class_section_id: int | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: EnrollmentService = Depends(build_enrollment_service),
) -> dict:
    try:
        result = service.list_enrollments(
            filters={"query": query, "status": status, "class_section_id": class_section_id},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/class-sections/{class_section_id}/students")
def list_class_section_students(
    class_section_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: EnrollmentService = Depends(build_enrollment_service),
) -> dict:
    try:
        result = service.list_class_section_students(
            class_section_id=class_section_id,
            filters={"query": query, "status": status},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/class-sections/{class_section_id}/enrollments")
def create_class_section_enrollment(
    class_section_id: int,
    payload: EnrollmentCreateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: EnrollmentService = Depends(build_enrollment_service),
) -> dict:
    try:
        result = service.enroll_student(
            class_section_id=class_section_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/class-sections/{class_section_id}/enrollments/{enrollment_id}/deactivate")
def deactivate_class_section_enrollment(
    class_section_id: int,
    enrollment_id: int,
    payload: EnrollmentDeactivateCommand,
    current_user: dict = Depends(require_master_data_write),
    service: EnrollmentService = Depends(build_enrollment_service),
) -> dict:
    try:
        result = service.deactivate_enrollment(
            class_section_id=class_section_id,
            enrollment_id=enrollment_id,
            reason=payload.reason,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/capture-profiles")
def list_capture_profiles(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: CaptureProfileService = Depends(build_capture_profile_service),
) -> dict:
    try:
        result = service.list_capture_profiles(
            filters={"query": query, "status": status, "source_type": source_type},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/capture-profiles/{capture_profile_id}")
def get_capture_profile(
    capture_profile_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: CaptureProfileService = Depends(build_capture_profile_service),
) -> dict:
    try:
        result = service.get_capture_profile(capture_profile_id=capture_profile_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/capture-profiles")
def create_capture_profile(
    payload: CaptureProfileCreateCommand,
    current_user: dict = Depends(require_capture_config_write),
    service: CaptureProfileService = Depends(build_capture_profile_service),
) -> dict:
    try:
        result = service.create_capture_profile(
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/capture-profiles/{capture_profile_id}")
def update_capture_profile(
    capture_profile_id: int,
    payload: CaptureProfileUpdateCommand,
    current_user: dict = Depends(require_capture_config_write),
    service: CaptureProfileService = Depends(build_capture_profile_service),
) -> dict:
    try:
        result = service.update_capture_profile(
            capture_profile_id=capture_profile_id,
            command=payload.model_dump(exclude_unset=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/capture-profiles/{capture_profile_id}/deactivate")
def deactivate_capture_profile(
    capture_profile_id: int,
    payload: CaptureProfileDeactivateCommand,
    current_user: dict = Depends(require_capture_config_write),
    service: CaptureProfileService = Depends(build_capture_profile_service),
) -> dict:
    try:
        result = service.deactivate_capture_profile(
            capture_profile_id=capture_profile_id,
            reason=payload.reason,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/capture-profiles/{capture_profile_id}/extractor-queries")
def list_capture_extractor_queries(
    capture_profile_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    status: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: CaptureExtractorQueryService = Depends(build_capture_extractor_query_service),
) -> dict:
    try:
        result = service.list_capture_extractor_queries(
            capture_profile_id=capture_profile_id,
            filters={"status": status},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/capture-profiles/{capture_profile_id}/extractor-queries")
def create_capture_extractor_query(
    capture_profile_id: int,
    payload: CaptureExtractorQueryCreateCommand,
    current_user: dict = Depends(require_capture_config_write),
    service: CaptureExtractorQueryService = Depends(build_capture_extractor_query_service),
) -> dict:
    try:
        result = service.create_capture_extractor_query(
            capture_profile_id=capture_profile_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/grading-engines")
def list_grading_engines(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    engine_category: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: GradingEngineService = Depends(build_grading_engine_service),
) -> dict:
    try:
        result = service.list_grading_engines(
            filters={"query": query, "is_active": is_active, "engine_category": engine_category},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/grading-engines/{grading_engine_id}")
def get_grading_engine(
    grading_engine_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: GradingEngineService = Depends(build_grading_engine_service),
) -> dict:
    try:
        result = service.get_grading_engine(grading_engine_id=grading_engine_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/grading-engines")
def create_grading_engine(
    payload: GradingEngineCreateCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: GradingEngineService = Depends(build_grading_engine_service),
) -> dict:
    try:
        result = service.create_grading_engine(command=payload.model_dump(exclude_none=True), actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/grading-engines/{grading_engine_id}")
def update_grading_engine(
    grading_engine_id: int,
    payload: GradingEngineUpdateCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: GradingEngineService = Depends(build_grading_engine_service),
) -> dict:
    try:
        result = service.update_grading_engine(
            grading_engine_id=grading_engine_id,
            command=payload.model_dump(exclude_unset=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/question-grading-profiles")
def list_question_grading_profiles(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    exam_version_id: int | None = Query(default=None),
    question_template_id: int | None = Query(default=None),
    input_source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: QuestionGradingProfileService = Depends(build_question_grading_profile_service),
) -> dict:
    try:
        result = service.list_question_grading_profiles(
            filters={
                "exam_version_id": exam_version_id,
                "question_template_id": question_template_id,
                "input_source": input_source,
                "status": status,
            },
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/question-grading-profiles/{question_grading_profile_id}")
def get_question_grading_profile(
    question_grading_profile_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: QuestionGradingProfileService = Depends(build_question_grading_profile_service),
) -> dict:
    try:
        result = service.get_question_grading_profile(
            question_grading_profile_id=question_grading_profile_id,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/question-grading-profiles")
def create_question_grading_profile(
    payload: QuestionGradingProfileCreateCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: QuestionGradingProfileService = Depends(build_question_grading_profile_service),
) -> dict:
    try:
        result = service.create_question_grading_profile(
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/question-grading-profiles/{question_grading_profile_id}")
def update_question_grading_profile(
    question_grading_profile_id: int,
    payload: QuestionGradingProfileUpdateCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: QuestionGradingProfileService = Depends(build_question_grading_profile_service),
) -> dict:
    try:
        result = service.update_question_grading_profile(
            question_grading_profile_id=question_grading_profile_id,
            command=payload.model_dump(exclude_unset=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/question-grading-profiles/{question_grading_profile_id}/retire")
def retire_question_grading_profile(
    question_grading_profile_id: int,
    payload: QuestionGradingProfileRetireCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: QuestionGradingProfileService = Depends(build_question_grading_profile_service),
) -> dict:
    try:
        result = service.retire_question_grading_profile(
            question_grading_profile_id=question_grading_profile_id,
            reason=payload.reason,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/exam-versions/{exam_version_id}/question-grading-profiles")
def list_exam_version_question_grading_profiles(
    exam_version_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    question_template_id: int | None = Query(default=None),
    input_source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_read),
    service: QuestionGradingProfileService = Depends(build_question_grading_profile_service),
) -> dict:
    try:
        result = service.list_question_grading_profiles(
            filters={
                "exam_version_id": exam_version_id,
                "question_template_id": question_template_id,
                "input_source": input_source,
                "status": status,
            },
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exam-versions/{exam_version_id}/question-grading-profiles")
def create_exam_version_question_grading_profile(
    exam_version_id: int,
    payload: QuestionGradingProfileCreateCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: QuestionGradingProfileService = Depends(build_question_grading_profile_service),
) -> dict:
    try:
        command = payload.model_dump(exclude_none=True)
        command["exam_version_id"] = int(exam_version_id)
        result = service.create_question_grading_profile(
            command=command,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/exam-versions/{exam_version_id}/questions")
def list_exam_version_questions(
    exam_version_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: ExamVersionQuestionAuthoringService = Depends(build_exam_version_question_authoring_service),
) -> dict:
    try:
        result = service.list_exam_version_questions(exam_version_id=exam_version_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exam-versions/{exam_version_id}/questions")
def create_exam_version_question(
    exam_version_id: int,
    payload: ExamVersionQuestionAuthoringUpsertCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: ExamVersionQuestionAuthoringService = Depends(build_exam_version_question_authoring_service),
) -> dict:
    try:
        result = service.create_exam_version_question(
            exam_version_id=exam_version_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/exam-versions/{exam_version_id}/questions/{question_template_id}")
def update_exam_version_question(
    exam_version_id: int,
    question_template_id: int,
    payload: ExamVersionQuestionAuthoringUpsertCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: ExamVersionQuestionAuthoringService = Depends(build_exam_version_question_authoring_service),
) -> dict:
    try:
        result = service.update_exam_version_question(
            exam_version_id=exam_version_id,
            question_template_id=question_template_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/rooms")
def list_rooms_master_data(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    room_type: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: RoomService = Depends(build_room_service),
) -> dict:
    return list_facility_rooms(page, page_size, query, status, room_type, current_user, service)


@router.post("/rooms")
def create_rooms_master_data(
    payload: RoomCreateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: RoomService = Depends(build_room_service),
) -> dict:
    return create_facility_room(payload, current_user, service)


@router.get("/rooms/{room_id}")
def get_room_master_data(
    room_id: int,
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: RoomService = Depends(build_room_service),
) -> dict:
    return get_facility_room(room_id, current_user, service)


@router.patch("/rooms/{room_id}")
def update_room_master_data(
    room_id: int,
    payload: RoomUpdateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: RoomService = Depends(build_room_service),
) -> dict:
    return update_facility_room(room_id, payload, current_user, service)


@router.post("/rooms/{room_id}/deactivate")
def deactivate_room_master_data(
    room_id: int,
    payload: RoomDeactivateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: RoomService = Depends(build_room_service),
) -> dict:
    return deactivate_facility_room(room_id, payload, current_user, service)


@router.get("/rooms/{room_id}/stations")
def list_room_stations_master_data(
    room_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: StationService = Depends(build_station_service),
) -> dict:
    try:
        result = service.list_stations(
            filters={"query": query, "status": status, "room_id": room_id},
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/rooms/{room_id}/stations")
def create_room_station_master_data(
    room_id: int,
    payload: StationCreateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: StationService = Depends(build_station_service),
) -> dict:
    try:
        command = payload.model_dump(exclude_none=True)
        command["room_id"] = int(room_id)
        result = service.create_station(command=command, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/rooms/{room_id}/stations/bulk-generate")
def bulk_generate_room_stations_master_data(
    room_id: int,
    payload: StationBulkGenerateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: StationService = Depends(build_station_service),
) -> dict:
    try:
        result = service.bulk_generate_stations(
            room_id=room_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.patch("/stations/{station_id}")
def update_station_master_data(
    station_id: int,
    payload: StationUpdateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: StationService = Depends(build_station_service),
) -> dict:
    return update_facility_station(station_id, payload, current_user, service)


@router.post("/stations/{station_id}/deactivate")
def deactivate_station_master_data(
    station_id: int,
    payload: StationDeactivateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: StationService = Depends(build_station_service),
) -> dict:
    try:
        result = service.deactivate_station(
            station_id=station_id,
            reason=payload.reason,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/devices")
def list_devices_master_data(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    room_id: int | None = Query(default=None),
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    return list_facility_devices(page, page_size, query, status, room_id, current_user, service)


@router.post("/devices")
def create_device_master_data(
    payload: DeviceCreateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    return create_facility_device(payload, current_user, service)


@router.get("/devices/{device_id}")
def get_device_master_data(
    device_id: int,
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    return get_facility_device(device_id, current_user, service)


@router.patch("/devices/{device_id}")
def update_device_master_data(
    device_id: int,
    payload: DeviceUpdateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    return update_facility_device(device_id, payload, current_user, service)


@router.post("/devices/{device_id}/assign-station")
def assign_device_station_master_data(
    device_id: int,
    payload: DeviceAssignStationCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    try:
        result = service.assign_device_to_station(
            device_id=device_id,
            station_id=payload.station_id,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/devices/{device_id}/retire")
def retire_device_master_data(
    device_id: int,
    payload: DeviceDeactivateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    try:
        result = service.retire_device(
            device_id=device_id,
            reason=payload.reason,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/devices/{device_id}/deactivate")
def deactivate_device_master_data(
    device_id: int,
    payload: DeviceDeactivateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: DeviceService = Depends(build_device_service),
) -> dict:
    return deactivate_facility_device(device_id, payload, current_user, service)


@router.get("/devices/{device_id}/registrations")
def list_device_registrations_master_data(
    device_id: int,
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: DeviceRegistrationService = Depends(build_device_registration_service),
) -> dict:
    try:
        result = service.list_device_registrations(device_id=device_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/devices/{device_id}/registrations")
def create_device_registration_master_data(
    device_id: int,
    payload: DeviceRegistrationCreateCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: DeviceRegistrationService = Depends(build_device_registration_service),
) -> dict:
    try:
        result = service.create_device_registration(
            device_id=device_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/device-registrations/{device_registration_id}/revoke")
def revoke_device_registration_master_data(
    device_registration_id: int,
    payload: DeviceRegistrationRevokeCommand,
    current_user: dict = Depends(require_facility_or_master_data_write),
    service: DeviceRegistrationService = Depends(build_device_registration_service),
) -> dict:
    try:
        result = service.revoke_device_registration(
            device_registration_id=device_registration_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/device-checkins")
def create_device_checkin_master_data(
    payload: DeviceCheckinCreateCommand,
    current_user: dict = Depends(require_master_data_read),
    service: DeviceCheckinService = Depends(build_device_checkin_service),
) -> dict:
    try:
        result = service.create_checkin(
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/rooms/{room_id}/station-readiness")
def list_room_station_readiness_master_data(
    room_id: int,
    current_user: dict = Depends(require_master_data_or_facility_read),
    service: DeviceCheckinService = Depends(build_device_checkin_service),
) -> dict:
    try:
        result = service.list_room_station_readiness(room_id=room_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exam-versions/{exam_version_id}/file-upload-placeholder-question")
def create_file_upload_placeholder_question(
    exam_version_id: int,
    payload: FileUploadPlaceholderQuestionCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: QuestionGradingProfileService = Depends(build_question_grading_profile_service),
) -> dict:
    try:
        result = service.create_file_upload_placeholder_question(
            exam_version_id=exam_version_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exam-versions/{exam_version_id}/configure-file-upload-manual-grading")
def configure_file_upload_manual_grading_exam_version(
    exam_version_id: int,
    payload: ConfigureFileUploadManualGradingCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: QuestionGradingProfileService = Depends(build_question_grading_profile_service),
) -> dict:
    try:
        result = service.configure_file_upload_manual_grading_exam_version(
            exam_version_id=exam_version_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/exam-versions/{exam_version_id}/delivery-profile")
def get_exam_version_delivery_profile(
    exam_version_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: ExamVersionDeliveryProfileService = Depends(build_exam_version_delivery_profile_service),
) -> dict:
    try:
        result = service.get_delivery_profile_for_exam_version(
            exam_version_id=exam_version_id,
            conn=None,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.put("/exam-versions/{exam_version_id}/delivery-profile")
def upsert_exam_version_delivery_profile(
    exam_version_id: int,
    payload: ExamVersionDeliveryProfileUpsertCommand,
    current_user: dict = Depends(require_grading_config_write),
    service: ExamVersionDeliveryProfileService = Depends(build_exam_version_delivery_profile_service),
) -> dict:
    try:
        result = service.upsert_delivery_profile_for_exam_version(
            exam_version_id=exam_version_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/exam-versions/{exam_version_id}/expected-answer-metadata")
def get_exam_version_expected_answer_metadata(
    exam_version_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: ExpectedAnswerMetadataService = Depends(build_expected_answer_metadata_service),
) -> dict:
    try:
        _ = current_user
        result = service.get_exam_version_metadata_summary(exam_version_id=exam_version_id)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/imports")
def create_master_data_import_job(
    payload: ImportJobCreateRequest,
    current_user: dict = Depends(require_master_data_import),
    service: MasterDataImportService = Depends(build_master_data_import_service),
) -> dict:
    try:
        result = service.create_import_job(
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/imports/{import_job_id}")
def get_master_data_import_job(
    import_job_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: MasterDataImportService = Depends(build_master_data_import_service),
) -> dict:
    try:
        result = service.get_import_job(import_job_id=import_job_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/imports/{import_job_id}/rows")
def list_master_data_import_rows(
    import_job_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: dict = Depends(require_master_data_read),
    service: ImportStatusService = Depends(build_import_status_service),
) -> dict:
    try:
        result = service.list_import_rows(
            import_job_id=import_job_id,
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/imports/{import_job_id}/status")
def get_master_data_import_status(
    import_job_id: int,
    current_user: dict = Depends(require_master_data_read_or_import),
    service: ImportStatusService = Depends(build_import_status_service),
) -> dict:
    try:
        result = service.get_import_status(import_job_id=import_job_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/imports/{import_job_id}/errors")
def list_master_data_import_errors(
    import_job_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: dict = Depends(require_master_data_import),
    service: ImportStatusService = Depends(build_import_status_service),
) -> dict:
    try:
        result = service.list_import_errors(
            import_job_id=import_job_id,
            pagination={"page": page, "page_size": page_size},
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/imports/{import_job_id}/validate")
def validate_master_data_import_job(
    import_job_id: int,
    current_user: dict = Depends(require_master_data_import),
    service: MasterDataImportService = Depends(build_master_data_import_service),
) -> dict:
    try:
        result = service.validate_import_job(import_job_id=import_job_id, actor=current_user)
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/imports/{import_job_id}/commit")
def commit_master_data_import_job(
    import_job_id: int,
    payload: ImportCommitRequest,
    current_user: dict = Depends(require_master_data_import),
    service: MasterDataImportService = Depends(build_master_data_import_service),
) -> dict:
    try:
        result = service.commit_import_job(
            import_job_id=import_job_id,
            command=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)
