"""Live 116, 19 Nov 2026 ~09:48Z: the grade loop failed 190 times with no traceback (the grader reaches its ledger
through its intake) and no cause in the journal. The grader's failure is kept, and the line carries a closed code.
"""

from __future__ import annotations

from types import SimpleNamespace

from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.interface import Unavailable


def _raised(error):
    try:
        raise error
    except Exception as caught:  # noqa: BLE001
        return caught


def test_a_graders_failure_is_kept_through_its_intake(tmp_path):
    ledger = SimpleNamespace(path=tmp_path / "attempts.sqlite3")
    adapter = SimpleNamespace(ledger=ledger)
    grader = SimpleNamespace(intake=SimpleNamespace(adapter=adapter))
    site = direct_intake._keep_failure(
        grader, "grade", _raised(Unavailable("served_recipe_source_changed"))
    )
    record = tmp_path / "worker-failures" / f"grade-{site}.txt"
    assert record.exists()
    assert "served_recipe_source_changed" in record.read_text()


def test_the_log_carries_only_a_closed_code():
    assert (
        direct_intake._closed_code(Unavailable("direct_provider_binding_unavailable"))
        == "direct_provider_binding_unavailable"
    )
    assert direct_intake._closed_code(Unavailable("a path /home/x")) is None
    assert direct_intake._closed_code(ValueError("x")) is None
