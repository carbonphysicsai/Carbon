"""The Constructor (phase 3) and the Attacker (phase 4) run at --level 1 against
battery's registered Level-1 variant, as dry runs: no network, no spend, no
pod (GRAPHITE-L1-BUILD-01)."""

from __future__ import annotations

import json
import sqlite3

from carbon.agent_campaign.graphite import phase3, phase4
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_variants as dv

BATTERY = cr.BATTERY_CHALLENGE


def _run(main, root, level=1):
    try:
        return main(
            ["run", "--root", str(root), "--challenge", BATTERY, "--dry-run"]
            + ["--level", str(level)]
        )
    except SystemExit as stopped:
        return stopped.code


def test_the_constructor_runs_at_level_1(tmp_path, monkeypatch):
    import containment_double

    # The dry run's carrier containment check (synthetic passing double).
    containment_double.install(monkeypatch)
    assert _run(phase3.main, tmp_path) == 0
    variant = dv.variant(BATTERY, 1)
    database = tmp_path / "dry-run" / "controller" / "campaign.sqlite3"
    with sqlite3.connect(database) as connection:
        rows = connection.execute("SELECT * FROM development_expansions").fetchall()
    assert rows and variant.digest in json.dumps(rows, default=str)


def test_the_attacker_runs_at_level_1(tmp_path, capsys):
    assert _run(phase4.main, tmp_path) == 0
    out = capsys.readouterr().out
    assert '"construction_level": 1' in out
    assert '"provider_state": "succeeded"' in out
    assert '"settled_usd": "0"' in out
