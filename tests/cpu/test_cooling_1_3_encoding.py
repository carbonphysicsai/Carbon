"""Cooling 1.3: the law-safe output encoding (Validator ruling
VALIDATOR_RULING_COOLING12_PEAK_GATE_20261022, finding G1).

A decoded row satisfies peak_bounds_profile and pressure_drop_positive by
construction; TRAIN is encoded once and pinned; practice and the receiver's
measurement decode before scoring; Cooling 1.0-1.2 identities (kit, TRAIN,
interface, producer) are unchanged."""

from __future__ import annotations

import numpy as np
import pytest

from carbon.challenge_kit import physical_public, physical_public_train
from carbon.cold_plate import exam
from carbon.cold_plate import output_encoding as enc

COOLING = "chip-cold-plate"


def _laws_hold(native):
    profile_max = max(native["profile_c"])
    return (
        native["peak_c"] >= profile_max - exam._ulp(profile_max)
        and native["pressure_drop_pa"] > 0
    )


def test_any_encoded_row_decodes_to_outputs_that_satisfy_both_laws():
    rng = np.random.default_rng(0)
    for row in rng.normal(scale=50.0, size=(500, 32)):
        assert _laws_hold(enc.decode_row(row))
    # Extreme raw slots still decode within the laws.
    for e, q in ((-1e3, -1e3), (1e3, 1e3), (0.0, 0.0)):
        row = np.zeros(32)
        row[0], row[31] = e, q
        native = enc.decode_row(row)
        assert native["peak_c"] >= max(native["profile_c"])
        assert native["pressure_drop_pa"] >= 0


def test_train_encoding_round_trips_exactly_and_passes_the_gates():
    native = physical_public_train.load_public_train(COOLING)["targets"]
    encoded = physical_public_train.load_public_train(COOLING, "1.3")["targets"]
    assert encoded.shape == native.shape
    for raw, row in zip(native, encoded, strict=True):
        decoded = enc.decode_flat(row)
        assert np.allclose(decoded, raw, rtol=1e-12, atol=1e-9)
        assert _laws_hold(enc.decode_row(row))


def test_the_encoded_train_is_the_pinned_derivation():
    raw, provenance = physical_public_train.derive_encoded_public_train(COOLING)
    loaded = physical_public_train.load_public_train(COOLING, "1.3")
    assert loaded["train"] == raw
    assert loaded["provenance"] == provenance
    assert provenance["encoding"] == enc.ENCODING


def test_1_2_identities_are_unchanged_and_1_3_differs():
    v12 = physical_public.construction_kit(COOLING, "1.2")
    v13 = physical_public.construction_kit(COOLING, "1.3")
    assert v12["train_digest"] == (
        "sha256:b8d7839dcbfc777aa8b506a18bb9fc9b216786cb0d3533df18e6fb76ca4ec3bf"
    )
    assert v12["interface_digest"] == (
        "sha256:0da0804b5bad5e628ed866350cafa8d90633d2550f3bbc32b387d95eed49bbd7"
    )
    assert "output_encoding" not in physical_public.interface_document(COOLING, "1.2")
    assert (
        physical_public.interface_document(COOLING, "1.3")["output_encoding"]
        == enc.ENCODING
    )
    assert v13["train_digest"] != v12["train_digest"]
    assert v13["interface_digest"] != v12["interface_digest"]


def test_1_3_scores_through_its_own_adapter_and_1_2_keeps_its_producer():
    from carbon.scoring import cooling_dual_pack, cooling_encoded_dual_pack
    from carbon.scoring.physical_adapters import _static

    choose = _static()[COOLING]
    assert choose("1.3") is cooling_encoded_dual_pack
    assert choose("1.2") is not cooling_encoded_dual_pack
    # Scoring v2 (D = min(V, C) and the physics half) adds its shared modules.
    assert cooling_dual_pack.FILES == (
        "cooling_dual_pack.py",
        "cooling_dual_measurement.py",
        "critical_fidelity.py",
        "design_fidelity.py",
        "physics_half.py",
        "probe_design.py",
        "cooling_physics.py",
    )
    assert "1.3" not in cooling_dual_pack.VERSIONS
    assert (
        cooling_encoded_dual_pack.producer_digest()
        != cooling_dual_pack.producer_digest()
    )
    rows = [list(np.linspace(40.0, 60.0, 32))]
    assert cooling_encoded_dual_pack._decoded(rows) == [enc.decode_flat(rows[0])]


def test_practice_decodes_an_encoded_row_and_leaves_a_native_one():
    from carbon.cold_plate.catalog_practice import _outputs

    slices = physical_public.interface_document(COOLING, "1.3")["target_slices"]
    row = [0.0] + [50.0] * 30 + [0.0]
    decoded = _outputs(row, slices, enc.ENCODING)
    assert decoded["peak_c"] > 50.0 and decoded["pressure_drop_pa"] > 0
    native = _outputs(row, slices)
    assert native["peak_c"] == 0.0 and native["pressure_drop_pa"] == 0.0
    with pytest.raises(ValueError, match="unknown Cooling output encoding"):
        _outputs(row, slices, "another")


def test_a_malformed_encoded_row_is_a_typed_gate_failure_not_an_exception():
    import json

    from carbon.challenge_kit import physical_pack
    from carbon.scoring import cooling_dual_pack, cooling_encoded_dual_pack
    from carbon.scoring import physical_dual_pack as physical

    bank = physical_pack.development_bank(COOLING, "1.2")
    public = physical_pack.public_roles(COOLING, "1.2")
    names = physical_public_train.numeric_interface_document(COOLING)["input_names"]
    rows = physical.bank_rows(bank, names)
    train = cooling_dual_pack._train_records(public["train"], names)
    native = np.asarray(cooling_dual_pack._baseline_outputs(rows, train))
    profile_max = native[:, 1:31].max(axis=1)
    native[:, 0] = np.maximum(native[:, 0], profile_max + 1.0)
    encoded = enc.encode_targets(native).tolist()
    definition = {
        **cooling_encoded_dual_pack.definition(bank=bank, train_raw=None),
        "producer_digest": cooling_encoded_dual_pack.producer_digest(),
    }

    def measure(outputs):
        return cooling_encoded_dual_pack.measure(
            bank_rows=rows,
            outputs=outputs,
            repeats=[outputs, outputs],
            definition=definition,
            limits=json.loads(public["important_limit_definition"]),
            objective=json.loads(public["design_objective"]),
            train_raw=None,
            names=names,
        )

    assert measure(encoded)["gates"]["native_cold_plate"] is True
    for bad in (
        encoded[0][:20],
        [*encoded[0][:31], float("nan")],
        [float("-inf")] + encoded[0][1:],
    ):
        result = measure([bad, *encoded[1:]])
        assert result["gates"]["native_cold_plate"] is False
