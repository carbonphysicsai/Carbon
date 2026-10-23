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


def test_the_sealed_table_is_1_1_and_1_2_and_1_3_is_the_decoding_adapter():
    from carbon.scoring import cooling_encoded_dual_pack as encoded

    assert set(adapter.SEALED_VERSIONS) == {"1.1", "1.2"}
    for version in ("1.1", "1.2"):
        chosen = adapter.sealed_adapter(version)
        assert chosen.EVALUATION_VERSION == "cooling-dual-sealed-batch-16-v2"
        assert chosen.VERSION == version
    # 1.3 changes the output interface: the one dispatch point here hands it to the
    # adapter that DECODES; no raw (non-decoding) adapter ever grades it.
    chosen = adapter.sealed_adapter("1.3")
    assert chosen.VERSION == "1.3" and chosen._module is encoded
    assert chosen.EVALUATION_VERSION == "cooling-dual-sealed-batch-16-v2"
    for version in ("1.0", "1.4", None):
        assert adapter.sealed_adapter(version) is None


def test_cooling_1_3_is_1_2_with_only_its_output_encoding_changed():
    """The guard for an encoding version: decode(TRAIN 1.3) is TRAIN 1.2 byte for byte,
    and the interfaces differ only by `output_encoding`."""
    import io

    import numpy as np

    from carbon.cold_plate.output_encoding import decode_flat

    try:
        newer = physical_pack.public_roles(adapter.CHALLENGE, "1.3")
    except ValueError:
        pytest.skip("Cooling 1.3 is not served at this base")
    older = physical_pack.public_roles(adapter.CHALLENGE, "1.2")
    with np.load(io.BytesIO(newer["train"]), allow_pickle=False) as one:
        encoded_inputs, encoded_targets = one["inputs"], one["targets"]
    with np.load(io.BytesIO(older["train"]), allow_pickle=False) as two:
        native_inputs, native_targets = two["inputs"], two["targets"]
    assert np.array_equal(encoded_inputs, native_inputs)
    decoded = np.array([decode_flat(row) for row in encoded_targets])
    assert np.array_equal(decoded, native_targets)  # byte-exact, not within a tolerance
    one_interface, two_interface = json.loads(newer["interface"]), json.loads(
        older["interface"]
    )
    changed = {
        key
        for key in set(one_interface) | set(two_interface)
        if one_interface.get(key) != two_interface.get(key)
    }
    assert "output_encoding" in changed
    # `transform` is the interface's prose for the same encoding (slot 0 holds e, slot
    # 31 holds q); nothing else differs: inputs, names, units, slices and shapes are 1.2's.
    assert changed <= {"output_encoding", "transform"}, changed
    assert "softplus" in one_interface["transform"]
    assert "softplus" not in two_interface["transform"]


def test_a_native_model_and_its_1_3_encoding_score_byte_identically_on_the_sealed_exam():
    from carbon.cold_plate.output_encoding import encode_targets
    from carbon.scoring import cooling_encoded_dual_pack as encoded

    bank = _sealed_bank()
    truth = _truth(bank)
    models = {
        "perfect": truth,
        # A fixed imperfect 1.2-native model: every output nudged by a case-wise amount.
        "nudged": [
            [v * (1.0 + 0.004 * ((i % 5) - 2)) for v in row]
            for i, row in enumerate(truth)
        ],
    }
    native = adapter.sealed_adapter("1.2")
    newer = encoded.sealed_adapter("1.3")
    rows = physical.bank_rows(bank, NAMES)
    for name, outputs in models.items():
        limits = json.loads(PUBLIC["important_limit_definition"])
        objective = json.loads(PUBLIC["design_objective"])
        definition = native.definition(bank=bank, train_raw=PUBLIC["train"])
        want = native.measure(
            bank_rows=rows,
            outputs=outputs,
            repeats=[outputs, outputs],
            definition=definition,
            limits=limits,
            objective=objective,
            train_raw=PUBLIC["train"],
            names=NAMES,
        )
        coded = encode_targets(outputs).tolist()
        definition_13 = newer.definition(bank=bank, train_raw=PUBLIC["train"])
        got = newer.measure(
            bank_rows=rows,
            outputs=coded,
            repeats=[coded, coded],
            definition=definition_13,
            limits=limits,
            objective=objective,
            train_raw=PUBLIC["train"],
            names=NAMES,
        )
        assert json.dumps(got, sort_keys=True, default=str) == json.dumps(
            want, sort_keys=True, default=str
        ), name
        assert definition_13["bank_kind"] == "sealed_batch"
    assert newer.EVALUATION_VERSION == native.EVALUATION_VERSION
    assert newer.VERSION == "1.3" and encoded.sealed_adapter("1.2") is None
