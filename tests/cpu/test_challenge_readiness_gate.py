"""The Graphite readiness gate command (GRAPHITE-READINESS-01).

Pins: the item registry equals the gate document; a check that cannot run never
passes; a missing or malformed review is REVIEW_REQUIRED; history is append-only
and drives the register's metrics; the runner names no challenge.
"""

import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline import __main__ as pipeline_cli
from carbon.challenge_pipeline.readiness import checks, model, q1, runner

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
    for module in (runner, checks, model, q1):
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

    for ref in {i["check"] for i in model.load_items()}:
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


# -- D7, R6 and the onboarding records (records PR) -------------------------------------------
CHALLENGES = (
    "battery-fastcharge-ageing-development-v1",
    "chip-cold-plate",
    "electric-motor-magnetics",
)


def _ctx(challenge=CHALLENGE):
    return checks.Context(challenge=challenge, level=0)


def _confirmation_dir(monkeypatch, tmp_path, strata):
    directory = tmp_path / "carbon/challenge_validator/confirmation_sets"
    directory.mkdir(parents=True)
    (directory / "registry.json").write_text(
        json.dumps({"sets": {"role-v1": "sha256:" + "0" * 64}}), encoding="utf-8"
    )
    (directory / "role-v1.json").write_text(
        json.dumps(
            {
                "role": "role-v1",
                "challenge_id": CHALLENGE,
                "sealable": True,
                "cases": 120,
                "sampling_law": {"id": "law"},
                "strata": strata,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(checks, "REPOSITORY", tmp_path)


@pytest.mark.parametrize(
    "strata, status",
    [
        ([], model.FAIL),
        ("", model.FAIL),
        (None, model.FAIL),
        ("NONE", model.FAIL),
        ("NONE_UNIFORM_LAW", model.PASS),
        ([{"id": "s"}], model.PASS),
    ],
)
def test_d7_accepts_only_explicit_none_never_empty(
    monkeypatch, tmp_path, strata, status
):
    _confirmation_dir(monkeypatch, tmp_path, strata)
    assert checks.confirmation_role({}, _ctx()).status == status


def test_r6_threshold_is_the_registered_test_lead_value():
    policy = _ctx().data_policy("R6")
    assert policy["min_free_gb"] == 30 and "Test Lead decision" in policy["authority"]


def test_r6_disk_check_compares_against_the_threshold(monkeypatch):
    from collections import namedtuple

    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(
        checks.shutil, "disk_usage", lambda path: usage(0, 0, 29 * 10**9)
    )
    assert checks.disk_free({}, _ctx()).status == model.FAIL
    monkeypatch.setattr(
        checks.shutil, "disk_usage", lambda path: usage(0, 0, 30 * 10**9)
    )
    assert checks.disk_free({}, _ctx()).status == model.PASS

    def unreadable(path):
        raise OSError("no such drive")

    monkeypatch.setattr(checks.shutil, "disk_usage", unreadable)
    result = checks.disk_free({}, _ctx())
    assert result.status == model.FAIL and "cannot measure" in result.detail


def test_r6_needs_the_window_review_as_well(tmp_path):
    item = next(i for i in model.load_items() if i["id"] == "R6")
    assert item["kind"] == "auto+review" and item["check"] == "disk_free"


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_onboarding_records_are_drafts_the_checks_can_read(challenge):
    base = model.PACKAGE / challenge
    for name in ("ownership", "branches", "onboarding", "lanes"):
        record = json.loads((base / f"{name}.json").read_text(encoding="utf-8"))
        assert record["challenge"] == challenge and record["status"] == "DRAFT"
    ctx = _ctx(challenge)
    item = {"id": "O3"}
    assert checks.onboarding_decisions(item, ctx).status == model.PASS
    assert checks.branch_plan.__name__  # O2 needs origin; the shape is tested below
    names = json.loads((base / "branches.json").read_text(encoding="utf-8"))
    assert names["planned_branches"] and all(
        isinstance(e["name"], str)
        and e["expected_owner"]
        and e["state"] in ("PROPOSED", "STARTED")
        for e in names["planned_branches"]
    )


def test_motor_pod_lane_stays_tbd_and_fails_closed():
    result = checks.compute_lanes({}, _ctx("electric-motor-magnetics"))
    assert result.status == model.FAIL and "TBD" in result.detail
    cooling = checks.compute_lanes({}, _ctx("chip-cold-plate"))
    assert cooling.status == model.FAIL and "cpu-carrier" in cooling.detail
    assert (
        checks.compute_lanes(
            {}, _ctx("battery-fastcharge-ageing-development-v1")
        ).status
        == model.PASS
    )


def test_a_lane_with_a_stale_policy_fails(monkeypatch, tmp_path):
    directory = tmp_path / "carbon/challenge_pipeline/readiness" / CHALLENGE
    directory.mkdir(parents=True)
    lane = {"lane": "pod", "state": "DECLARED", "probe": "p", "policy": "old-v1"}
    (directory / "lanes.json").write_text(
        json.dumps({"lanes": [lane]}), encoding="utf-8"
    )
    monkeypatch.setattr(checks, "PACKAGE", directory.parent)
    assert checks.compute_lanes({}, _ctx()).status == model.FAIL


def test_ownership_map_refuses_unassigned_missing_and_phantom_artifacts(
    monkeypatch, tmp_path
):
    directory = tmp_path / CHALLENGE
    directory.mkdir()
    monkeypatch.setattr(checks, "PACKAGE", tmp_path)
    good = {
        name: {
            "owner": "Codex",
            "acceptance": "Ryan",
            "state": "NOT_BUILT",
            "artifact": None,
            "basis": "b",
        }
        for name in checks.OWNERSHIP_COMPONENTS
    }

    def check(components):
        (directory / "ownership.json").write_text(
            json.dumps({"components": components}), encoding="utf-8"
        )
        return checks.ownership_map({}, _ctx()).status

    assert check(good) == model.PASS
    assert check({k: v for k, v in good.items() if k != "scorer"}) == model.FAIL
    assert (
        check({**good, "scorer": {**good["scorer"], "owner": "UNASSIGNED"}})
        == model.FAIL
    )
    assert (
        check(
            {
                **good,
                "scorer": {**good["scorer"], "state": "EXISTS", "artifact": "no/such"},
            }
        )
        == model.FAIL
    )
    assert check({**good, "scorer": {**good["scorer"], "basis": ""}}) == model.FAIL


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_committed_ownership_maps_name_every_component(challenge):
    ctx = _ctx(challenge)
    result = checks.ownership_map({}, ctx)
    assert result.status == model.PASS, result.detail
    record = json.loads(
        (model.PACKAGE / challenge / "ownership.json").read_text(encoding="utf-8")
    )
    for entry in record["components"].values():
        assert entry["acceptance"] == "Ryan (technical owner)"
        assert entry["owner"] != "UNASSIGNED"


def test_ownership_map_needs_an_acceptance_owner(monkeypatch, tmp_path):
    directory = tmp_path / CHALLENGE
    directory.mkdir()
    monkeypatch.setattr(checks, "PACKAGE", tmp_path)
    components = {
        name: {"owner": "Codex", "state": "NOT_BUILT", "basis": "b"}
        for name in checks.OWNERSHIP_COMPONENTS
    }
    (directory / "ownership.json").write_text(
        json.dumps({"components": components}), encoding="utf-8"
    )
    result = checks.ownership_map({}, _ctx())
    assert result.status == model.FAIL and "acceptance" in result.detail


def _branches(monkeypatch, tmp_path, entries, heads):
    directory = tmp_path / CHALLENGE
    directory.mkdir()
    monkeypatch.setattr(checks, "PACKAGE", tmp_path)
    (directory / "branches.json").write_text(
        json.dumps({"planned_branches": entries}), encoding="utf-8"
    )

    class Done:
        returncode = 0
        stdout = "".join("abc" + chr(9) + "refs/heads/" + h + chr(10) for h in heads)

    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: Done())


def test_o2_flags_only_a_name_on_origin_under_another_owner(monkeypatch, tmp_path):
    entry = {"name": "x/y", "expected_owner": "Codex", "state": "PROPOSED"}
    _branches(monkeypatch, tmp_path, [entry], ["x/y"])
    assert checks.branch_plan({}, _ctx()).status == model.FAIL
    tmp2 = tmp_path / "two"
    tmp2.mkdir()
    _branches(monkeypatch, tmp2, [{**entry, "state": "STARTED"}], ["x/y"])
    assert checks.branch_plan({}, _ctx()).status == model.PASS
    tmp3 = tmp_path / "three"
    tmp3.mkdir()
    _branches(monkeypatch, tmp3, [entry], ["other"])
    assert checks.branch_plan({}, _ctx()).status == model.PASS
    tmp4 = tmp_path / "four"
    tmp4.mkdir()
    _branches(monkeypatch, tmp4, [{"name": "x/y"}], [])
    assert checks.branch_plan({}, _ctx()).status == model.FAIL


def test_carrier_lane_references_its_own_registered_policy_not_the_gpu_probe():
    for challenge in ("chip-cold-plate", "electric-motor-magnetics"):
        lanes = json.loads(
            (model.PACKAGE / challenge / "lanes.json").read_text(encoding="utf-8")
        )["lanes"]
        carrier = next(x for x in lanes if x["lane"] == "cpu-carrier")
        assert carrier["policy"] == "carrier-lane-v1"
        assert carrier["registry"].endswith("compute_lanes/registry.json")
        assert carrier["policy"] != "pod-attribution-v2"


def _lane(**over):
    lane = {
        "lane": "c",
        "state": "DECLARED",
        "probe": "p",
        "policy": "lane-v1",
        "registry": "reg.json",
        "registry_key": "c",
    }
    lane.update(over)
    return lane


def _lane_tree(monkeypatch, tmp_path, lane, registry=None):
    directory = tmp_path / "carbon/challenge_pipeline/readiness" / CHALLENGE
    directory.mkdir(parents=True)
    (directory / "lanes.json").write_text(
        json.dumps({"lanes": [lane]}), encoding="utf-8"
    )
    (tmp_path / "reg.json").write_text(
        json.dumps(
            registry
            or {
                "current": {"c": "lane-v1"},
                "versions": {"lane-v1": "sha256:" + "1" * 64},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(checks, "PACKAGE", directory.parent)
    monkeypatch.setattr(checks, "REPOSITORY", tmp_path)


def test_lane_with_dict_registry_current_passes_and_stale_fails(monkeypatch, tmp_path):
    _lane_tree(monkeypatch, tmp_path, _lane())
    assert checks.compute_lanes({}, _ctx()).status == model.PASS
    _lane_tree(
        monkeypatch,
        tmp_path / "b",
        _lane(),
        {"current": {"c": "lane-v2"}, "versions": {"lane-v1": "sha256:" + "1" * 64}},
    )
    assert checks.compute_lanes({}, _ctx()).status == model.FAIL


class _Done:
    def __init__(self, code, body):
        self.returncode, self.stdout, self.stderr = code, json.dumps(body), ""


def _probe_lane(**over):
    return _lane(
        probe_cli=["{python}", "-m", "x", "--m", "{input}"],
        probe_input_env="X_MANIFEST",
        **over,
    )


def test_lane_probe_without_input_fails_closed_and_says_why(monkeypatch, tmp_path):
    monkeypatch.delenv("X_MANIFEST", raising=False)
    _lane_tree(monkeypatch, tmp_path, _probe_lane())
    result = checks.compute_lanes({}, _ctx())
    assert result.status == model.FAIL and "X_MANIFEST" in result.detail


@pytest.mark.parametrize(
    "code, body, ok",
    [
        (
            0,
            {
                "eligible": True,
                "lane_policy": "lane-v1",
                "lane_policy_digest": "sha256:" + "1" * 64,
            },
            True,
        ),
        (
            0,
            {
                "eligible": True,
                "lane_policy": "lane-v1",
                "lane_policy_digest": "sha256:" + "2" * 64,
            },
            False,
        ),
        (
            1,
            {
                "eligible": False,
                "doctor_code": "worker.doctor.image_unavailable",
                "image_present": False,
            },
            False,
        ),
        (2, {"refused": "lane.policy_altered"}, False),
        (0, {"eligible": False}, False),
    ],
)
def test_lane_probe_outcomes(monkeypatch, tmp_path, code, body, ok):
    monkeypatch.setenv("X_MANIFEST", "m.json")
    _lane_tree(monkeypatch, tmp_path, _probe_lane())
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: _Done(code, body))
    assert (checks.compute_lanes({}, _ctx()).status == model.PASS) is ok


# -- history location, --no-history and R1's own grant ------------------------------------------
def test_history_and_reports_live_outside_carbon():
    assert model.RUNTIME.relative_to(model.REPOSITORY).as_posix() == (
        "docs/development/challenge_pipeline/readiness"
    )
    assert model.PACKAGE.relative_to(model.REPOSITORY).parts[0] == "carbon"


def test_append_history_defaults_to_runtime_and_writes_a_digest_named_report(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(runner, "RUNTIME", tmp_path)
    report = runner.run_gate(CHALLENGE, 0, only=["R7"], root=tmp_path / "cfg")
    path = runner.append_history(report)
    assert path == tmp_path / CHALLENGE / "history.jsonl"
    name = report["report_digest"].split(":", 1)[1][:16]
    stored = json.loads(
        (tmp_path / CHALLENGE / "reports" / f"{name}.json").read_text(encoding="utf-8")
    )
    assert stored["report_digest"] == report["report_digest"]
    assert runner.history_metrics(CHALLENGE)["runs"] == 1


def test_cli_no_history_appends_nothing_and_default_appends(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "RUNTIME", tmp_path)
    args = ["readiness", "--challenge", CHALLENGE, "--only", "R7"]
    pipeline_cli.main([*args, "--no-history"])
    assert not (tmp_path / CHALLENGE).exists()
    pipeline_cli.main(args)
    assert (tmp_path / CHALLENGE / "history.jsonl").is_file()


def test_a_gate_run_leaves_carbon_clean(monkeypatch, tmp_path):
    before = sorted(str(p) for p in model.PACKAGE.rglob("*"))
    monkeypatch.setattr(runner, "RUNTIME", tmp_path)
    pipeline_cli.main(["readiness", "--challenge", CHALLENGE, "--only", "R7"])
    assert sorted(str(p) for p in model.PACKAGE.rglob("*")) == before


def test_r1_never_passes_on_another_challenges_grant(monkeypatch):
    calls = []
    monkeypatch.setattr(checks.os, "name", "posix")
    monkeypatch.setattr(
        checks.subprocess,
        "run",
        lambda *a, **k: calls.append(a) or _Done(0, {"verdict": "PASS"}),
    )
    cooling = checks.Context(
        challenge="chip-cold-plate",
        level=0,
        data=checks.load_challenge_data("chip-cold-plate"),
    )
    result = checks.prelive({}, cooling)
    assert (
        result.status == model.FAIL and "no grant for chip-cold-plate" in result.detail
    )
    assert calls == [], "prelive must not run without the challenge's own grant"


def test_r1_passes_the_challenges_own_grant_to_prelive(monkeypatch):
    seen = []

    def fake(command, **kwargs):
        seen.append(command)
        return _Done(0, {"verdict": "PASS"})

    monkeypatch.setattr(checks.os, "name", "posix")
    monkeypatch.setattr(checks.subprocess, "run", fake)
    battery = "battery-fastcharge-ageing-development-v1"
    ctx = checks.Context(
        challenge=battery, level=0, data=checks.load_challenge_data(battery)
    )
    assert checks.prelive({}, ctx).status == model.PASS
    command = seen[0]
    assert command[command.index("--grant") + 1].endswith("GRAPHITE-GRANT-PHASE4.json")


def test_r1_refuses_a_recorded_grant_that_is_not_committed(monkeypatch):
    monkeypatch.setattr(checks.os, "name", "posix")
    ctx = checks.Context(
        challenge=CHALLENGE, level=0, data={"grants": {"phase4": "no/such.json"}}
    )
    assert checks.prelive({}, ctx).status == model.FAIL
