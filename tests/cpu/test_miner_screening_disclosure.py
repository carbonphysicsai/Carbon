"""PLT-08 disclosure regressions: synthetic evidence, no chain or solver."""

import copy
import json
from types import SimpleNamespace

import pytest

from carbon.battery import exam
from carbon.challenge_validator import ledger, score_feed
from carbon.challenge_validator import screening_ladder as sl

IDENTITIES = {"challenge": {"id": "fixture-battery"},
              "rule_digest": "sha256:" + "a" * 64,
              "contract_digest": "sha256:" + "b" * 64}  # fmt: skip
# A real rule dict: its `rule_version` is 2, not a name (the r8.5 cutover's
# sealed ladder came from a fixture that put the name there).
RULE = exam.RULES["v2-bank-sched"]
CHAIN = {"participants": {"hk-A": {"coldkey": "ck-A"},
                           "hk-A2": {"coldkey": "ck-A"},
                           "hk-B": {"coldkey": "ck-B"},
                           "canary": {"coldkey": "ck-canary"}}}  # fmt: skip


@pytest.fixture
def registration(tmp_path):
    # #1205 supplies the implementation. Never put its measurement values in
    # this ticket: this deliberately synthetic policy has a different grain.
    pytest.importorskip("carbon.challenge_validator.screening_grain")
    doc = {
        "schema": "carbon.battery.screening-grain.v1",
        "challenge": "fixture-battery",
        "display_grid": "geometric",
        "version": 2,
        "noise_floor": {"min_cases": 10, "min_design_questions": 4},
        "entries": [
            {
                "match": {
                    "rule": "v2-bank-sched",
                    "score_section": "accuracy",
                    "rule_digest": IDENTITIES["rule_digest"],
                },
                "sense": "lower_is_better",
                "grain": 0.04,
                "grain_pct": 4.0,
                "measured_se": 0.039,
            }
        ],
    }
    directory = tmp_path / sl.GRAIN_DIR
    directory.mkdir(parents=True)
    path = directory / "screening-grain-v2.json"
    path.write_text(json.dumps(doc))
    return tmp_path, path, doc


def row(sid="s1", hotkey="hk-A", score=0.1234, **changes):
    found = {
        "submission_id": sid,
        "hotkey": hotkey,
        "score": score,
        "block": 20,
        "noise": {"errors": [0.1] * 10, "regrets": [0.2] * 4},
        "private-case-marker": "must-never-leak",
    }
    found.update(changes)
    return found


def shown(rows, policy, rule=RULE):
    return sl.ladder(
        rows, {h: v["coldkey"] for h, v in CHAIN["participants"].items()}, policy, rule
    )


def test_missing_module_or_file_never_invents_a_grain(tmp_path, monkeypatch):
    import sys

    assert sl.load_grain(tmp_path, IDENTITIES, RULE) is None
    monkeypatch.setitem(sys.modules, "carbon.challenge_validator.screening_grain", None)
    assert sl.load_grain(tmp_path, IDENTITIES, RULE) is None
    result = shown([row()], None)
    assert result["grain_pct"] is None
    item = result["coldkeys"][0]
    assert item["status"] == "SEALED_UNTIL_GRAIN"
    assert all(
        item[k] is None
        for k in ("displayed_score", "rank", "best_submission_id", "displayed_at_block")
    )
    assert "must-never-leak" not in json.dumps(result)


def test_loader_accepts_the_committed_reference_registration():
    from pathlib import Path

    sg = pytest.importorskip("carbon.challenge_validator.screening_grain")
    repository = Path(__file__).resolve().parents[2]
    doc = sg.load(repository / sl.GRAIN_DIR)
    for entry in doc["entries"]:
        match = entry["match"]
        identities = {
            "challenge": {"id": doc["challenge"]},
            "rule_digest": match.get("rule_digest", "sha256:" + "d" * 64),
        }
        rule = dict(exam.RULES[match["rule"]])
        if match["score_section"] == "registered":
            rule["score"] = {
                "candidate": match["score_candidate"],
                "registry_sha256": match["registry_sha256"],
            }
        policy = sl.load_grain(repository, identities, rule)
        assert policy is not None and policy[1] == doc and policy[2] == entry
        if "score" in rule:
            rule["score"]["candidate"] = "unregistered-fixture-term"
            assert sl.load_grain(repository, identities, rule) is None


