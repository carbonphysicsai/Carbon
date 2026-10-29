"""Trusted F02 grid truth-check routing with synthetic batches, truths and pool material only.

No solver, custody, signed evidence, official score or production constant is supplied by these fixtures.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, replace

import pytest
from test_f02_group_response_reference import _truth
from test_f02_sealed_pack import batch
from test_pool_plugin import _grid_spec

from carbon.scoring import (
    f02_physics,
    pool_adapters,
    pool_grader,
    pool_plugin,
    pool_version,
)
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import sealed_batch_source as source
from scripts.dev import pool_proof_grid as script


@pytest.fixture
def sealed_case(tmp_path):
    document, records = batch()
    plain = source._build(source.F02, source._kit(source.F02), document, records, "2.4")
    rows = physical.bank_rows(plain, ("peak_w", "on_time_s"))
    probes = [r for r in rows if r["reference"] is None]
    truths = {
        r["case_id"]: [_truth(r["inputs"]["peak_w"], r["inputs"]["on_time_s"])]
        for r in probes
    }
    anchor = {
        "input": "on_time_s",
        "by_base": f02_physics.local_slopes(
            probes, [truths[r["case_id"]][0] for r in probes]
        ),
    }
    target = pool_grader.build_target(
        target_id="synthetic",
        conditions={"target_id": "synthetic", "fixed": {}},
        outputs=("synthetic",),
        objective="synthetic",
        sense="max",
        limits=(),
        u={"synthetic": 0.01},
        box=((70.0, 100.0), (4.0, 6.0)),
        designs=((75.0, 4.2), (85.0, 5.0), (95.0, 5.8)),
        truths=[{"synthetic": float(i)} for i in (1, 2, 3)],
        agen=(),
        start=(0.5, 0.5),
        seed=7,
    )
    material = {
        "schema": pool_version.MATERIAL_SCHEMA,
        "kind": "f02",
        "version": "2.5",
        "input_names": ["peak_w", "on_time_s"],
        "design_names": ["peak_w", "on_time_s"],
        "input_dtype": "<f8",
        "set_digest": "sha256:" + "5" * 64,
        "sets": [[pool_grader.dump_pool(target)]],
        "response_reference": anchor,
    }
    carried = {**document, "pool": material}
    truth_file = tmp_path / "truth.json"
    truth_file.write_text(json.dumps(truths), encoding="utf-8")

    def write_batch():
        (tmp_path / source.SEALED_BATCH_FILE).write_bytes(
            source.batch_bytes(carried, records)
        )

    write_batch()

    def serve(inputs):
        return [[_truth(row["peak_w"], row["on_time_s"])] for row in inputs]

    binding = pool_adapters.binding(
        "f02",
        "2.5",
        u={"peak_top_c": 0.1},
        serve_good=serve,
        serve_train=serve,
        serve_default=serve,
    )
    legs = pool_plugin.practice_bank_legs(
        binding,
        truth_probe_rule="perfect",
        response_leg="A_response",
        ignored_gates=("physics_laws",),
        truth_tolerance=1e-9,
    )
    return tmp_path, truth_file, carried, records, truths, legs, write_batch


def test_own_sealed_anchor_passes_real_native_measure_without_changing_practice_grading(
    sealed_case,
):
    root, truth_file, _, _, _, legs, _ = sealed_case
    before = copy.deepcopy(legs.arguments)
    good_before = legs.legs({"kind": "good"})
    checked = script.sealed_truth_bank_legs(legs, root, truth_file)
    assert checked.state is legs.state and "truth_check" not in legs.state
    assert sum(r["reference"] is not None for r in checked.rows) == 8
    assert checked.rows is not legs.rows
    record = checked.verify_truth_rows()
    assert record["response_leg"] == pytest.approx(1.0)
    assert legs.state == {"truth_check": record}
    assert legs.arguments == before
    assert legs.legs({"kind": "good"}) == good_before
    assert checked.binding is not legs.binding and legs.binding.probe_truth is None
    # Removing the sealed anchor restores the existing global reference and STOP, not a measured-rule fallback.
    global_check = replace(
        checked,
        arguments={
            **checked.arguments,
            "definition": {
                k: v
                for k, v in checked.arguments["definition"].items()
                if k != "group_response_reference"
            },
        },
        state={},
    )
    with pytest.raises(pool_plugin.TruthCheckStop, match="truth_outputs_fail"):
        global_check.verify_truth_rows()


@pytest.mark.parametrize(
    "fault",
    [
        "version",
        "kind",
        "names",
        "no_anchor",
        "partial_anchor",
        "extra_anchor",
        "nonfinite_anchor",
        "other_anchor",
        "no_pool",
        "missing_cell",
    ],
)
def test_incompatible_or_incomplete_material_stops_before_authorizing_perfect_rule(
    sealed_case,
    fault,
):
    root, truth_file, carried, records, _, legs, write_batch = sealed_case
    material = carried["pool"]
    if fault in ("version", "kind"):
        material[fault] = "incompatible"
    elif fault == "names":
        material["input_names"].reverse()
    elif fault == "no_anchor":
        del material["response_reference"]
    elif fault == "partial_anchor":
        by_base = material["response_reference"]["by_base"]
        by_base.pop(next(iter(by_base)))
    elif fault == "extra_anchor":
        material["response_reference"]["by_base"]["unrelated"] = 0.2
    elif fault == "nonfinite_anchor":
        material["response_reference"]["by_base"] = {"0": float("nan")}
    elif fault == "other_anchor":
        material["response_reference"]["input"] = "peak_w"
    elif fault == "no_pool":
        del carried["pool"]
    else:
        records.pop()
    if fault == "nonfinite_anchor":
        # Deliberately malformed bytes: the normal writer refuses NaN before this loader ever sees it.
        (root / source.SEALED_BATCH_FILE).write_text(
            json.dumps(
                {"schema": source.SCHEMA, "document": carried, "records": records}
            ),
            encoding="utf-8",
        )
    else:
        write_batch()
    with pytest.raises(pool_plugin.TruthCheckStop, match="sealed_truth_check"):
        script.sealed_truth_bank_legs(legs, root, truth_file)
    assert legs.state == {}


@pytest.mark.parametrize(
    "fault", ["missing", "extra", "width", "nonfinite", "boolean", "not_dict"]
)
def test_probe_truth_must_match_the_sealed_probes_exactly_and_be_finite_width_one(
    sealed_case,
    fault,
):
    root, truth_file, _, _, truths, legs, _ = sealed_case
    first = next(iter(truths))
    if fault == "missing":
        truths.pop(first)
    elif fault == "extra":
        truths["synthetic-unrelated-probe"] = [50.0]
    elif fault == "not_dict":
        truths = []
    else:
        truths[first] = {
            "width": [50.0, 51.0],
            "nonfinite": [float("nan")],
            "boolean": [True],
        }[fault]
    truth_file.write_text(json.dumps(truths), encoding="utf-8")
    with pytest.raises(pool_plugin.TruthCheckStop, match="sealed_truth_check_truth"):
        script.sealed_truth_bank_legs(legs, root, truth_file)
    assert legs.state == {}


def test_a_huge_json_integer_truth_is_sanitized_before_the_perfect_rule(sealed_case):
    root, truth_file, _, _, truths, legs, _ = sealed_case
    truths[next(iter(truths))] = [10**400]
    truth_file.write_text(json.dumps(truths), encoding="utf-8")
    with pytest.raises(
        pool_plugin.TruthCheckStop,
        match="^sealed_truth_check_material_or_truth_malformed$",
    ):
        script.sealed_truth_bank_legs(legs, root, truth_file)
    assert legs.state == {}


def test_a_remaining_real_native_gate_failure_still_stops_the_sealed_truth_check(
    sealed_case,
):
    root, truth_file, _, _, truths, legs, _ = sealed_case
    truths[next(iter(truths))] = [0.0]
    truth_file.write_text(json.dumps(truths), encoding="utf-8")
    checked = script.sealed_truth_bank_legs(legs, root, truth_file)
    with pytest.raises(pool_plugin.TruthCheckStop, match="physics_laws"):
        checked.verify_truth_rows()
    assert legs.state == {}


def test_cli_routes_only_the_truth_check_and_reports_aggregates(
    sealed_case, monkeypatch, capsys
):
    root, truth_file, _, _, truths, legs, _ = sealed_case
    monkeypatch.setattr(script, "_binding", lambda *_: legs.binding)
    monkeypatch.setattr(
        pool_plugin, "practice_bank_legs", lambda *_args, **_kwargs: legs
    )
    monkeypatch.setattr(
        pool_plugin,
        "make_plugin",
        lambda binding, bank, *_args, **_kwargs: (binding, bank),
    )

    def run_grid(plugin, _grid):
        # CLI wiring only; the real native truth measurement ran above this boundary. No synthetic score is emitted.
        assert plugin == (legs.binding, legs) and "truth_check" in legs.state
        return {"meta": {"rows": 0, "rows_meeting_all": 0}, "rows": []}

    from carbon.scoring import pool_proof_grid

    monkeypatch.setattr(pool_proof_grid, "run_grid", run_grid)
    monkeypatch.setattr(
        pool_proof_grid, "sheet_markdown", lambda *_: "synthetic wiring test\n"
    )
    (root / "sets.json").write_text(json.dumps({"A": []}), encoding="utf-8")
    (root / "grid.json").write_text(json.dumps(asdict(_grid_spec())), encoding="utf-8")
    argv = [
        "--kind",
        "f02",
        "--version",
        "2.5",
        "--binding",
        "synthetic:binding",
        "--pools-dir",
        str(root),
        "--sets",
        str(root / "sets.json"),
        "--grid",
        str(root / "grid.json"),
        "--out-dir",
        str(root / "out"),
        "--truth-probe-rule",
        "perfect",
        "--response-leg",
        "A_response",
        "--ignored-gates",
        "physics_laws",
        "--truth-tolerance",
        "1e-9",
        "--pool-gates",
        "off",
        "--in-distribution",
        "reported",
        "--truth-row-sealed-batch-dir",
        str(root),
        "--probe-truth-file",
        str(truth_file),
    ]
    assert script.main(argv) == 0
    result = json.loads(
        (root / "out/owner-sheet-f02-2.5.json").read_text(encoding="utf-8")
    )
    assert result["meta"]["truth_row_check"] == {
        "source": "sealed_native",
        **legs.state["truth_check"],
    }
    disclosed = capsys.readouterr().out + json.dumps(result)
    assert "sealed bank" in disclosed and "by_base" not in disclosed
    assert all(case_id not in disclosed for case_id in truths)
    for flag, bad in (
        ("--version", "2.4"),
        ("--truth-probe-rule", "measured"),
        ("--probe-truth-file", ""),
    ):
        refused = list(argv)
        refused[refused.index(flag) + 1] = bad
        assert script.main(refused) == 3
    # A partial sealed truth file must STOP before writing another sheet or setting perfect-rule state.
    truths.pop(next(iter(truths)))
    truth_file.write_text(json.dumps(truths), encoding="utf-8")
    legs.state.clear()
    refused = list(argv)
    refused[refused.index("--out-dir") + 1] = str(root / "refused")
    assert script.main(refused) == 3
    assert not (root / "refused").exists() and legs.state == {}
