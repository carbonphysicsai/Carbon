"""The v8 graph-route attack harness (scripts/dev/v8_graph_attacks.py) runs end to end and reports each scenario.

It pins no verdict: a FAIL is an attack that succeeded against this build (a finding), not a test failure. What is
pinned is that every scenario runs (none crashes into a 'harness' row), and that the controls hold.
"""

from __future__ import annotations

import pytest

pytest.importorskip("jax")

from scripts.dev import v8_graph_attacks as attacks


def test_every_scenario_runs_and_the_controls_hold():
    results = {r.id: r for r in attacks.run()}
    assert not [r for r in results.values() if r.area == "harness"], [
        (r.id, r.observed) for r in results.values() if r.area == "harness"
    ]
    assert {
        "V1",
        "V2",
        "V4",
        "V5a",
        "V5b",
        "V5c",
        "V5d",
        "V6",
        "V7",
        "V8",
        "V10",
    } <= set(results)
    # Controls: honest structured weights are admitted and cheap, and real-storage packing is charged what it holds.
    assert results["V5c"].verdict == "PASS"
    assert results["V5d"].verdict == "PASS"
    assert results["V4"].verdict == "PASS"
    for result in results.values():
        assert result.verdict in {"PASS", "FAIL", "RISK", "INFO", "NOT_RUN"}
