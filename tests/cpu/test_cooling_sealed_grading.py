"""Cooling's adapter grades a sealed exam batch (Validator, 2026-10-20,
cooling-dual-sealed-batch-16-v2): one 4 x 4 grid in one cohort, so A is the
minimum over all 16 cells and the worst geometry (no boundary reduction), its
grid gate is `complete_grid_common_mask`, its reference evidence is pinned by
sha256, and D is the development bank's decision unchanged. The development
bank's definition and grading are unchanged."""

from __future__ import annotations

import copy
import hashlib
import json
import random

import pytest
from test_cooling_hidden_family import document, ok_record

from carbon.challenge_kit import cooling_sealed_pack as sealed
from carbon.challenge_kit import physical_pack
from carbon.cold_plate_exam import population
from carbon.scoring import cooling_dual_measurement as cdm
from carbon.scoring import cooling_dual_pack as adapter
from carbon.scoring import physical_dual_pack as physical

PUBLIC = physical_pack.public_roles(adapter.CHALLENGE, "1.1")
NAMES = physical.input_names(adapter)


def _sealed_bank(probes=False):
    """Data Collection's fixture grid, its synthetic (non-production) outputs
    set so every design is feasible and each has its own hydraulic power."""
    doc = document(population.draw(random.Random(2), 16)[0])
    records = []
    for i, case in enumerate(doc["cases"]):
        record = ok_record(case["case_id"], case["inputs"], peak=60.0)
        record["outputs"]["pressure_drop_pa"] = 40.0 + 3.0 * i
        records.append(record)
    return sealed.sealed_bank(doc, records, probes=probes)


def _measure(bank, outputs, definition=None):
    definition = definition or adapter.definition(bank=bank, train_raw=PUBLIC["train"])
    return adapter.measure(
        bank_rows=physical.bank_rows(bank, NAMES),
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=definition,
        limits=json.loads(PUBLIC["important_limit_definition"]),
        objective=json.loads(PUBLIC["design_objective"]),
        train_raw=PUBLIC["train"],
        names=NAMES,
    )


def _truth(bank):
    return [[float(v) for v in row] for row in bank["references"]]


def test_a_sealed_definition_registers_its_grid_and_its_evidence():
    bank = _sealed_bank()
    definition = adapter.definition(bank=bank, train_raw=PUBLIC["train"])
    adapter.validate_definition(definition)
    assert definition["bank_kind"] == "sealed_batch"
    assert definition["reductions"] == ["all16", "worst_geometry"]
    assert definition["cohort_counts"] == {"decision_sealed_grid": 16}
    assert definition["reference_evidence_sha256"] == (
        "sha256:" + hashlib.sha256(bank["solver_evidence"]).hexdigest()
    )
    # The method pins are kept.
    for pin in ("source_script_sha256", "study_config_sha256", "source_replay_sha256"):
        assert definition[pin].startswith("sha256:")
    assert cdm.gates_for(definition) == cdm.SEALED_GATES


def test_the_development_definition_is_unchanged():
    bank = physical_pack.development_bank(adapter.CHALLENGE, "1.1")
    definition = adapter.definition(bank=bank, train_raw=PUBLIC["train"])
    assert "bank_kind" not in definition
    assert "reference_evidence_sha256" not in definition
    assert definition["reductions"] == ["all48", "worst_geometry", "boundary"]
    assert definition["cohort_counts"] == cdm.COHORT_COUNTS
    assert cdm.gates_for(definition) == cdm.GATES


def test_a_model_equal_to_the_sealed_references_earns_full_a_and_d():
    bank = _sealed_bank()
    measured = _measure(bank, _truth(bank))
    assert measured["A"] == 1.0 and measured["D"] == 1.0
    assert measured["gates"] == {
        "native_cold_plate": True,
        "complete_grid_common_mask": True,
        "selected_design_verified_feasible": True,
    }
    assert sorted(measured["components"]) == sorted(
        f"{c}_{r}"
        for c in ("peak", "profile", "pressure")
        for r in ("all16", "worst_geometry")
    )
    assert measured["decision_outcome"] == "VERIFIED_FEASIBLE"


def test_a_is_the_minimum_over_all16_and_the_worst_geometry():
    bank = _sealed_bank()
    outputs = _truth(bank)
    # Shift one design's peaks: its geometry becomes the worst one.
    rows = bank["reference_records"]
    for i, record in enumerate(rows):
        if record["design_id"] == "d3":
            outputs[i][0] += 2.0
    measured = _measure(bank, outputs)
    components = measured["components"]
    assert components["peak_worst_geometry"] > components["peak_all16"] > 0
    assert measured["A"] == min(1 / (1 + e) for e in components.values())


def test_a_pick_the_references_beat_has_regret():
    bank = _sealed_bank()
    outputs = _truth(bank)
    best = _measure(bank, outputs)["pick"]
    # Predict the true best design's pressure drop far above the limit.
    for i, record in enumerate(bank["reference_records"]):
        if record["design_id"] == best:
            outputs[i][31] *= 1.0e4
    measured = _measure(bank, outputs)
    assert measured["pick"] != best
    assert measured["regret_w"] > 0 and 0 < measured["D"] < 1


