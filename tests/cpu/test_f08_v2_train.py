"""RB 2.0's 22-column interface and its public TRAIN derivation (`carbon.challenge_kit.f08_v2_train`).

Owner RB20-COLS (22 Nov 2026) widens the graded outputs from the MOUNT deck's 7 to 22 columns in exam-rb's order. The
TRAIN is re-assembled from public data by exam-rb's tool; this module derives and pins it and refuses until every ruling
and pin is set. Every row here is a SYNTHETIC fixture built in the test.
"""

from __future__ import annotations

import hashlib
import io
import json

import numpy as np
import pytest

from carbon.challenge_kit import f08_v2_train as rb

#: exam-rb's column order (RECEIPTS 22 Nov 01:58:57Z), by the public records' keys.
EXAM_RB_ORDER = (
    "worst_dynamic_mm_per_n",
    "static_tip_mm_per_n",
    "static_fillet_stress_mpa_per_n",
    "dynamic_fillet_stress_mpa_per_n",
    "first_mode_hz",
    "worst_dynamic_base_mm_per_g",
    "dynamic_fillet_stress_base_mpa_per_g",
    *(f"modes_hz[{i}]" for i in range(1, 11)),
    "patch.dynamic_frequency_hz",
    "patch.dynamic_max_principal_at_vm_frequency",
    "patch.static_max_principal",
    "tip_static_displacement_mm_per_n[0]",
    "tip_static_displacement_mm_per_n[1]",
)


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _design(i):
    inputs = {name: 1.0 + 0.001 * i + 0.01 * k for k, name in enumerate(rb.INPUT_NAMES)}
    inputs["alloy_index"] = float(i % 3)
    outputs = {key: 10.0 * (k + 1) + 0.5 * i for k, key in enumerate(EXAM_RB_ORDER)}
    outputs["cad_mass_kg"] = 0.25 + 0.001 * i
    return inputs, outputs


def _source(rows=None, mutate=None):
    rows = [_design(i) for i in range(rb.ROWS)] if rows is None else rows
    if mutate is not None:
        rows = [mutate(i, x, y) for i, (x, y) in enumerate(rows)]
    keyed = sorted(
        (
            hashlib.sha256(_canonical({k: float(v) for k, v in x.items()})).hexdigest(),
            x,
            y,
        )
        for x, y in rows
    )
    lines = [
        _canonical({"case_id": f"train-{i:04d}", "inputs": x, "outputs": y})
        for i, (_, x, y) in enumerate(keyed, 1)
    ]
    return b"\n".join(lines) + b"\n"


def test_the_graded_outputs_are_exam_rb_s_22_columns_in_order_under_identifier_names():
    assert len(rb.GRADED_OUTPUTS) == 22
    assert tuple(rb.SOURCE_KEYS[k] for k in rb.GRADED_OUTPUTS) == EXAM_RB_ORDER
    assert rb.GRADED_OUTPUTS[:7] == tuple(
        k for k in rb.DECK_OUTPUTS if k not in rb.EXACT_OUTPUTS
    )
    assert (
        rb.GRADED_OUTPUTS[7] == "modes_hz_1" and rb.GRADED_OUTPUTS[16] == "modes_hz_10"
    )
    assert "cad_mass_kg" not in rb.GRADED_OUTPUTS
    document = rb.interface_document()
    assert document["target_names"] == list(rb.GRADED_OUTPUTS)
    assert document["target_source_keys"] == list(EXAM_RB_ORDER)
    assert document["exact_outputs"] == ["cad_mass_kg"]


def test_the_derived_train_is_240_by_12_and_240_by_22_in_interface_order():
    source = _source()
    raw, provenance = rb.derive_public_train(source)
    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        x, y = data["inputs"], data["targets"]
    assert x.shape == (240, 12) and y.shape == (240, 22)
    assert x.dtype == np.float32 and y.dtype == np.float32
    first = json.loads(source.split(b"\n")[0])
    assert y[0].tolist() == pytest.approx(
        [first["outputs"][key] for key in EXAM_RB_ORDER], rel=1e-6
    )
    assert provenance["case_ids"][0] == "train-0001"
    assert provenance["aux_sha256"] == "sha256:" + rb.AUX_SHA256
    # deterministic bytes
    assert rb.derive_public_train(source)[0] == raw


def _drop(key):
    def change(i, x, y):
        return x, {k: v for k, v in y.items() if k != key}

    return change


@pytest.mark.parametrize(
    "mutate",
    [
        _drop("cad_mass_kg"),
        _drop("modes_hz[10]"),
        _drop("patch.static_max_principal"),
        lambda i, x, y: (x, {**y, "modes_hz[11]": 1.0}),
        lambda i, x, y: (x, {k: y[k] for k in (*rb.DECK_OUTPUTS,)}),  # a slice-1 row
        lambda i, x, y: ({**x, "alloy_index": 3.0}, y),
        lambda i, x, y: (x, {**y, "first_mode_hz": "1"}),
        lambda i, x, y: (x, {**y, "first_mode_hz": True}),
    ],
)
def test_a_malformed_row_refuses(mutate):
    with pytest.raises(ValueError):
        rb.derive_public_train(_source(mutate=mutate))


def test_order_count_and_duplicates_refuse():
    source = _source()
    lines = source.split(b"\n")[:-1]
    with pytest.raises(ValueError):
        rb.derive_public_train(b"\n".join(lines[:-1]) + b"\n")  # 239 rows
    swapped = [lines[1], lines[0], *lines[2:]]
    with pytest.raises(ValueError):
        rb.derive_public_train(b"\n".join(swapped) + b"\n")
    with pytest.raises(ValueError):
        rb.derive_public_train(source.replace(b"\n", b"\r\n"))
    rows = [_design(i) for i in range(rb.ROWS - 1)] + [_design(0)]
    with pytest.raises(ValueError):
        rb.derive_public_train(_source(rows))


def test_it_refuses_until_every_ruling_and_pin_is_set():
    assert all(value is None for value in rb.RULINGS.values())
    assert set(rb.RULINGS) == {
        "graded_outputs",
        "train_of_record",
        "mesh_statement",
        "interface_order",
        "new_output_units",
    }
    assert None in (rb.SOURCE_SHA256, rb.TRAIN_SHA256, rb.PROVENANCE_SHA256)
    with pytest.raises(ValueError, match="HUMAN_INPUT"):
        rb.load_public_train()
    with pytest.raises(ValueError, match="unknown"):
        rb.load_public_train("1.7")


def test_the_two_patch_stress_units_are_not_invented():
    assert rb.OUTPUT_UNITS["patch_dynamic_max_principal_at_vm_frequency"] is None
    assert rb.OUTPUT_UNITS["patch_static_max_principal"] is None
    assert all(
        rb.OUTPUT_UNITS[k] is not None
        for k in rb.GRADED_OUTPUTS
        if not k.startswith("patch_") or k == "patch_dynamic_frequency_hz"
    )
