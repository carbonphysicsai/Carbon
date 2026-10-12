"""A design bank fill fails when its truth solve fails, never exits 0.

On r8.1 a Q3 fill's container never started (`-v` split the tranche path
`bank-design:battery-q3-T1` on its colon), the solve's return code was
ignored, and the fill exited 0 with the tranche silently pending. Now a
non-zero solve refuses (`producer_truth_solve_failed`) and a fill that leaves
a tranche unsolved exits non-zero, so the systemd unit fails.
"""

from __future__ import annotations

import json

import pytest

from carbon.challenge_validator import design_bank as dbk
from carbon.challenge_validator.batch_source import ProducerRefused


@pytest.mark.parametrize("returncode", [1, 125])
def test_a_failed_container_refuses_the_fill(returncode):
    calls = []

    def solve(directory, overlay, *, workers, **options):
        calls.append((directory, overlay, workers, options))
        return {"returncode": returncode}

    with pytest.raises(ProducerRefused, match="producer_truth_solve_failed"):
        dbk.checked_solve(solve, "work", "overlay", 8, runner="r")
    assert calls == [("work", "overlay", 8, {"runner": "r"})]


def test_a_clean_container_passes_through():
    found = dbk.checked_solve(
        lambda d, o, *, workers: {"returncode": 0, "solved": 3}, "w", "o", 6
    )
    assert found == {"returncode": 0, "solved": 3}


def test_an_unsolved_tranche_fails_the_fill_command(monkeypatch, tmp_path, capsys):
    class Bank:
        def __init__(self, *a, **k):
            self.ledger = type("L", (), {"status": staticmethod(dict)})()

        def top_up(self, **options):
            return [{"tranche": "bank-design:battery-q3-T1", "state": "PENDING"}]

    class Producer:
        def __init__(self):
            self.sources = {"c": type("S", (), {"overlay": "o"})()}

        @classmethod
        def from_config(cls, path):
            return cls()

    from carbon.challenge_validator import producer

    monkeypatch.setattr(dbk, "DesignBank", Bank)
    monkeypatch.setattr(producer, "Producer", Producer)
    monkeypatch.setattr(
        dbk, "law_for", lambda *a, **k: type("Law", (), {"challenge_id": "c"})()
    )
    code = dbk.main(
        ["fill", "--config", "p.json", "--bank", "battery-q3", "--dir", str(tmp_path)]
    )
    assert code == 3
    lines = capsys.readouterr().out.strip().splitlines()
    assert json.loads(lines[-1]) == {"refused": "producer_design_tranche_unsolved"}