def test_a_development_definition_never_grades_a_sealed_bank():
    bank = _sealed_bank()
    development = adapter.definition(
        bank=physical_pack.development_bank(adapter.CHALLENGE, "1.1"),
        train_raw=PUBLIC["train"],
    )
    with pytest.raises(adapter.Refused) as refused:
        _measure(bank, _truth(bank), development)
    assert refused.value.code == "cooling_bank_cohort"


def test_a_malformed_evidence_pin_refuses():
    bank = _sealed_bank()
    definition = copy.deepcopy(adapter.definition(bank=bank, train_raw=PUBLIC["train"]))
    definition["reference_evidence_sha256"] = "not-a-digest"
    with pytest.raises(adapter.Refused):
        adapter.validate_definition(definition)
    definition = copy.deepcopy(adapter.definition(bank=bank, train_raw=PUBLIC["train"]))
    definition["reductions"] = ["all48", "worst_geometry", "boundary"]
    with pytest.raises(adapter.Refused):
        adapter.validate_definition(definition)


def test_the_sealed_pack_registers_its_own_gate_keys():
    bank = _sealed_bank()
    definition = adapter.definition(bank=bank, train_raw=PUBLIC["train"])
    pack = adapter.applied_pack(
        bank_rows=physical.bank_rows(bank, NAMES),
        definition=definition,
        limits=json.loads(PUBLIC["important_limit_definition"]),
        objective=json.loads(PUBLIC["design_objective"]),
        train_raw=PUBLIC["train"],
        names=NAMES,
    )
    assert pack["hard_gates"] == list(cdm.SEALED_GATES)


def test_the_sealed_adapter_serves_exactly_cooling_1_1_to_1_3():
    for version in ("1.1", "1.2", "1.3"):
        chosen = adapter.sealed_adapter(version)
        assert chosen.EVALUATION_VERSION == "cooling-dual-sealed-batch-16-v2"
        assert chosen.VERSION == version
    for version in ("1.0", "1.4", None):
        assert adapter.sealed_adapter(version) is None


def test_the_sealed_exam_is_graded_under_every_served_cooling_version():
    from carbon.challenge_kit import physical_pack
    from carbon.scoring import cooling_dual_pack as cdp

    assert set(cdp.SEALED_VERSIONS) == {"1.1", "1.2", "1.3"}
    assert len(set(cdp.SEALED_VERSIONS.values())) == 1
    # 1.3 is 1.2 plus allowlist v7: the same exam, so its train and interface
    # roles must equal 1.2's wherever 1.3 is served.
    try:
        newer = physical_pack.public_roles(cdp.CHALLENGE, "1.3")
    except ValueError:
        pytest.skip("Cooling 1.3 is not served at this base")
    older = physical_pack.public_roles(cdp.CHALLENGE, "1.2")
    assert newer["train"] == older["train"]
    assert newer["interface"] == older["interface"]


def _shift_cell(outputs, cell, degrees):
    """One cell whole temperature profile (and peak) moved by ``degrees``."""
    outputs = copy.deepcopy(outputs)
    for k in range(0, 31):
        outputs[cell][k] += degrees
    return outputs


def test_the_sealed_definition_registers_the_critical_block():
    bank = _sealed_bank()
    block = adapter.definition(bank=bank, train_raw=PUBLIC["train"])["critical"]
    assert block["rule"] == "D=min(V,C)"
    assert {c["quantity"]: c["scale"] for c in block["components"]} == {
        "die_margin_c": 1.0,
        "hydraulic_margin_w": 0.025,
    }
    assert block["objective"]["scale"] == 0.025
    assert "critical" not in adapter.definition(
        bank=physical_pack.development_bank(adapter.CHALLENGE, "1.1"),
        train_raw=PUBLIC["train"],
    )


def test_a_right_pick_with_wrong_die_margins_scores_d_below_one():
    bank = _sealed_bank()
    truth = _truth(bank)
    exact = _measure(bank, truth)
    assert exact["D"] == 1.0 and exact["design_fidelity"]["C"] == 1.0
    skewed = _measure(bank, _shift_cell(truth, 0, 2.0))
    assert skewed["pick"] == exact["pick"] and skewed["regret_w"] == 0.0
    assert skewed["design_fidelity"]["C"] < 1.0
    assert skewed["D"] == skewed["design_fidelity"]["C"] < 1.0


def test_a_definition_without_the_critical_block_grades_value_only():
    bank = _sealed_bank()
    legacy = {
        k: v
        for k, v in adapter.definition(bank=bank, train_raw=PUBLIC["train"]).items()
        if k != "critical"
    }
    truth = _truth(bank)
    measured = _measure(bank, _shift_cell(truth, 0, 2.0), legacy)
    assert measured["D"] == 1.0 and "design_fidelity" not in measured


# --- the physics half ----------------------------------------------------------


def _model():
    from carbon.scoring import cooling_physics

    return cooling_physics.registered_model(PUBLIC["train"])


