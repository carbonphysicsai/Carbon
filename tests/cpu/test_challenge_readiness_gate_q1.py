"""V1 (Q1 alignment report) and V2 (panel discrimination) of the readiness gate."""

import json

import pytest

from carbon.challenge_pipeline.readiness import checks, model, q1

CHALLENGE = "chip-cold-plate"


def _members(outcomes=("d03", "d07", "d03")):
    return {
        f"m{i}": {
            "score": 1.0 - 0.1 * i,
            "value": (0, 0.1 * i),
            "eligible": True,
            "recipe": f"r{i}",
            "kind": "MODEL",
            "decision_outcome": o,
        }
        for i, o in enumerate(outcomes)
    }


REAL = {
    "provenance": "COUNTED_CAMPAIGN",
    "ref": "docs/development/evidence/motor-decision-counted-v2",
}


def _panel(members=None, reference=REAL):
    return {
        "reference": reference,
        "decision_study": "decision-study-ref",
        "members": members or _members(),
    }


@pytest.fixture
def recorded(monkeypatch, tmp_path):
    """Point the report loader at tmp_path and pin the scoring rule digest."""
    directory = tmp_path / CHALLENGE
    directory.mkdir()
    monkeypatch.setattr(q1, "PACKAGE", tmp_path)
    monkeypatch.setattr(
        q1, "current_rule_digest", lambda c, r=None: "sha256:" + "a" * 64
    )

    def write(panel=None, *, digest="sha256:" + "a" * 64, mutate=None):
        report = q1.build_report(CHALLENGE, 0, panel or _panel(), digest)
        if mutate:
            mutate(report)
        (directory / "q1_report.json").write_text(json.dumps(report), encoding="utf-8")

    return write


def _ctx():
    return checks.Context(challenge=CHALLENGE, level=0)


def _status(function):
    return function({}, _ctx()).status


def test_missing_report_fails_both_items(recorded):
    assert _status(q1.v1_alignment_report) == model.FAIL
    assert _status(q1.v2_panel_discrimination) == model.FAIL


def test_a_recorded_current_report_passes_v1_without_any_threshold(recorded):
    recorded(_panel(_members(("d03", "d03", "d03"))))
    result = q1.v1_alignment_report({}, _ctx())
    assert result.status == model.PASS
    assert any(e.startswith("tau:") for e in result.evidence)


def test_a_negative_tau_still_passes_v1(recorded):
    members = _members()
    for row in members.values():
        row["score"] = -row["score"]
    recorded(_panel(members))
    assert q1.v1_alignment_report({}, _ctx()).status == model.PASS


def test_stale_scoring_rule_digest_fails_v1(recorded):
    recorded(digest="sha256:" + "b" * 64)
    result = q1.v1_alignment_report({}, _ctx())
    assert result.status == model.FAIL and "stale" in result.detail


def test_tampered_alignment_fails_v1(recorded):
    recorded(mutate=lambda r: r["alignment"].__setitem__("kendall_tau_b", 0.99))
    result = q1.v1_alignment_report({}, _ctx())
    assert result.status == model.FAIL and "does not follow" in result.detail


@pytest.mark.parametrize(
    "reference",
    [
        {"provenance": "ANALYTICAL_FIXTURE", "ref": REAL["ref"]},
        {"provenance": "SYNTHETIC", "ref": REAL["ref"]},
        {"provenance": "MADE_UP", "ref": REAL["ref"]},
        {"provenance": "COUNTED_CAMPAIGN", "ref": "no/such/path"},
        {"provenance": "COUNTED_CAMPAIGN"},
        {"ref": REAL["ref"]},
        None,
    ],
)
def test_fixture_or_undetermined_references_fail_both_items(recorded, reference):
    recorded(_panel(reference=reference))
    assert _status(q1.v1_alignment_report) == model.FAIL
    assert _status(q1.v2_panel_discrimination) == model.FAIL


@pytest.mark.parametrize("kind", q1.REAL_REFERENCE_KINDS)
def test_constructed_members_judged_on_real_references_pass(recorded, kind):
    members = _members()
    members["m0"]["kind"] = "REGISTERED_BASELINE"
    members["m1"]["kind"] = "CONTROL"
    recorded(_panel(members, {"provenance": kind, "ref": REAL["ref"]}))
    result = q1.v1_alignment_report({}, _ctx())
    assert result.status == model.PASS, result.detail
    assert _status(q1.v2_panel_discrimination) == model.PASS
    report = json.loads(
        (q1.PACKAGE / CHALLENGE / "q1_report.json").read_text(encoding="utf-8")
    )
    assert report["member_kinds"] == {
        "CONTROL": 1,
        "MODEL": 1,
        "REGISTERED_BASELINE": 1,
    }


