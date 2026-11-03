"""Cooling data kit (kits/cooling): the parser, parity with Carbon's own code,
the Validator's amendments A1-A6, and the leak check."""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_kit import physical_public_train
from carbon.cold_plate import challenge, domain, exam, openfoam, population
from carbon.cold_plate.output_encoding import ENCODING, decode_row, encode_targets
from carbon.scoring import cooling_dual_measurement as cdm
from carbon.scoring import cooling_dual_pack
from kits.cooling import kit

KIT_DIR = Path(kit.__file__).resolve().parent


def _outputs(base, i=0):
    profile = [base + 0.2 * k + i for k in range(30)]
    return {
        "peak_c": max(profile) + 1.5,
        "profile_c": profile,
        "pressure_drop_pa": 9000.0 + 100 * i,
    }


def _fixture(tmp_path):
    cases = kit.sample(2, 11)
    rows = [
        {
            "schema": kit.RECORD_SCHEMA,
            "case_id": c["case_id"],
            "status": "OK",
            "inputs": c["inputs"],
            "outputs": _outputs(50.0, i),
        }
        for i, c in enumerate(cases)
    ]
    rows.append(
        {
            "schema": kit.RECORD_SCHEMA,
            "case_id": "x",
            "status": "REFERENCE_INVALID",
            "inputs": {},
        }
    )
    path = tmp_path / "records.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return cases, rows, path


# --- parser -------------------------------------------------------------------


def test_parser_writes_the_encoded_train_format(tmp_path):
    cases, rows, path = _fixture(tmp_path)
    raw, provenance = kit.parse(path)
    native = [kit.native_row(r["outputs"]) for r in rows[:2]]
    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        assert data["inputs"].shape == (2, 9)
        assert data["targets"].shape == (2, 32)
        assert data["inputs"].dtype == np.dtype("<f8")
        assert data["inputs"][1].tolist() == [
            cases[1]["inputs"][n] for n in domain.INPUTS
        ]
        # The targets are Carbon's own encoding of the native rows.
        assert data["targets"].tolist() == encode_targets(native).tolist()
        # And the bytes are what Carbon's TRAIN writer writes.
        assert raw == physical_public_train._npz(data["inputs"], data["targets"])
        decoded = decode_row(data["targets"][0])
        assert decoded["profile_c"] == native[0][1:31]
    assert provenance["skipped"] == {"REFERENCE_INVALID": 1}
    assert provenance["encoding"] == ENCODING
    assert provenance["scope"] == "MINER_GENERATED_PRACTICE_ONLY"
    assert provenance[
        "numeric_interface"
    ] == physical_public_train.numeric_interface_document(
        "chip-cold-plate", physical_public_train._cooling_encoding()
    )


def test_reader_reads_carbons_encoded_train():
    path = kit.ROOT / "carbon/challenge_kit/data/cooling-dev-train-400-v2-encoded.npz"
    arrays = kit.read_npz(path)
    with np.load(path) as data:
        assert arrays["targets"][1] == data["targets"].tolist()


def test_parser_refuses_out_of_box_and_short_profiles(tmp_path):
    path = tmp_path / "r.jsonl"
    bad = dict(domain.NOMINAL, inlet_c=99.0)
    row = {
        "schema": kit.RECORD_SCHEMA,
        "case_id": "a",
        "status": "OK",
        "inputs": bad,
        "outputs": _outputs(50.0),
    }
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(kit.KitError):
        kit.parse(path)
    short = dict(row, inputs=dict(domain.NOMINAL))
    short["outputs"] = dict(_outputs(50.0), profile_c=[50.0] * 29)
    path.write_text(json.dumps(short) + "\n")
    with pytest.raises(kit.KitError):
        kit.parse(path)


# --- generate -----------------------------------------------------------------


def test_sampler_is_carbons_train_law_in_its_own_domain():
    """A2: Carbon's law (population.draw and its screen), domain-separated label."""
    cases = kit.sample(4, 7)
    expected, _ = population.draw(population.public_rng(kit.label_for(7)), 4)
    assert [c["inputs"] for c in cases] == expected
    assert kit.label_for(7).startswith(kit.LABEL_DOMAIN)
    assert not kit.label_for(7).startswith("carbon.")
    for c in cases:
        domain.check_inputs(c["inputs"])
        assert population.admitted(c["inputs"])