def test_latest_file_matches_exactly_or_seals_without_history_fallback(registration):
    repo, path, doc = registration
    assert sl.load_grain(repo, IDENTITIES, RULE) is not None
    (path.parent / "screening-grain-v1.json").write_text(json.dumps(doc))
    for bad in (
        {**doc, "challenge": "other"},
        {**doc, "entries": doc["entries"] * 2},
        {**doc, "noise_floor": None},
        {**doc, "entries": [{"match": None}]},
        {**doc, "entries": [{**doc["entries"][0], "grain": 0.03}]},
        {**doc, "entries": [{**doc["entries"][0], "match": {"rule": "v2-bank-sched"}}]},
    ):
        path.write_text(json.dumps(bad))
        assert sl.load_grain(repo, IDENTITIES, RULE) is None
    path.write_text("{")
    assert sl.load_grain(repo, IDENTITIES, RULE) is None
    path.write_text(json.dumps(doc))
    assert sl.load_grain(repo, {**IDENTITIES, "rule_digest": "other"}, RULE) is None


@pytest.mark.parametrize(
    "sense,score,better",
    [("lower_is_better", 0.1234, 0.09), ("higher_is_better", 0.8, 0.95)],
)
def test_reference_grid_noise_floor_and_monotone_replay(
    registration, sense, score, better
):
    repo, path, doc = registration
    rule = RULE
    if sense == "higher_is_better":
        rule = {
            **exam.RULES["v3-bank-sched"],
            "score": {"candidate": "fixture-term", "registry_sha256": "c" * 64},
        }
        doc["entries"][0].update(
            sense=sense,
            match={
                "rule": "v3-bank-sched",
                "score_section": "registered",
                "score_candidate": "fixture-term",
                "registry_sha256": "c" * 64,
            },
        )
        path.write_text(json.dumps(doc))
    policy = sl.load_grain(repo, IDENTITIES, rule)
    assert policy is not None
    first = shown([row(score=score)], policy, rule)["coldkeys"][0]
    value = first["displayed_score"]
    assert value >= score if sense == "lower_is_better" else value <= score
    too_small = value / 1.02 if sense == "lower_is_better" else value * 1.02
    again = shown([row(score=score), row("s2", "hk-A2", too_small)], policy, rule)[
        "coldkeys"
    ][0]
    assert again["displayed_score"] == value and again["best_submission_id"] == "s1"
    assert again["status"] == "NO_IMPROVEMENT_BEYOND_GRAIN"
    improved = shown([row(score=score), row("s2", "hk-A2", better)], policy, rule)[
        "coldkeys"
    ][0]
    assert improved["best_submission_id"] == "s2"
    replay = shown([row(score=score), row("s2", "hk-A2", better)], policy, rule)
    assert replay == shown([row(score=score), row("s2", "hk-A2", better)], policy, rule)
    assert (
        improved["displayed_score"] <= value
        if sense == "lower_is_better"
        else improved["displayed_score"] >= value
    )
    # Neither historical attempts nor another coldkey supplies minimum evidence.
    short = row(noise={"errors": [0.1] * 9, "regrets": [0.2] * 3})
    result = shown([short, short, row("other", "hk-B")], policy, rule)
    mine = next(r for r in result["coldkeys"] if r["coldkey"] == "ck-A")
    assert mine["displayed_score"] is None and mine["status"] == "SEALED_UNTIL_GRAIN"
    noisy = row(
        "noisy",
        score=value / 1.06 if sense == "lower_is_better" else value * 1.06,
        noise={"errors": [0.0] * 9 + [10.0], "regrets": [0.0, 0.0, 0.0, 10.0]},
    )
    assert (
        shown([row(score=score), noisy], policy, rule)["coldkeys"][0]["displayed_score"]
        == value
    )
    assert "errors" not in json.dumps(replay) and "regrets" not in json.dumps(replay)


