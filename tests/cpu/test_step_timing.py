"""mcp_slow (live 116, 21 Nov 2026): the door names its own slow submit step (`step_timing`): one ``submit_timing``
journal line of step names and milliseconds only; outside a submit every step is a no-op.
"""

from __future__ import annotations

import contextlib
import threading

from carbon.challenge_validator import direct_intake, step_timing


def test_steps_collect_only_inside_a_collection_and_add_up():
    with step_timing.step("outside"):
        pass  # no collection: nothing recorded, nothing raised
    with step_timing.collecting() as steps:
        with step_timing.step("a"):
            pass
        with step_timing.step("a"):
            pass
        lock = threading.Lock()
        with contextlib.ExitStack() as held:
            step_timing.enter(held, "lock_wait", lock)
            assert lock.locked()
        assert not lock.locked()
    assert set(steps) == {"a", "lock_wait"}
    assert all(type(ms) is int and ms >= 0 for ms in steps.values())
    with step_timing.collecting() as fresh:
        pass
    assert fresh == {}


def test_the_journal_line_is_names_and_milliseconds_only(monkeypatch):
    import carbon.battery.intake

    lines = []
    monkeypatch.setattr(
        carbon.battery.intake,
        "log",
        lambda event, **fields: lines.append((event, fields)),
    )
    direct_intake._log_submit_timing(
        0.0, 0.5, 0.6, {"evaluate": 900, "scope_lock_wait": 12, "bad name": 3}
    )
    ((event, fields),) = lines
    assert event == "submit_timing"
    assert set(fields) == {
        "total_ms",
        "receive_ms",
        "charge_ms",
        "evaluate",
        "scope_lock_wait",
    }
    assert (fields["receive_ms"], fields["charge_ms"]) == (500, 100)
    assert all(type(value) is int for value in fields.values())
