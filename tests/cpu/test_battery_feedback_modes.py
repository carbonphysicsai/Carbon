"""The battery campaign's feedback modes: the pre-registered control arm.

docs/development/BATTERY_AGENT_CAMPAIGN_PREREGISTRATION.md section 2: arm B
is the same agent at the same budget, seeing admissibility and failed gate
names but no score. Every absence asserted here is paired with the same
value's presence in the full view, so a check that could never fail would
show up as a failing specimen.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.battery import campaign

SCORE, IMPORTANT = 0.123456, 0.654321


def feedback():
    """A realistic permitted feedback, shaped like the daemon's outcome."""
    return {
        "schema": "carbon.battery.permitted-feedback.v1",
        "epoch": 1,
        "outcome": {
            "schema": "carbon.battery.submission-outcome.v1",
            "submission_id": "sub-1",
            "challenge": {"id": "battery-fastcharge-ageing-development-v1"},
            "state": "SCREENED",
            "evidence": "DEVELOPMENT_SHADOW",
            "rule": "PROVISIONAL_DEVELOPMENT_NON_PAYING",
            "qualification": False,
            "reward": False,
            "recipe_digest": "sha256:" + "a" * 64,
            "contract_digest": "sha256:" + "b" * 64,
            "reconstruction": {"backend": "carrier", "validator_path": True},
            "screening": {
                "pool_version": 3,
                "eligible": False,
                "score": SCORE,
                "important_score": IMPORTANT,
                "gates_failed": ["voltage_ceiling"],
                "cases": {"scored": 300, "reference_invalid": 0, "failed_infra": 0},
            },
            "nominated": True,
            "finals": [
                {"state": "DECIDED", "outcome": "IMPROVEMENT", "promoted": True}
            ],
        },
        "official_eligible": False,
        "reward": False,
    }


def prepared(mode=None):
    manifest = {"provider": {"agent": "autonomous"}}
    if mode is not None:
        manifest["feedback_mode"] = mode
    return SimpleNamespace(manifest=manifest)


def shown(mode, fb):
    return campaign.agent_observation(prepared(mode), 2, fb)[
        "prior_permitted_evaluation_feedback"
    ]


def test_withheld_feedback_keeps_admissibility_and_drops_every_score_value():
    full = json.dumps(shown(campaign.FEEDBACK_FULL, feedback()), sort_keys=True)
    blind_view = shown(campaign.FEEDBACK_SCORE_WITHHELD, feedback())
    blind = json.dumps(blind_view, sort_keys=True)
    for marker in (
        str(SCORE),
        str(IMPORTANT),
        '"nominated"',
        '"finals"',
        '"pool_version"',
        '"scored"',
    ):
        assert marker in full, marker  # the specimen: the check can find it
        assert marker not in blind, marker
    outcome = blind_view["outcome"]
    assert outcome["screening"] == {
        "eligible": False,
        "gates_failed": ["voltage_ceiling"],
    }
    assert outcome["state"] == "SCREENED"
    assert blind_view["feedback_mode"] == campaign.FEEDBACK_SCORE_WITHHELD


def test_the_withheld_view_is_an_allow_list_so_new_fields_stay_hidden():
    fb = feedback()
    fb["outcome"]["ranking_hint"] = "LEADER"
    fb["outcome"]["screening"]["percentile"] = 97
    full = json.dumps(shown(None, fb))
    blind = json.dumps(shown(campaign.FEEDBACK_SCORE_WITHHELD, fb))
    for marker in ("LEADER", "percentile"):
        assert marker in full
        assert marker not in blind


def test_a_manifest_without_the_setting_shows_the_full_feedback():
    """Campaigns frozen before this change keep their behaviour exactly."""
    assert shown(None, feedback()) == feedback()


def test_the_first_epoch_has_no_feedback_in_either_mode():
    for mode in campaign.FEEDBACK_MODES:
        assert shown(mode, None) is None


def test_an_unknown_mode_is_refused_even_before_there_is_feedback():
    with pytest.raises(ValueError, match="unknown battery feedback mode"):
        shown("SCORE_ONLY", None)
    with pytest.raises(ValueError, match="unknown battery feedback mode"):
        campaign.feedback_mode(None)