def test_case_writer_is_carbons_at_train_settings(tmp_path):
    kit_dir, ref_dir = tmp_path / "k", tmp_path / "r"
    openfoam.write_case(domain.NOMINAL, kit_dir, **kit.TRAIN_OPTIONS)
    openfoam.write_case(domain.NOMINAL, ref_dir, iterations=2000)
    for path in ref_dir.rglob("*"):
        if path.is_file():
            assert (
                kit_dir / path.relative_to(ref_dir)
            ).read_bytes() == path.read_bytes()
    train = challenge.PublicMaterial.load(kit.ROOT).train
    assert {json.dumps(r["options"], sort_keys=True) for r in train} == {
        json.dumps(kit.TRAIN_OPTIONS, sort_keys=True)
    }
    assert kit.IMAGE == openfoam.IMAGE
    script = kit._script()
    assert all(command in script for command in openfoam.COMMANDS)


def test_kit_refuses_outside_the_screen():
    hot = dict(
        domain.NOMINAL,
        heat_load_w=1500.0,
        flow_lpm_per_kw=1.25,
        inlet_c=45.0,
        channel_width_mm=0.2,
        channel_depth_mm=1.0,
        hotspot_ratio=3.0,
    )
    assert not population.admitted(hot)
    with pytest.raises(kit.KitError, match="outside the population"):
        kit.check_case({"case_id": "h", "inputs": hot})


# --- A3: protected paths ------------------------------------------------------


@pytest.mark.parametrize(
    "part",
    ["custody", "cooling-pool-sealed-v3", "case_bank.npz", "packs", "ops_20261101"],
)
def test_kit_refuses_pack_and_custody_paths(tmp_path, part):
    bad = tmp_path / part / "x"
    with pytest.raises(kit.KitError):
        kit.generate(kit.nominal(), bad)
    with pytest.raises(kit.KitError):
        kit.parse(bad / "records.jsonl")
    with pytest.raises(kit.KitError):
        kit.load_verify_set(bad / "verify_set.json", "0" * 64)


# --- A4: output allow-list ----------------------------------------------------


def test_record_fields_are_allow_listed():
    with pytest.raises(kit.KitError):
        kit.allowed_record({"case_id": "a", "seed": 3})
    assert kit.allowed_record({"case_id": "a", "status": "OK", "mesh": {}})


# --- A1: verify ---------------------------------------------------------------


def _verify_set(outputs, inputs=None):
    design = {
        "case_id": "v1",
        "inputs": inputs or dict(domain.NOMINAL),
        "truth": outputs,
    }
    return {
        "challenge": kit.CHALLENGE_ID,
        "u": json.loads(json.dumps(kit.U_COOLING_16)),
        "designs": [design],
    }


def test_verify_is_unpublished_until_receipted():
    assert kit.VERIFY_SET_SHA256 is None
    assert not kit.VERIFY_SET.exists()
    with pytest.raises(kit.KitError, match="no verify set"):
        kit.load_verify_set()


def test_verify_loads_only_the_receipted_bytes(tmp_path):
    outside = dict(domain.NOMINAL, inlet_c=domain.INPUT_BOUNDS["inlet_c"][1] + 0.5)
    path = tmp_path / "verify_set.json"
    raw = json.dumps(_verify_set(_outputs(50.0), outside)).encode()
    path.write_bytes(raw)
    with pytest.raises(kit.KitError):
        kit.load_verify_set(path, "0" * 64)
    loaded = kit.load_verify_set(path, hashlib.sha256(raw).hexdigest())
    assert loaded["designs"][0]["inputs"] == outside
    assert domain.INPUT_BOUNDS["inlet_c"][1] < outside["inlet_c"]
    with pytest.raises(kit.KitError):
        kit.check_case({"case_id": "g", "inputs": outside}, screen=False)


def test_verify_compares_within_u():
    truth = _outputs(50.0)
    q = kit.quantities(domain.NOMINAL, truth)
    f = exam.feasibility(domain.NOMINAL, truth, die_limit_c=0.0, hydraulic_limit_w=0.0)
    assert q == {"die_peak_c": f["die_peak_c"], "hydraulic_w": f["hydraulic_w"]}
    verify_set = _verify_set(truth)
    same = [{"case_id": "v1", "status": "OK", "outputs": truth}]
    assert kit.verify_compare(verify_set, same)["pass"]
    off = dict(truth, pressure_drop_pa=truth["pressure_drop_pa"] * 1.05)
    assert not kit.verify_compare(
        verify_set, [{"case_id": "v1", "status": "OK", "outputs": off}]
    )["pass"]
    with pytest.raises(kit.KitError):
        kit.verify_compare({**verify_set, "u": kit.HUMAN_INPUT}, same)


