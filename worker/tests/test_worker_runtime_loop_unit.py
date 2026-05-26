"""Unit tests for reusable worker runtime loop engine."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.runtime_loop import RuntimeLoopEngine
from worker_runtime.runtime_loop import RuntimeLoopOutcome
from worker_runtime.runtime_loop import outcome_from_processed


def test_one_shot_exits_after_one_cycle() -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def _cycle() -> RuntimeLoopOutcome:
        calls["count"] += 1
        return outcome_from_processed(True)

    engine = RuntimeLoopEngine(
        role="grading",
        worker_id="grading-unit",
        run_cycle=_cycle,
        idle_sleep_seconds=0.2,
        retry_backoff_seconds=1.0,
        max_retry_backoff_seconds=5.0,
        sleep_fn=lambda seconds: sleeps.append(float(seconds)),
    )

    summary = engine.run(mode="one-shot")

    assert summary.cycles == 1
    assert calls["count"] == 1
    assert summary.stop_reason == "one_shot_completed"
    assert sleeps == []


def test_bounded_idle_exits_after_configured_idle_cycles() -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def _cycle() -> RuntimeLoopOutcome:
        calls["count"] += 1
        return RuntimeLoopOutcome(
            role="capture",
            processed_count=0,
            claimed_count=0,
            completed_count=0,
            failed_count=0,
            idle=True,
            error=None,
        )

    engine = RuntimeLoopEngine(
        role="capture",
        worker_id="capture-unit",
        run_cycle=_cycle,
        idle_sleep_seconds=0.5,
        retry_backoff_seconds=1.0,
        max_retry_backoff_seconds=5.0,
        sleep_fn=lambda seconds: sleeps.append(float(seconds)),
    )

    summary = engine.run(mode="bounded-idle", stop_after_idle_cycles=3)

    assert summary.cycles == 3
    assert calls["count"] == 3
    assert summary.stop_reason == "idle_limit_reached"
    assert len(sleeps) == 2
    assert all(value == 0.5 for value in sleeps)


def test_continuous_loop_can_be_stopped_by_injected_condition() -> None:
    calls = {"count": 0}

    def _cycle() -> RuntimeLoopOutcome:
        calls["count"] += 1
        return outcome_from_processed(True)

    engine = RuntimeLoopEngine(
        role="grading",
        worker_id="grading-stop",
        run_cycle=_cycle,
        idle_sleep_seconds=0.1,
        retry_backoff_seconds=1.0,
        max_retry_backoff_seconds=10.0,
        stop_condition=lambda cycles, _last: cycles >= 3,
    )

    summary = engine.run(mode="continuous")

    assert calls["count"] == 3
    assert summary.cycles == 3
    assert summary.stop_reason == "stop_condition"


def test_idle_cycle_sleeps() -> None:
    sleeps: list[float] = []
    calls = {"count": 0}

    def _cycle() -> RuntimeLoopOutcome:
        calls["count"] += 1
        return RuntimeLoopOutcome(
            role="capture",
            processed_count=0,
            claimed_count=0,
            completed_count=0,
            failed_count=0,
            idle=True,
            error=None,
        )

    engine = RuntimeLoopEngine(
        role="capture",
        worker_id="capture-idle",
        run_cycle=_cycle,
        idle_sleep_seconds=0.25,
        retry_backoff_seconds=1.0,
        max_retry_backoff_seconds=3.0,
        sleep_fn=lambda seconds: sleeps.append(float(seconds)),
    )
    summary = engine.run(mode="bounded-idle", stop_after_idle_cycles=2)

    assert summary.cycles == 2
    assert sleeps == [0.25]


def test_transient_error_backs_off() -> None:
    sleeps: list[float] = []
    calls = {"count": 0}

    def _cycle() -> RuntimeLoopOutcome:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary worker failure")
        return outcome_from_processed(False)

    engine = RuntimeLoopEngine(
        role="grading",
        worker_id="grading-backoff",
        run_cycle=_cycle,
        idle_sleep_seconds=0.2,
        retry_backoff_seconds=1.0,
        max_retry_backoff_seconds=4.0,
        sleep_fn=lambda seconds: sleeps.append(float(seconds)),
        stop_condition=lambda cycles, _last: cycles >= 2,
    )
    summary = engine.run(mode="continuous")

    assert summary.cycles == 2
    assert sleeps[0] == 1.0
    assert summary.failed_count == 1


def test_successful_cycle_resets_backoff() -> None:
    sleeps: list[float] = []
    calls = {"count": 0}

    def _cycle() -> RuntimeLoopOutcome:
        calls["count"] += 1
        if calls["count"] in {1, 3}:
            raise RuntimeError("dsn=postgresql://user:pw-secret@localhost:5432/db password=top-secret")
        return outcome_from_processed(True)

    engine = RuntimeLoopEngine(
        role="grading",
        worker_id="grading-reset",
        run_cycle=_cycle,
        idle_sleep_seconds=0.2,
        retry_backoff_seconds=1.0,
        max_retry_backoff_seconds=8.0,
        sleep_fn=lambda seconds: sleeps.append(float(seconds)),
        stop_condition=lambda cycles, _last: cycles >= 3,
    )
    summary = engine.run(mode="continuous")

    assert summary.cycles == 3
    assert sleeps[0] == 1.0
    assert sleeps[1] == 1.0
    assert summary.failed_count == 2


def test_logs_do_not_include_password_dsn_or_answer_fields(caplog: pytest.LogCaptureFixture) -> None:
    def _cycle() -> RuntimeLoopOutcome:
        return RuntimeLoopOutcome(
            role="grading",
            processed_count=0,
            claimed_count=0,
            completed_count=0,
            failed_count=1,
            idle=False,
            error=(
                "postgresql://exam_sys_app:pw-secret@localhost:5432/exam_sys_dev "
                "password=top-secret answer_state=sealed raw_answer=SELECT 1"
            ),
        )

    caplog.set_level("INFO")
    engine = RuntimeLoopEngine(
        role="grading",
        worker_id="grading-redact",
        run_cycle=_cycle,
        idle_sleep_seconds=0.1,
        retry_backoff_seconds=1.0,
        max_retry_backoff_seconds=2.0,
    )

    _ = engine.run(mode="one-shot")
    text = caplog.text.lower()

    assert "pw-secret" not in text
    assert "top-secret" not in text
    assert "postgresql://" not in text
    assert "answer_state" not in text
    assert "raw_answer" not in text
