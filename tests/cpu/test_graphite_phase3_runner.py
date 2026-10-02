"""The phase 3 runner (CHALLENGE-PROTOCOL-04 slice 5): dry run end to end, the
iteration log, one store per grant, and the refusals before anything live."""

from __future__ import annotations

import json

import pytest

from carbon.agent_campaign.graphite import phase3
from carbon.agent_campaign.graphite.phase2 import RunnerRefused

pytest.importorskip("numpy")


def test_a_dry_run_session_is_launched_scored_and_logged(tmp_path):
    root = tmp_path / "step4"
    assert phase3.main(["session", "--root", str(root), "--dry-run"]) == 0
    assert phase3.main(["session", "--root", str(root), "--dry-run"]) == 0
    lines = (root / "dry-run" / "iteration-log.jsonl").read_text().splitlines()
    entries = [json.loads(line) for line in lines]
    assert [e["session"] for e in entries] == ["constructor-1", "constructor-2"]
    for entry in entries:
        assert entry["stage"] == "test_iterate" and entry["state"] == "succeeded"
        assert entry["selection"]["strategy"]["backbone"] == "knn"
        assert entry["score"]["eligible"] in (True, False)
        assert entry["refused"] is None and entry["finding"] is None
    # The same recipe rebuilds to the same model.
    assert entries[0]["score"]["state_sha256"] == entries[1]["score"]["state_sha256"]
    assert (root / "dry-run" / "scores" / (entries[0]["run_id"] + ".json")).is_file()


def test_one_store_holds_one_grant(tmp_path):
    from graphite_fixtures import grant

    from carbon.agent_campaign.grant import SpendingGrant

    phase3._bind_store(tmp_path, grant())
    phase3._bind_store(tmp_path, grant())
    other = SpendingGrant.from_document(
        {**grant().document(), "monetary_ceiling": "4.00"}
    )
    with pytest.raises(RunnerRefused):
        phase3._bind_store(tmp_path, other)


def test_a_live_session_is_refused_without_its_inputs(tmp_path):
    root = str(tmp_path / "step4")
    with pytest.raises(RunnerRefused):
        phase3.main(["session", "--root", root])
    grant = (
        phase3.REPOSITORY / "docs/development/graphite/grants/GRAPHITE-GRANT-STEP4.json"
    )
    args = phase3.parser().parse_args(
        [
            "session",
            "--root",
            root,
            "--grant",
            str(grant),
            "--configuration",
            str(tmp_path / "runner.json"),
            "--campaign",
            "c1",
        ]
    )
    with pytest.raises(RunnerRefused):
        phase3.session(args, environ={})  # no ENGY_API_KEY: refused, nothing sent
    with pytest.raises(RunnerRefused):
        phase3.main(
            ["session", "--root", str(phase3.REPOSITORY / "tmp-step4"), "--dry-run"]
        )
    assert not (phase3.REPOSITORY / "tmp-step4").exists()