def test_no_registered_scoring_fails_v1(recorded, monkeypatch):
    recorded()
    monkeypatch.setattr(q1, "current_rule_digest", lambda c, r=None: None)
    assert _status(q1.v1_alignment_report) == model.FAIL


def test_report_for_another_challenge_or_level_is_unusable(recorded):
    recorded(mutate=lambda r: r.__setitem__("level", 1))
    assert _status(q1.v1_alignment_report) == model.FAIL


@pytest.mark.parametrize(
    "outcomes, status",
    [
        (("d03", "d03", "d03"), model.FAIL),
        (("d03", "d07", "d03"), model.PASS),
        (("d03", "ABSTAIN"), model.PASS),
    ],
)
def test_v2_needs_two_distinct_decision_outcomes(recorded, outcomes, status):
    recorded(_panel(_members(outcomes)))
    assert _status(q1.v2_panel_discrimination) == status


def test_v2_ignores_ineligible_members_and_refuses_unrecorded_outcomes(recorded):
    members = _members(("d03", "d03", "d09"))
    members["m2"]["eligible"] = False
    recorded(_panel(members))
    assert _status(q1.v2_panel_discrimination) == model.FAIL
    members = _members()
    del members["m1"]["decision_outcome"]
    recorded(_panel(members))
    assert _status(q1.v2_panel_discrimination) == model.FAIL


def test_the_real_scoring_rule_digest_resolves_for_registered_scorings():
    assert q1.current_rule_digest("chip-cold-plate").startswith("sha256:")
    # Every registered scoring resolves to the digest of its own rule identity
    # (not a fixed count: more challenges register over time).
    from carbon.challenge_validator import scoring

    for challenge in scoring.registered():
        digest = q1.current_rule_digest(challenge)
        assert digest is not None and digest.startswith("sha256:"), challenge
    # A challenge with no registered scoring has no rule to be current against.
    assert q1.current_rule_digest("not-a-registered-challenge") is None


def test_build_cli_binds_the_rule_digest_and_recomputes(tmp_path):
    panel = tmp_path / "panel.json"
    panel.write_text(json.dumps(_panel()), encoding="utf-8")
    out = tmp_path / "report.json"
    assert (
        q1.main(
            [
                "build",
                "--challenge",
                CHALLENGE,
                "--panel",
                str(panel),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["scoring_rule_digest"] == q1.current_rule_digest(CHALLENGE)
    assert (
        q1.main(
            [
                "build",
                "--challenge",
                "not-a-registered-challenge",
                "--panel",
                str(panel),
                "--out",
                str(out),
            ]
        )
        == 2
    )


def test_v2_counts_distinct_whole_vector_outcomes_for_per_scenario_decisions(recorded):
    members = _members(("x", "x", "x"))
    vector = {"s1": "c1=1", "s2": "ABSTAIN"}
    for row in members.values():
        row["decision_outcome"] = dict(vector)
    recorded(_panel(members))
    assert _status(q1.v2_panel_discrimination) == model.FAIL
    members["m1"]["decision_outcome"] = {"s2": "ABSTAIN", "s1": "c1=2"}
    recorded(_panel(members))
    assert _status(q1.v2_panel_discrimination) == model.PASS
    members["m1"]["decision_outcome"] = {"s2": "ABSTAIN", "s1": "c1=1"}
    recorded(_panel(members))
    assert (
        _status(q1.v2_panel_discrimination) == model.FAIL
    ), "key order is not a difference"
    members["m1"]["decision_outcome"] = {}
    recorded(_panel(members))
    assert (
        _status(q1.v2_panel_discrimination) == model.FAIL
    ), "an empty vector is unrecorded"


def test_v2_does_not_count_aliased_members_as_distinct(recorded):
    members = _members(("d03", "d03", "d07"))
    # m2 chose differently but is an alias of m0 (identical predictions): its
    # outcome is not distinct evidence, so only one outcome remains.
    panel = _panel(members)
    panel["aliases"] = [{"alias": "m2", "target": "m0"}]
    recorded(panel)
    assert _status(q1.v2_panel_discrimination) == model.FAIL
    panel["aliases"] = []
    recorded(panel)
    assert _status(q1.v2_panel_discrimination) == model.PASS


@pytest.mark.parametrize(
    "aliases",
    [
        [{"alias": "m2", "target": "nobody"}],
        [{"alias": "m2", "target": "m2"}],
        [{"alias": "m1", "target": "m2"}, {"alias": "m2", "target": "m0"}],
        "m2",
    ],
)
def test_malformed_aliases_fail_closed(recorded, aliases):
    panel = _panel(_members(("d03", "d07", "d09")))
    panel["aliases"] = aliases
    recorded(panel)
    assert _status(q1.v2_panel_discrimination) == model.FAIL
