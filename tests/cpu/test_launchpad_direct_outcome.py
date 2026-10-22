"""M1 E2E U53: a direct campaign's submit read "readback unavailable".

A direct campaign's permitted feedback (Motor, Cooling, the direct versions)
carries its outcome as `result` beside the Ladder (`exam_feedback`) and no
epoch field; the projection read only the Battery shape. It now reads both,
and shows the Ladder as the display rule says: one graded total, A and D as
detail, a gate failure as not eligible.
"""

from __future__ import annotations

import json

from scripts.dev.miner_launchpad import projection

LADDER = {
    "schema": "carbon.private-exam.ladder-feedback.v1",
    "exam_version": "motor-1.3-dev",
    "status": "IMPROVED",
    "total": 0.5488,
    "A": 0.298,
    "D": 0.8,
    "gate_names": [],
}


def _document(exam_feedback):
    return {
        "schema": "carbon.motor.permitted-feedback.v1",
        "challenge": {"id": "electric-motor-magnetics", "version": "1.3"},
        "recipe_digest": "sha256:" + "a" * 64,
        "result": {
            "state": "SCORED",
            "evidence": "DEVELOPMENT",
            "qualification": False,
            "reward": False,
        },
        "exam_feedback": exam_feedback,
    }


def _project(tmp_path, document):
    path = tmp_path / "permitted-final-feedback.json"
    path.write_text(json.dumps(document))
    return projection._validator_outcome(1, path)


def test_a_direct_outcome_is_read_with_its_grade(tmp_path):
    shown = _project(tmp_path, _document({"best": LADDER, "latest": LADDER}))
    assert shown["status"] == "VALIDATOR_OUTCOME"
    assert shown["result"]["state"] == "SCORED"
    grade = shown["result"]["grade"]
    assert grade["latest"] == {
        "status": "IMPROVED",
        "total": 0.5488,
        "A": 0.298,
        "D": 0.8,
        "exam_version": "motor-1.3-dev",
    }
    assert grade["best"]["total"] == 0.5488
    assert "gate_names" not in grade["latest"]


def test_a_direct_outcome_before_any_grade_says_none_yet(tmp_path):
    shown = _project(tmp_path, _document({"best": None, "latest": None}))
    assert shown["result"]["grade"] == {
        "latest": None,
        "best": None,
        "submission": "sha256:" + "a" * 64,
    }


def test_a_battery_shaped_outcome_is_unchanged(tmp_path):
    document = {
        "schema": "carbon.battery.permitted-feedback.v1",
        "epoch": 1,
        "outcome": {"state": "SCORED", "evidence": "DEVELOPMENT"},
    }
    shown = _project(tmp_path, document)
    assert shown["status"] == "VALIDATOR_OUTCOME"
    assert "grade" not in shown["result"]


# --- U53 part 2: "Check for result" reads the Ladder again ------------------


def _submitted(tmp_path, monkeypatch, ladder_at_submit):
    from types import SimpleNamespace

    from carbon.development_session import direct_submission as ds

    digest = "sha256:" + "a" * 64
    monkeypatch.setattr(
        ds.ConstructionRecipe,
        "from_dict",
        staticmethod(lambda value: SimpleNamespace(digest=digest)),
    )
    folder = tmp_path / "epoch-1"
    folder.mkdir()
    (folder / "selected-recipe.json").write_text(json.dumps({"strategy": {}}))
    (folder / "permitted-final-feedback.json").write_text(
        json.dumps(_document(ladder_at_submit))
    )
    (tmp_path / "construction-intake-epoch-1.json").write_text(
        json.dumps(
            {
                "schema": ds.RECORD_SCHEMA,
                "url": "http://127.0.0.1:8769",
                "epoch": 1,
                "receiver": "receiver-hotkey",
                "context": {
                    "network": "testnet",
                    "endpoint": "wss://chain.example",
                    "provider": "fixture",
                    "genesis_hash": "0x" + "1" * 64,
                    "netuid": 567,
                },
                "recipe_digest": digest,
                "contract_digest": "sha256:" + "c" * 64,
            }
        )
    )
    return ds, folder


def test_check_for_result_stores_the_fresh_ladder_and_the_page_shows_it(
    tmp_path, monkeypatch
):
    ds, folder = _submitted(tmp_path, monkeypatch, {"best": None, "latest": None})
    asked = []

    def read(url, signer, **kwargs):
        asked.append((url, signer, kwargs["receiver"], kwargs["contract_digest"]))
        return {"best": LADDER, "latest": LADDER}

    monkeypatch.setattr(ds, "read_exam_feedback", read)
    ladder = ds.refresh_exam_feedback(tmp_path, 1, "miner-signer")
    assert ladder["latest"] == LADDER
    # Everything the read binds comes from the epoch's own admission record.
    assert asked == [
        (
            "http://127.0.0.1:8769",
            "miner-signer",
            "receiver-hotkey",
            "sha256:" + "c" * 64,
        )
    ]
    assert (folder / ds.EXAM_FEEDBACK_FILE).is_file()
    shown = projection._validator_outcome(1, folder / "permitted-final-feedback.json")
    assert shown["result"]["grade"]["latest"]["total"] == 0.5488


