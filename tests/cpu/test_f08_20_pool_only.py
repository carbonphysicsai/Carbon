"""RB 2.0 head B2: the RB-only pieces of a pool-only version (spec RB20_HEAD_B2_SPEC_20261122 8b514b8c).

Claims:
- ``cad_mass_kg`` is exam-rb's closed form: it equals all 240 public TRAIN rows (public table cd78ee98) to rel 1e-12,
  and its densities are the signed alloy table's (d5b8cc56) in the deck's unit conversion;
- the derive reads a 22-wide answer in `GRADED_OUTPUTS` order and adds the exact mass; anything else is no answer;
- G1-G5 are model-eval's gates (04:23:00Z (d)), each failing on its own, with no sign rule on the tip vector; G5's band
  is `f08_proof.BAND_HZ`;
- the pool roles are the RB menus' (7 geometry inputs as the box, 5 duty inputs as conditions, cad_mass_kg min);
- the record -> truth mapping reads the RESULTS record keys (exam-rb 04:22:13Z), and the all-pool bank refuses a pool
  truth that differs from its record, a design without its production job and every malformed batch;
- the pool-only definition / applied pack carry no sealed row and no gate of their own (PoolVariant adds the pool's);
- the live 1.x producer files are byte-unchanged, and the F08 kit delegates 2.0 with one line.

Every design, record and truth here is a SYNTHETIC fixture except the public TRAIN masses.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_kit import f08_v2_sealed_pack as kit
from carbon.challenge_kit import f08_v2_train as train
from carbon.scoring import f08_20_dual_pack as rb
from carbon.scoring import f08_20_mass as mass
from carbon.scoring import pool_exam, pool_grader, pool_version

ROOT = Path(__file__).resolve().parents[2]
CALCULIX = ROOT / "scripts" / "dev" / "reference_packages" / "calculix"


def _assigned(path, name):
    """A module-level literal of a reference-package file, read by ``ast`` (never imported)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and getattr(node.targets[0], "id", None) == name
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(name)


# -- the closed-form mass ------------------------------------------------------------------------------------------------


def test_the_mass_equals_every_public_train_row():
    document = json.loads(
        (ROOT / "tests/fixtures/rb20/public_train_mass_240.json").read_text("utf-8")
    )
    assert document["source_sha256"] == train.TABLE_SHA256
    assert len(document["rows"]) == 240
    names = document["columns"][:-1]
    assert tuple(names) == mass.INPUTS
    for row in document["rows"]:
        expected = row[-1]
        got = mass.cad_mass_kg(dict(zip(names, row[:-1], strict=True)))
        assert abs(got - expected) <= 1e-12 * abs(expected)


def test_the_densities_are_the_signed_table_in_the_deck_conversion():
    table = CALCULIX / "f08_v2_alloy_table.json"
    raw = table.read_bytes().replace(b"\r\n", b"\n")
    assert "sha256:" + hashlib.sha256(raw).hexdigest() == _assigned(
        CALCULIX / "f08_deck_v2.py", "ALLOY_SHA256"
    )
    file_ids = _assigned(CALCULIX / "f08_deck_v2.py", "ALLOY_FILE_IDS")
    rows = {row["id"]: row for row in json.loads(raw)["alloys"]}
    assert tuple(_assigned(CALCULIX / "f08_deck_v2.py", "ALLOY_IDS")) == tuple(
        train.ALLOY_IDS
    )
    assert mass.RHO_KG_M3 == tuple(
        rows[file_ids[name]]["rho_kg_m3"] for name in train.ALLOY_IDS
    )
    assert mass.KG_M3_TO_T_MM3 == _assigned(
        CALCULIX / "f08_deck_v2.py", "KG_M3_TO_T_MM3"
    )


def test_the_mass_refuses_a_missing_input_or_an_unknown_alloy():
    good = dict(_DESIGN)
    mass.cad_mass_kg(good)
    for name in mass.INPUTS:
        with pytest.raises(mass.MassRefused, match="mass_input_missing_" + name):
            mass.cad_mass_kg({k: v for k, v in good.items() if k != name})
    for alloy in (3.0, 0.5, -1.0):
        with pytest.raises(mass.MassRefused, match="mass_alloy_index"):
            mass.cad_mass_kg({**good, "alloy_index": alloy})
    with pytest.raises(mass.MassRefused, match="mass_input_missing_length_mm"):
        mass.cad_mass_kg({**good, "length_mm": float("nan")})


# -- the answer, the derive and G1-G5 ------------------------------------------------------------------------------------

