"""A registered crown floor (V2C's option B for Motor 1.8, Fri 13 Nov): the host-side floor registry.

The 1.8 pack carries neither leg minimums nor a ``baseline_floor_total``, so the crown floor was never available. A
measured floor is registered beside the margins, keyed by the exact exam (challenge, version, menu epoch, sealed evaluation
pack digest). V2C's five must-haves:

1. the key is the exact sealed pack digest + challenge + version + epoch;
2. the pack's own floor wins; both present and unequal is a refusal;
3. a missing floor is UNAVAILABLE, never a default;
4. every entry carries its measurement digest;
5. no crown is decided before the floor, the noise and the margin are registered: the entry names the noise and margin
   measurements it was registered beside, and is found only while those are the registered ones.

Every value here is a SYNTHETIC fixture; no registered number is read or typed.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import koth_registry as kr
from carbon.challenge_validator import lean_recipe_retention as lrr
from carbon.challenge_validator.interface import digest
from carbon.reconstruction.worker import build_inputs
from carbon.scoring import dual_score, pool_exam, pool_version

CHALLENGE = "electric-motor-magnetics"
ROOT = Path(__file__).resolve().parents[2]
SHA = "sha256:" + "a" * 64
PACK = digest("a sealed evaluation pack")
NOISE = digest("a rebuild noise measured on this exam")
MARGIN = digest("a crown margin measured on this exam")
EXAM = {"version": "9.9", "epoch": "E1", "evaluation_pack_digest": PACK}


def _entry(**changes):
    return {
        "challenge": CHALLENGE,
        "version": "9.9",
        "epoch": "E1",
        "evaluation_pack_digest": PACK,
        "value": 0.31,
        "measurement_digest": digest("two bit-equal counted grades of the baseline"),
        "rebuild_noise_measurement_digest": NOISE,
        "crown_margin_measurement_digest": MARGIN,
        **changes,
    }


def _files(tmp_path, entries=None, *, noise=NOISE, margin=MARGIN, margin_n=10):
    floors = tmp_path / "crown_floor.json"
    floors.write_text(
        json.dumps(
            {
                "schema": kr.FLOOR_SCHEMA,
                "floors": [_entry()] if entries is None else entries,
            }
        )
    )
    noises = tmp_path / "koth_rebuild_noise.json"
    noises.write_text(
        json.dumps(
            {
                "schema": kr.SCHEMA,
                "challenges": (
                    {}
                    if noise is None
                    else {CHALLENGE: {"value": 0.01, "measurement_digest": noise}}
                ),
            }
        )
    )
    margins = tmp_path / "crown_average.json"
    margins.write_text(
        json.dumps(
            {
                "schema": "carbon.crown.average-rule.v1",
                "rule_version": "crown-average-v1",
                "n": 10,
                "challenge_n": {},
                "seed_range": 2147483647,
                "margins": (
                    {}
                    if margin is None
                    else {
                        CHALLENGE: {
                            "value": 0.002,
                            "n": margin_n,
                            "measurement_digest": margin,
                        }
                    }
                ),
            }
        )
    )
    return {"path": floors, "noise_path": noises, "margin_path": margins}


def _found(files, exam=EXAM):
    return kr.registered_floor(CHALLENGE, exam, **files)


def _pack(a=None, d=None, **extra):
    leg = {
        "components": [
            {
                "metric": "m",
                "unit": "1",
                "transform": "unit_benefit",
                "scale": None,
                "weight": 1.0,
            }
        ],
    }
    return dual_score.register_pack(
        {
            "schema": dual_score.PACK_SCHEMA,
            "scope": "PUBLIC_DEVELOPMENT",
            "challenge": CHALLENGE,
            "physics_contract_digest": SHA,
            "measurement_contract_digest": SHA,
            "hard_gates": ["g"],
            "legs": {
                "A": {
                    "components": [{**leg["components"][0], "metric": "a"}],
                    "minimum": a,
                },
                "D": {
                    "components": [{**leg["components"][0], "metric": "d"}],
                    "minimum": d,
                },
            },
            "value_weight": 0.5,
            "combination": "weighted_arithmetic_mean",
            "decision_policy": {
                "VERIFIED_FEASIBLE": {"eligible": True, "maximum_D": 1.0},
                "MISSED_OPPORTUNITY": {"eligible": False, "maximum_D": 0.0},
                "NONE_FEASIBLE": {"eligible": False, "maximum_D": 0.0},
            },
            **extra,
        }
    )


# --- 1. the key is the exact exam ------------------------------------------------------------------------------------


def test_the_exact_exam_finds_its_floor(tmp_path):
    assert _found(_files(tmp_path)) == 0.31


@pytest.mark.parametrize(
    "other",
    [
        {"version": "9.8"},
        {"epoch": "E2"},
        {"evaluation_pack_digest": digest("another pack")},
    ],
)
def test_another_version_epoch_or_pack_finds_nothing(tmp_path, other):
    assert _found(_files(tmp_path), {**EXAM, **other}) is None


def test_another_challenge_finds_nothing(tmp_path):
    files = _files(tmp_path)
    assert kr.registered_floor("chip-cold-plate", EXAM, **files) is None


def test_no_exam_finds_nothing_so_the_default_is_the_pack_alone(tmp_path):
    assert _found(_files(tmp_path), None) is None


# --- 3. a missing floor is UNAVAILABLE, never a default ---------------------------------------------------------------


def test_an_empty_registry_finds_nothing(tmp_path):
    assert _found(_files(tmp_path, [])) is None


def test_the_committed_registry_loads_and_holds_only_exact_entries():
    # structure, never values: a registered floor must not break main
    for entry in kr._load_floors():
        assert set(entry) == kr._FLOOR_ENTRY


def test_a_pack_without_a_floor_and_no_registered_floor_has_no_baseline():
    assert kr.baseline_total(_pack()) is None
    assert kr.baseline_total(_pack(), None) is None


# --- 5. a floor stands only beside the noise and the margin it was registered with ------------------------------------


def test_a_floor_is_not_found_while_the_noise_is_unregistered(tmp_path):
    assert _found(_files(tmp_path, noise=None)) is None


def test_a_floor_is_not_found_while_the_margin_is_unregistered(tmp_path):
    assert _found(_files(tmp_path, margin=None)) is None


def test_a_floor_is_not_found_while_the_margin_is_for_another_n(tmp_path):
    # `margin_for` is None for a margin measured at a different N: stale is never used
    assert _found(_files(tmp_path, margin_n=7)) is None


def test_a_floor_is_not_found_while_the_noise_is_not_the_one_it_names(tmp_path):
    assert _found(_files(tmp_path, noise=digest("the old 1.5 noise"))) is None


def test_a_floor_is_not_found_while_the_margin_is_not_the_one_it_names(tmp_path):
    assert _found(_files(tmp_path, margin=digest("the old 1.5 margin"))) is None


# --- 2. the pack's own floor wins; unequal is a refusal ----------------------------------------------------------------


def test_the_registered_floor_stands_in_for_a_pack_with_none():
    assert kr.baseline_total(_pack(), 0.31) == 0.31


def test_the_packs_own_floor_wins_when_equal():
    own = _pack(baseline_floor_total=0.31)
    assert kr.baseline_total(own, 0.31) == 0.31
    minimums = _pack(a=0.2, d=0.4)
    assert kr.baseline_total(minimums, 0.3) == pytest.approx(0.3)


@pytest.mark.parametrize(
    "pack",
    [_pack(baseline_floor_total=0.4), _pack(a=0.2, d=0.4)],
)
def test_a_registered_floor_unequal_to_the_packs_own_refuses(pack):
    with pytest.raises(kr.RegistryInvalid, match="registered_floor_differs"):
        kr.baseline_total(pack, 0.9)


# --- 4. every entry carries its measurement digest; the shape is closed ------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        {"measurement_digest": "not a digest"},
        {"rebuild_noise_measurement_digest": "x"},
        {"crown_margin_measurement_digest": None},
        {"evaluation_pack_digest": "sha256:short"},
        {"value": -0.01},
        {"value": 1.01},
        {"value": float("nan")},
        {"value": True},
        {"value": "0.3"},
        {"epoch": ""},
        {"version": 9},
        {"challenge": "a-misspelled-challenge"},
    ],
)
def test_a_malformed_entry_refuses(tmp_path, bad):
    with pytest.raises(kr.RegistryInvalid, match="crown_floor_registry_invalid"):
        _found(_files(tmp_path, [_entry(**bad)]))


def test_an_entry_without_its_measurement_digest_refuses(tmp_path):
    entry = _entry()
    del entry["measurement_digest"]
    with pytest.raises(kr.RegistryInvalid, match="crown_floor_registry_invalid"):
        _found(_files(tmp_path, [entry]))


def test_an_unknown_field_and_a_duplicate_key_refuse(tmp_path):
    with pytest.raises(kr.RegistryInvalid):
        _found(_files(tmp_path, [{**_entry(), "extra": 1}]))
    with pytest.raises(kr.RegistryInvalid):
        _found(_files(tmp_path, [_entry(), _entry(value=0.4)]))


def test_the_registry_shape_is_closed(tmp_path):
    files = _files(tmp_path)
    files["path"].write_text(json.dumps({"schema": "x", "floors": []}))
    with pytest.raises(kr.RegistryInvalid):
        _found(files)
    files["path"].write_text(json.dumps({"schema": kr.FLOOR_SCHEMA}))
    with pytest.raises(kr.RegistryInvalid):
        _found(files)


# --- the comparator -------------------------------------------------------------------------------------------------------


def _comparator(files, exam, pack):
    return kr.comparator(
        CHALLENGE,
        pack,
        {"definition": "accuracy"},
        path=files["noise_path"],
        exam=exam,
        floors=files["path"],
        margins=files["margin_path"],
    )


@pytest.fixture
def no_sources(monkeypatch):
    from carbon.scoring import physical_dual_pack

    monkeypatch.setattr(
        physical_dual_pack, "minimum_source_entry_ids", lambda definition: []
    )


def test_the_comparator_takes_the_registered_floor_for_the_exact_exam(
    tmp_path, no_sources
):
    files = _files(tmp_path)
    found = _comparator(files, EXAM, _pack())
    assert found["baseline_total"] == 0.31
    assert found["rebuild_noise"]["measurement_digest"] == NOISE
    # no exam given (every existing caller): exactly the pack alone, so no floor
    assert _comparator(files, None, _pack())["baseline_total"] is None
    # another epoch: no floor, so UNAVAILABLE downstream
    assert (
        _comparator(files, {**EXAM, "epoch": "E2"}, _pack())["baseline_total"] is None
    )


def test_the_comparator_keeps_every_existing_pack_exactly(tmp_path, no_sources):
    files = _files(tmp_path)
    for pack in (_pack(a=0.2, d=0.4), _pack(baseline_floor_total=0.7)):
        without = kr.comparator(
            CHALLENGE, pack, {"definition": "accuracy"}, path=files["noise_path"]
        )
        assert without["baseline_total"] == kr.baseline_total(pack)


def test_the_comparator_refuses_a_floor_unequal_to_the_packs_own(tmp_path, no_sources):
    files = _files(tmp_path)
    with pytest.raises(kr.RegistryInvalid, match="registered_floor_differs"):
        _comparator(files, EXAM, _pack(baseline_floor_total=0.5))


def test_the_registered_floor_decides_the_first_crown_like_a_pack_floor(
    tmp_path, no_sources
):
    """With no floor: UNAVAILABLE baseline_floor_unregistered. With the registered one: a challenger beats floor + noise."""
    files = _files(tmp_path)
    pack = _pack()

    def pair(total):
        return {
            "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
            "evaluation_key": digest("evaluation context"),
            "expected_incumbent": None,
            "incumbent": None,
            "candidate": {
                "submission_id": "c",
                "evidence": {
                    "schema": bp.PAIRED_BINDING,
                    "challenge": CHALLENGE,
                    "score_compatibility": {"score_pack_digest": pack["pack_digest"]},
                    "entry_id": digest(["entry", "c"]),
                    "model_p": {"score_status": bp.SCORED, "total_score": total},
                },
            },
        }

    absent = bp.compare_private_pair(pair(0.9), _comparator(files, None, pack))
    assert (absent["outcome"], absent["reason"]) == (
        bp.UNAVAILABLE,
        "baseline_floor_unregistered",
    )
    registered = _comparator(files, EXAM, pack)
    first = bp.compare_private_pair(pair(0.9), registered)
    assert (first["outcome"], first["reason"]) == (
        bp.FIRST_INCUMBENT,
        "first_scored_contender_beats_baseline",
    )
    assert bp.compare_private_pair(pair(0.2), registered)["outcome"] == bp.NO_WINNER


# --- the call site's exam identity ------------------------------------------------------------------------------------


def _adapter(digest_value=PACK, version="9.9"):
    return SimpleNamespace(
        challenge_id=CHALLENGE,
        challenge_version=version,
        discovery=SimpleNamespace(evaluation_pack_digest=digest_value),
    )


@pytest.fixture
def menu_version(monkeypatch):
    """The fixture version registers a menu (the raw-registration check `crown_hold` makes)."""
    from carbon.challenge_validator import crown_hold

    monkeypatch.setattr(crown_hold, "menu_registered", lambda challenge, version: True)


def test_the_floor_exam_is_the_version_its_registered_epoch_and_the_exact_pack(
    monkeypatch, menu_version
):
    monkeypatch.setattr(
        pool_version,
        "registered_menu",
        lambda challenge, version: SimpleNamespace(epoch="E1"),
    )
    assert lrr._floor_exam(_adapter()) == EXAM


def test_a_version_with_no_menu_block_never_parses_its_other_constants(monkeypatch):
    """A live non-menu door: only the raw registration is read, never `registered_policies`."""
    from carbon.challenge_validator import crown_hold

    def never(challenge, version):
        raise AssertionError("registered_menu consulted for a non-menu version")

    monkeypatch.setattr(pool_version, "registered_menu", never)
    monkeypatch.setattr(crown_hold, "menu_registered", lambda challenge, version: False)
    assert lrr._floor_exam(_adapter()) is None


@pytest.mark.parametrize(
    "error",
    [
        pool_version.PoolConstantsNotRegistered("x"),
        pool_exam.ExamRefused("x"),
        TypeError("x"),
        ValueError("x"),
        KeyError("x"),
        RuntimeError("x"),
    ],
)
def test_no_failure_of_the_lookup_breaks_a_grade(monkeypatch, menu_version, error):
    def raises(challenge, version):
        raise error

    monkeypatch.setattr(pool_version, "registered_menu", raises)
    assert lrr._floor_exam(_adapter()) is None


def test_the_floor_exam_is_none_when_anything_is_missing(monkeypatch, menu_version):
    monkeypatch.setattr(pool_version, "registered_menu", lambda c, v: None)
    assert lrr._floor_exam(_adapter()) is None  # a menu row that reads as no rule
    monkeypatch.setattr(
        pool_version, "registered_menu", lambda c, v: SimpleNamespace(epoch="E1")
    )
    assert lrr._floor_exam(_adapter(digest_value=None)) is None
    assert lrr._floor_exam(SimpleNamespace(challenge_id=CHALLENGE)) is None
    monkeypatch.setattr(
        pool_version, "registered_menu", lambda c, v: SimpleNamespace(epoch=None)
    )
    assert lrr._floor_exam(_adapter()) is None


def test_every_pool_grade_call_site_passes_the_exam():
    source = (
        ROOT / "carbon" / "challenge_validator" / "lean_recipe_retention.py"
    ).read_text(encoding="utf-8")
    assert source.count("koth_registry.comparator(") == 3
    assert source.count("exam=_floor_exam(adapter)") == 3


# --- where it lives ----------------------------------------------------------------------------------------------------


def test_the_floor_registry_is_outside_the_worker_image_build_inputs():
    assert kr.FLOORS.is_file()
    relative = kr.FLOORS.resolve().relative_to(ROOT).as_posix()
    assert not any(
        relative == item or relative.startswith(item + "/")
        for item in build_inputs.paths()
    )
    assert kr.FLOORS.parent.name == "validator_host_classes"
