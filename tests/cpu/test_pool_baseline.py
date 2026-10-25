"""The TRAIN-fit model of the pool grid run: learned-krr-v1 on TRAIN only, registered or selected on PRACTICE."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.scoring import pool_baseline as baseline
from carbon.scoring import practice_grid

VERSIONS = {"f08": "1.5", "motor": "1.4", "f02": "2.4", "cooling": "1.4"}
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev/pool_predict_table.py"
spec = importlib.util.spec_from_file_location("pool_predict_table_t", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


@pytest.mark.parametrize("kind", sorted(VERSIONS))
def test_the_declared_box_covers_every_input_and_is_increasing(kind):
    bounds = baseline.declared_bounds(kind, VERSIONS[kind])
    assert list(bounds) == list(practice_grid.input_names(kind, VERSIONS[kind]))
    assert all(hi > lo for lo, hi in bounds.values())


@pytest.mark.parametrize("kind", ["f08", "motor"])
def test_f08_and_motor_use_their_registered_values(kind):
    predict, choice = baseline.fit(kind, VERSIONS[kind])
    assert (choice["length"], choice["ridge"]) == baseline.REGISTERED[kind]
    assert choice["source"] == "registered" and choice["at_edge"] == []
    from carbon.scoring import pool_adapters

    _enc, inputs, targets = pool_adapters._train_arrays(kind, VERSIONS[kind])
    rows = inputs[:3].tolist()
    out = predict(rows)
    assert len(out) == 3 and len(out[0]) == targets.shape[1]
    assert all(math.isfinite(v) for row in out for v in row)
    # a TRAIN-fit kernel ridge with a small ridge reproduces its own TRAIN rows closely
    spread = targets.std(axis=0)
    spread[spread == 0] = 1.0
    assert (abs(targets[:3] - out) / spread).max() < 0.1
    assert predict(rows) == out  # deterministic


@pytest.mark.parametrize("kind", ["f02", "cooling"])
def test_f02_and_cooling_pick_their_values_on_practice_and_report_the_choice(kind):
    predict, choice = baseline.fit(kind, VERSIONS[kind])
    assert choice["source"] == "select on PRACTICE"
    from carbon.learned_baseline import LENGTHS, RIDGES

    assert choice["length"] in LENGTHS and choice["ridge"] in RIDGES
    assert set(choice["at_edge"]) <= {"length", "ridge"}
    assert type(choice["gate_failed_on_practice"]) is bool  # reported, never hidden
    names = practice_grid.input_names(kind, VERSIONS[kind])
    out = predict([[1.0] * len(names)])
    assert len(out) == 1 and all(math.isfinite(v) for v in out[0])


def test_the_train_command_writes_a_table_and_flags_an_edge_choice(tmp_path, capsys):
    from carbon.scoring import pool_adapters, pool_serving

    chosen = pool_adapters.adapter("f08", "1.5")
    _enc, inputs, _t = pool_adapters._train_arrays("f08", "1.5")
    rows = inputs[:4].tolist()
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(
        json.dumps(
            {
                "schema": tool.ROWS_SCHEMA,
                "kind": "f08",
                "version": "1.5",
                "input_names": list(chosen.input_names),
                "rows": rows,
            }
        )
    )
    args = SimpleNamespace(
        kind="f08", rows=str(rows_file), out=str(tmp_path / "t.json")
    )
    assert tool.train_command(args) == 0
    table = pool_serving.load_table(tmp_path / "t.json")
    assert table["recipe_digest"] == "learned-krr-v1" and len(table["rows"]) == 4
    server = pool_serving.TableServer(table, chosen.input_names)
    assert len(server([dict(zip(chosen.input_names, rows[0]))])[0]) == 7
    rows_file.write_text(
        json.dumps({"schema": "other", "kind": "f08", "version": "1.5"})
    )
    with pytest.raises(tool.Stop):
        tool.train_command(args)
