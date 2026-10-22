"""Cooling 1.3: scoring on decoded rows equals Cooling's own scoring.

Complements test_cooling_1_3_encoding: encoded references measured through the
1.3 adapter equal the native references measured through Cooling's adapter; a
non-finite encoded row fails the native finite gate as a native one does; a
tampered encoded TRAIN fails its pin."""

from __future__ import annotations

import json

import numpy as np
import pytest
from test_cooling_dual_pack import cooling, physical, physical_pack

from carbon.challenge_kit import physical_public_train as train
from carbon.cold_plate import output_encoding as enc
from carbon.scoring import cooling_encoded_dual_pack as encoded_pack


@pytest.fixture(scope="module")
def case():
    bank = physical_pack.development_bank(cooling.CHALLENGE, cooling.VERSION)
    public = physical_pack.public_roles(cooling.CHALLENGE, cooling.VERSION)
    names = train.numeric_interface_document(cooling.CHALLENGE)["input_names"]
    return {
        "bank": bank,
        "public": public,
        "names": names,
        "rows": physical.bank_rows(bank, names),
        "limits": json.loads(public["important_limit_definition"]),
        "objective": json.loads(public["design_objective"]),
    }


def _definition(module, case):
    return {
        **module.definition(bank=case["bank"], train_raw=case["public"]["train"]),
        "producer_digest": module.producer_digest(),
    }


def _measure(module, case, outputs):
    return module.measure(
        bank_rows=case["rows"],
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=_definition(module, case),
        limits=case["limits"],
        objective=case["objective"],
        train_raw=case["public"]["train"],
        names=case["names"],
    )


def _native(case):
    return [list(map(float, row)) for row in case["bank"]["references"]]


def test_encoded_references_measure_as_the_native_references_do(case):
    native = _native(case)
    raw = [list(map(float, row)) for row in enc.encode_targets(np.array(native))]
    plain = _measure(cooling, case, native)
    mapped = _measure(encoded_pack, case, raw)
    assert plain["A"] == 1.0 and plain["gate_failed_cases"] == []
    # Decoding the encoded references returns them to rounding (the reference
    # peaks sit above the gate's floor), so the measurement is the same.
    assert mapped["gates"] == plain["gates"] and mapped["pick"] == plain["pick"]
    assert mapped["A"] == pytest.approx(plain["A"], abs=1e-9)
    for name, value in plain["components"].items():
        assert mapped["components"][name] == pytest.approx(value, abs=1e-9)


def test_a_non_finite_encoded_row_fails_the_native_gate_as_a_native_one_does(case):
    native = _native(case)
    raw = [list(map(float, row)) for row in enc.encode_targets(np.array(native))]
    native[0][3] = float("nan")
    raw[0][3] = float("nan")
    plain = _measure(cooling, case, native)
    mapped = _measure(encoded_pack, case, raw)
    assert plain["gates"]["native_cold_plate"] is False
    assert mapped["gates"] == plain["gates"]
    assert mapped["gate_failed_cases"] == plain["gate_failed_cases"]


def test_a_tampered_encoded_train_fails_its_pin(monkeypatch):
    cid = "chip-cold-plate"
    monkeypatch.setitem(
        train._ENCODED_PINNED, cid, ("0" * 64, train._ENCODED_PINNED[cid][1])
    )
    with pytest.raises(ValueError, match="identity differs"):
        train.load_public_train(cid, "1.3")
