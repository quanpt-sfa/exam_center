"""Reusable runtime loop engine for worker process orchestration."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
import signal
import time
from typing import Any
from typing import Callable

from worker_runtime.runtime_logging import log_runtime_cycle
from worker_runtime.runtime_logging import sanitize_log_value


logger = logging.getLogger("worker_runtime.runtime_loop")


@dataclass(frozen=True)
class RuntimeLoopOutcome:
    role: str
    processed_count: int
    claimed_count: int
    completed_count: int
    failed_count: int
    idle: bool
    retryable_error: bool = False
    fatal_error: bool = False
    sanitized_message: str = ""
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": str(self.role),
            "processed_count": int(self.processed_count),
            "claimed_count": int(self.claimed_count),
            "completed_count": int(self.completed_count),
            "failed_count": int(self.failed_count),
            "idle": bool(self.idle),
            "retryable_error": bool(self.retryable_error),
            "fatal_error": bool(self.fatal_error),
            "sanitized_message": str(self.sanitized_message),
            "error": self.error,
        }


@dataclass
class RuntimeLoopSummary:
    cycles: int = 0
    processed_count: int = 0
    claimed_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    idle_cycles: int = 0
    stop_reason: str = "completed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycles": int(self.cycles),
            "processed_count": int(self.processed_count),
            "claimed_count": int(self.claimed_count),
            "completed_count": int(self.completed_count),
            "failed_count": int(self.failed_count),
            "idle_cycles": int(self.idle_cycles),
            "stop_reason": str(self.stop_reason),
        }


class RuntimeStopController:
    def __init__(self) -> None:
        self._stop_requested = False
        self._reason = "running"

    @property
    def stop_requested(self) -> bool:
        return bool(self._stop_requested)

    @property
    def reason(self) -> str:
        return str(self._reason)

    def request_stop(self, reason: str) -> None:
        self._stop_requested = True
        self._reason = str(reason or "requested")


@contextmanager
def runtime_signal_handlers(stop_controller: RuntimeStopController):
    previous_handlers: dict[int, Any] = {}

    def _handle_signal(signum, _frame) -> None:  # noqa: ANN001
        _ = _frame
        stop_controller.request_stop(f"signal:{int(signum)}")

    supported = [signal.SIGTERM]
    for sig in supported:
        try:
            previous_handlers[int(sig)] = signal.getsignal(sig)
            signal.signal(sig, _handle_signal)
        except (ValueError, OSError, RuntimeError, AttributeError):
            continue

    try:
        yield
    finally:
        for signum, handler in previous_handlers.items():
            try:
                signal.signal(signal.Signals(signum), handler)
            except (ValueError, OSError, RuntimeError, AttributeError):
                continue


class RuntimeLoopEngine:
    def __init__(
        self,
        *,
        role: str,
        worker_id: str,
        run_cycle: Callable[[], RuntimeLoopOutcome],
        idle_sleep_seconds: float,
        retry_backoff_seconds: float,
        max_retry_backoff_seconds: float,
        sleep_fn: Callable[[float], None] | None = None,
        stop_controller: RuntimeStopController | None = None,
        stop_condition: Callable[[int, RuntimeLoopOutcome | None], bool] | None = None,
        log: logging.Logger | None = None,
    ) -> None:
        self._role = str(role)
        self._worker_id = str(worker_id)
        self._run_cycle = run_cycle
        self._idle_sleep_seconds = max(0.01, float(idle_sleep_seconds))
        self._retry_backoff_seconds = max(0.01, float(retry_backoff_seconds))
        self._max_retry_backoff_seconds = max(
            self._retry_backoff_seconds,
            float(max_retry_backoff_seconds),
        )
        self._sleep_fn = sleep_fn or time.sleep
        self._stop_controller = stop_controller or RuntimeStopController()
        self._stop_condition = stop_condition
        self._logger = log or logger

    def run(
        self,
        *,
        mode: str,
        stop_after_idle_cycles: int | None = None,
    ) -> RuntimeLoopSummary:
        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in {"one-shot", "bounded-idle", "continuous"}:
            raise ValueError("Unsupported runtime loop mode")

        if normalized_mode == "bounded-idle":
            if stop_after_idle_cycles is None:
                raise ValueError("bounded-idle mode requires stop_after_idle_cycles")
            idle_limit = max(1, int(stop_after_idle_cycles))
        else:
            idle_limit = None

        summary = RuntimeLoopSummary()
        last_outcome: RuntimeLoopOutcome | None = None
        backoff_seconds = float(self._retry_backoff_seconds)

        with runtime_signal_handlers(self._stop_controller):
            try:
                while not self._stop_controller.stop_requested:
                    if self._stop_condition and bool(self._stop_condition(summary.cycles, last_outcome)):
                        self._stop_controller.request_stop("stop_condition")
                        break

                    summary.cycles += 1
                    try:
                        outcome = self._run_cycle()
                    except Exception as exc:  # noqa: BLE001
                        error_text = str(sanitize_log_value(str(exc)))
                        outcome = RuntimeLoopOutcome(
                            role=self._role,
                            processed_count=0,
                            claimed_count=0,
                            completed_count=0,
                            failed_count=1,
                            idle=False,
                            retryable_error=True,
                            fatal_error=False,
                            sanitized_message=error_text,
                            error=error_text,
                        )

                    last_outcome = outcome
                    summary.processed_count += int(outcome.processed_count)
                    summary.claimed_count += int(outcome.claimed_count)
                    summary.completed_count += int(outcome.completed_count)
                    summary.failed_count += int(outcome.failed_count)
                    if bool(outcome.idle):
                        summary.idle_cycles += 1
                    else:
                        summary.idle_cycles = 0

                    log_runtime_cycle(
                        self._logger,
                        role=self._role,
                        worker_id=self._worker_id,
                        cycle_number=summary.cycles,
                        outcome=outcome.as_dict(),
                    )

                    if normalized_mode == "one-shot":
                        summary.stop_reason = "one_shot_completed"
                        break

                    if idle_limit is not None and summary.idle_cycles >= idle_limit:
                        summary.stop_reason = "idle_limit_reached"
                        break

                    if bool(outcome.fatal_error):
                        summary.stop_reason = "fatal_error"
                        break

                    if outcome.error or bool(outcome.retryable_error):
                        self._sleep_fn(backoff_seconds)
                        backoff_seconds = min(
                            self._max_retry_backoff_seconds,
                            max(self._retry_backoff_seconds, backoff_seconds * 2),
                        )
                        continue

                    if bool(outcome.idle):
                        self._sleep_fn(self._idle_sleep_seconds)
                    else:
                        backoff_seconds = float(self._retry_backoff_seconds)
            except KeyboardInterrupt:
                self._stop_controller.request_stop("keyboard_interrupt")

        if self._stop_controller.stop_requested and summary.stop_reason == "completed":
            summary.stop_reason = self._stop_controller.reason

        return summary


def outcome_from_processed(processed: bool) -> RuntimeLoopOutcome:
    if bool(processed):
        return RuntimeLoopOutcome(
            role="worker",
            processed_count=1,
            claimed_count=1,
            completed_count=1,
            failed_count=0,
            idle=False,
            retryable_error=False,
            fatal_error=False,
            sanitized_message="processed",
            error=None,
        )

    return RuntimeLoopOutcome(
        role="worker",
        processed_count=0,
        claimed_count=0,
        completed_count=0,
        failed_count=0,
        idle=True,
        retryable_error=False,
        fatal_error=False,
        sanitized_message="idle",
        error=None,
    )
