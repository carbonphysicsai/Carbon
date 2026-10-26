"""The pool prediction-table script: inputs-only rows in custody, a digest-checked build on the host."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev/pool_predict_table.py"
spec = importlib.util.spec_from_file_location("pool_predict_table", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def _document(tid, fixed, designs, names):
    return {
        "design_names": names,
        "conditions": {"target_id": tid, "fixed": fixed},
        "designs": designs,
        # sealed material the build host must never receive
        "truths": [{"x": 1.0}] * len(designs),
        "limits": [["x", "<=", 1.0]],
        "u": {"x": 0.1},
        "seed": 7,
    }


def test_rows_are_inputs_only_deduplicated_and_not_grouped_by_target():
    from carbon.scoring import pool_adapters

    chosen = pool_adapters.adapter("cooling", "1.4")
    names = list(chosen.design_names)
    fixed_a = {
        "inlet_c": 35.0,
        "heat_load_w": 800.0,
        "hotspot_ratio": 1.0,
        "hotspot_center_mm": 15.0,
        "hotspot_width_mm": 2.5,
    }
    fixed_b = {**fixed_a, "heat_load_w": 900.0}
    d1, d2 = [0.25, 0.3, 2.5, 1.25], [0.3, 0.35, 2.0, 1.5]
    documents = [
        _document("t1", fixed_a, [d1, d2], names),
        _document("t2", fixed_b, [d2, d1, d1], names),
        _document("t3", fixed_a, [d1], names),  # repeats t1's first row
    ]
    out = tool.build_rows("cooling", "1.4", documents)
    assert out["input_names"] == list(chosen.input_names)
    assert len(out["rows"]) == 4 and out["rows"] == sorted(out["rows"])
    text = json.dumps(out)
    for forbidden in ("truth", "limit", "seed", "target", '"u"', "t1", "agen"):
        assert forbidden not in text
    with pytest.raises(tool.Stop):
        tool.build_rows("cooling", "1.4", [_document("t", fixed_a, [d1], names[:-1])])


def test_rows_command_reads_the_sets_and_writes_one_file(tmp_path, capsys):
    from carbon.scoring import pool_adapters

    chosen = pool_adapters.adapter("f02", "2.4")
    names = list(chosen.design_names)
    pools = tmp_path / "pools"
    pools.mkdir()
    (pools / "pool-source-a.json").write_text(
        json.dumps(_document("a", {}, [[90.0, 4.0], [80.0, 3.0]], names))
    )
    (tmp_path / "sets.json").write_text(json.dumps({"A": ["a"]}))
    args = SimpleNamespace(
        kind="f02",
        version="2.4",
        pools_dir=str(pools),
        sets=str(tmp_path / "sets.json"),
        out=str(tmp_path / "rows.json"),
    )
    assert tool.rows_command(args) == 0
    written = json.loads((tmp_path / "rows.json").read_text())
    assert written["schema"] == tool.ROWS_SCHEMA
    assert written["rows"] == [[80.0, 3.0], [90.0, 4.0]]


class _Binder:
    def __init__(self, drift=None):
        self.drift = drift

    def bind_pick(self, pick, runtime):
        out = {
            "bound_recipe_digest": "sha256:" + "1" * 64,
            "bundle_recipe_digest": "sha256:" + "2" * 64,
        }
        if self.drift:
            out[self.drift] = "sha256:" + "9" * 64
        return out

    def catalog_recipe(self, challenge_id, version, catalog_id, procedure):
        return {"catalog_id": catalog_id}


def _bound():
    return {
        "picks": [
            {
                "role": "good",
                "challenge_id": "f02",
                "version": "2.4",
                "catalog_id": "e",
                "procedure": {},
                "runtime": None,
                "bound_recipe_digest": "sha256:" + "1" * 64,
                "bundle_recipe_digest": "sha256:" + "2" * 64,
            }
        ]
    }


def test_a_digest_that_moved_is_a_stop(tmp_path):
    for key in ("bound_recipe_digest", "bundle_recipe_digest"):
        with pytest.raises(tool.Stop) as raised:
            tool.check_pick(_Binder(drift=key), _bound(), "good", "f02", "2.4")
        assert key in str(raised.value)
    with pytest.raises(tool.Stop):
        tool.check_pick(_Binder(), _bound(), "default", "f02", "2.4")
    assert (
        tool.check_pick(_Binder(), _bound(), "good", "f02", "2.4")["catalog_id"] == "e"
    )


def test_predict_builds_once_and_writes_the_table(tmp_path, monkeypatch):
    from carbon.scoring import pool_serving

    seen = {}

    def predict_rows(practice, identity, strategy, rows):
        seen.update(practice=practice, identity=identity, strategy=strategy, rows=rows)
        return [[0.5] for _ in rows], "sha256:" + "3" * 64

    monkeypatch.setattr(pool_serving, "predict_rows", predict_rows)
    (tmp_path / "bound.json").write_text(json.dumps(_bound()))
    (tmp_path / "rows.json").write_text(
        json.dumps(
            {
                "schema": tool.ROWS_SCHEMA,
                "kind": "f02",
                "version": "2.4",
                "input_names": ["peak_w", "on_time_s"],
                "rows": [[90.0, 4.0]],
            }
        )
    )
    curves = SimpleNamespace(
        TARGETS={"f02": ("f02", "2.4")},
        practice_for=lambda kind, args: "practice-object",
    )
    args = SimpleNamespace(
        kind="f02",
        role="good",
        bound=str(tmp_path / "bound.json"),
        rows=str(tmp_path / "rows.json"),
        out=str(tmp_path / "t.json"),
        work_dir=str(tmp_path / "w"),
    )
    assert tool.predict_command(args, binder=_Binder(), curves=curves) == 0
    assert seen["practice"] == "practice-object" and seen["rows"] == [[90.0, 4.0]]
    table = pool_serving.load_table(tmp_path / "t.json")
    assert table["recipe_digest"] == "sha256:" + "2" * 64
    assert table["state_digest"] == "sha256:" + "3" * 64
    # a rows file for another version is refused
    (tmp_path / "rows.json").write_text(
        json.dumps(
            {
                "schema": tool.ROWS_SCHEMA,
                "kind": "f02",
                "version": "9.9",
                "input_names": [],
                "rows": [],
            }
        )
    )
    with pytest.raises(tool.Stop):
        tool.predict_command(args, binder=_Binder(), curves=curves)
