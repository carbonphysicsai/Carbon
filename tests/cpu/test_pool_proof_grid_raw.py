"""The proof grid script reads a pool-raw document as the pool merge writes it (V8_RULINGS section 12).

The Motor grid run crashed (PoolRefused raw_rows_must_match_the_original_pool) because the whole
`{"target_id", "design_names", "raw_outputs"}` document went to `attach_raw`, which takes the rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_plugin import binding, toy_target, truth

from carbon.scoring import pool_grader, pool_plugin
from scripts.dev import pool_proof_grid as grid_script


def _document(target_id="t1"):
    spec = toy_target(target_id, 5)
    rows = [truth({"x": d[0], "y": d[1]}) for d in spec.designs]
    return spec, {
        "target_id": target_id,
        "design_names": ["x", "y"],
        "raw_outputs": rows,
    }


def test_the_raw_rows_of_a_pool_raw_document_attach_in_the_original_pool_order():
    spec, document = _document()
    # the pool merge's document is the whole thing; its rows are the original pool's (spec.pool_size of them)
    original = [truth({"x": 0.0, "y": 0.0}) for _ in range(spec.pool_size)]
    document = {**document, "raw_outputs": original}
    rows = grid_script._raw_rows(document, "t1", binding())
    attached = pool_grader.attach_raw(spec, rows)
    assert attached.raw is not None and len(attached.raw) == len(spec.designs)
    with pytest.raises(pool_grader.PoolRefused, match="raw_rows_must_match"):
        pool_grader.attach_raw(
            spec, document
        )  # the crash this fixes: the whole document


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(target_id="other"),
        lambda d: d.update(design_names=["y", "x"]),
        lambda d: d.update(design_names=["x"]),
        lambda d: d.pop("raw_outputs"),
        lambda d: d.update(raw_outputs="rows"),
        lambda d: d.update(extra=1),
    ],
)
def test_a_pool_raw_document_that_is_not_this_targets_is_a_stop_not_a_guess(mutate):
    _, document = _document()
    mutate(document)
    with pytest.raises(pool_plugin.TruthCheckStop):
        grid_script._raw_rows(document, "t1", binding())
    with pytest.raises(pool_plugin.TruthCheckStop):
        grid_script._raw_rows([1, 2, 3], "t1", binding())


# --- each raw item is laid out as the bank's native flat row (grid crash 2) ----------------------------------

from carbon.scoring import pool_raw

VERSIONS = {"f02": "2.4", "f08": "1.5", "motor": "1.4", "cooling": "1.4"}


def _reference_layout(kind, version, record):
    """The pool operator's `probe_truth.raw_row`, which lays a record out as the sealed bank builders do."""
    if kind == "f02":
        from carbon.challenge_kit import f02_public

        slices = f02_public.interface_document("f02", version)["output"]["named_slices"]
        row = [0.0] * max(e for _, e in slices.values())
        row[slice(*slices["peak_top_c"])] = [float(record["outputs"]["peak_top_c"])]
        return row
    if kind == "f08":
        from carbon.challenge_kit import f08_public
        from carbon.challenge_kit.f08_sealed_pack import TARGETS

        slices = f08_public.interface_document("f08-ribbed-bracket", version)["output"][
            "named_slices"
        ]
        row = [0.0] * max(e for _, e in slices.values())
        outputs, damping = record["outputs"], record["damping"]
        for name, zeta, key in TARGETS:
            value = outputs[name] if zeta is None else damping[zeta][key]
            start, end = slices[name]
            row[start:end] = [float(value)]
        return row
    from carbon.challenge_kit import physical_public_train

    challenge = "electric-motor-magnetics" if kind == "motor" else "chip-cold-plate"
    slices = physical_public_train.numeric_interface_document(challenge)[
        "target_slices"
    ]
    row = [0.0] * max(e for _, e in slices.values())
    for name, (start, end) in slices.items():
        value = record["outputs"][name]
        value = value if type(value) is list else [value]
        row[start:end] = [float(v) for v in value]
    return row


