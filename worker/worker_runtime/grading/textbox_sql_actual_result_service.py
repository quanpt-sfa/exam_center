"""Service layer for one-task TEXTBOX_SQL actual_result processing."""

from __future__ import annotations

import os
import re
from typing import Any

from worker_runtime.grading.textbox_sql.sql_executor import TextboxSqlExecutor
from worker_runtime.grading.textbox_sql_actual_result_repository import (
    TextboxSqlActualResultRepository,
)


class TextboxSqlActualResultService:
    """Claims at most one SQL task, executes it, and persists actual_result."""

    def __init__(
        self,
        *,
        repository: TextboxSqlActualResultRepository | None = None,
        executor: TextboxSqlExecutor | None = None,
    ) -> None:
        self._repository = repository or TextboxSqlActualResultRepository()
        self._executor = executor or TextboxSqlExecutor(
            executor_dsn=os.getenv("TEXTBOX_SQL_EXECUTOR_DSN")
        )

    def process_next_task(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        task = self._repository.claim_next_queued_sql_task(
            grading_job_id=int(grading_job_id),
            grading_run_id=int(grading_run_id),
            worker_id=worker_id,
        )
        if task is None:
            return {
                "processed": False,
                "reason": "no_queued_sql_task",
            }

        execution_result = self._executor.execute(str(task.get("sql_text") or ""))
        execution_result = self._sanitize_execution_result(execution_result)

        persisted = self._repository.write_actual_result_and_finish_task(
            task=task,
            execution_result=execution_result,
            worker_id=worker_id,
        )

        return {
            "processed": True,
            "question_grading_task_id": int(persisted["question_grading_task_id"]),
            "actual_result_id": int(persisted["actual_result_id"]),
            "result_type": str(persisted["result_type"]),
            "task_status": str(persisted["task_status"]),
            "runtime_ms": int(execution_result.get("runtime_ms") or 0),
        }

    def _sanitize_execution_result(self, execution_result: dict[str, Any]) -> dict[str, Any]:
        result = dict(execution_result or {})
        error_message = result.get("error_message")
        if error_message is not None:
            safe = str(error_message).strip().splitlines()[0]
            safe = re.sub(r"(?i)password\s*=\s*[^\s;]+", "password=<redacted>", safe)
            safe = re.sub(r"(?i)(postgres(?:ql)?://[^:\s]+:)[^@\s]+@", r"\1<redacted>@", safe)
            if len(safe) > 500:
                safe = safe[:500].rstrip() + "..."
            result["error_message"] = safe or "SQL execution failed."
        return result
