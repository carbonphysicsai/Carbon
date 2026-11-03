"""Motor data kit (kits/motor): the parser, parity with Carbon's own code, the
Validator's amendments A1-A6 (07:39 CST, 3 Nov), and the leak check."""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_kit import physical_public_train
from carbon.motor import challenge, domain, exam, population
from carbon.motor import score_candidates as candidates
from carbon.scoring import motor_dual_measurement as mdm
from carbon.scoring import motor_dual_pack
from kits.motor import kit

KIT_DIR = Path(kit.__file__).resolve().parent


def _record(case_id, inputs, curve, status="OK"):
    return {
        "schema": kit.RECORD_SCHEMA,
        "case_id": case_id,
        "status": status,
        "inputs": inputs,
        "outputs": {"torque_nm": curve},
    }


def _fixture(tmp_path):
    """Synthetic, clearly non-reference curves on sampled cases, plus one failed record."""
    cases = kit.sample(2, 11)
    rows = [
        _record(c["case_id"], c["inputs"], [5.0 + 0.01 * k + i for k in range(60)])
        for i, c in enumerate(cases)
    ]
    rows.append(
        {
            "schema": kit.RECORD_SCHEMA,
            "case_id": "x",
            "status": "REFERENCE_TIMEOUT",
            "inputs": {},
        }
    )
    path = tmp_path / "records.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return cases, rows, path


# --- parser -------------------------------------------------------------------


def test_parser_writes_the_train_format(tmp_path):
    cases, rows, path = _fixture(tmp_path)
    raw, provenance = kit.parse(path)
    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        assert data["inputs"].shape == (2, 8)
        assert data["inputs"].dtype == np.dtype("<f8")
        assert data["targets"].shape == (2, 60)
        assert data["inputs"][1].tolist() == [
            cases[1]["inputs"][n] for n in domain.INPUTS
        ]
        assert data["targets"][0].tolist() == rows[0]["outputs"]["torque_nm"]
        # The standard-library writer is byte-identical to Carbon's TRAIN writer.
        assert raw == physical_public_train._npz(data["inputs"], data["targets"])
    assert provenance["skipped"] == {"REFERENCE_TIMEOUT": 1}
    assert provenance["scope"] == "MINER_GENERATED_PRACTICE_ONLY"
    # The numeric layout is Carbon's public TRAIN interface, unchanged.
    assert provenance[
        "numeric_interface"
    ] == physical_public_train.numeric_interface_document("electric-motor-magnetics")
    assert kit.read_npz(io.BytesIO(raw))["targets"][0] == (2, 60)


def test_reader_reads_carbons_public_train():
    path = kit.ROOT / "carbon/challenge_kit/data/motor-dev-train-150-v1.npz"
    arrays = kit.read_npz(path)
    with np.load(path) as data:
        assert arrays["inputs"][1] == data["inputs"].tolist()
        assert arrays["targets"][1] == data["targets"].tolist()


def test_parser_refuses_out_of_box_and_short_curves(tmp_path):
    path = tmp_path / "r.jsonl"
    path.write_text(
        json.dumps(_record("a", dict(domain.NOMINAL, magnet_mm=99.0), [1.0] * 60))
        + "\n"
    )
    with pytest.raises(kit.KitError):
        kit.parse(path)
    path.write_text(json.dumps(_record("a", dict(domain.NOMINAL), [1.0] * 59)) + "\n")
    with pytest.raises(kit.KitError):
        kit.parse(path)


# --- generate -----------------------------------------------------------------


def test_sampler_is_carbons_train_law_in_its_own_domain():
    """A2: Carbon's law (population.draw), from a domain-separated label."""
    cases = kit.sample(5, 7)
    expected, _ = population.draw(population.public_rng(kit.label_for(7)), 5)
    assert [c["inputs"] for c in cases] == expected
    assert kit.label_for(7).startswith(kit.LABEL_DOMAIN)
    assert not kit.label_for(7).startswith("carbon.")
    assert kit.label_for(7) != kit.label_for(8)
    for c in cases:
        domain.check_inputs(c["inputs"])
        assert not domain.validity(c["inputs"])
    with pytest.raises(kit.KitError):
        kit.label_for(-1)