def test_the_manifest_records_the_mode_and_refuses_an_unknown_one():
    product = SimpleNamespace(
        campaign_id="c1",
        agent="none",
        budget={},
        manifest_fields=lambda: {"campaign_id": "c1"},
    )
    common = {"owner": "o", "implementation": {"commit": "x"}, "images": ["i"]}
    assert campaign.manifest_document(product, **common)["feedback_mode"] == "FULL"
    blind = campaign.manifest_document(
        product, feedback=campaign.FEEDBACK_SCORE_WITHHELD, **common
    )
    assert blind["feedback_mode"] == "SCORE_WITHHELD"
    with pytest.raises(ValueError, match="unknown battery feedback mode"):
        campaign.manifest_document(product, feedback="NONE", **common)


#: The leak ladder (v2 section 7; amendment 4), lowest rung first. Each rung's
#: screening view, and the markers the rung above it adds.
LADDER = (
    (campaign.FEEDBACK_ELIGIBILITY_ONLY, {"eligible": False}),
    (
        campaign.FEEDBACK_SCORE_WITHHELD,
        {"eligible": False, "gates_failed": ["voltage_ceiling"]},
    ),
    (
        campaign.FEEDBACK_AGGREGATE_SCORE,
        {
            "eligible": False,
            "gates_failed": ["voltage_ceiling"],
            "score": SCORE,
            "important_score": IMPORTANT,
        },
    ),
)


@pytest.mark.parametrize(("mode", "screening"), LADDER)
def test_each_restricted_rung_shows_exactly_its_screening_fields(mode, screening):
    view = shown(mode, feedback())
    assert view["outcome"]["screening"] == screening
    assert view["feedback_mode"] == mode
    assert view["outcome"]["state"] == "SCREENED"


def test_each_rung_adds_only_its_channel_over_the_rung_below():
    """Rung 1 withholds the gate names that rung 2 shows; rung 2 withholds the
    scores that rung 3 shows; rung 3 withholds what only FULL shows. Each
    absence is paired with the next rung showing it (the specimen)."""
    adds = (
        (
            campaign.FEEDBACK_ELIGIBILITY_ONLY,
            campaign.FEEDBACK_SCORE_WITHHELD,
            ('"gates_failed"', "voltage_ceiling"),
        ),
        (
            campaign.FEEDBACK_SCORE_WITHHELD,
            campaign.FEEDBACK_AGGREGATE_SCORE,
            (str(SCORE), str(IMPORTANT)),
        ),
        (
            campaign.FEEDBACK_AGGREGATE_SCORE,
            campaign.FEEDBACK_FULL,
            ('"pool_version"', '"scored"', '"nominated"', '"finals"'),
        ),
    )
    for lower, upper, markers in adds:
        below = json.dumps(shown(lower, feedback()), sort_keys=True)
        above = json.dumps(shown(upper, feedback()), sort_keys=True)
        for marker in markers:
            assert marker in above, (upper, marker)
            assert marker not in below, (lower, marker)


@pytest.mark.parametrize("mode", [mode for mode, _ in LADDER])
def test_every_restricted_rung_is_an_allow_list(mode):
    fb = feedback()
    fb["outcome"]["ranking_hint"] = "LEADER"
    fb["outcome"]["screening"]["percentile"] = 97
    full = json.dumps(shown(campaign.FEEDBACK_FULL, fb))
    restricted = json.dumps(shown(mode, fb))
    for marker in ("LEADER", "percentile"):
        assert marker in full
        assert marker not in restricted


def test_the_score_withheld_view_is_unchanged_by_the_ladder():
    """Arm B campaigns frozen before the ladder keep their exact view."""
    assert campaign.withheld_feedback(feedback()) == campaign.restricted_feedback(
        feedback(), campaign.FEEDBACK_SCORE_WITHHELD
    )
    assert campaign.withheld_feedback(feedback())["withheld"] == (
        "scores, case counts, pool version, nomination and finals"
    )
