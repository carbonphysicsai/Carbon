"""A miner sees the validator's outcome for their own submission.

Found in the live battery journey (Launchpad H, 2026-09-29): the validator
scored and nominated the submission, the campaign held its permitted
feedback, and the Control Center still said "no independent result
available", because only the retired Burgers comparison pointer was read.
Synthetic feedback documents; the projection code is real.
"""

import json

from carbon.challenge_registry.campaigns import campaign_for_id
from scripts.dev.miner_launchpad.projection import _validator_outcome

# The schema comes from the Challenge's own campaign (C-MLP-04).
BATTERY_FEEDBACK_SCHEMA = campaign_for_id(
    "battery-fastcharge-ageing-development-v1"
).feedback_schema


def feedback(tmp_path, epoch=1, **outcome_changes):
    outcome = {
        "schema": "carbon.battery.evaluation-feedback.v1",
        "submission_id": "bsub-" + "a" * 32,
        "challenge": {"id": "battery-fastcharge-ageing-development-v1"},
        "state": "SCORED",
        "evidence": "DEVELOPMENT_SHADOW",
        "rule": "fixture-rule",
        "qualification": False,
        "reward": False,
        "recipe_digest": "sha256:" + "b" * 64,
        "contract_digest": "sha256:" + "c" * 64,
        "reconstruction": {"backend": "ISOLATED_CARRIER", "validator_path": True},
        "screening": {
            "eligible": True,
            "gates_failed": [],
            "cases": {"scored": 300, "reference_invalid": 0, "failed_infra": 0},
            "score": 0.5,
            "important_score": 0.25,
            "pool_version": 0,
        },
        "nominated": True,
        "finals": [{"state": "FROZEN", "promoted": False, "outcome": None}],
        **outcome_changes,
    }
    path = tmp_path / "permitted-final-feedback.json"
    path.write_text(
        json.dumps(
            {
                "schema": BATTERY_FEEDBACK_SCHEMA,
                "epoch": epoch,
                "official_eligible": False,
                "reward": False,
                "outcome": outcome,
            }
        )
    )
    return path


def test_the_scored_outcome_is_shown(tmp_path):
    shown = _validator_outcome(1, feedback(tmp_path))
    assert shown["status"] == "VALIDATOR_OUTCOME"
    result = shown["result"]
    assert result["state"] == "SCORED"
    assert result["nominated"] is True
    assert result["screening"]["eligible"] is True
    assert result["screening"]["cases"]["scored"] == 300
    assert result["finals"] == [{"state": "FROZEN", "promoted": False}]
    assert result["qualification"] is False and result["reward"] is False


def test_a_field_outside_the_allow_list_is_never_shown(tmp_path):
    path = feedback(tmp_path, private_rebuild_seed="PRIVATE-SENTINEL")
    # Specimen: the sentinel is in the file the projection reads.
    assert "PRIVATE-SENTINEL" in path.read_text()
    assert "PRIVATE-SENTINEL" not in json.dumps(_validator_outcome(1, path))


def test_a_differing_file_is_readback_unavailable_not_guessed(tmp_path):
    for path, epoch in (
        (feedback(tmp_path, epoch=2), 1),  # another epoch's file
        (feedback(tmp_path, state=None), 1),  # no state
    ):
        assert _validator_outcome(epoch, path)["status"] == "READBACK_UNAVAILABLE"
    wrong = tmp_path / "other.json"
    wrong.write_text(
        json.dumps({"schema": "carbon.other.v1", "epoch": 1, "outcome": {}})
    )
    assert _validator_outcome(1, wrong)["status"] == "READBACK_UNAVAILABLE"


def test_a_withheld_view_shows_no_score(tmp_path):
    """SCORE_WITHHELD feedback omits score-bearing values; nothing is filled in."""
    shown = _validator_outcome(
        1, feedback(tmp_path, screening={"eligible": True, "gates_failed": []})
    )
    assert "score" not in shown["result"]["screening"]
    assert "cases" not in shown["result"]["screening"]
