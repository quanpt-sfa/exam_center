"""API-first import template contracts for master-data imports."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class ImportTemplateService:
    """Returns UI-safe import file contracts aligned with validation rules."""

    _TEMPLATES: list[dict[str, Any]] = [
        {
            "import_type": "STUDENTS",
            "label": "Sinh viên",
            "columns": [
                {"name": "student_code", "required": True, "default": None, "description": "Mã sinh viên; dùng làm username và mật khẩu mặc định."},
                {"name": "full_name", "required": True, "default": None, "description": "Họ tên sinh viên."},
                {"name": "program_id", "required": False, "default": None, "description": "ID chương trình đào tạo nếu có."},
                {"name": "cohort", "required": False, "default": None, "description": "Khóa học."},
                {"name": "entry_year", "required": False, "default": None, "description": "Năm nhập học."},
                {"name": "student_status", "required": False, "default": "ACTIVE", "description": "Trạng thái sinh viên."},
                {"name": "person_status", "required": False, "default": "ACTIVE", "description": "Trạng thái hồ sơ cá nhân."},
            ],
        },
        {
            "import_type": "INSTRUCTORS",
            "label": "Giảng viên",
            "columns": [
                {"name": "instructor_code", "required": True, "default": None, "description": "Mã giảng viên; dùng làm username và mật khẩu mặc định."},
                {"name": "full_name", "required": True, "default": None, "description": "Họ tên giảng viên."},
                {"name": "department_code", "required": False, "default": None, "description": "Mã đơn vị/khoa (khuyến nghị)."},
                {"name": "department_id", "required": False, "default": None, "description": "ID đơn vị/khoa (tương thích ngược). Nếu có cả department_id và department_code thì ưu tiên department_id."},
                {"name": "instructor_status", "required": False, "default": "ACTIVE", "description": "Trạng thái giảng viên."},
                {"name": "person_status", "required": False, "default": "ACTIVE", "description": "Trạng thái hồ sơ cá nhân."},
            ],
        },
        {
            "import_type": "COURSES",
            "label": "Môn học",
            "columns": [
                {"name": "department_code", "required": False, "default": None, "description": "Mã đơn vị/khoa quản lý môn học (khuyến nghị)."},
                {"name": "department_id", "required": False, "default": None, "description": "ID đơn vị/khoa (tương thích ngược). Nếu có cả department_id và department_code thì ưu tiên department_id."},
                {"name": "course_code", "required": True, "default": None, "description": "Mã môn học."},
                {"name": "course_name", "required": True, "default": None, "description": "Tên môn học."},
                {"name": "credit", "required": False, "default": None, "description": "Số tín chỉ."},
                {"name": "course_type", "required": False, "default": None, "description": "Phân nhóm tùy chọn: SQL_SERVER, MISA, AMIS, ACCOUNTING hoặc GENERAL."},
                {"name": "status", "required": False, "default": "ACTIVE", "description": "Trạng thái môn học."},
            ],
        },
        {
            "import_type": "CLASS_SECTIONS",
            "label": "Lớp học phần",
            "columns": [
                {"name": "course_code", "required": False, "default": None, "description": "Mã môn học (khuyến nghị)."},
                {"name": "course_id", "required": False, "default": None, "description": "ID môn học (tương thích ngược). Nếu có cả course_id và course_code thì ưu tiên course_id."},
                {"name": "term_code", "required": False, "default": None, "description": "Mã học kỳ/đợt mở lớp (khuyến nghị)."},
                {"name": "term_id", "required": False, "default": None, "description": "ID học kỳ/đợt mở lớp (tương thích ngược). Nếu có cả term_id và term_code thì ưu tiên term_id."},
                {"name": "class_code", "required": True, "default": None, "description": "Mã lớp học phần."},
                {"name": "class_name", "required": True, "default": None, "description": "Tên lớp học phần."},
                {"name": "capacity", "required": False, "default": None, "description": "Sức chứa."},
                {"name": "delivery_mode", "required": False, "default": None, "description": "Hình thức tổ chức."},
                {"name": "status", "required": False, "default": "PLANNED", "description": "Trạng thái lớp học phần."},
                {"name": "offering_code", "required": False, "default": None, "description": "Mã mở môn theo học kỳ nếu có."},
            ],
        },
        {
            "import_type": "ENROLLMENTS",
            "label": "Ghi danh lớp học phần",
            "columns": [
                {"name": "class_section_id", "required": True, "default": None, "description": "ID lớp học phần."},
                {"name": "student_id", "required": True, "default": None, "description": "ID sinh viên."},
                {"name": "note", "required": False, "default": None, "description": "Ghi chú."},
            ],
        },
        {
            "import_type": "ROOMS",
            "label": "Phòng thi",
            "columns": [
                {"name": "room_code", "required": True, "default": None, "description": "Mã phòng thi/phòng máy."},
                {"name": "room_name", "required": True, "default": None, "description": "Tên phòng."},
                {"name": "building", "required": False, "default": None, "description": "Tòa nhà."},
                {"name": "floor_no", "required": False, "default": None, "description": "Tầng."},
                {"name": "capacity", "required": False, "default": None, "description": "Sức chứa."},
                {"name": "room_type", "required": False, "default": "LAB", "description": "Loại phòng."},
                {"name": "status", "required": False, "default": "ACTIVE", "description": "Trạng thái phòng."},
            ],
        },
        {
            "import_type": "STATIONS",
            "label": "Chỗ ngồi",
            "columns": [
                {"name": "room_id", "required": True, "default": None, "description": "ID phòng."},
                {"name": "station_code", "required": True, "default": None, "description": "Mã chỗ ngồi/máy."},
                {"name": "seat_no", "required": False, "default": None, "description": "Số ghế."},
                {"name": "row_no", "required": False, "default": None, "description": "Hàng."},
                {"name": "column_no", "required": False, "default": None, "description": "Cột."},
                {"name": "status", "required": False, "default": "ACTIVE", "description": "Trạng thái chỗ ngồi."},
                {"name": "device_id", "required": False, "default": None, "description": "ID thiết bị nếu có."},
            ],
        },
        {
            "import_type": "DEVICES",
            "label": "Thiết bị",
            "columns": [
                {"name": "device_code", "required": True, "default": None, "description": "Mã thiết bị."},
                {"name": "device_name", "required": False, "default": None, "description": "Tên thiết bị."},
                {"name": "device_type", "required": False, "default": "LAB_PC", "description": "Loại thiết bị."},
                {"name": "serial_no", "required": False, "default": None, "description": "Serial."},
                {"name": "current_station_id", "required": False, "default": None, "description": "ID chỗ ngồi đang gắn."},
                {"name": "status", "required": False, "default": "ACTIVE", "description": "Trạng thái thiết bị."},
            ],
        },
    ]

    @staticmethod
    def _sample_value(column: dict[str, Any]) -> str:
        if column.get("name") == "full_name":
            return "Nông Ngọc Duy"
        if column.get("name") == "department_code":
            return "SFA"
        if column.get("name") == "course_code":
            return "ACC101"
        if column.get("name") == "term_code":
            return "2025A"
        if column.get("default") not in (None, ""):
            return str(column["default"])
        if column.get("required"):
            return f"sample_{column['name']}"
        return ""

    def list_import_templates(self, *, actor: dict) -> dict[str, Any]:
        _ = actor
        templates = deepcopy(self._TEMPLATES)
        for template in templates:
            template["sample_row"] = {
                column["name"]: self._sample_value(column)
                for column in template["columns"]
            }
        return {"items": templates}


def build_import_template_service() -> ImportTemplateService:
    """FastAPI dependency factory for import template contracts."""

    return ImportTemplateService()
