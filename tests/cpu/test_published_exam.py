"""What each launch Challenge's exam tests is served as structured fields
(OWNER-PUBLISH-WHAT-IS-TESTED-01): every value equals its registered constant,
every served section is on the Validator's allow-list, and nothing the ruling
withholds is in the answer."""

import importlib
import json
from pathlib import Path

import pytest

from carbon import challenge_registry as challenges
from carbon.challenge_registry import published_exam as pe

EVERYTHING = challenges.HostFacts(
    frozenset({"docker_cli", "trusted_worker_image", "jax", "optax"})
)
SERVED = pe.served()
F08, F02 = ("f08-ribbed-bracket", "1.5"), ("f02", "2.4")
MOTOR, COOLING = ("electric-motor-magnetics", "1.4"), ("chip-cold-plate", "1.4")
ROOT = Path(__file__).resolve().parents[2]

#: What the ruling withholds (section 2): none of it may appear in a served
#: value. Words, plus the two Motor placement figures the ruling names.
WITHHELD = (
    "seeds",
    "seed_root",
    "derived seed",
    "draw_id",
    "hidden_case",
    "private_metadata",
    "predictor_v2",
    "ripple window",
    "clearance",
    "0.5599",
    "0.274",
    "fingerprint",
    "pack_set",
    "manifest",
    "custody",
    "lattice",
    "mesh",
    "refit",
    "yield",
)


def _described(key):
    return challenges.describe(*key, host=EVERYTHING)


def _block(key):
    return _described(key)["published_exam"]


def _walk(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)
    elif isinstance(value, str):
        yield value


def _module(name):
    return importlib.import_module(name)


def test_the_four_launch_versions_serve_a_block_and_others_serve_none():
    assert SERVED == sorted([F08, F02, MOTOR, COOLING])
    for key in SERVED:
        assert _block(key)["schema"] == pe.SCHEMA
        assert _block(key)["scope"].startswith(key[0])
    assert _described(("f08-ribbed-bracket", "1.4"))["published_exam"] is None


@pytest.mark.parametrize("key", SERVED)
def test_every_served_section_is_on_the_allow_list(key):
    block = _block(key)
    assert set(block) <= pe.ALLOWED_FIELDS
    # Every ruled item is present: nothing is silently absent.
    for name in (
        "score",
        "minimums",
        "gates",
        "physics_laws",
        "design_value_scales",
        "limits",
        "uncertainty",
        "exam_shape",
        "population",
        "koth",
        "grade_statuses",
        "practice_vs_exam",
        "rotation",
    ):
        assert block[name], name
    assert block["score"]["formula"] == "TOTAL = 0.5 * A + 0.5 * D"
    assert block["score"]["weights"] == {"A": 0.5, "D": 0.5}
    # A value that is not registered says so, never a blank or a number.
    assert block["koth"]["margin"] == pe.NOT_REGISTERED
    assert block["physics_laws"]["gross_violation_margin"] == pe.NOT_REGISTERED


@pytest.mark.parametrize("key", SERVED)
def test_nothing_the_ruling_withholds_is_served(key):
    words = " ".join(_walk(_block(key))).lower()
    for word in WITHHELD:
        assert word not in words, (key, word)


def test_the_block_survives_json_and_is_small():
    for key in SERVED:
        assert len(json.dumps(_block(key), sort_keys=True)) < 16000


def test_a_section_off_the_allow_list_is_caught(monkeypatch):
    monkeypatch.setitem(pe._BY_VERSION, F02, {**pe._BY_VERSION[F02], "case_ids": []})
    assert not set(pe.for_version(*F02)) <= pe.ALLOWED_FIELDS


def test_the_exam_fields_are_filled_for_the_launch_versions_only():
    for key in (F08, F02):
        exam = _described(key)["exam"]
        assert exam["rule"] == "TOTAL = 0.5 * A + 0.5 * D"
        assert "A_acc" in exam["components"] and "C" in exam["components"]
        assert "paired_repeat" in exam["gates"]
    older = _described(("f08-ribbed-bracket", "1.4"))["exam"]
    assert older["gates"] == older["components"] == older["rule"] == "HUMAN_INPUT"


# ---- every value is its registered constant --------------------------------


def test_shared_constants_match_code():
    cf = _module("carbon.scoring.critical_fidelity")
    gf = _module("carbon.scoring.grade_feedback")
    pd = _module("carbon.scoring.probe_design")
    for key in SERVED:
        block = _block(key)
        assert block["score"]["nearby_variant_shift"]["value"] == cf.SHIFT
        assert block["koth"]["ladder_step"]["value"] == gf.ETA
        assert block["grade_statuses"]["statuses"] == list(gf.STATUSES)
        assert sorted(block["grade_statuses"]["reasons"]) == sorted(gf.REASONS)
        step = block["exam_shape"]["probes"]["step"]["value"]
        assert step == f"{pd.DELTA_RANGE[0]} to {pd.DELTA_RANGE[1]}"


