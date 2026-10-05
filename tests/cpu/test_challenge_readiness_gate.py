"""The Graphite readiness gate command (GRAPHITE-READINESS-01).

Pins: the item registry equals the gate document; a check that cannot run never
passes; a missing or malformed review is REVIEW_REQUIRED; history is append-only
and drives the register's metrics; the runner names no challenge.
"""

import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline import __main__ as pipeline_cli
from carbon.challenge_pipeline.readiness import checks, model, runner

CHALLENGE = "example-challenge"
REVIEW_IDS = [i["id"] for i in model.load_items() if i["kind"] != "auto"]


def _review(item_id, **over):
    base = {
        "schema": runner.REVIEW_SCHEMA,
        "challenge": CHALLENGE,
        "level": 0,
        "item": item_id,
        "decision": "PASS",
        "reviewer": "Test Lead",
        "date": "2026-10-05",
        "evidence": [{"kind": "decision", "ref": "OWNER-GRAPHITE-TEST-WAVE-07"}],
    }
    base.update(over)
    return base


def _write_review(root, item, document):
    directory = Path(root) / CHALLENGE / "reviews"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{item}.json").write_text(json.dumps(document), encoding="utf-8")


def test_items_json_matches_the_gate_document_row_for_row():
    rows = model.parse_gate_document()
    items = model.load_items()
    assert [r["id"] for r in rows] == [i["id"] for i in items]
    for row, item in zip(rows, items):
        assert (item["title"], item["kind"], item["lesson"]) == (
            row["check"],
            row["kind"],
            row["lesson"],
        )


def test_every_item_has_a_registered_check_and_a_reason_when_unwired():
    for item in model.load_items():
        assert item["check"] in checks.CHECKS, item["id"]
        if item["check"] == "recorded_tests":
            assert item["pending"]["reason"] and item["pending"]["owner"], item["id"]


def test_runner_and_checks_name_no_challenge():
    for module in (runner, checks, model):
        text = Path(module.__file__).read_text(encoding="utf-8").lower()
        for token in ("battery", "chip-cold-plate", "cooling", "motor"):
            assert token not in text, (module.__name__, token)


@pytest.mark.parametrize("item_id", REVIEW_IDS)
def test_missing_review_is_review_required_never_pass(tmp_path, item_id):
    result = runner.load_review(CHALLENGE, 0, item_id, root=tmp_path)
    assert result.status == model.REVIEW_REQUIRED


@pytest.mark.parametrize(
    "mutation",
    [
        {"schema": "other"},
        {"challenge": "another"},
        {"level": 1},
        {"item": "ZZ"},
        {"decision": "MAYBE"},
        {"reviewer": " "},
        {"date": "yesterday"},
        {"evidence": []},
        {"evidence": [{"kind": "rumour", "ref": "x"}]},
        {"evidence": [{"kind": "pr", "ref": "623", "sha256": "abc"}]},
    ],
)
def test_malformed_review_is_review_required(tmp_path, mutation):
    _write_review(tmp_path, "O1", _review("O1", **mutation))
    assert runner.load_review(CHALLENGE, 0, "O1", root=tmp_path).status == (
        model.REVIEW_REQUIRED
    )


def test_unparseable_review_is_review_required(tmp_path):
    directory = tmp_path / CHALLENGE / "reviews"
    directory.mkdir(parents=True)
    (directory / "O1.json").write_text("{not json", encoding="utf-8")
    assert runner.load_review(CHALLENGE, 0, "O1", root=tmp_path).status == (
        model.REVIEW_REQUIRED
    )


def test_valid_review_decides_pass_or_fail(tmp_path):
    _write_review(tmp_path, "O1", _review("O1"))
    _write_review(tmp_path, "S4", _review("S4", decision="FAIL"))
    assert runner.load_review(CHALLENGE, 0, "O1", root=tmp_path).status == model.PASS
    assert runner.load_review(CHALLENGE, 0, "S4", root=tmp_path).status == model.FAIL


def test_a_check_that_raises_fails_closed(monkeypatch, tmp_path):
    def boom(item, ctx):
        raise RuntimeError("no docker here")

    monkeypatch.setitem(checks.CHECKS, "registered_l0", boom)
    report = runner.run_gate(CHALLENGE, 0, only=["P1"], root=tmp_path)
    (row,) = report["items"]
    assert row["status"] == model.FAIL and "RuntimeError" in row["detail"]


def test_unregistered_check_reference_fails(monkeypatch, tmp_path):
    monkeypatch.delitem(checks.CHECKS, "registered_l0")
    (row,) = runner.run_gate(CHALLENGE, 0, only=["P1"], root=tmp_path)["items"]
    assert row["status"] == model.FAIL


