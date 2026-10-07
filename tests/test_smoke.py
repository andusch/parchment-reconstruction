"""Smoke tests for the package scaffold."""

import pytest

import prw


def test_package_imports() -> None:
    assert prw.__version__ == "0.0.0"


@pytest.mark.slow
def test_slow_marker_is_excluded() -> None:
    """Registered so `pytest -m "not slow"` has a marker to exclude."""