def test_scales_match_code():
    f08c = _module("carbon.scoring.f08_critical")
    f02p = _module("carbon.scoring.f02_dual_pack")
    mot = _module("carbon.scoring.motor_sealed_dual_pack")
    cdm = _module("carbon.scoring.cooling_dual_measurement")
    scales = {k: _block(k)["design_value_scales"] for k in SERVED}
    assert scales[F08]["static_margin"]["value"] == f08c.STATIC_MARGIN_SCALE
    assert scales[F08]["dynamic_margin"]["value"] == f08c.DYNAMIC_MARGIN_SCALE
    assert scales[F08]["resonance"]["value"] == f08c.RESONANCE_SCALE_HZ
    assert scales[F02]["value_scale"]["value"] == f02p.S_VALUE_J
    assert scales[F02]["margin_scale"]["value"] == f02p.MARGIN_SCALE_C
    assert scales[MOTOR]["torque_margin"]["value"] == mot.TORQUE_MARGIN_SCALE_NM
    assert scales[MOTOR]["ripple_margin"]["value"] == mot.RIPPLE_MARGIN_SCALE
    assert scales[COOLING]["die_margin"]["value"] == cdm.DIE_MARGIN_SCALE_C
    assert scales[COOLING]["hydraulic_margin"]["value"] == cdm.HYDRAULIC_MARGIN_SCALE_W


def test_limits_match_code():
    f02 = _module("carbon.challenge_kit.f02_train")
    f08d = _module("carbon.f08.domain")
    mgd = _module("carbon.motor_grid_exam.domain")
    cpd = _module("carbon.cold_plate_exam.domain")
    limits = {k: _block(k)["limits"] for k in SERVED}
    assert limits[F02]["peak_top_c_max"] == f02.LIMIT_C
    assert limits[F08]["dynamic_tip_mm_per_n_max"] == f08d.LIMIT_MM_PER_N
    assert limits[MOTOR]["min_mean_torque_nm"] == mgd.MIN_TORQUE_NM
    assert limits[MOTOR]["max_ripple_fraction"] == mgd.MAX_RIPPLE_FRACTION
    assert limits[COOLING]["die_peak_c_max"] == cpd.DIE_LIMIT_C
    assert limits[COOLING]["hydraulic_power_w_max"] == cpd.HYDRAULIC_LIMIT_W


def _flat(document):
    for k, v in document.items():
        if isinstance(v, dict):
            yield from _flat(v)
        else:
            yield (k, v)


@pytest.mark.parametrize(
    ("folder", "key", "name"),
    [
        (
            "f08-near-limit-public-20261020/reference-uncertainty",
            F08,
            "static_tip_mm_per_n",
        ),
        (
            "f08-near-limit-public-20261020/reference-uncertainty",
            F08,
            "worst_dynamic_mm_per_n",
        ),
        ("f02-cold-pack-20261020/reference-uncertainty", F02, "peak_top_c"),
        ("motor-reference-uncertainty-20261020", MOTOR, "mean_torque_nm"),
        ("motor-reference-uncertainty-20261020", MOTOR, "ripple_fraction"),
        ("cooling-reference-uncertainty-20261020", COOLING, "die_peak_c"),
    ],
)
def test_uncertainty_matches_the_pinned_evidence(folder, key, name):
    files = sorted((ROOT / "docs/development/evidence" / folder).glob("*.json"))
    files = [f for f in files if "uncertainty" in f.name]
    assert files, folder
    document = json.loads(files[0].read_text(encoding="utf-8"))
    found = [v for k, v in _flat(document) if k == name]
    assert found and found[0] == _block(key)["uncertainty"][name], (key, name)


def test_exam_shapes_match_the_sealed_packs():
    shapes = {k: _block(k)["exam_shape"] for k in SERVED}
    for key, module in (
        (F08, "carbon.scoring.f08_sealed_dual_pack"),
        (F02, "carbon.scoring.f02_sealed_dual_pack"),
        (MOTOR, "carbon.scoring.motor_sealed_dual_pack"),
    ):
        pack = _module(module)
        shape = shapes[key]
        assert (shape["designs"], shape["conditions"]) == (
            pack.DESIGNS,
            pack.CONDITIONS,
        )
        assert shape["cells"] == pack.CASES
    cooling = shapes[COOLING]
    assert cooling["cells"] == cooling["designs"] * cooling["conditions"] == 16
