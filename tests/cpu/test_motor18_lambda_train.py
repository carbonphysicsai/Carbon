"""Motor 1.8's FRESH lambda TRAIN (owner all-in 7 Nov; Carbon Validator-B ad947355 section 1): every row from the
record-now route, TRAIN 150 ids kept with torque byte-equal (else STOP), added rows ordered by inputs, 240 targets =
torque_nm[60] + phase_flux_linkage_wb A/B/C [60 each]. Synthetic flux linkage only (no Carbon truth); the production
table stays unfrozen (every pin None), so loading it refuses."""

from __future__ import annotations

import dataclasses
import hashlib
import json

import numpy as np
import pytest

from carbon.challenge_kit import physical_public_train as ppt
from carbon.challenge_kit import version_registry
from carbon.motor import domain

MOTOR = "electric-motor-magnetics"
NAME = "motor-dev-train-1p8-v1"
STEPS = domain.ANGLE_STEPS


def _native():
    with open(ppt.motor.TRAIN_PATH, "rb") as handle:
        return [json.loads(line) for line in handle.read().splitlines()]


def _lam(seed):
    return {
        p: [0.01 * (seed + 1) * (k + 1 + i) for k in range(STEPS)]
        for i, p in enumerate("ABC")
    }


def _resolve(row, i):
    """A record-now re-solve of a native TRAIN row: same id, inputs and torque, plus lambda + custody-only extras."""
    return {
        "schema": row["schema"],
        "case_id": row["case_id"],
        "batch": "m18-train-resolve-s00",
        "run": "custody-run",
        "status": "OK",
        "kind": "ordinary",
        "inputs": dict(row["inputs"]),
        "outputs": {"torque_nm": list(row["outputs"]["torque_nm"])},
        "record_now": {
            "schema": "x",
            "phase_flux_linkage_wb": _lam(i),
            "coil_a_integral_wbm": [[1.0]],
            "magnet_min_b_t": [0.5],
        },
        "runner": {"name": "run_batch_record_now"},
        "image": "carbon-motor-reference:record-now",
    }


def _added(i, cid=None):
    inputs = dict(domain.NOMINAL)
    inputs["airgap_mm"] = inputs["airgap_mm"] + 0.0013 * (i + 1)
    return {
        "schema": "carbon.motor.reference-record.v1",
        "case_id": cid or f"pool-s6100-c{i:02d}",
        "status": "OK",
        "inputs": inputs,
        "outputs": {"torque_nm": [5.0 + 0.01 * k for k in range(STEPS)]},
        "record_now": {"phase_flux_linkage_wb": _lam(100 + i)},
    }


def _records(n_added=3, pilot=2):
    rows = [_resolve(r, i) for i, r in enumerate(_native())]
    rows += [_added(50 + j, cid=f"train-{150 + j:04d}") for j in range(pilot)]
    rows += [_added(i) for i in range(n_added)]
    return rows


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    table = {k: dict(v) for k, v in ppt.FRESH_LAMBDA.items()}
    monkeypatch.setattr(ppt, "FRESH_LAMBDA", table)
    monkeypatch.setattr(ppt, "_EXTENDED_DATA", tmp_path)

    def freeze(records):
        source = ppt.assemble_motor18_source(records)
        raw, prov = ppt.derive_motor18_public_train(NAME, source)
        prov_raw = (json.dumps(prov, indent=1, sort_keys=True) + "\n").encode()
        for suffix, data in (
            (".source.jsonl", source),
            (".npz", raw),
            (".provenance.json", prov_raw),
        ):
            (tmp_path / f"{NAME}{suffix}").write_bytes(data)
        table[NAME].update(
            rows=len(prov["case_ids"]),
            source_sha256=hashlib.sha256(source).hexdigest(),
            train_sha256=hashlib.sha256(raw).hexdigest(),
            provenance_sha256=hashlib.sha256(prov_raw).hexdigest(),
        )
        return source

    return freeze


def test_the_production_motor18_train_is_not_frozen_and_refuses():
    assert ppt.FRESH_LAMBDA[NAME]["train_sha256"] is None
    with pytest.raises(ValueError, match="not frozen yet"):
        ppt.load_extended_train(NAME, MOTOR)


def test_interface_is_torque_then_lambda_abc_240_wide():
    d = ppt.motor18_interface_document()
    assert d["target_slices"] == {
        "torque_nm": [0, 60],
        "phase_flux_linkage_wb_A": [60, 120],
        "phase_flux_linkage_wb_B": [120, 180],
        "phase_flux_linkage_wb_C": [180, 240],
    }
    assert d["target_units"]["phase_flux_linkage_wb_A"] == "weber"
    assert d != ppt.numeric_interface_document(MOTOR)