def _record(kind):
    if kind == "f02":
        return {"outputs": {"peak_top_c": 71.5, "extra_energy_j": 12.0}}
    if kind == "f08":
        from carbon.challenge_kit.f08_sealed_pack import TARGETS

        return {
            "outputs": {
                "static_tip_mm_per_n": 0.031,
                "worst_dynamic_mm_per_n": 0.12,
                "mass_kg": 0.4,
                "cad_mass_kg": 0.4,
            },
            "damping": {
                zeta: {"worst_mm_per_n": 0.1 + i / 100, "worst_hz": 300.0 + i}
                for i, zeta in enumerate(
                    sorted({z for _, z, _ in TARGETS if z is not None})
                )
            },
        }
    if kind == "motor":
        return {"outputs": {"torque_nm": [4.0 + 0.01 * i for i in range(60)]}}
    return {
        "outputs": {
            "peak_c": 80.0,
            "profile_c": [70.0 - 0.1 * i for i in range(30)],
            "pressure_drop_pa": 900.0,
            "mean_c": 70.0,
            "outlet_c": 50.0,
        }
    }


@pytest.mark.parametrize("kind", sorted(VERSIONS))
def test_a_raw_output_dict_is_the_same_flat_row_the_bank_builders_lay_out(kind):
    version = VERSIONS[kind]
    record = _record(kind)
    raw = record if kind == "f08" else record["outputs"]
    row = pool_raw.flat_row(kind, version, raw)
    assert row == _reference_layout(kind, version, record)
    assert all(type(v) is float for v in row)
    # a flat row of the interface width passes through unchanged
    assert pool_raw.flat_row(kind, version, list(row)) == row


@pytest.mark.parametrize(("kind", "width"), [("motor", 60), ("cooling", 32)])
def test_widths_match_the_interface(kind, width):
    row = pool_raw.flat_row(kind, VERSIONS[kind], _record(kind)["outputs"])
    assert len(row) == width


@pytest.mark.parametrize(
    ("kind", "mutate"),
    [
        ("motor", lambda r: r["outputs"].update(torque_nm=[1.0] * 59)),
        ("motor", lambda r: r["outputs"].pop("torque_nm")),
        ("motor", lambda r: r["outputs"].update(torque_nm=[float("nan")] * 60)),
        ("cooling", lambda r: r["outputs"].update(profile_c=[1.0] * 29)),
        ("cooling", lambda r: r["outputs"].pop("pressure_drop_pa")),
        ("f02", lambda r: r["outputs"].pop("peak_top_c")),
        ("f02", lambda r: r["outputs"].update(peak_top_c=float("inf"))),
        ("f08", lambda r: r.pop("damping")),
        ("f08", lambda r: r["damping"].pop(next(iter(r["damping"])))),
    ],
)
def test_a_raw_output_that_cannot_be_laid_out_is_refused_never_zero_filled(
    kind, mutate
):
    record = _record(kind)
    mutate(record)
    raw = record if kind == "f08" else record["outputs"]
    with pytest.raises(pool_raw.PoolRawRefused):
        pool_raw.flat_row(kind, VERSIONS[kind], raw)


def test_f08_outputs_alone_cannot_fill_the_damped_peaks():
    outputs = _record("f08")["outputs"]
    with pytest.raises(pool_raw.PoolRawRefused, match="outputs_and_damping"):
        pool_raw.flat_row("f08", "1.5", outputs)
    with pytest.raises(pool_raw.PoolRawRefused):
        pool_raw.flat_row("motor", "1.4", 3.0)
    with pytest.raises(pool_raw.PoolRawRefused):
        pool_raw.flat_row("unknown", "1.0", {"a": 1})