_DESIGN = {
    "length_mm": 180.0,
    "width_mm": 64.0,
    "thickness_mm": 4.5,
    "rib_height_mm": 12.0,
    "rib_thickness_mm": 3.0,
    "relief_length_mm": 40.0,
    "fillet_radius_mm": 1.5,
    "alloy_index": 1.0,
    "payload_mass_kg": 0.5,
    "load_angle_deg": 22.5,
    "load_position_in_gap": 0.25,
    "damping_ratio": 0.0078125,
}


def _good_row():
    row = dict.fromkeys(train.GRADED_OUTPUTS, 1.0)
    row["first_mode_hz"] = 100.0
    for i in range(1, 11):
        row[f"modes_hz_{i}"] = 100.0 + 50.0 * i
    row["patch_dynamic_frequency_hz"] = 150.0
    row["tip_static_displacement_mm_per_n_0"] = -0.25  # no sign rule on the tip vector
    row["tip_static_displacement_mm_per_n_1"] = 0.5
    return row


def _raw(row):
    return [row[name] for name in train.GRADED_OUTPUTS]


def test_the_derive_reads_22_outputs_and_adds_the_exact_mass():
    row = _good_row()
    derived = rb.derive_answer(_DESIGN, _raw(row))
    assert derived == {**row, "cad_mass_kg": mass.cad_mass_kg(_DESIGN)}
    assert rb.pool_adapter().outputs == (*train.GRADED_OUTPUTS, "cad_mass_kg")
    for bad in (_raw(row)[:-1], [*_raw(row), 1.0], None, "x", [*_raw(row)[:-1], "x"]):
        assert rb.derive_answer(_DESIGN, bad) is None
    assert rb.derive_answer(_DESIGN, [*_raw(row)[:-1], float("inf")]) is None


def test_a_good_answer_passes_every_gate():
    assert rb.failed_gates(_raw(_good_row())) == ()
    # G3 is non-strict: a degenerate pair passes
    row = _good_row()
    row["modes_hz_2"] = row["modes_hz_1"]
    assert rb.failed_gates(_raw(row)) == ()
    # G4 allows a zero stress; G5 includes both band ends
    for name in ("static_fillet_stress_mpa_per_n", "patch_static_max_principal"):
        assert rb.failed_gates(_raw({**_good_row(), name: 0.0})) == ()
    for edge in rb.BAND_HZ:
        assert (
            rb.failed_gates(_raw({**_good_row(), "patch_dynamic_frequency_hz": edge}))
            == ()
        )


@pytest.mark.parametrize(
    "change,gate",
    [
        ({"worst_dynamic_mm_per_n": float("nan")}, "g1_finite"),
        ({"first_mode_hz": 0.0}, "g2_frequency_positive"),
        ({"modes_hz_3": 120.0}, "g3_modes_non_decreasing"),
        ({"first_mode_hz": 160.0}, "g3_modes_non_decreasing"),
        ({"dynamic_fillet_stress_base_mpa_per_g": -1e-9}, "g4_stress_non_negative"),
        (
            {"patch_dynamic_max_principal_at_vm_frequency": -1.0},
            "g4_stress_non_negative",
        ),
        ({"patch_dynamic_frequency_hz": 79.999}, "g5_patch_frequency_in_band"),
        ({"patch_dynamic_frequency_hz": 600.001}, "g5_patch_frequency_in_band"),
    ],
)
def test_each_gate_fails_on_its_own(change, gate):
    assert rb.failed_gates(_raw({**_good_row(), **change})) == (gate,)
    assert rb.physics_gates().failed(_DESIGN, _raw({**_good_row(), **change})) == (
        gate,
    )


def test_a_row_that_is_not_22_numbers_fails_the_schema_gate_only():
    assert rb.failed_gates(_raw(_good_row())[:21]) == ("g1_finite",)
    assert rb.failed_gates(None) == ("g1_finite",)
    assert rb.physics_gates().gate_names == rb.GATES


def test_the_band_is_the_registered_proof_constant():
    assert rb.BAND_HZ == _assigned(CALCULIX / "f08_proof.py", "BAND_HZ")


def test_the_pool_roles_are_the_menus():
    adapter = rb.pool_adapter()
    assert adapter.input_names == train.INPUT_NAMES
    assert set(adapter.design_names) | set(adapter.condition_names) == set(
        train.INPUT_NAMES
    )
    assert not set(adapter.design_names) & set(adapter.condition_names)
    assert adapter.condition_names == (
        "alloy_index",
        "payload_mass_kg",
        "load_angle_deg",
        "load_position_in_gap",
        "damping_ratio",
    )
    assert (adapter.objective, adapter.sense, adapter.limits) == (
        "cad_mass_kg",
        "min",
        (),
    )
    with pytest.raises(Exception, match="for_2.0_only"):
        rb.pool_adapter("1.7")