def _full(bank, cells, probe=None):
    """Predictions for every row in the delivered order: the cell predictions in
    the order the cells appear, the stand-in model (or ``probe``) at each probe."""
    probe = probe or _model()
    cells = iter(cells)
    return [
        (
            probe([float(r["inputs"][n]) for n in NAMES])
            if r["cohort"] == "probe_response"
            else list(map(float, next(cells, [0.0] * 32)))
        )
        for r in physical.bank_rows(bank, NAMES)
    ]


@pytest.fixture(scope="module")
def probed():
    bank = _sealed_bank(probes=True)
    return {
        "bank": bank,
        "definition": adapter.definition(bank=bank, train_raw=PUBLIC["train"]),
        "cells": _truth(sealed_cells(bank)),
    }


def sealed_cells(bank):
    from carbon.scoring import probe_design

    return probe_design.cells_only(bank)


def _pmeasure(probed, outputs, definition=None):
    return _measure(
        probed["bank"],
        outputs,
        definition=definition or probed["definition"],
    )


def test_the_probed_definition_registers_probes_and_the_physics_block(probed):
    definition = probed["definition"]
    adapter.validate_definition(definition)
    assert definition["probes"] == {"cohort": "probe_response", "rows": 4 * 21}
    block = definition["physics"]
    assert block["rule"] == "A=mean(A_acc,A_robust,A_law,A_response)"
    assert block["response"]["outputs"] == ["rise_c", "pressure_drop_pa"]
    assert {law["name"] for law in block["laws"]} >= {
        "inlet_shift_temperatures",
        "pressure_ignores_hotspot",
    }


def test_the_probes_are_private_unreferenced_rows_among_the_cells(probed):
    rows = physical.bank_rows(probed["bank"], NAMES)
    cohorts = [r["cohort"] for r in rows]
    assert cohorts.count("decision_sealed_grid") == 16 and len(rows) == 100
    # interleaved with the cells, never a suffix
    assert cohorts[:16] != ["decision_sealed_grid"] * 16
    assert cohorts[-16:] != ["decision_sealed_grid"] * 16
    probes = [r for r in rows if r["cohort"] == "probe_response"]
    assert len(probes) == 84 and all(r["reference"] is None for r in probes)
    assert probed["bank"]["reference_present"] == tuple(
        c == "decision_sealed_grid" for c in cohorts
    )


def test_a_model_with_the_registered_sensitivities_earns_full_response(probed):
    result = _pmeasure(probed, _full(probed["bank"], probed["cells"]))
    assert result["A_legs"]["A_response"] == pytest.approx(1.0, abs=1e-3)
    assert result["physics_half"]["sign_gate_failed"] == []
    assert result["A_legs"]["A_acc"] == 1.0
    assert result["gates"]["physics_laws"] is True


def test_a_model_that_ignores_the_inlet_loses_on_the_law_leg(probed):
    registered = _model()

    def stuck(point):
        moved = list(point)
        moved[4] = 40.0  # temperatures built at a fixed inlet
        row = registered(moved)
        return row

    good = _pmeasure(probed, _full(probed["bank"], probed["cells"]))
    bad = _pmeasure(probed, _full(probed["bank"], probed["cells"], probe=stuck))
    assert bad["A_legs"]["A_law"] < good["A_legs"]["A_law"] - 0.02


def test_a_pressure_drop_that_follows_the_hotspot_loses_on_the_law_leg(probed):
    registered = _model()

    def hotspot_pressure(point):
        row = registered(point)
        row[31] *= 1.0 + 0.5 * (point[6] - 2.0)
        return row

    good = _pmeasure(probed, _full(probed["bank"], probed["cells"]))
    bad = _pmeasure(
        probed, _full(probed["bank"], probed["cells"], probe=hotspot_pressure)
    )
    assert bad["A_legs"]["A_law"] < good["A_legs"]["A_law"] - 0.02


def test_a_wrong_flow_trend_loses_on_the_response_leg_and_fails_the_gate(probed):
    registered = _model()

    def flipped(point):
        moved = list(point)
        moved[3] = 1.25 + 2.0 - point[3]  # flow mirrored in its range
        return registered(moved)

    result = _pmeasure(probed, _full(probed["bank"], probed["cells"], probe=flipped))
    assert result["A_legs"]["A_response"] < 0.95
    assert result["gates"]["physics_laws"] is False
    assert any(
        "flow_lpm_per_kw" in item for item in result["physics_half"]["gate_failed_laws"]
    )


def test_a_peak_below_a_profile_segment_fails_the_law_gate(probed):
    cells = [list(r) for r in probed["cells"]]
    cells[0][0] = cells[0][5] - 1.0
    result = _pmeasure(probed, _full(probed["bank"], cells))
    assert result["gates"]["physics_laws"] is False
    assert "peak_above_profile" in result["physics_half"]["gate_failed_laws"]


def test_a_sealed_cooling_bank_is_graded_under_the_v2_version(probed):
    for version in ("1.1", "1.2", "1.3"):
        chosen = adapter.sealed_adapter(version)
        assert chosen.EVALUATION_VERSION == "cooling-dual-sealed-batch-16-v2"
