from __future__ import annotations

import pytest

from app.modules.master_data.repositories.student_repository import StudentRepository


def test_optional_int_blank_returns_none() -> None:
    assert StudentRepository._optional_int(None) is None
    assert StudentRepository._optional_int("") is None
    assert StudentRepository._optional_int("   ") is None


def test_optional_int_valid_integer_returns_int() -> None:
    assert StudentRepository._optional_int("2025") == 2025
    assert StudentRepository._optional_int(7) == 7


def test_optional_int_invalid_raises_value_error() -> None:
    with pytest.raises(ValueError):
        StudentRepository._optional_int("abc")