# -- the record -> truth mapping and the all-pool bank ---------------------------------------------------------------------


def _record(job_id, design, row):
    """A synthetic RESULTS record in exam-rb's layout carrying ``row``'s 22 truths."""
    modes = [row["first_mode_hz"], *(row[f"modes_hz_{i}"] for i in range(1, 11))]
    modes += [modes[-1] + 10.0 * k for k in range(1, 38)]  # 48 modes in all
    return {
        "job_id": job_id,
        "status": "OK",
        "outputs": {
            **{k: row[k] for k in train.DECK_OUTPUTS if k != "cad_mass_kg"},
            "cad_mass_kg": mass.cad_mass_kg(design),
        },
        "auxiliary": {
            "modes_hz": modes,
            "tip_static_displacement_mm_per_n": [
                row["tip_static_displacement_mm_per_n_0"],
                row["tip_static_displacement_mm_per_n_1"],
                0.125,
            ],
            "patch": {
                "2.0": {
                    "dynamic_frequency_hz": row["patch_dynamic_frequency_hz"],
                    "dynamic_max_principal_at_vm_frequency": row[
                        "patch_dynamic_max_principal_at_vm_frequency"
                    ],
                    "static_max_principal": row["patch_static_max_principal"],
                }
            },
        },
    }


def test_the_truths_come_from_the_record_keys():
    row = _good_row()
    assert kit.truths_from_record(_record("job-1", _DESIGN, row)) == row
    bad = _record("job-1", _DESIGN, row)
    bad["status"] = "REFERENCE_INVALID"
    with pytest.raises(kit.SealedPackRefused, match="record_not_ok"):
        kit.truths_from_record(bad)
    for path in (
        ("auxiliary", "modes_hz"),
        ("auxiliary", "patch"),
        ("outputs", "first_mode_hz"),
    ):
        bad = _record("job-1", _DESIGN, row)
        del bad[path[0]][path[1]]
        with pytest.raises(kit.SealedPackRefused, match="record_value_missing"):
            kit.truths_from_record(bad)
    bad = _record("job-1", _DESIGN, row)
    bad["auxiliary"]["modes_hz"][3] = float("nan")
    with pytest.raises(kit.SealedPackRefused, match="record_value_missing"):
        kit.truths_from_record(bad)


_SECOND = {**_DESIGN, "length_mm": 200.0, "fillet_radius_mm": 2.0}


def _batch(designs=(_DESIGN, _SECOND)):
    rows = [_good_row(), {**_good_row(), "first_mode_hz": 90.0}]
    document = {
        "schema": kit.DOCUMENT_SCHEMA,
        "designs": [
            {
                "design_id": f"d{i}",
                "class": "H-RB1",
                "job_id": f"job-{i}",
                "inputs": dict(d),
            }
            for i, d in enumerate(designs)
        ],
    }
    records = [_record(f"job-{i}", d, rows[i]) for i, d in enumerate(designs)]
    fixed = {k: _DESIGN[k] for k in rb.condition_names()}
    spec = pool_grader.build_accuracy_target(
        target_id="t-1",
        conditions={"target_id": "t-1", "fixed": fixed},
        outputs=train.GRADED_OUTPUTS,
        u=dict.fromkeys(train.GRADED_OUTPUTS, 1.0),
        box=[(0.0, 1000.0)] * len(rb.DESIGN_NAMES),
        designs=[[d[n] for n in rb.DESIGN_NAMES] for d in designs],
        truths=rows[: len(designs)],
    )
    material = {
        "schema": pool_version.MATERIAL_SCHEMA,
        "kind": "f08",
        "version": "2.0",
        "input_names": list(train.INPUT_NAMES),
        "design_names": list(rb.DESIGN_NAMES),
        "input_dtype": "float32",
        "set_digest": "sha256:" + "0" * 64,
        "sets": [[pool_grader.dump_pool(spec)]],
    }
    return document, records, material


