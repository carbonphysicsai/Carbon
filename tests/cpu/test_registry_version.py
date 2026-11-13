"""The version key of the host-side registries (the Lead's ruling, 13 Nov): Motor 1.8 gets its own noise, control and
margin_N without moving Motor 1.5's live values.

An entry may be keyed ``"<challenge id> <version>"``; a lookup reads it FIRST and falls back to the bare Challenge id. A
registry as committed (bare ids only) therefore reads exactly as before, for every version. Every value is a SYNTHETIC
fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import koth_registry as kr
from carbon.challenge_validator import lean_recipe_retention as lrr
from carbon.challenge_validator import registry_version as rv
from carbon.challenge_validator.interface import digest

ROOT = Path(__file__).resolve().parents[2]
CHALLENGE = "electric-motor-magnetics"
OLD, NEW = digest("the 1.5-era measurement"), digest("the 1.8 measurement")


@pytest.fixture(autouse=True)
def _no_served_version():
    rv.serve(None, None)
    yield
    rv.serve(None, None)


def _noise_file(tmp_path, entries):
    path = tmp_path / "koth_rebuild_noise.json"
    path.write_text(json.dumps({"schema": kr.SCHEMA, "challenges": entries}))
    return path


def _rule(tmp_path, margins, challenge_n=None):
    path = tmp_path / "crown_average.json"
    path.write_text(
        json.dumps(
            {
                "schema": ca.SCHEMA,
                "rule_version": "crown-average-v1",
                "n": 10,
                "challenge_n": challenge_n or {},
                "seed_range": 2147483647,
                "margins": margins,
            }
        )
    )
    return ca.load_rule(path)


def _noise(value, measurement):
    return {"value": value, "measurement_digest": measurement}


def _margin(value, measurement, n=10):
    return {"value": value, "n": n, "measurement_digest": measurement}


# --- the key resolver ---------------------------------------------------------------------------------------------------


def test_the_keys_are_the_version_first_then_the_challenge():
    assert rv.keys(CHALLENGE) == (CHALLENGE,)
    assert rv.keys(CHALLENGE, "1.8") == (f"{CHALLENGE} 1.8", CHALLENGE)


def test_a_served_version_applies_to_its_own_challenge_only_and_a_named_one_wins():
    rv.serve(CHALLENGE, "1.8")
    assert rv.keys(CHALLENGE) == (f"{CHALLENGE} 1.8", CHALLENGE)
    assert rv.keys("chip-cold-plate") == ("chip-cold-plate",)
    assert rv.keys(CHALLENGE, "1.5") == (f"{CHALLENGE} 1.5", CHALLENGE)


@pytest.mark.parametrize(
    "bad", [("", "1.8"), (CHALLENGE, ""), (CHALLENGE, "1 8"), (None, "1.8"), (1, 2)]
)
def test_a_malformed_served_version_refuses(bad):
    with pytest.raises(ValueError, match="served_version_invalid"):
        rv.serve(*bad)


@pytest.mark.parametrize(
    ("key", "valid"),
    [
        (CHALLENGE, True),
        (f"{CHALLENGE} 1.8", True),
        ("not-a-challenge 1.8", False),
        (f"{CHALLENGE} ", False),
        (f"{CHALLENGE} 1.8 extra", False),
        (f"{CHALLENGE}  1.8", False),
        ("not-a-challenge", False),
    ],
)
def test_a_key_is_a_registered_challenge_and_at_most_one_version(key, valid):
    assert rv.known_key(key, (CHALLENGE,)) is valid


# --- rebuild noise and control -----------------------------------------------------------------------------------------


def test_a_versions_own_noise_is_read_first_and_no_other_version_moves(tmp_path):
    path = _noise_file(
        tmp_path,
        {CHALLENGE: _noise(0.01, OLD), f"{CHALLENGE} 1.8": _noise(0.02, NEW)},
    )
    assert kr.rebuild_noise(CHALLENGE, path=path, version="1.8")["value"] == 0.02
    # 1.5 (and no version at all) still read the Challenge's value
    assert kr.rebuild_noise(CHALLENGE, path=path, version="1.5")["value"] == 0.01
    assert kr.rebuild_noise(CHALLENGE, path=path)["value"] == 0.01
    # the served version is the default
    rv.serve(CHALLENGE, "1.8")
    assert kr.rebuild_noise(CHALLENGE, path=path)["value"] == 0.02


def test_a_version_with_no_entry_of_its_own_reads_the_challenge(tmp_path):
    path = _noise_file(tmp_path, {CHALLENGE: _noise(0.01, OLD)})
    assert kr.rebuild_noise(CHALLENGE, path=path, version="1.8")["value"] == 0.01


def test_a_version_entry_alone_leaves_the_bare_challenge_unregistered(tmp_path):
    path = _noise_file(tmp_path, {f"{CHALLENGE} 1.8": _noise(0.02, NEW)})
    assert kr.rebuild_noise(CHALLENGE, path=path) is None
    assert kr.rebuild_noise(CHALLENGE, path=path, version="1.5") is None
    assert kr.rebuild_noise(CHALLENGE, path=path, version="1.8")["value"] == 0.02


def test_a_misspelled_versioned_key_refuses(tmp_path):
    path = _noise_file(tmp_path, {"electric-motor-magnetic 1.8": _noise(0.02, NEW)})
    with pytest.raises(kr.RegistryInvalid):
        kr.rebuild_noise(CHALLENGE, path=path)


def test_the_control_is_the_versions_own(tmp_path):
    control = {
        "entry_id": digest("a control"),
        "reference_total": 0.5,
        "reference_fingerprint": digest("a fingerprint"),
        "control_basis": "bit_identical",
        "evaluation_pack_digest": digest("the 1.8 pack"),
    }
    path = _noise_file(
        tmp_path,
        {
            CHALLENGE: _noise(0.01, OLD),
            f"{CHALLENGE} 1.8": {**_noise(0.02, NEW), "control": control},
        },
    )
    assert kr.control(CHALLENGE, path=path, version="1.8") == control
    assert kr.control(CHALLENGE, path=path, version="1.5") is None
    assert "control" not in kr.rebuild_noise(CHALLENGE, path=path, version="1.8")


# --- crown_average: N and margin_N ----------------------------------------------------------------------------------------


def test_a_versions_own_margin_is_read_first_and_no_other_version_moves(tmp_path):
    rule = _rule(
        tmp_path,
        {CHALLENGE: _margin(0.0025, OLD), f"{CHALLENGE} 1.8": _margin(0.004, NEW)},
    )
    assert rule.margin_for(CHALLENGE, "1.8") == 0.004
    assert rule.margin_digest_for(CHALLENGE, "1.8") == NEW
    assert rule.margin_for(CHALLENGE, "1.5") == 0.0025
    assert rule.margin_for(CHALLENGE) == 0.0025
    assert rule.margin_digest_for(CHALLENGE) == OLD
    rv.serve(CHALLENGE, "1.8")
    assert rule.margin_for(CHALLENGE) == 0.004


def test_a_versions_margin_at_another_n_is_never_replaced_by_the_challenges(tmp_path):
    """A stale version entry is UNAVAILABLE (None), never silently the 1.5-era value."""
    rule = _rule(
        tmp_path,
        {CHALLENGE: _margin(0.0025, OLD), f"{CHALLENGE} 1.8": _margin(0.004, NEW, 7)},
    )
    assert rule.margin_for(CHALLENGE, "1.8") is None
    assert rule.margin_for(CHALLENGE, "1.5") == 0.0025


def test_a_versions_own_n_applies_and_the_others_keep_the_default(tmp_path):
    rule = _rule(
        tmp_path,
        {f"{CHALLENGE} 1.8": _margin(0.004, NEW, 12)},
        challenge_n={f"{CHALLENGE} 1.8": 12},
    )
    assert rule.n_for(CHALLENGE, "1.8") == 12
    assert rule.n_for(CHALLENGE, "1.5") == 10
    assert rule.n_for(CHALLENGE) == 10
    assert rule.margin_for(CHALLENGE, "1.8") == 0.004
    assert rule.margin_for(CHALLENGE, "1.5") is None  # no 1.5 entry at all


@pytest.mark.parametrize(
    "key", ["not-a-challenge 1.8", f"{CHALLENGE} ", f"{CHALLENGE} 1 8"]
)
def test_a_malformed_margin_or_n_key_refuses(tmp_path, key):
    with pytest.raises(ca.CrownAverageInvalid):
        _rule(tmp_path, {key: _margin(0.004, NEW)})
    with pytest.raises(ca.CrownAverageInvalid):
        _rule(tmp_path, {}, challenge_n={key: 5})


# --- the committed registries read exactly as before ----------------------------------------------------------------------


def test_every_committed_entry_reads_the_same_for_any_version():
    """Bare ids only: a version lookup falls back to the Challenge's entry, so no value moves."""
    document = json.loads(kr.REGISTRY.read_bytes())
    rule = ca.load_rule()
    for challenge in document["challenges"]:
        assert " " not in challenge
        for version in ("1.5", "1.8", "2.0"):
            assert kr.rebuild_noise(challenge, version=version) == kr.rebuild_noise(
                challenge
            )
            assert rule.margin_for(challenge, version) == rule.margin_for(challenge)
            assert rule.n_for(challenge, version) == rule.n_for(challenge)


