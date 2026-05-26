"""Bridge worker commit execution to the API master-data import service path."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from pathlib import Path
import sys
from typing import Any

from worker_runtime.master_data.import_handlers import TransientImportError


def _ensure_api_package_importable() -> None:
    """Ensure apps/api is first on sys.path so `app.*` resolves to FastAPI package."""

    api_root = Path(__file__).resolve().parents[3] / "api"
    api_root_text = str(api_root)

    if api_root_text not in sys.path:
        sys.path.insert(0, api_root_text)

    app_module = sys.modules.get("app")
    if app_module is not None and not hasattr(app_module, "__path__"):
        # The root entrypoint can shadow the FastAPI package in worker entrypoints.
        del sys.modules["app"]


def _load_master_data_import_service_factory() -> Callable[[], Any]:
    try:
        _ensure_api_package_importable()
        module = import_module("app.modules.master_data.services.master_data_import_service")
        factory = getattr(module, "build_master_data_import_service", None)
    except Exception as exc:  # noqa: BLE001
        raise TransientImportError("Unable to import API master-data import service") from exc

    if factory is None or not callable(factory):
        raise TransientImportError("API master-data import service factory is unavailable")

    return factory


def _build_worker_actor(*, job: dict[str, Any], worker_id: str) -> dict[str, Any]:
    actor_user_id = job.get("actor_user_id")
    username = str(job.get("actor_agent") or "").strip() or worker_id

    actor: dict[str, Any] = {"username": username}
    if actor_user_id is not None:
        actor["user_id"] = int(actor_user_id)

    return actor


def _build_commit_command(*, job: dict[str, Any], worker_id: str) -> dict[str, Any]:
    job_id = int(job["import_job_id"])
    attempt_count = int(job.get("attempt_count") or 0)
    idempotency_key = f"md-worker:{worker_id}:job:{job_id}:attempt:{attempt_count}"
    return {"idempotency_key": idempotency_key}


def execute_commit_via_api_service(
    *,
    job: dict[str, Any],
    worker_id: str,
    service_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Execute commit by calling MasterDataImportService.commit_import_job directly."""

    factory = service_factory or _load_master_data_import_service_factory()
    service = factory()
    result = service.commit_import_job(
        import_job_id=int(job["import_job_id"]),
        command=_build_commit_command(job=job, worker_id=worker_id),
        actor=_build_worker_actor(job=job, worker_id=worker_id),
    )

    if not isinstance(result, dict):
        raise TransientImportError("Commit service returned invalid response shape")

    return result