def test_the_bank_is_all_pool_rows_with_no_reference():
    document, records, material = _batch()
    bank = kit.sealed_bank(document, records, version="2.0", pool=material)
    assert set(bank["cohorts"]) == {pool_exam.POOL_COHORT}
    assert len(bank["case_ids"]) == 2
    assert bank["inputs"].shape == (2, 12) and bank["inputs"].dtype == np.float32
    assert bank["references"].shape == (2, 22) and np.isnan(bank["references"]).all()
    assert bank["reference_present"] == (False, False)
    assert bank["pool"] is material
    assert rb.is_pool_bank(bank)
    assert type(bank["solver_evidence"]) is bytes
    # the definition over ZERO sealed rows (PoolVariant strips the pool) and its validation
    definition = rb.definition(bank=pool_version.strip_pool(bank), train_raw=b"")
    assert rb.validate_definition(definition) is definition
    with pytest.raises(rb.Refused, match="f08_20_definition"):
        rb.validate_definition({**definition, "pool_only": False})


def test_a_bank_with_a_sealed_row_or_no_pool_row_is_not_a_2_0_bank():
    document, records, material = _batch()
    bank = kit.sealed_bank(document, records, version="2.0", pool=material)
    mixed = dict(bank, cohorts=(bank["cohorts"][0], "decision_sealed_grid"))
    assert not rb.is_pool_bank(mixed)
    assert not rb.is_pool_bank(dict(bank, cohorts=()))
    assert not rb.is_pool_bank(None)
    with pytest.raises(rb.Refused, match="bank_holds_a_sealed_row"):
        rb.definition(bank=dict(bank, cohorts=("decision_sealed_grid",)), train_raw=b"")


@pytest.mark.parametrize(
    "mutate,code",
    [
        (
            lambda d, r, m: d["designs"].append(dict(d["designs"][0])),
            "duplicate_design",
        ),
        (lambda d, r, m: d["designs"][1].update(job_id="job-0"), "duplicate_job"),
        (lambda d, r, m: r.pop(), "production_job_missing"),
        (lambda d, r, m: r.append(copy.deepcopy(r[0])), "job_typed_twice"),
        (lambda d, r, m: r[0].update(status="FAILED_INFRA"), "record_not_ok"),
        (
            lambda d, r, m: r[0]["outputs"].update(cad_mass_kg=1.0),
            "mass_not_closed_form",
        ),
        (
            lambda d, r, m: d["designs"][0]["inputs"].update(alloy_index=3.0),
            "alloy_index",
        ),
        (
            lambda d, r, m: d["designs"][0]["inputs"].pop("damping_ratio"),
            "design_inputs",
        ),
        (lambda d, r, m: d.update(schema="other"), "document_malformed"),
        (
            lambda d, r, m: r[1]["auxiliary"]["patch"]["2.0"].update(
                static_max_principal=7.0
            ),
            "material_truth_differs_from_record",
        ),
    ],
)
def test_a_malformed_batch_refuses_the_whole_pack(mutate, code):
    document, records, material = _batch()
    mutate(document, records, material)
    with pytest.raises(kit.SealedPackRefused, match=code):
        kit.sealed_bank(document, records, version="2.0", pool=material)


def test_a_pool_design_without_its_record_refuses():
    document, records, material = _batch()
    document["designs"].pop()
    records.pop()
    with pytest.raises(kit.SealedPackRefused, match="pool_design_without_record"):
        kit.sealed_bank(document, records, version="2.0", pool=material)


def test_the_kit_refuses_another_version_or_no_material():
    document, records, material = _batch()
    with pytest.raises(kit.SealedPackRefused, match="sealed_version"):
        kit.sealed_bank(document, records, version="1.7", pool=material)
    with pytest.raises(kit.SealedPackRefused, match="pool_material_missing"):
        kit.sealed_bank(document, records, version="2.0", pool=None)


def test_the_f08_kit_delegates_2_0_with_one_line(monkeypatch):
    from carbon.challenge_kit import f08_sealed_pack

    seen = {}
    monkeypatch.setattr(
        kit, "sealed_bank", lambda *a, **k: seen.setdefault("call", (a, k))
    )
    f08_sealed_pack.sealed_bank({"d": 1}, [{"r": 1}], version="2.0", pool={"p": 1})
    assert seen["call"] == (
        ({"d": 1}, [{"r": 1}]),
        {"version": "2.0", "pool": {"p": 1}},
    )


# -- the pool-only pack pieces and the dispatch ---------------------------------------------------------------------------


def test_the_applied_pack_is_f08s_form_with_no_gate_of_its_own():
    from carbon.scoring import f08_sealed_dual_pack

    applied = rb.applied_pack(bank_rows=[])
    registered = f08_sealed_dual_pack.applied_pack()
    assert applied["hard_gates"] == []
    assert {k: v for k, v in applied.items() if k != "hard_gates"} == {
        k: v for k, v in registered.items() if k != "hard_gates"
    }
    with pytest.raises(rb.Refused, match="bank_holds_a_sealed_row"):
        rb.applied_pack(bank_rows=[{"cohort": "decision_sealed_grid"}])
    with pytest.raises(rb.Refused, match="has_no_base_measure"):
        rb.measure()