# --- A5 / A6: the practice score is the grade's own code ----------------------


def _train_cases(count=6):
    return [dict(r) for r in challenge.PublicMaterial.load(kit.ROOT).train[:count]]


def _encoded_predictions(records, factor):
    natives = [
        [
            r["outputs"]["peak_c"] * factor,
            *(t * factor for t in r["outputs"]["profile_c"]),
            r["outputs"]["pressure_drop_pa"] * factor,
        ]
        for r in records
    ]
    return {
        r["case_id"]: row
        for r, row in zip(records, encode_targets(natives).tolist(), strict=True)
    }


def test_grade_pin_matches_this_commit():
    assert kit.grade_pin() == kit.GRADE_MODULES


def test_score_equals_the_grade_code():
    records = _train_cases()
    predictions = _encoded_predictions(records, 1.002)
    result = kit.score(records, predictions)
    scales = exam.scales_from_train(challenge.PublicMaterial.load(kit.ROOT).train)
    a_scale = cooling_dual_pack._MEASUREMENT["A_scale"]
    errors = []
    for r in records:
        prediction = decode_row(predictions[r["case_id"]])
        assert exam.evaluate_case(prediction, r)["state"] == exam.SCORABLE
        errors.append(exam.case_components(prediction, r, scales))
    means = {c: sum(e[c] for e in errors) / len(errors) for c in exam.COMPONENTS}
    assert result["accuracy"]["mean_errors"] == means
    assert result["accuracy"]["a_scale"] == a_scale
    assert result["accuracy"]["benefit"] == min(
        cdm._benefit(e, a_scale) for e in means.values()
    )


def test_score_is_labelled_practice_and_never_defaults_minimums():
    records = _train_cases(2)
    result = kit.score(records, _encoded_predictions(records, 1.0))
    assert result["label"] == "practice score"
    assert result["minimums"] == "not evaluated locally"
    assert result["design_value"] == "not evaluated locally"
    assert result["gates"]["speed"] == "not evaluated locally"


def test_score_reports_a_failed_gate():
    records = _train_cases(2)
    # A profile below the inlet fails face_above_inlet.
    predictions = {r["case_id"]: [0.0] + [1.0] * 30 + [5.0] for r in records}
    result = kit.score(records, predictions)
    assert result["gates"]["native_per_case"] == "FAIL"
    assert result["accuracy"]["benefit"] is None


# --- leak check -----------------------------------------------------------------

FORBIDDEN = [
    r"-sealed-v",
    r"case_bank\.",
    r"private_rng",
    r"pools-v1",
    r"\bhmac\b",
    r"ops_20\d\d",
    r"/home/",
    r"C:\\Users",
    r"gpuyard",
    r"\bax42\b",
    r"hostkey",
    r"hetzner",
    r"\blium\b",
    r"runpod",
    r"targon",
    r"carbonphysics\.ai",
    r"hotkey",
    r"coldkey",
    r"password",
    r"PRIVATE KEY",
    r"token=",
    r"07098092",
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
]


def _kit_files():
    return [
        p for p in KIT_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts
    ]


def test_kit_holds_no_data_files():
    assert not [
        p
        for p in _kit_files()
        if p.suffix in {".npz", ".npy", ".jsonl", ".json", ".tgz", ".gz"}
    ]


def test_kit_text_has_no_forbidden_material():
    hits = []
    for path in _kit_files():
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN:
            if re.search(pattern, text, flags=re.IGNORECASE):
                hits.append((path.name, pattern))
    assert not hits


def test_kit_digests_are_only_its_grade_pins():
    allowed = set(kit.GRADE_MODULES.values())
    found = set()
    for path in _kit_files():
        found |= set(re.findall(r"\b[0-9a-f]{64}\b", path.read_text(encoding="utf-8")))
    assert found <= allowed


def test_kit_numbers_stay_inside_the_published_box():
    """No input bound in the kit's text lies outside the published TRAIN box:
    every 'low to high' range the pages state is a TRAIN-box range."""
    text = (KIT_DIR / "HOW_YOURE_TESTED.md").read_text(encoding="utf-8")
    stated = re.findall(r"\| (\w+) \| [^|]+ \| ([\d.]+) to ([\d.]+) \|", text)
    assert len(stated) == len(domain.INPUTS)
    for name, low, high in stated:
        assert (float(low), float(high)) == tuple(domain.INPUT_BOUNDS[name])
