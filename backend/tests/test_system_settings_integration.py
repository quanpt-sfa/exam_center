import os
import pytest
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection
from app.infrastructure.database.pool import close_pool, initialize_pool
from app.modules.ops.repositories.settings_repository import SettingsRepository
from app.modules.ops.services.settings_service import SettingsService


pytestmark = pytest.mark.skipif(
    os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1",
    reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests",
)


@pytest.fixture(scope="module", autouse=True)
def db_pool():
    initialize_pool()
    yield
    close_pool()


def test_postgres_settings_crud_and_trigger_history() -> None:
    repo = SettingsRepository()
    service = SettingsService(repository=repo)

    # 1. Fetch initial settings (seeded by migrations)
    settings = repo.get_settings()
    assert settings is not None
    assert settings["academy_name"] == "Học viện Công nghệ Bưu chính Viễn thông"
    initial_version = settings["version"]
    settings_id = settings["settings_id"]

    # Find a valid user in identity.app_user if one exists, otherwise None
    user_id = None
    with open_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT user_id FROM identity.app_user ORDER BY user_id ASC LIMIT 1")
            row = cur.fetchone()
            if row:
                user_id = int(row["user_id"])

    # 2. Perform concurrent update verification (Optimistic locking)
    # Perform a valid update
    payload = {
        "academy_name": "PTIT Hà Nội",
        "portal_logo_url": "https://ptit.edu.vn/logo.png",
        "exam_regulations": "Quy định mới.",
        "support_email": "support@ptit.edu.vn",
        "support_hotline": "0243354113",
        "session_heartbeat_seconds": 60,
        "concurrent_login_check": True,
        "autosave_interval_seconds": 15,
        "exam_start_window_minutes": 20,
        "late_entry_window_minutes": 15,
        "min_proctors_per_room": 1,
        "max_sessions_per_proctor_per_day": 3,
        "version": initial_version,
    }

    updated = service.update_settings(payload, actor_user_id=user_id)
    assert updated is not None
    assert updated["academy_name"] == "PTIT Hà Nội"
    assert updated["version"] == initial_version + 1
    assert updated["session_heartbeat_seconds"] == 60

    # 3. Test version conflict (Optimistic lock failure)
    # The version in database is now initial_version + 1. If we send initial_version, it must fail.
    payload["version"] = initial_version
    with pytest.raises(Exception) as exc_info:
        service.update_settings(payload, actor_user_id=user_id)
    # It should raise ApiError with 409
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "version_conflict"

    # 4. Verify trigger wrote to system_settings_history
    history_query = """
    SELECT academy_name, version, changed_by
    FROM ops.system_settings_history
    WHERE settings_id = %s
    ORDER BY history_id DESC
    LIMIT 1
    """
    with open_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(history_query, (settings_id,))
            history_row = cur.fetchone()

    assert history_row is not None
    assert history_row["academy_name"] == "PTIT Hà Nội"
    assert history_row["version"] == initial_version + 1
    assert history_row["changed_by"] == user_id

    # 5. Clean up / restore baseline settings for other runs
    restore_payload = {
        "academy_name": "Học viện Công nghệ Bưu chính Viễn thông",
        "portal_logo_url": None,
        "exam_regulations": "1. Thí sinh phải mặt đúng giờ quy định.\n2. Không mang thiết bị ghi âm, ghi hình hoặc tài liệu không được cho phép vào phòng thi.\n3. Tuyệt đối không được gian lận hoặc trao đổi bài thi.",
        "support_email": "support@ptit.edu.vn",
        "support_hotline": "0243354113",
        "session_heartbeat_seconds": 30,
        "concurrent_login_check": True,
        "autosave_interval_seconds": 10,
        "exam_start_window_minutes": 15,
        "late_entry_window_minutes": 10,
        "min_proctors_per_room": 1,
        "max_sessions_per_proctor_per_day": 3,
        "version": initial_version + 1,
    }
    restored = service.update_settings(restore_payload, actor_user_id=None)
    assert restored["academy_name"] == "Học viện Công nghệ Bưu chính Viễn thông"
    assert restored["version"] == initial_version + 2