def test_a_stored_read_of_another_recipe_is_not_shown(tmp_path, monkeypatch):
    ds, folder = _submitted(tmp_path, monkeypatch, {"best": None, "latest": None})
    (folder / ds.EXAM_FEEDBACK_FILE).write_text(
        json.dumps(
            {
                "schema": ds.EXAM_FEEDBACK_SCHEMA,
                "epoch": 1,
                "recipe_digest": "sha256:" + "f" * 64,
                "exam_feedback": {"best": LADDER, "latest": LADDER},
            }
        )
    )
    shown = projection._validator_outcome(1, folder / "permitted-final-feedback.json")
    assert shown["result"]["grade"] == {
        "latest": None,
        "best": None,
        "submission": "sha256:" + "a" * 64,
    }


def test_check_for_result_without_an_admission_record_is_refused(tmp_path, monkeypatch):
    import pytest

    ds, _folder = _submitted(tmp_path, monkeypatch, {"best": None, "latest": None})
    (tmp_path / "construction-intake-epoch-1.json").unlink()
    with pytest.raises(ds.DirectIntakeRefusal) as refused:
        ds.refresh_exam_feedback(tmp_path, 1, "miner-signer")
    assert refused.value.code == "construction_admission_record_required"


def test_the_research_view_shows_a_direct_outcome_and_its_grade():
    # M1 E2E U53 (browser): the Submission tab read "withheld" for every
    # direct campaign, whose research views name no feedback fields.
    from types import SimpleNamespace

    from scripts.dev.miner_launchpad.campaign_view import outcomes

    view = SimpleNamespace(feedback_fields=lambda mode: None)
    own = {
        "final_results": [
            {
                "epoch": 1,
                "status": "VALIDATOR_OUTCOME",
                "result": {
                    "state": "SCORED",
                    "grade": {"latest": {"status": "IMPROVED", "total": 0.5488}},
                    "secret": "never shown",
                },
            }
        ]
    }
    (entry,) = outcomes(own, view, "FULL")
    assert entry["result"]["grade"]["latest"]["total"] == 0.5488
    assert "withheld" not in entry["result"] and "secret" not in entry["result"]


def test_a_v3_grade_shows_only_on_the_submit_it_is_about(tmp_path):
    # M1 E2E U63: a hotkey's earlier grade read as a newer submit's.
    other = {
        **LADDER,
        "schema": "carbon.private-exam.ladder-feedback.v3",
        "recipe_digest": "sha256:" + "b" * 64,
        "epoch": 1,
    }
    mine = {**other, "recipe_digest": "sha256:" + "a" * 64, "epoch": 2}
    shown = _project(tmp_path, _document({"best": other, "latest": other}))
    grade = shown["result"]["grade"]
    assert grade["latest"] is None
    assert grade["best"]["recipe_digest"] == "sha256:" + "b" * 64
    (tmp_path / "permitted-final-feedback.json").unlink()
    shown = _project(tmp_path, _document({"best": other, "latest": mine}))
    assert shown["result"]["grade"]["latest"]["epoch"] == 2


def test_two_campaigns_freezing_one_recipe_never_share_a_request_id(tmp_path):
    # M1 E2E H16: the request id was epoch + recipe only, so a second campaign
    # on the same hotkey read TRANSPORT_CONFLICT forever.
    from types import SimpleNamespace

    from carbon.development_session import direct_submission as ds

    recipe = SimpleNamespace(digest="sha256:" + "8" * 64)
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    a = ds._submit_request(first, 1, recipe)
    assert a == ds._submit_request(first, 1, recipe)  # exact replay
    assert a != ds._submit_request(second, 1, recipe)
    assert len(a) <= 128
    ds._bump_submit_attempt(first, 1)
    assert ds._submit_request(first, 1, recipe) == a + "-r1"


def test_a_direct_freezes_epoch_outcome_is_read(tmp_path):
    # M1 E2E H20: the direct record's schema replaced the outcome's, so the
    # epoch read READBACK_UNAVAILABLE while its result was graded.
    import json as _json

    path = tmp_path / "outcome.json"
    written = {
        "schema": "carbon.direct-selected-recipe.v2",
        "epoch": 1,
        "status": "SELECTED",
        "reason": "practiced",
        "selected_by": "miner",
    }
    path.write_text(_json.dumps(written))
    shown = projection._epoch_outcome(1, path)
    assert shown["status"] == "SELECTED" and shown["selected_by"] == "miner"
    # Not another epoch's file, and not a foreign shape.
    assert projection._epoch_outcome(2, path)["status"] == "READBACK_UNAVAILABLE"
    path.write_text(_json.dumps({**written, "selected_by": "agent"}))
    assert projection._epoch_outcome(1, path)["status"] == "READBACK_UNAVAILABLE"
