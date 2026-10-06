"""Graphite's neutral plumbing for a named Challenge (VALIDATOR-05).

Pins:
- each Challenge's published material is its own checkout allowlist, battery's
  byte-identical; an unknown Challenge is refused; the scoring adapter may
  supply its own list (`ChallengeScoring.published_material`), and the
  boundary's denylist still wins;
- the phase-3 Constructor and the phase-4 Attacker check out the session
  Challenge's material, never battery's by default;
- bundle and rebuild text names no Challenge; a cooling bundle's writeup
  renders the cooling rule end to end (fixture dry run only). The agents'
  tool text is part of every recorded plan, so it changes only as a
  versioned role record, not here.

No pod, key, network or spend.
"""

import json
from pathlib import Path

import pytest

from carbon.agent_campaign import boundaries
from carbon.agent_campaign.graphite import phase3, phase4
from carbon.challenge_validator import scoring as cs

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = "battery-fastcharge-ageing-development-v1"
COOLING = "chip-cold-plate"
MOTOR = "electric-motor-magnetics"


def test_each_challenge_has_its_own_published_material():
    assert boundaries.published_material(BATTERY) is boundaries._PUBLISHED_CHALLENGE
    assert boundaries.ALLOWLIST[boundaries.Role.CONSTRUCTION] == (
        boundaries._PUBLISHED_CHALLENGE
    )
    for challenge in (BATTERY, COOLING, MOTOR):
        paths = boundaries.published_material(challenge)
        assert "carbon/reconstruction/capability_registry.py" in paths
        assert "carbon/schema/strategy.py" in paths
        # Every listed file exists and passes the denylist.
        manifest = boundaries.checkout_manifest(
            REPOSITORY, boundaries.Role.CONSTRUCTION, paths
        )
        assert len(manifest["files"]) == len(paths)
    cooling = boundaries.published_material(COOLING)
    assert not any("battery" in p or "motor" in p for p in cooling)
    motor = boundaries.published_material(MOTOR)
    assert not any("battery" in p or "cold_plate" in p for p in motor)
    for unknown in ("not-a-challenge", None, BATTERY.upper()):
        with pytest.raises(
            boundaries.BoundaryError, match="challenge_material_not_registered"
        ):
            boundaries.published_material(unknown)


def test_battery_checkout_is_unchanged():
    default = boundaries.checkout_manifest(REPOSITORY, boundaries.Role.CONSTRUCTION)
    named = boundaries.checkout_manifest(
        REPOSITORY,
        boundaries.Role.CONSTRUCTION,
        cs.scoring_for(BATTERY).published_material(),
    )
    assert boundaries.manifest_digest(named) == boundaries.manifest_digest(default)


def test_the_scoring_hook_supplies_the_list_and_the_denylist_still_wins(monkeypatch):
    cooling = cs.scoring_for(COOLING)
    assert cs.published_material(COOLING) == boundaries.published_material(COOLING)
    # A Challenge with no registered scoring falls back to the boundary's list.
    assert cs.published_material(MOTOR) == boundaries.published_material(MOTOR)
    narrowed = ("carbon/cold_plate/domain.py", "carbon/schema/strategy.py")
    monkeypatch.setattr(type(cooling), "published_material", lambda self: narrowed)
    assert cs.published_material(COOLING) == narrowed
    monkeypatch.setattr(
        type(cooling),
        "published_material",
        lambda self: ("docs/development/evidence/cold-plate-pools-v1/train.jsonl",),
    )
    with pytest.raises(boundaries.BoundaryError, match="checkout_path_denied"):
        boundaries.checkout_manifest(
            REPOSITORY, boundaries.Role.CONSTRUCTION, cooling.published_material()
        )


def _brief_digest(scoring):
    from graphite_phase3_fixtures import grant

    from carbon.agent_campaign.graphite import experiment as ex

    brief = phase3.session_brief(
        checkout_commit="1" * 40,
        budget=ex.phase3_budget(grant(), scoring),
        scoring=scoring,
    )
    return brief.checkout_manifest_digest


def test_the_constructor_checks_out_its_own_challenge():
    for challenge in (BATTERY, COOLING):
        scoring = cs.scoring_for(challenge)
        expected = boundaries.manifest_digest(
            boundaries.checkout_manifest(
                REPOSITORY,
                boundaries.Role.CONSTRUCTION,
                boundaries.published_material(challenge),
            )
        )
        assert _brief_digest(scoring) == expected
    assert _brief_digest(cs.scoring_for(COOLING)) != _brief_digest(
        cs.scoring_for(BATTERY)
    )


def test_the_attacker_checks_out_the_attacked_challenge():
    from carbon.agent_campaign.attack import adapter as attack

    seen = set()
    for (challenge, _level), adapter in sorted(attack.ADAPTERS.items()):
        if challenge not in boundaries.PUBLISHED_MATERIAL:
            continue
        brief = phase4.session_brief(adapter, checkout_commit="1" * 40)
        expected = boundaries.manifest_digest(
            boundaries.checkout_manifest(
                REPOSITORY,
                boundaries.Role.ADVERSARIAL,
                cs.published_material(challenge),
            )
        )
        assert brief.checkout_manifest_digest == expected
        seen.add(challenge)
    assert BATTERY in seen and COOLING in seen


def test_a_cooling_bundle_reads_as_cooling(tmp_path, capsys, monkeypatch):
    import containment_double

    # The dry run's carrier containment check (synthetic passing double).
    containment_double.install(monkeypatch)
    assert phase3.dry_run(tmp_path, cs.scoring_for(COOLING)) == 0
    output = capsys.readouterr().out
    result = json.loads(output[output.index("{\n") :])
    delivery = result["delivery"]
    assert delivery["clean_rebuild"]["status"] == "REBUILT"
    bundle = Path(delivery["bundle"])
    writeup = (bundle / "WRITEUP.md").read_text()
    rule = cs.scoring_for(COOLING).frozen_rule(REPOSITORY).identity["rule"]
    assert f"(`{rule}`)" in writeup
    rebuild = (bundle / "REBUILD.md").read_text()
    for text in (writeup, rebuild):
        assert "battery" not in text.lower()
        assert "rule v2" not in text