@pytest.mark.parametrize("kind", sorted(VERSIONS))
def test_the_grid_script_flattens_every_item_of_a_pool_raw_document(kind):
    from types import SimpleNamespace

    version = VERSIONS[kind]
    record = _record(kind)
    item = record if kind == "f08" else record["outputs"]
    names = ["x", "y"]
    document = {
        "target_id": "t1",
        "design_names": names,
        "raw_outputs": [item, item],
    }
    shape = SimpleNamespace(kind=kind, version=version, design_names=tuple(names))
    rows = grid_script._raw_rows(document, "t1", shape)
    assert rows == [_reference_layout(kind, version, record)] * 2
    # one that cannot be laid out stops the run (exit 3), as any other wrong document does
    bad = {**document, "raw_outputs": [item, "not outputs"]}
    with pytest.raises(pool_plugin.TruthCheckStop):
        grid_script._raw_rows(bad, "t1", shape)


def test_the_truth_check_bank_counts_the_probe_rows_that_remain_after_the_closed_exclusion():
    """Pool operator, grid stop 5 (2026-10-27): F08's measure refuses a bank whose probe cohort differs from
    its definition's registered probe count (`f08_bank_cohort`); the exclusion removed 13 of 39 probe rows.
    """
    from dataclasses import replace

    rows = [{"case_id": f"c{i}", "reference": [1.0]} for i in range(4)] + [
        {"case_id": f"p{i}", "reference": None} for i in range(5)
    ]
    legs = pool_plugin.BankLegs(
        binding=binding(),
        measure=lambda **_: {},
        rows=rows,
        arguments={"definition": {"probes": {"cohort": "probe", "rows": 5}, "x": 1}},
        truth_probe_rule="perfect",
        response_leg="A_response",
        ignored_gates=(),
        truth_tolerance=0.01,
        state={},
    )
    checked = grid_script.without_excluded_probes(legs, {"p1", "p4"})
    assert [r["case_id"] for r in checked.rows] == [
        "c0",
        "c1",
        "c2",
        "c3",
        "p0",
        "p2",
        "p3",
    ]
    assert checked.arguments["definition"]["probes"] == {"cohort": "probe", "rows": 3}
    assert checked.arguments["definition"]["x"] == 1
    # the grid's own bank and definition are untouched: every model is still graded on the full bank
    assert len(legs.rows) == 9 and legs.arguments["definition"]["probes"]["rows"] == 5
    # no exclusion, or a definition with no probe count: unchanged
    same = grid_script.without_excluded_probes(legs, set())
    assert same.rows == rows and same.arguments == legs.arguments
    plain = grid_script.without_excluded_probes(
        replace(legs, arguments={"definition": {}}), {"p1"}
    )
    assert plain.arguments == {"definition": {}} and len(plain.rows) == 8


def _cooling_versions(encoded):
    from carbon.challenge_kit import version_registry

    return tuple(
        version
        for (challenge, version), entry in version_registry.VERSIONS.items()
        if challenge == version_registry.COOLING
        and (entry.output_encoding is not None) == encoded
    )


def _cooling_truth_spec(version, native):
    """Synthetic pool geometry; actual registered Cooling encoding and gates."""
    from dataclasses import replace

    from carbon.scoring import pool_adapters

    chosen = binding()
    chosen = replace(
        chosen,
        kind="cooling",
        version=version,
        input_names=(*chosen.input_names, "inlet_c"),
        to_model_space=pool_adapters._to_model_space("cooling", version),
        physics_gates=pool_adapters.physics_gates("cooling", version),
    )
    spec = toy_target("synthetic-cooling-truth", 5)
    spec = replace(
        spec,
        conditions={
            **spec.conditions,
            "fixed": {**spec.conditions["fixed"], "inlet_c": 20.0},
        },
    )
    return chosen, pool_grader.attach_raw(spec, [native] * spec.pool_size)