def test_unwired_item_is_not_built_with_owner(tmp_path):
    (row,) = runner.run_gate(CHALLENGE, 0, only=["R7"], root=tmp_path)["items"]
    assert row["status"] == model.NOT_BUILT and "owner:" in row["detail"]


def test_green_only_when_every_item_passes(monkeypatch, tmp_path):
    def ok(item, ctx):
        return model.Result(model.PASS, "ok", ("e",))

    for ref in set(i["check"] for i in model.load_items()):
        monkeypatch.setitem(checks.CHECKS, ref, ok)
    monkeypatch.setattr(runner, "load_conditions", lambda challenge: [])
    report = runner.run_gate(CHALLENGE, 0, root=tmp_path)
    # Review items still have no recorded review.
    assert not report["green"]
    assert report["counts"][model.REVIEW_REQUIRED] == len(REVIEW_IDS)
    for item_id in REVIEW_IDS:
        _write_review(tmp_path, item_id, _review(item_id))
    report = runner.run_gate(CHALLENGE, 0, root=tmp_path)
    assert report["green"] and report["counts"][model.PASS] == len(model.load_items())
    partial = runner.run_gate(CHALLENGE, 0, only=["P1"], root=tmp_path)
    assert not partial["green"] and partial["partial"]


def test_report_digest_binds_the_report(tmp_path):
    report = runner.run_gate(CHALLENGE, 0, only=["R7"], root=tmp_path)
    claimed = report.pop("report_digest")
    assert model.digest(report) == claimed


def test_cooling_style_condition_fails_until_policy_registered(tmp_path):
    condition = {
        "id": "c",
        "type": "policy_registered",
        "registry": "registry.json",
        "name": "policy-v2",
        "note": "n",
    }
    (tmp_path / "registry.json").write_text(
        json.dumps({"versions": {"policy-v1": "sha256:" + "0" * 64}}), encoding="utf-8"
    )
    assert runner.evaluate_condition(condition, tmp_path).status == model.FAIL
    (tmp_path / "registry.json").write_text(
        json.dumps({"versions": {"policy-v2": "sha256:" + "1" * 64}}), encoding="utf-8"
    )
    assert runner.evaluate_condition(condition, tmp_path).status == model.PASS
    condition["registry"] = "missing.json"
    assert runner.evaluate_condition(condition, tmp_path).status == model.FAIL


def test_the_cooling_candidate_fault_v2_condition_is_registered_data():
    conditions = [
        c
        for c in json.loads(
            (model.PACKAGE / "conditions.json").read_text(encoding="utf-8")
        )["conditions"]
    ]
    assert any(
        c["name"] == "cooling-candidate-fault-v2" and c["item"] == "A5"
        for c in conditions
    )


def test_history_is_append_only_and_drives_metrics(tmp_path):
    first = runner.run_gate(CHALLENGE, 0, root=tmp_path)
    path = runner.append_history(first, root=tmp_path)
    before = path.read_text(encoding="utf-8")
    runner.append_history(
        runner.run_gate(CHALLENGE, 0, only=["R7"], root=tmp_path), root=tmp_path
    )
    after = path.read_text(encoding="utf-8")
    assert after.startswith(before) and after.count("\n") == 2
    line = json.loads(before)
    assert line["schema"] == runner.RUN_SCHEMA
    assert line["report_digest"] == first["report_digest"]
    assert {i["id"] for i in line["items"]} == {i["id"] for i in model.load_items()}
    metrics = runner.history_metrics(CHALLENGE, root=tmp_path)
    assert metrics["runs"] == 2
    assert metrics["first_run_not_passing"] == sum(
        1 for r in first["items"] if r["status"] != model.PASS
    )
    assert metrics["first_green_utc"] is None


@pytest.mark.parametrize("challenge", ["../x", "A", "", "a/b"])
def test_request_refuses_unsafe_challenge_tokens(challenge):
    with pytest.raises(runner.ReadinessRefused):
        runner.run_gate(challenge, 0)


def test_request_refuses_bad_level_and_unknown_item():
    with pytest.raises(runner.ReadinessRefused):
        runner.run_gate(CHALLENGE, 9)
    with pytest.raises(runner.ReadinessRefused):
        runner.run_gate(CHALLENGE, 0, only=["Z9"])


def test_cli_exits_nonzero_and_refuses(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        runner, "append_history", lambda report, root=tmp_path: tmp_path / "h"
    )
    assert pipeline_cli.main(["readiness", "--challenge", "../bad"]) == 2
    code = pipeline_cli.main(
        [
            "readiness",
            "--challenge",
            CHALLENGE,
            "--only",
            "R7",
            "--json",
            str(tmp_path / "r.json"),
        ]
    )
    assert code == 1
    written = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert written["report_digest"].startswith("sha256:")
    assert "R7" in capsys.readouterr().out