# --- the crown floor pins the version's own noise and margin -----------------------------------------------------------------


def test_a_floor_pins_the_versions_own_noise_and_margin(tmp_path):
    pack = digest("a sealed pack")
    exam = {"version": "1.8", "epoch": "E1", "evaluation_pack_digest": pack}
    floors = tmp_path / "crown_floor.json"
    floors.write_text(
        json.dumps(
            {
                "schema": kr.FLOOR_SCHEMA,
                "floors": [
                    {
                        "challenge": CHALLENGE,
                        "version": "1.8",
                        "epoch": "E1",
                        "evaluation_pack_digest": pack,
                        "value": 0.3,
                        "measurement_digest": digest("the floor measurement"),
                        "rebuild_noise_measurement_digest": NEW,
                        "crown_margin_measurement_digest": NEW,
                    }
                ],
            }
        )
    )
    only_old_noise = _noise_file(tmp_path, {CHALLENGE: _noise(0.01, OLD)})
    old_margin_path = tmp_path / "old_margin.json"
    old_margin_path.write_text(
        json.dumps(
            {
                "schema": ca.SCHEMA,
                "rule_version": "crown-average-v1",
                "n": 10,
                "challenge_n": {},
                "seed_range": 2147483647,
                "margins": {CHALLENGE: _margin(0.0025, OLD)},
            }
        )
    )
    # only the 1.5-era noise and margin are registered: the 1.8 floor is NOT found (no crown before 1.8's own)
    assert (
        kr.registered_floor(
            CHALLENGE,
            exam,
            path=floors,
            noise_path=only_old_noise,
            margin_path=old_margin_path,
        )
        is None
    )
    # 1.8's own noise and margin are registered beside the 1.5-era ones: the floor is found
    new_noise = _noise_file(
        tmp_path,
        {CHALLENGE: _noise(0.01, OLD), f"{CHALLENGE} 1.8": _noise(0.02, NEW)},
    )
    new_margin_path = tmp_path / "new_margin.json"
    new_margin_path.write_text(
        json.dumps(
            {
                "schema": ca.SCHEMA,
                "rule_version": "crown-average-v1",
                "n": 10,
                "challenge_n": {},
                "seed_range": 2147483647,
                "margins": {
                    CHALLENGE: _margin(0.0025, OLD),
                    f"{CHALLENGE} 1.8": _margin(0.004, NEW),
                },
            }
        )
    )
    assert (
        kr.registered_floor(
            CHALLENGE,
            exam,
            path=floors,
            noise_path=new_noise,
            margin_path=new_margin_path,
        )
        == 0.3
    )