def test_run_script_is_carbons(tmp_path):
    runner = kit._runner()
    p = kit.write_case(runner, kit.nominal()[0], tmp_path / "c")
    assert p == runner.case_params(domain.NOMINAL, {})
    script = kit._script(runner, p)
    assert script.count("getdp machine.pro") == domain.ANGLE_STEPS + 1
    assert (tmp_path / "c" / "mesh.py").read_bytes() == kit.MESH.read_bytes()


# --- A3: protected paths ------------------------------------------------------


@pytest.mark.parametrize(
    "part",
    [
        "custody",
        "motor-pool-sealed-v2",
        "case_bank.npz",
        "evaluation_packs",
        "packs",
        "ops_20261101",
        ".carbon-local",
        "validator_host_classes",
    ],
)
def test_kit_refuses_pack_and_custody_paths(tmp_path, part):
    bad = tmp_path / part / "x"
    with pytest.raises(kit.KitError):
        kit.refuse_protected(bad)
    with pytest.raises(kit.KitError):
        kit.generate(kit.nominal(), bad)
    with pytest.raises(kit.KitError):
        kit.parse(bad / "records.jsonl")
    with pytest.raises(kit.KitError):
        kit.load_verify_set(bad / "verify_set.json", "0" * 64)


def test_kit_allows_ordinary_paths(tmp_path):
    assert kit.refuse_protected(tmp_path / "runs" / "backpacks-2") is not None


# --- A4: output allow-list ----------------------------------------------------


def test_outputs_are_allow_listed(tmp_path):
    with pytest.raises(kit.KitError):
        kit.allowed_record({"case_id": "a", "seed": 3})
    with pytest.raises(kit.KitError):
        kit.write_output(tmp_path, "case_bank.npz", b"")
    kit.write_output(tmp_path, "train.npz", b"")
    kit.audit_output(tmp_path)
    (tmp_path / "extra.json").write_text("{}")
    with pytest.raises(kit.KitError):
        kit.audit_output(tmp_path)


# --- A1: verify ---------------------------------------------------------------


def _verify_set(curve, inputs=None):
    design = {
        "case_id": "v1",
        "inputs": inputs or dict(domain.NOMINAL),
        "truth": {"torque_nm": curve},
    }
    return {
        "challenge": kit.CHALLENGE_ID,
        "u": dict(kit.U_MOTOR_15),
        "designs": [design],
    }


def test_verify_is_unpublished_until_receipted():
    assert kit.VERIFY_SET_SHA256 is None
    assert not kit.VERIFY_SET.exists()
    with pytest.raises(kit.KitError, match="no verify set"):
        kit.load_verify_set()


def test_verify_loads_only_the_receipted_bytes(tmp_path):
    curve = [4.0 + 0.1 * (k % 2) for k in range(60)]
    # A just-outside-the-box design, as the inner band (R15) holds.
    outside = dict(domain.NOMINAL, airgap_mm=domain.INPUT_BOUNDS["airgap_mm"][1] + 0.01)
    path = tmp_path / "verify_set.json"
    raw = json.dumps(_verify_set(curve, outside)).encode()
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    with pytest.raises(kit.KitError):
        kit.load_verify_set(path, "0" * 64)
    assert kit.load_verify_set(path, digest)["designs"][0]["inputs"] == outside
    # The widening is the verify set's own and ends with it.
    assert domain.INPUT_BOUNDS["airgap_mm"][1] < outside["airgap_mm"]
    with pytest.raises(kit.KitError):
        kit.check_case({"case_id": "g", "inputs": outside})


