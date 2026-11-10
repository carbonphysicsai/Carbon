"""Extended public TRAINs (Motor 1.8 / Cooling 1.8): native rows byte-equal plus added in-box rows, same interface.

Synthetic added rows only (no Carbon truth): the pins are patched to a temporary data directory, so the production
table stays unfrozen (every pin None) and loading it refuses.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import numpy as np
import pytest

from carbon.challenge_kit import physical_public_train as ppt
from carbon.challenge_kit import version_registry
from carbon.cold_plate import domain as cooling_domain
from carbon.motor import domain as motor_domain

MOTOR = "electric-motor-magnetics"
COOLING = "chip-cold-plate"


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _motor_record(i, **extra_outputs):
    inputs = dict(motor_domain.NOMINAL)
    inputs["airgap_mm"] = inputs["airgap_mm"] + 0.001 * (i + 1)
    return {
        "schema": "carbon.motor.reference-record.v1",
        "case_id": f"pool-s6100-c{i:02d}",  # a custody draw id: must never be published
        "batch": "pool-s6100",
        "run": "custody-run",
        "wall_s": 12.0,
        "kind": "ordinary",
        "status": "OK",
        "inputs": inputs,
        "outputs": {
            "torque_nm": [5.0 + 0.01 * k for k in range(motor_domain.ANGLE_STEPS)],
            **extra_outputs,
        },
        "options": {},
        "image": "carbon-motor-reference:dev",
    }


def _cooling_record(i):
    inputs = dict(cooling_domain.NOMINAL)
    inputs["inlet_c"] = inputs["inlet_c"] + 0.01 * (i + 1)
    profile = [50.0 + 0.5 * k for k in range(cooling_domain.PROFILE_SEGMENTS)]
    return {
        "schema": "carbon.cold-plate.reference-record.v1",
        "case_id": f"pool-s6200-c{i:02d}",
        "batch": "pool-s6200",
        "diagnostics": {"host": "custody"},
        "kind": "ordinary",
        "status": "OK",
        "inputs": inputs,
        "outputs": {
            "peak_c": max(profile) + 2.0,
            "profile_c": profile,
            "pressure_drop_pa": 900.0,
            "mean_c": 55.0,
        },
        "options": {"iterations": 2000},
        "image": "opencfd/openfoam-default@sha256:x",
    }


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    """Freeze synthetic extended TRAINs into a temporary data dir; returns {name: provenance}."""
    table = {k: dict(v) for k, v in ppt.EXTENDED.items()}
    monkeypatch.setattr(ppt, "EXTENDED", table)
    monkeypatch.setattr(ppt, "_EXTENDED_DATA", tmp_path)
    made = {}

    def freeze(name, records):
        spec = table[name]
        source = ppt.assemble_extended_source(spec["challenge"], records)
        raw, prov = ppt.derive_extended_public_train(name, source)
        prov_raw = (json.dumps(prov, indent=1, sort_keys=True) + "\n").encode()
        (tmp_path / f"{name}.source.jsonl").write_bytes(source)
        (tmp_path / f"{name}.npz").write_bytes(raw)
        (tmp_path / f"{name}.provenance.json").write_bytes(prov_raw)
        spec.update(
            rows=len(prov["case_ids"]),
            source_sha256=_sha(source),
            train_sha256=_sha(raw),
            provenance_sha256=_sha(prov_raw),
        )
        made[name] = prov
        return source

    def freeze_encoded(name):
        spec = table[name]
        native = ppt._load_extended(spec["encoded_from"], spec["challenge"])
        raw, prov = ppt.derive_extended_encoded_public_train(name, native)
        prov_raw = (json.dumps(prov, indent=1, sort_keys=True) + "\n").encode()
        (tmp_path / f"{name}.npz").write_bytes(raw)
        (tmp_path / f"{name}.provenance.json").write_bytes(prov_raw)
        spec.update(
            rows=len(prov["case_ids"]),
            train_sha256=_sha(raw),
            provenance_sha256=_sha(prov_raw),
        )

    return freeze, freeze_encoded


def test_every_registered_motor_and_cooling_version_loads_the_same_train_as_before():
    for challenge in (MOTOR, COOLING):
        native = ppt.load_public_train(challenge)["train"]
        for version in version_registry.versions(challenge):
            entry = version_registry.entry(challenge, version)
            if entry.train in ppt.EXTENDED or entry.train in ppt.FRESH_LAMBDA:
                continue  # a 1.8 version serves its OWN frozen TRAIN (tested below)
            got = ppt.load_public_train(challenge, entry.version)["train"]
            if entry.train == version_registry.COOLING_TRAIN_ENCODED:
                assert got == ppt._load_encoded(challenge)["train"]
            else:
                assert got == native


def test_the_production_extended_trains_load_when_frozen_and_refuse_until_then():
    for name, spec in ppt.EXTENDED.items():
        if spec["train_sha256"] is None:
            assert spec["rows"] is None
            with pytest.raises(ValueError, match="not frozen yet"):
                ppt._load_extended(name, spec["challenge"])
            continue
        got = ppt._load_extended(name, spec["challenge"])
        assert got["inputs"].shape[0] == len(got["case_ids"]) == spec["rows"]


def test_cooling_1_8_serves_its_frozen_458_row_train():
    """The Carbon Validator-B receipted freeze (9 Nov, R2 canonical pins): TRAIN 400 byte-equal, then 58 added rows."""
    native = ppt.load_public_train(COOLING)
    got = ppt.load_public_train(COOLING, "1.8")
    assert got["inputs"].shape == (458, 9) and got["targets"].shape == (458, 32)
    assert np.array_equal(got["inputs"][:400], native["inputs"])
    assert got["case_ids"] == tuple(f"train-{i:04d}" for i in range(458))
    assert got["provenance"]["encoding"] == ppt._cooling_encoding()


def test_a_registered_version_naming_an_unknown_train_refuses(monkeypatch):
    entry = version_registry.entry(COOLING, "1.6")
    monkeypatch.setattr(
        version_registry,
        "find",
        lambda c, v: dataclasses.replace(entry, train="cooling-somewhere-else"),
    )
    with pytest.raises(ValueError, match="not served by this loader"):
        ppt.load_public_train(COOLING, "1.6")


def test_a_registered_version_naming_an_unfrozen_extended_train_refuses(monkeypatch):
    table = {k: dict(v) for k, v in ppt.FRESH_LAMBDA.items()}
    table["motor-dev-train-1p8-v1"].update(
        rows=None, source_sha256=None, train_sha256=None, provenance_sha256=None
    )
    monkeypatch.setattr(ppt, "FRESH_LAMBDA", table)
    entry = version_registry.entry(MOTOR, "1.5")
    monkeypatch.setattr(
        version_registry,
        "find",
        lambda c, v: dataclasses.replace(entry, train="motor-dev-train-1p8-v1"),
    )
    with pytest.raises(ValueError, match="not frozen yet"):
        ppt.load_public_train(MOTOR, "1.5")


def test_cooling_extended_added_rows_are_allow_listed_with_predicted_outputs_only(
    frozen,
):
    freeze, _ = frozen
    source = freeze("cooling-dev-train-1p8-v1", [_cooling_record(i) for i in range(3)])
    n = len(ppt.load_public_train(COOLING)["case_ids"])
    native = ppt.load_public_train(COOLING)
    got = ppt._load_extended("cooling-dev-train-1p8-v1", COOLING)
    assert got["inputs"].shape[0] == n + 3
    assert np.array_equal(got["targets"][:n], native["targets"])
    assert got["case_ids"][n:] == tuple(f"train-{i:04d}" for i in range(n, n + 3))
    for line in source.splitlines()[n:]:
        row = json.loads(line)
        assert set(row) <= {
            "schema",
            "case_id",
            "kind",
            "status",
            "inputs",
            "outputs",
            "options",
            "image",
        }
        assert set(row["outputs"]) == {"peak_c", "profile_c", "pressure_drop_pa"}
    # the added rows only (the native rows are public as they are)
    text = b"\n".join(source.splitlines()[n:]).decode()
    assert "pool-s6200" not in text and "custody" not in text and "mean_c" not in text


def test_added_rows_are_ordered_by_their_inputs_not_by_the_records_order(frozen):
    records = [_motor_record(i) for i in range(4)]
    a = ppt.assemble_extended_source(MOTOR, records)
    b = ppt.assemble_extended_source(MOTOR, list(reversed(records)))
    assert a == b


def test_cooling_extended_encoded_train_roundtrip(frozen, monkeypatch):
    freeze, freeze_encoded = frozen
    freeze("cooling-dev-train-1p8-v1", [_cooling_record(i) for i in range(2)])
    freeze_encoded("cooling-dev-train-1p8-v1-encoded")
    entry = version_registry.entry(COOLING, "1.6")
    monkeypatch.setattr(
        version_registry,
        "find",
        lambda c, v: dataclasses.replace(
            entry, train="cooling-dev-train-1p8-v1-encoded"
        ),
    )
    got = ppt.load_public_train(COOLING, "1.6")
    native = ppt._load_extended("cooling-dev-train-1p8-v1", COOLING)
    assert np.array_equal(got["inputs"], native["inputs"])
    assert (
        got["inputs"].shape[0] == ppt.load_public_train(COOLING)["inputs"].shape[0] + 2
    )
    assert got["provenance"]["encoding"] == ppt._cooling_encoding()


def test_a_tampered_extended_train_refuses(frozen, tmp_path):
    freeze, _ = frozen
    freeze("cooling-dev-train-1p8-v1", [_cooling_record(0)])
    path = tmp_path / "cooling-dev-train-1p8-v1.npz"
    path.write_bytes(path.read_bytes() + b"\0")
    with pytest.raises(ValueError, match="identity differs"):
        ppt._load_extended("cooling-dev-train-1p8-v1", COOLING)


@pytest.mark.parametrize(
    "change, match",
    [
        (lambda r: {**r, "status": "REFERENCE_INVALID"}, "typed-OK"),
        (lambda r: {**r, "outputs": {"mean_c": 1.0}}, "typed-OK"),
        (lambda r: {**r, "inputs": {**r["inputs"], "extra": 1.0}}, "typed-OK"),
    ],
)
def test_assemble_refuses_a_non_ok_or_malformed_added_record(change, match):
    with pytest.raises(ValueError, match=match):
        ppt.assemble_extended_source(MOTOR, [change(_motor_record(0))])


def test_assemble_refuses_an_added_row_that_repeats_a_train_design():
    with open(ppt.motor.TRAIN_PATH, "rb") as handle:
        native_first = json.loads(handle.readline())
    record = {**_motor_record(0), "inputs": dict(native_first["inputs"])}
    with pytest.raises(ValueError, match="repeats a TRAIN design"):
        ppt.assemble_extended_source(MOTOR, [record])
    with pytest.raises(ValueError, match="repeats a TRAIN design"):
        ppt.assemble_extended_source(MOTOR, [_motor_record(1), _motor_record(1)])


def test_derive_refuses_a_source_that_does_not_start_with_the_native_rows():
    source = ppt.assemble_extended_source(COOLING, [_cooling_record(0)])
    lines = source.splitlines()
    with pytest.raises(ValueError, match="native TRAIN rows byte-equal"):
        ppt.derive_extended_public_train(
            "cooling-dev-train-1p8-v1", b"\n".join(lines[1:]) + b"\n"
        )