@pytest.mark.parametrize("version", _cooling_versions(True))
@pytest.mark.parametrize("invalid", ["peak", "zero_pressure", "negative_pressure"])
def test_native_truth_violations_cannot_be_hidden_by_decoding_as_a_model(
    version, invalid
):
    from carbon.cold_plate import exam

    native = _reference_layout("cooling", version, _record("cooling"))
    if invalid == "peak":
        native[0] = 60.0
    else:
        native[-1] = 0.0 if invalid == "zero_pressure" else -1.0
    chosen, spec = _cooling_truth_spec(version, native)
    prediction = {
        "peak_c": native[0],
        "profile_c": native[1:31],
        "pressure_drop_pa": native[31],
    }
    assert exam.FAIL in exam.gates(prediction, {"inlet_c": 20.0}).values()
    # The old preflight treated this native reference as encoded model output,
    # concealing the invalid native peak/pressure with the decoder's softplus.
    assert chosen.physics_gates.failed({"inlet_c": 20.0}, native) == ()
    with pytest.raises(
        pool_plugin.TruthCheckStop, match="^pool_truth_reference_encoding_invalid$"
    ):
        grid_script._check_pool_truths(chosen, [spec])


@pytest.mark.parametrize("version", _cooling_versions(True) + _cooling_versions(False))
def test_truth_preflight_preserves_native_references_and_the_oracles_single_conversion(
    version,
):
    from carbon.scoring import pool_gates

    native = _reference_layout("cooling", version, _record("cooling"))
    chosen, spec = _cooling_truth_spec(version, native)
    original = spec.raw
    record = grid_script._check_pool_truths(chosen, [spec])
    assert record == {
        "rows": len(spec.designs),
        "gates": sorted(chosen.physics_gates.gate_names),
    }
    assert spec.raw == original
    rows = pool_gates.pool_rows(chosen, [spec])
    oracle = pool_plugin.model_outputs(chosen, rows, {"kind": "oracle"})
    expected = (
        chosen.to_model_space(native) if chosen.to_model_space is not None else native
    )
    assert oracle == [expected] * len(rows)
    assert spec.raw == original


@pytest.mark.parametrize("version", _cooling_versions(False))
def test_native_gate_contracts_still_refuse_invalid_native_truth(version):
    native = _reference_layout("cooling", version, _record("cooling"))
    native[-1] = -1.0
    chosen, spec = _cooling_truth_spec(version, native)
    assert chosen.to_model_space is None
    with pytest.raises(pool_plugin.TruthCheckStop, match="pool_truths_fail_gates"):
        grid_script._check_pool_truths(chosen, [spec])


def test_truth_preflight_uses_a_declared_conversion_without_a_challenge_dispatch():
    from dataclasses import replace

    from carbon.scoring import pool_adapters, pool_gates

    def model_space(row):
        return [value + 10.0 for value in row]

    def failed(_inputs, row):
        return (
            ()
            if all(value == 10.5 for value in row)
            else ("synthetic_model_space",)
        )

    chosen = replace(
        binding(),
        to_model_space=model_space,
        physics_gates=pool_adapters.PhysicsGates(
            "toy", "1", ("synthetic_model_space",), failed
        ),
    )
    spec = toy_target("synthetic-conversion", 5)
    spec = pool_grader.attach_raw(spec, [[0.5, 0.5]] * spec.pool_size)
    original = spec.raw
    assert grid_script._check_pool_truths(chosen, [spec])["rows"] == len(spec.designs)
    assert spec.raw == original
    rows = pool_gates.pool_rows(chosen, [spec])
    assert pool_plugin.model_outputs(chosen, rows, {"kind": "oracle"}) == [
        [10.5, 10.5]
    ] * len(rows)
    with pytest.raises(
        pool_plugin.TruthCheckStop, match="truths_gate_check_needs_the_raw_truths"
    ):
        grid_script._check_pool_truths(chosen, [replace(spec, raw=None)])