def test_verify_compares_within_u():
    curve = [4.0 + 0.1 * (k % 2) for k in range(60)]
    f = exam.feasibility(
        {"torque_nm": curve}, min_torque_nm=0.0, max_ripple_fraction=1.0
    )
    q = kit.quantities(curve)
    assert q["mean_torque_nm"] == f["mean_nm"]
    assert q["ripple_fraction"] == f["ripple_pk_pk_nm"] / f["mean_nm"]
    verify_set = _verify_set(curve)
    same = [{"case_id": "v1", "status": "OK", "outputs": {"torque_nm": curve}}]
    assert kit.verify_compare(verify_set, same)["pass"]
    off = [
        {
            "case_id": "v1",
            "status": "OK",
            "outputs": {"torque_nm": [v + 0.01 for v in curve]},
        }
    ]
    assert not kit.verify_compare(verify_set, off)["pass"]
    failed = [{"case_id": "v1", "status": "REFERENCE_INVALID"}]
    assert not kit.verify_compare(verify_set, failed)["pass"]
    with pytest.raises(kit.KitError):
        kit.verify_compare({**verify_set, "u": kit.HUMAN_INPUT}, same)


# --- A5 / A6: the practice score is the grade's own code ----------------------


def _train_cases(count=6):
    train = challenge.PublicMaterial.load(kit.ROOT).train
    return [dict(r) for r in train[:count]]


def test_grade_pin_matches_this_commit():
    """A6: the kit is pinned to the grade code at this commit."""
    assert kit.grade_pin() == kit.GRADE_MODULES


def test_score_equals_the_grade_code():
    """A6: every number the practice score shows is the grade's own function."""
    records = _train_cases()
    predictions = {
        r["case_id"]: [
            v * 1.01 + 0.002 * k for k, v in enumerate(r["outputs"]["torque_nm"])
        ]
        for r in records
    }
    result = kit.score(records, predictions)
    train = challenge.PublicMaterial.load(kit.ROOT).train
    scales = candidates.scales(train)
    f0_scale = motor_dual_pack._definition_values()["f0_scale"]
    f0s = []
    for r in records:
        prediction = {"torque_nm": predictions[r["case_id"]]}
        assert exam.evaluate_case(prediction, r)["state"] == exam.SCORABLE
        parts = candidates.components(prediction, r, scales)
        f0s.append((parts["mean"] + parts["shape"]) / 2)
    mean_f0 = sum(f0s) / len(f0s)
    assert result["accuracy"]["mean_f0"] == mean_f0
    assert result["accuracy"]["f0_scale"] == f0_scale
    assert result["accuracy"]["benefit"] == mdm._benefit(mean_f0, f0_scale)
    assert [row["f0"] for row in result["cases_detail"]] == f0s


def test_score_is_labelled_practice_and_never_defaults_minimums():
    """A5: sealed minimums are not evaluated locally and never defaulted."""
    records = _train_cases(2)
    predictions = {r["case_id"]: r["outputs"]["torque_nm"] for r in records}
    result = kit.score(records, predictions)
    assert result["label"] == "practice score"
    assert result["minimums"] == "not evaluated locally"
    assert result["design_value"] == "not evaluated locally"
    assert result["gates"]["speed"] == "not evaluated locally"
    assert "minimum" not in json.dumps(result["accuracy"])


def test_score_reports_a_failed_gate():
    records = _train_cases(2)
    predictions = {r["case_id"]: [-5.0] * 60 for r in records}
    result = kit.score(records, predictions)
    assert result["gates"]["native_per_case"] == "FAIL"
    assert result["accuracy"]["benefit"] is None


# --- leak check: the kit holds no hidden material -------------------------------

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


def test_kit_carries_no_out_of_range_extent():
    """Every out-of-range extent that differs from the TRAIN box is read here at
    run time (never written into this test) and must not appear in the kit."""
    overlay = json.loads(
        (kit.ROOT / "scripts/validator_host_classes/version_overlay.json").read_text()
    )
    train_values = {v for bounds in domain.INPUT_BOUNDS.values() for v in bounds}
    extents = set()
    for entry in overlay["versions"].values():
        if entry.get("challenge_id") != kit.CHALLENGE_ID:
            continue
        box = entry.get("dispatch", {}).get("config", {}).get("baseline_box", {})
        for bounds in box.values():
            extents |= {v for v in bounds if v not in train_values}
    assert extents  # the check has something to look for
    numbers = set()
    for path in _kit_files():
        for token in re.findall(r"-?\d+\.\d+", path.read_text(encoding="utf-8")):
            numbers.add(float(token))
    assert not numbers & extents
