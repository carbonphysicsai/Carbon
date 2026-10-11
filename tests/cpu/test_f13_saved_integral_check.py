"""Fixture-only arithmetic and refusal tests; no acquisition outputs/solvers."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.dev.f13_saved_integral_check import (
    CLOSURE,
    QUANTITIES,
    SCHEMA,
    InputError,
    check_saved,
    main,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "f13_saved_integrals"
PACKET = (
    Path(__file__).parents[2]
    / "docs/development/challenge_pipeline/round1/f13-compressor-silencer.md"
)


def bundle(kind="plane"):
    data = (FIXTURES / f"{kind}.dat").read_bytes()
    names = (FIXTURES / "ports.dat.names").read_bytes()
    deck = (FIXTURES / "deck.json").read_bytes()
    labels = [line.split(":", 1)[1].strip() for line in names.decode().splitlines()[1:]]
    side = {
        "schema": SCHEMA,
        "scope": "SYNTHETIC_FIXTURE",
        "sha256": {},
        "source": {
            "revision": "0" * 40,
            "image_digest": "sha256:" + "0" * 64,
            "model": "EQUAL_PORT_PLANE_ROBIN_REAL_INCIDENT",
            "phasor": "exp(+i*omega*t)",
        },
        "area_basis": "OPERATOR_VERIFIED_EQUAL_PORT_AREAS_AND_BC_IDS",
        "columns": {
            key: {"index": i + 1, "name": labels[i]} for i, key in enumerate(QUANTITIES)
        },
    }
    return data, names, deck, side


def run(data, names, deck, side):
    side = copy.deepcopy(side)
    side["sha256"] = {
        key: hashlib.sha256(raw).hexdigest()
        for key, raw in (("data", data), ("names", names), ("deck", deck))
    }
    return check_saved(data, names, deck, json.dumps(side).encode())


def test_plane_and_criterion():
    result = run(*bundle())
    assert result["status"] == "ACCOUNTING_CLOSURE"
    assert result["old_closure"] and result["robin_closure"]
    assert result["physical_reference_status"] == "UNRESOLVED"
    assert result["basis"]["rows_examined"] == result["basis"]["expected_rows"] == 3
    assert result["basis"]["operator_assertions_independently_verified"] is False
    assert len(result["basis"]["not_checked"]) == 5
    assert CLOSURE == 0.01
    assert "power balance≤1%" in PACKET.read_text(encoding="utf-8")


def test_mixed_definition_explains_positive_residual_without_physical_claim():
    result = run(*bundle("mixed"))
    assert result["status"] == "MIXED_EXTRACTION_FINDING"
    assert not result["old_closure"] and result["robin_closure"]
    assert result["worst_old"]["frequency_hz"] == 500
    for row in result["rows"]:
        assert row["old_residual_fraction"] == pytest.approx(0.047)
        assert row["inlet_variance_w"] == pytest.approx(0.047)
        assert row["outlet_variance_w"] == pytest.approx(0.063)
        assert row["robin_residual_w"] == pytest.approx(0, abs=1e-14)
        assert row["identity_error_w"] == pytest.approx(0, abs=1e-14)
    assert result["physical_reference_status"] == "UNRESOLVED"


@pytest.mark.parametrize(
    "h_in,h_out,expected",
    [
        (1, 1.04, "CLOSURE_FINDING"),
        (1.04, 1, "CLOSURE_FINDING"),
        (0.9, 1, "INTEGRAL_FINDING"),
        (1, 0.9, "INTEGRAL_FINDING"),
        (-1, 1, "INTEGRAL_FINDING"),
    ],
)
def test_signed_deficit_excess_and_unclamped_negative_variance(h_in, h_out, expected):
    data, names, deck, side = bundle()
    data = (
        f"500 1 1 0 0 {h_in} {h_out}\n1500 1 1 0 0 1 1\n2500 1 1 0 0 1 1\n"
    ).encode()
    result = run(data, names, deck, side)
    assert result["status"] == expected
    if h_out > 1:
        assert result["rows"][0]["old_residual_w"] < 0
    if h_in < 1:
        assert result["rows"][0]["inlet_variance_w"] < 0
    if h_out < 1:
        assert result["rows"][0]["outlet_variance_w"] < 0


def test_computed_incident_power_not_forced_unit():
    data, names, deck, side = bundle()
    meta = json.loads(deck)
    meta["amplitude_pa"] = 2
    data = b"500 2 2 0 0 4 4\n1500 2 2 0 0 4 4\n2500 2 2 0 0 4 4\n"
    result = run(data, names, json.dumps(meta).encode(), side)
    assert result["basis"]["incident_w"] == 4
    assert result["basis"]["incident_minus_unit_w"] == 3


def test_explicit_mapping_permits_different_column_order():
    data, names, deck, side = bundle("mixed")
    order = [6, 2, 1, 5, 3, 0, 4]
    labels = [line.split(":", 1)[1].strip() for line in names.decode().splitlines()[1:]]
    names = "\n".join(f"{i + 1}: {labels[j]}" for i, j in enumerate(order)).encode()
    rows = [
        line.split() for line in data.decode().splitlines() if not line.startswith("#")
    ]
    data = "\n".join(" ".join(row[j] for j in order) for row in rows).encode()
    for key, col in side["columns"].items():
        col["index"] = order.index(QUANTITIES.index(key)) + 1
    assert run(data, names, deck, side)["status"] == "MIXED_EXTRACTION_FINDING"


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "missing",
        "duplicate",
        "extra",
        "reorder",
        "nan",
        "infinity",
        "short",
        "long",
        "nonnumeric",
    ],
)
def test_raw_data_refusals(mutation):
    data, names, deck, side = bundle()
    rows = data.decode().splitlines()
    if mutation == "empty":
        data = b"# no evidence\n"
    elif mutation == "missing":
        data = "\n".join(rows[:-1]).encode()
    elif mutation == "duplicate":
        data = "\n".join(rows + [rows[0]]).encode()
    elif mutation == "extra":
        data += b"3000 1 1 0 0 1 1\n"
    elif mutation == "reorder":
        data = "\n".join(rows[::-1]).encode()
    elif mutation == "nan":
        data = data.replace(b"500 1", b"500 nan")
    elif mutation == "infinity":
        data = data.replace(b"500 1", b"500 inf")
    elif mutation == "short":
        data = data.replace(b"500 1 1", b"500 1")
    elif mutation == "long":
        data = data.replace(b"500 1 1", b"500 1 1 1")
    else:
        data = data.replace(b"500 1", b"500 secret-token")
    with pytest.raises(InputError):
        run(data, names, deck, side)


@pytest.mark.parametrize(
    "key,value",
    [
        ("rho", 0),
        ("c", -1),
        ("port_area_m2", False),
        ("amplitude_pa", 1e308),
        ("rho", 1e308),
        ("frequencies_hz", []),
        ("frequencies_hz", [500, 500, 2500]),
        ("frequencies_hz", [500, float("nan"), 2500]),
        ("frequencies_hz", [500, 2500, 1500]),
    ],
)
def test_bad_deck(key, value):
    data, names, deck, side = bundle()
    meta = json.loads(deck)
    meta[key] = value
    with pytest.raises(InputError):
        run(data, names, json.dumps(meta).encode(), side)


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "hidden",
        "model",
        "area",
        "name",
        "alias",
        "boolindex",
        "source",
        "namesduplicate",
        "namesgap",
    ],
)
def test_mapping_and_names_refusals(mutation):
    data, names, deck, side = bundle()
    if mutation == "unknown":
        side["hidden_seed"] = 1
    elif mutation == "hidden":
        side["scope"] = "HIDDEN_EVAL"
    elif mutation == "model":
        side["source"]["model"] = "PHYSICAL_MODAL"
    elif mutation == "area":
        side["area_basis"] = "ASSUMED"
    elif mutation == "name":
        side["columns"]["frequency"]["name"] = "wrong"
    elif mutation == "alias":
        side["columns"]["in_real"] = side["columns"]["out_real"]
    elif mutation == "boolindex":
        side["columns"]["frequency"]["index"] = True
    elif mutation == "source":
        side["source"]["revision"] = "floating-main"
    elif mutation == "namesduplicate":
        names += b"\n1: another\n"
    else:
        names = names.replace(b"7:", b"9:")
    with pytest.raises(InputError):
        run(data, names, deck, side)


def test_hash_and_duplicate_json_refusal():
    data, names, deck, side = bundle()
    side["sha256"] = {key: "0" * 64 for key in ("data", "names", "deck")}
    with pytest.raises(InputError, match="HASH_MISMATCH"):
        check_saved(data, names, deck, json.dumps(side).encode())
    with pytest.raises(InputError):
        check_saved(data, names, deck, b'{"schema": 1, "schema": 2}')


@pytest.mark.parametrize("kind,code", [("plane", 0), ("mixed", 1)])
def test_readonly_cli(tmp_path, capsys, kind, code):
    data, names, deck, side = bundle(kind)
    side["sha256"] = {
        key: hashlib.sha256(raw).hexdigest()
        for key, raw in (("data", data), ("names", names), ("deck", deck))
    }
    blobs = {
        "data": data,
        "names": names,
        "deck": deck,
        "mapping": json.dumps(side).encode(),
    }
    args = []
    for key, raw in blobs.items():
        path = tmp_path / key
        path.write_bytes(raw)
        args.extend([f"--{key}", str(path)])
    assert main(args) == code
    result = json.loads(capsys.readouterr().out)
    assert result["physical_reference_status"] == "UNRESOLVED"
    assert {key: (tmp_path / key).read_bytes() for key in blobs} == blobs


def test_missing_cli_inputs_are_non_echoing(tmp_path, capsys):
    args = [
        part
        for key in ("data", "names", "deck", "mapping")
        for part in (f"--{key}", str(tmp_path / "private-token"))
    ]
    assert main(args) == 2
    output = capsys.readouterr().out
    assert "private-token" not in output
    assert json.loads(output)["rows_examined"] == 0