@pytest.mark.parametrize(
    "config",
    [
        None,
        {},
        {"pool_versions": ["a"]},
        {"pool_versions": ["a", ""]},
        {"pool_versions": ["a", "b"], "subset_repeat": {}},
    ],
)
def test_a_malformed_dispatch_config_refuses(config):
    with pytest.raises(ValueError):
        rb.dispatch(config)


def test_an_official_2_0_answer_grades_on_a_22_output_target(monkeypatch):
    # exam-rb 07:18:16Z: the derive adds cad_mass_kg, which an accuracy target does not grade; without the companion
    # registration every 2.0 answer would be invalid on its target
    monkeypatch.setattr(rb, "POOL_VERSIONS", {})
    monkeypatch.setattr(pool_version, "_BINDINGS", {})
    monkeypatch.setattr(pool_grader, "_COMPANIONS", set())
    derived = rb.derive_answer(_DESIGN, _raw(_good_row()))
    assert pool_grader.graded_answer(derived, train.GRADED_OUTPUTS) is None
    rb.dispatch({"pool_versions": ["rb20-pool-sealed-v1", "rb20-pool-set"]})
    binding = pool_version.official_binding("f08", "2.0")
    official = binding.derive(_DESIGN, _raw(_good_row()))
    assert official == derived
    assert pool_grader.graded_answer(official, train.GRADED_OUTPUTS) == _good_row()
    # the menus' objective still reads the mass from the same answer
    assert official["cad_mass_kg"] == mass.cad_mass_kg(_DESIGN)


def test_the_dispatch_registers_2_0_and_nothing_else(monkeypatch):
    monkeypatch.setattr(rb, "POOL_VERSIONS", {})
    monkeypatch.setattr(pool_version, "_BINDINGS", {})
    monkeypatch.setattr(pool_grader, "_COMPANIONS", set())
    assert rb.sealed_adapter("2.0") is None  # nothing grades 2.0 before its entry
    spec = rb.dispatch({"pool_versions": ["rb20-pool-sealed-v1", "rb20-pool-set"]})
    assert (spec["challenge"], spec["version"]) == ("f08-ribbed-bracket", "2.0")
    assert rb.POOL_VERSIONS == {"2.0": ("rb20-pool-sealed-v1", "rb20-pool-set")}
    assert pool_version._BINDINGS == {("f08", "2.0"): rb.official_binding}
    adapter = rb.sealed_adapter("2.0")
    assert (adapter.VERSION, adapter.EVALUATION_VERSION, adapter.CASE_ID) == (
        "2.0",
        "rb20-pool-sealed-v1",
        "rb20-pool-set",
    )
    assert rb.sealed_adapter("1.7") is None
    with pytest.raises(ValueError, match="already dispatched"):
        rb.dispatch({"pool_versions": ["other", "rb20-pool-set"]})
    binding = pool_version.official_binding("f08", "2.0")
    assert binding.physics_gates.gate_names == rb.GATES
    assert binding.design_names == rb.DESIGN_NAMES


def test_the_producer_identity_is_2_0s_own_files():
    assert set(rb.FILES) == {
        "f08_20_dual_pack.py",
        "f08_20_mass.py",
        "sealed_pack_writer.py",
    }
    assert rb.producer_digest().startswith("sha256:")


#: The live 1.x producer files B2 must not move (LF sha256), as at main bdffc434.
_LIVE = {
    "carbon/scoring/sealed_batch_source.py": "438aae83e7d0231e1feeecec1e8c4248d23899164e722e1e01450228a862ec3f",
    "carbon/scoring/pool_adapters.py": "dae8469be734d7ee866a5b17b8a5794e839b108edcc32a30baf9ac1fd9def004",
    "carbon/scoring/f08_sealed_dual_pack.py": "5f19c9145f28cd02749882271f5931f8f05ece53a157414258bc673d5bb0f72a",
    "carbon/scoring/f08_dual_pack.py": "5a1238e81d28df0ee65743a548de253101d3bfa17214f5aea65474f4e5d5139c",
}


@pytest.mark.parametrize("path", sorted(_LIVE))
def test_the_live_1x_producer_files_are_unchanged(path):
    raw = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == _LIVE[path]


def test_no_2_0_value_is_a_nan_or_a_default():
    assert all(math.isfinite(v) and v > 0 for v in mass.RHO_KG_M3)
    assert rb.BAND_HZ[0] < rb.BAND_HZ[1]