def test_roundtrip_through_a_registered_version(frozen, monkeypatch):
    source = frozen(_records())
    entry = version_registry.entry(MOTOR, "1.5")
    monkeypatch.setattr(
        version_registry, "find", lambda c, v: dataclasses.replace(entry, train=NAME)
    )
    got = ppt.load_public_train(MOTOR, "1.5")
    native = ppt.load_public_train(MOTOR)
    assert got["inputs"].shape == (155, 8) and got["targets"].shape == (155, 240)
    assert np.array_equal(got["targets"][:150, :60], native["targets"])
    assert np.array_equal(got["inputs"][:150], native["inputs"])
    assert got["targets"][0, 60] == pytest.approx(0.01) and got["targets"][
        0, 180
    ] == pytest.approx(0.01 * 3)
    assert got["case_ids"] == tuple(f"train-{i:04d}" for i in range(155))
    rows = [json.loads(line) for line in source.splitlines()]
    for row in rows:
        assert set(row) <= {
            "schema",
            "case_id",
            "kind",
            "status",
            "inputs",
            "outputs",
            "options",
            "image",
            "runner",
        }
        assert set(row["outputs"]) == {"torque_nm", "phase_flux_linkage_wb"}
    text = source.decode()
    assert (
        "pool-s6100" not in text
        and "custody-run" not in text
        and "coil_a" not in text
        and "magnet_min" not in text
    )


def test_added_rows_are_ordered_by_inputs_after_the_kept_ids():
    a = ppt.assemble_motor18_source(_records())
    recs = _records()
    b = ppt.assemble_motor18_source(recs[:152] + list(reversed(recs[152:])))
    assert a == b


def test_a_torque_not_byte_equal_to_train_150_stops():
    recs = _records()
    recs[7]["outputs"]["torque_nm"][3] += 1e-9
    with pytest.raises(ValueError, match="byte-equal to TRAIN 150"):
        ppt.assemble_motor18_source(recs)


def test_a_missing_train_row_or_an_id_gap_refuses():
    recs = _records()
    with pytest.raises(ValueError, match="without a gap"):
        ppt.assemble_motor18_source(recs[:5] + recs[6:])
    with pytest.raises(ValueError, match="without a gap"):
        ppt.assemble_motor18_source(_records(pilot=0) + [_added(77, cid="train-0152")])


def test_a_record_without_flux_linkage_refuses():
    recs = _records()
    del recs[10]["record_now"]
    with pytest.raises(ValueError, match="phase flux linkage"):
        ppt.assemble_motor18_source(recs)


def test_a_non_ok_or_duplicate_record_refuses():
    recs = _records()
    recs[-1]["status"] = "REFERENCE_INVALID"
    with pytest.raises(ValueError, match="typed-OK"):
        ppt.assemble_motor18_source(recs)
    recs = _records() + [_added(0)]
    with pytest.raises(ValueError, match="repeats a design"):
        ppt.assemble_motor18_source(recs)


def test_derive_rechecks_the_byte_equal_torque(frozen):
    source = ppt.assemble_motor18_source(_records())
    lines = source.splitlines()
    row = json.loads(lines[0])
    row["outputs"]["torque_nm"][0] += 1.0
    lines[0] = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="byte-equal"):
        ppt.derive_motor18_public_train(NAME, b"\n".join(lines) + b"\n")


def test_host_order_rounding_within_the_ruling_is_accepted_and_recorded(frozen):
    recs = _records()
    for i in (3, 40, 99):
        recs[i]["outputs"]["torque_nm"][5] += 3e-13
    frozen(recs)
    got = ppt.load_extended_train(NAME, MOTOR)
    t = got["provenance"]["torque_vs_train150"]
    assert t["host_order_rounding_rows"] == ["train-0003", "train-0040", "train-0099"]
    assert t["byte_equal_rows"] == 147 and 0 < t["max_abs_delta_nm"] <= 4.0e-13
    assert (
        got["targets"][3, 5] == recs[3]["outputs"]["torque_nm"][5]
    )  # the record-now torque, one source


def test_rounding_beyond_the_ruling_still_stops():
    recs = _records()
    recs[3]["outputs"]["torque_nm"][5] += 5e-13
    with pytest.raises(ValueError, match="STOP"):
        ppt.assemble_motor18_source(recs)
    recs = _records()
    for i in (1, 2, 3, 4):
        recs[i]["outputs"]["torque_nm"][0] += 1e-13
    with pytest.raises(ValueError, match="more TRAIN 150 rows"):
        ppt.assemble_motor18_source(recs)