def test_missing_nonfinite_and_nonpositive_noise_cannot_publish(registration):
    repo, _, _ = registration
    policy = sl.load_grain(repo, IDENTITIES, RULE)
    for change in (
        {"noise": None},
        {"noise": {"errors": [float("nan")] * 10}},
        {"score": 0},
        {"score": float("inf")},
        {"score": True},
    ):
        assert shown([row(**change)], policy)["coldkeys"][0]["displayed_score"] is None


def test_ledger_projection_is_counts_only_closed_and_includes_overflow(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    path = directory / "attempts.sqlite"
    book = ledger.AttemptLedger(path, clock=lambda: ledger.HOUR_NS)
    submission = SimpleNamespace(
        hotkey="hk-A",
        contract_digest=IDENTITIES["contract_digest"],
        receipt={"private": "receipt-marker"},
        strategy_json="strategy-marker",
    )
    for _ in range(2):
        book.record(submission, kind="RECEIVED")
    for _ in range(ledger.MAX_REFUSED_ROWS_PER_HOUR + 3):
        book.record(submission, kind="REFUSED", code="strategy_not_json")
    book.record(submission, kind="REFUSED", code="private-case-marker")
    book.record(submission, kind="FAILED_INFRA", code="infra-marker")
    book.record(
        SimpleNamespace(**{**vars(submission), "contract_digest": "other"}),
        kind="RECEIVED",
    )
    book.record(
        SimpleNamespace(**{**vars(submission), "hotkey": "canary"}), kind="RECEIVED"
    )
    result = ledger.public_status_counts(path, IDENTITIES["contract_digest"], {"hk-A"})
    assert result == {
        "hk-A": {
            "hotkey": "hk-A",
            "received": 2,
            "refused": {"strategy_not_json": 123, "unclassified_refusal": 1},
        }
    }
    assert "marker" not in json.dumps(result)
    absent = directory / "absent.sqlite"
    with pytest.raises(ledger.LedgerUnavailable):
        ledger.public_status_counts(absent, IDENTITIES["contract_digest"], {"hk-A"})
    assert not absent.exists()


def test_disclosure_filters_final_fresh_canary_rule_device_and_development(
    registration,
):
    repo, _, _ = registration
    original = {
        "submission_id": "s1",
        "hotkey": "hk-A",
        "state": "SCORED",
        "binding": {"rule_digest": IDENTITIES["rule_digest"], "receipt": {"block": 20}},
        "record": {
            "rule_digest": IDENTITIES["rule_digest"],
            "active_batches": ["private-screening-window"],
            "eligible": True,
            "score": 0.1234,
            "screening_noise": {"errors": [0.1] * 10},
        },
    }
    records = [original]
    for side, change in (
        ("record", {"active_batches": ["private-final-window"]}),
        ("record", {"active_batches": ["unknown-fresh-window"]}),
        ("record", {"rebuild": {"device_class": "gpu"}}),
        ("record", {"rule_digest": "other"}),
        ("record", {"eligible": False}),
        ("binding", {"development": {}}),
        ("binding", {"rule_digest": "other"}),
    ):
        bad = copy.deepcopy(original)
        bad[side].update(change)
        bad["submission_id"] = "must-not-display"
        records.append(bad)
    records.append({**original, "hotkey": "canary"})

    class Store:
        def scored_submissions(self, *, scoring_order):
            assert scoring_order is True
            return records

        def batch(self, fingerprint):
            return {
                "kind": (
                    "screening"
                    if fingerprint == "private-screening-window"
                    else "finalist"
                )
            }

    target = SimpleNamespace(store=Store(), rule=RULE)
    status, ladder = score_feed._screening_disclosure(
        target, IDENTITIES, "cpu", CHAIN, {"canary"}, None, repo
    )
    assert status is None
    assert len(ladder["coldkeys"]) == 1
    assert ladder["coldkeys"][0]["best_submission_id"] == "s1"
    public = json.dumps(ladder)
    assert all(
        marker not in public
        for marker in (
            "private-",
            "must-not-display",
            "canary",
            "screening_noise",
            "errors",
        )
    )
    directory = repo / "private"
    directory.mkdir(mode=0o700)
    path = directory / "attempts.sqlite"
    ledger.AttemptLedger(path)
    status, same_ladder = score_feed._screening_disclosure(
        target, IDENTITIES, "cpu", CHAIN, {"canary"}, path, repo
    )
    mine = next(r for r in status if r["hotkey"] == "hk-A")
    # Received/refused counts cannot know a future rebuild device. All three
    # current-rule screening outcomes count as activity; only the CPU eligible
    # one may provide this board's displayed score.
    assert mine == {"hotkey": "hk-A", "received": 0, "refused": {}, "scored": 3}
    assert same_ladder == ladder


def test_scoring_preserves_only_its_scored_noise_without_changing_grade(monkeypatch):
    from carbon.battery import daemon

    rows = [
        {"state": "SCORABLE", "error": 0.1},
        {"state": "SCORABLE", "error": 0.2},
        {"state": "REFERENCE_INVALID", "error": 9.0},
    ]
    grade = {"score": 0.15, "eligible": True, "important_score": 0.1}
    monkeypatch.setattr(daemon.exam, "evaluate", lambda *args: (rows, grade))
    store = SimpleNamespace(active_case_ids=lambda p: [], case_inputs=lambda p: {})
    target = SimpleNamespace(
        store=store,
        rule={"equivalence_margin_rel": 0.5},
        _infer=lambda *args: {},
        _case_store=lambda *args: None,
        _rebuild=lambda *args: {"device_class": "cpu"},
        _reference_identity=lambda *args: {},
    )
    result = daemon.BatteryValidator._pool_records(
        target, {"version": 1, "active": []}, "s1", None, ""
    )
    assert result["screening_noise"] == {"errors": [0.1, 0.2]}
    assert all(result[k] == v for k, v in grade.items())


def test_registered_noise_is_same_question_measurement_not_another_run():
    from carbon.battery import daemon

    measured = {
        "screening-window": {
            "status": "OK",
            "mean_regret": 0.2,
            "per_question": [{"regret": 0.1}, {"regret": 0.3}],
        }
    }
    calls = []

    def measure(designs, predictions):
        calls.append((designs, predictions))
        return {"batches": measured}

    scorer = SimpleNamespace(
        design=SimpleNamespace(inputs=lambda d: {}, measure=measure),
        pooled=lambda b: (0.2, None),
        measure=lambda *args: {"score": 0.8, "eligible": True, "gate": "PASS"},
    )
    target = SimpleNamespace(
        registered_score=scorer,
        store=SimpleNamespace(design=lambda f: {}),
        _quiz_predictions=lambda *a, **kw: {},
        DESIGN_PREDICTIONS="design/",
    )
    record = daemon.BatteryValidator._registered(
        target, "s1", {}, [], None, {"version": 1, "active": ["screening-window"]}, ""
    )
    assert len(calls) == 1
    assert record == {
        "score": 0.8,
        "eligible": True,
        "gate": "PASS",
        "screening_noise": {"regrets": [0.1, 0.3]},
    }


def test_python_and_worker_read_geometric_ladders_and_refuse_raw_scores(tmp_path):
    from test_dashboard_worker import NODE, _node, _python

    from carbon.dashboard import feed, fixtures

    if NODE is None:
        pytest.skip("node is not installed here")
    body = fixtures.ladder_document(
        "fixture-challenge-epsilon", "gpu:FIXTURE-GPU", seed=6, sealed=False
    )
    ladder = body["leaderboard"]["ladder"]
    ladder.update(grain_pct=4.0, display_grid="geometric", sense="lower_is_better")
    for k, item in enumerate(ladder["coldkeys"]):
        item["displayed_score"] = 1.04 ** (-60 + k)
    variants = [body]
    for change in (
        {"displayed_score": 0.123456},
        {"displayed_score": 0},
        {"displayed_score": True},
        {"status": "SEALED_UNTIL_GRAIN"},
    ):
        bad = copy.deepcopy(body)
        bad["leaderboard"]["ladder"]["coldkeys"][0].update(change)
        variants.append(bad)
    bad = copy.deepcopy(body)
    bad["leaderboard"]["ladder"]["display_grid"] = "absolute"
    variants.append(bad)
    trust = fixtures.fixture_trust()
    items, expected = [], []
    for variant in variants:
        text = json.dumps(fixtures.sign(variant))
        items.append({"text": text, "fixture": True, "keys": sorted(trust.keys)})
        expected.append(_python(text, trust))
    assert "board" in expected[0]
    assert expected[1]["code"] == "ladder_unrounded"
    assert all("code" in e for e in expected[1:])
    assert _node({"mode": "project", "items": items}, tmp_path) == expected
    assert (
        feed.project(fixtures.sign(body), trust)["ladder"]["display_grid"]
        == "geometric"
    )


def test_the_live_v3_deployment_rule_finds_its_committed_grain():
    """Regression (r8.5 cutover, 2026-10-13): the feed read `rule_version` (2)
    as the rule's name, so the live v3-bank-sched deployment matched no entry
    and its ladder stayed sealed. The rule here is built exactly as a
    deployment builds it (`deployment.rule_for`), with the active candidate."""
    from pathlib import Path

    from carbon.battery import daemon, deployment

    repository = Path(__file__).resolve().parents[2]
    term = {
        "registry": "docs/development/evidence/battery-score-tuning/registry-v5.json",
        "registry_sha256": "70f2943814db0531429613e6ca5e2bd1c0b656673c6ee74de08e98f540758277",
        "candidate": "G-FEAS/A-Q>@0.05",
        "decision": "OWNER-BATTERY-SCORE-CANDIDATE-01",
    }
    v3 = deployment.rule_for({"rule": "v3-bank-sched", "score": term})
    assert v3["rule_version"] == 2  # not a name: the cause of the sealed ladder
    assert sl.rule_name(v3) == "v3-bank-sched"
    identities = {
        "challenge": {"id": "battery-fastcharge-ageing-development-v1"},
        "rule_digest": daemon.rule_digest(v3),
    }
    policy = sl.load_grain(repository, identities, v3)
    assert policy is not None and policy[2]["grain"] == 0.025
    # v2-bank-sched, as a deployment builds it, finds its own entry too.
    v2 = deployment.rule_for({"rule": "v2-bank-sched"})
    assert sl.rule_name(v2) == "v2-bank-sched"
    policy = sl.load_grain(
        repository,
        {**identities, "rule_digest": daemon.rule_digest(v2)},
        v2,
    )
    assert policy is not None and policy[2]["grain"] == 0.035
    # End to end: the live v3 rule DISPLAYS a score through the ladder (the
    # own-SE step also read `rule_version`, so nothing could ever display).
    policy3 = sl.load_grain(
        repository, {**identities, "rule_digest": daemon.rule_digest(v3)}, v3
    )
    noise = {
        "errors": [0.1, 0.12] * 147,
        "regrets": [0.2, 0.25] * 12,
    }  # 294 cases, 24 questions
    item = shown([row(score=0.8, noise=noise)], policy3, v3)["coldkeys"][0]
    assert item["displayed_score"] is not None and item["displayed_score"] <= 0.8
    # An unregistered rule body names no rule, so it seals.
    assert sl.rule_name({**v2, "window_cases": -1}) is None
    assert sl.load_grain(repository, identities, {**v2, "window_cases": -1}) is None
