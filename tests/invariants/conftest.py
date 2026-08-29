"""Runtime fail-closed guard for the dedicated A12 invariant lane."""

from __future__ import annotations

from typing import Any

import pytest

_deselected_count = 0
_forbidden_outcome_seen = False


def pytest_deselected(items: list[pytest.Item]) -> None:
    """Record any test removed from the canonical proof set."""

    global _deselected_count
    _deselected_count += len(items)


def pytest_collectreport(report: Any) -> None:
    """Treat collection-time skips as a forbidden green path."""

    global _forbidden_outcome_seen
    if report.skipped:
        _forbidden_outcome_seen = True


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Treat runtime skip, xfail, and xpass outcomes as lane failures."""

    global _forbidden_outcome_seen
    if report.skipped or hasattr(report, "wasxfail"):
        _forbidden_outcome_seen = True


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Force nonzero exit when the proof set was hidden or did not run."""

    del exitstatus
    if session.testscollected == 0 or _deselected_count != 0 or _forbidden_outcome_seen:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
