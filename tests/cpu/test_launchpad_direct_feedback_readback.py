"""A direct (receiver-rebuilt) campaign's permitted feedback carries its outcome as
`result` and names no epoch; the Submission view reads it instead of reporting
READBACK_UNAVAILABLE (U48). A file for another epoch is still refused."""

import json

from scripts.dev.miner_launchpad import projection

DOCUMENT = {
    "challenge": {"id": "electric-motor-magnetics", "version": "1.3"},
    "exam_feedback": {"best": None, "latest": None},
    "result": {
        "evidence": "DEVELOPMENT_PUBLIC_PHYSICAL",
        "qualification": False,
        "reward": False,
        "schema": "carbon.lean-recipe-development-outcome.v1",
        "state": "RECONSTRUCTED",
        "submission_id": "rtsk_" + "ab" * 32,
    },
    "schema": "carbon.motor.permitted-feedback.v1",
}


def write(tmp_path, document):
    path = tmp_path / "permitted-final-feedback.json"
    path.write_text(json.dumps(document))
    return path


def test_a_direct_result_is_read_back(tmp_path):
    found = projection._validator_outcome(1, write(tmp_path, DOCUMENT))
    assert found["status"] == "VALIDATOR_OUTCOME"
    assert found["result"]["state"] == "RECONSTRUCTED"
    assert (
        found["result"]["qualification"] is False and found["result"]["reward"] is False
    )


def test_another_epoch_and_an_unknown_schema_stay_unavailable(tmp_path):
    other = {**DOCUMENT, "epoch": 2}
    assert (
        projection._validator_outcome(1, write(tmp_path, other))["status"]
        == "READBACK_UNAVAILABLE"
    )
    odd = {**DOCUMENT, "schema": "carbon.unknown.v1"}
    assert (
        projection._validator_outcome(1, write(tmp_path, odd))["status"]
        == "READBACK_UNAVAILABLE"
    )