# --- the comparator and the call sites ----------------------------------------------------------------------------------------


def test_the_comparator_carries_the_versions_noise(tmp_path, monkeypatch):
    from carbon.scoring import physical_dual_pack

    monkeypatch.setattr(
        physical_dual_pack, "minimum_source_entry_ids", lambda definition: []
    )
    path = _noise_file(
        tmp_path,
        {CHALLENGE: _noise(0.01, OLD), f"{CHALLENGE} 1.8": _noise(0.02, NEW)},
    )
    pack = {
        "pack_digest": digest("p"),
        "legs": {"A": {"minimum": None}, "D": {"minimum": None}},
    }
    for version, value in (("1.8", 0.02), ("1.5", 0.01), (None, 0.01)):
        found = kr.comparator(CHALLENGE, pack, {}, path=path, version=version)
        assert found["rebuild_noise"]["value"] == value


def test_the_ladder_step_reads_the_versions_noise(tmp_path, monkeypatch):
    path = _noise_file(
        tmp_path,
        {CHALLENGE: _noise(0.03, OLD), f"{CHALLENGE} 1.8": _noise(0.09, NEW)},
    )
    real = kr.rebuild_noise
    seen = []

    def fake(challenge_id, *, version=None):
        seen.append((challenge_id, version))
        return real(challenge_id, path=path, version=version)

    monkeypatch.setattr(kr, "rebuild_noise", fake)
    adapter = SimpleNamespace(
        discovery=SimpleNamespace(
            info=SimpleNamespace(
                challenge_key=SimpleNamespace(challenge_id=CHALLENGE, version="1.8")
            )
        )
    )
    step = lrr._timing_step(adapter)
    assert seen == [(CHALLENGE, "1.8")]
    from carbon.scoring import grade_feedback

    assert step == grade_feedback.step(0.09)


def test_every_decision_call_site_passes_the_version():
    source = (
        ROOT / "carbon" / "challenge_validator" / "lean_recipe_retention.py"
    ).read_text(encoding="utf-8")
    assert (
        source.count("version=adapter.challenge_version") >= 4
    )  # 3 comparators + control
    receiver = (
        ROOT / "carbon" / "challenge_validator" / "direct_receiver.py"
    ).read_text(encoding="utf-8")
    hold = receiver.index(
        "crown_hold.install(challenge.challenge_id, challenge.version)"
    )
    assert (
        "registry_version.serve(challenge.challenge_id, challenge.version)"
        in receiver[hold : hold + 600]
    )
