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

    def write(
        panel=None, *, digest="sha256:" + "a" * 64, mutate=None, level=0, name=None
    ):
        report = q1.build_report(CHALLENGE, level, panel or _panel(), digest)
        if mutate:
            mutate(report)
        (directory / (name or q1.report_name(level))).write_text(
            json.dumps(report), encoding="utf-8"
        )

    return write


def _ctx(level=0):
    return checks.Context(challenge=CHALLENGE, level=level)


def _status(function, level=0):
    return function({}, _ctx(level)).status


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


# -- P4: tool text v2 neutrality ----------------------------------------------------------------
def _fake_roles(monkeypatch, v1_text, v2_text, v2=True):
    import sys
    import types

    class Role:
        def tool_schemas(self, version):
            return [{"description": v1_text if version == "v1" else v2_text}]

    module = types.ModuleType("fake_roles")
    module.TOOL_TEXT_V1 = "v1"
    if v2:
        module.TOOL_TEXT_V2 = "v2"
    module.ROLES = {"r": Role()}
    monkeypatch.setitem(sys.modules, "carbon.agent_campaign.graphite.roles", module)
    import carbon.agent_campaign.graphite as package

    monkeypatch.setattr(package, "roles", module, raising=False)


def test_p4_v2_neutral_is_not_built_not_pass_until_other_parts_land(monkeypatch):
    monkeypatch.setattr(checks, "_challenge_tokens", lambda: ["chip-cold-plate"])
    _fake_roles(monkeypatch, "scores chip-cold-plate", "scores the Challenge")
    result = checks.neutral_path({}, _ctx())
    assert result.status == model.NOT_BUILT and "names no challenge" in result.detail


def test_p4_fails_when_v2_names_a_challenge_or_detector_is_blind(monkeypatch):
    monkeypatch.setattr(checks, "_challenge_tokens", lambda: ["chip-cold-plate"])
    _fake_roles(monkeypatch, "scores chip-cold-plate", "still chip-cold-plate")
    assert checks.neutral_path({}, _ctx()).status == model.FAIL
    _fake_roles(monkeypatch, "no names here", "no names here")
    blind = checks.neutral_path({}, _ctx())
    assert blind.status == model.FAIL and "blind" in blind.detail


def test_p4_without_versioned_tool_text_is_not_built(monkeypatch):
    _fake_roles(monkeypatch, "a", "b", v2=False)
    assert checks.neutral_path({}, _ctx()).status == model.NOT_BUILT


def test_neutral_test_ids_are_selected_for_this_challenge(monkeypatch):
    seen = []
    monkeypatch.setattr(
        checks,
        "run_tests",
        lambda ctx, paths: seen.append(paths) or model.Result(model.PASS, "ok"),
    )
    item = {
        "id": "P5",
        "pending": {
            "neutral_tests": [
                "tests/cpu/test_challenge_readiness_gate_q1.py::t[{challenge}]"
            ]
        },
    }
    checks.recorded_tests(item, _ctx())
    assert seen == [[f"tests/cpu/test_challenge_readiness_gate_q1.py::t[{CHALLENGE}]"]]


def test_p4_passes_only_with_neutral_v2_and_passing_plumbing_tests(monkeypatch):
    monkeypatch.setattr(checks, "_challenge_tokens", lambda: ["chip-cold-plate"])
    _fake_roles(monkeypatch, "scores chip-cold-plate", "scores the Challenge")
    ctx = checks.Context(challenge=CHALLENGE, level=0, data={"tests": {"P4": ["t.py"]}})
    monkeypatch.setattr(
        checks, "run_tests", lambda c, p: model.Result(model.PASS, "ok")
    )
    assert checks.neutral_path({"id": "P4"}, ctx).status == model.PASS
    monkeypatch.setattr(
        checks, "run_tests", lambda c, p: model.Result(model.FAIL, "red")
    )
    assert checks.neutral_path({"id": "P4"}, ctx).status == model.FAIL


# -- per-level reports ---------------------------------------------------------------------------
def test_the_l0_report_does_not_satisfy_l1(recorded):
    recorded()  # level 0, the legacy name q1_report.json
    assert _status(q1.v1_alignment_report, 0) == model.PASS
    assert _status(q1.v1_alignment_report, 1) == model.FAIL
    assert _status(q1.v2_panel_discrimination, 1) == model.FAIL


def test_an_l1_report_satisfies_l1_and_leaves_l0_alone(recorded):
    recorded(level=1)
    assert _status(q1.v1_alignment_report, 1) == model.PASS
    assert _status(q1.v2_panel_discrimination, 1) == model.PASS
    assert _status(q1.v1_alignment_report, 0) == model.FAIL


def test_both_levels_can_be_recorded_side_by_side(recorded):
    recorded(level=0)
    recorded(level=1)
    for level in (0, 1):
        assert _status(q1.v1_alignment_report, level) == model.PASS
        assert _status(q1.v2_panel_discrimination, level) == model.PASS


def test_a_report_whose_recorded_level_differs_from_its_file_fails(recorded):
    recorded(level=0, name="q1_report.L1.json")  # records level 0 under the L1 name
    result = q1.v1_alignment_report({}, _ctx(1))
    assert result.status == model.FAIL and "another challenge or level" in result.detail
    assert _status(q1.v2_panel_discrimination, 1) == model.FAIL


def test_the_legacy_name_is_read_as_level_zero_only(recorded):
    recorded(level=1, name="q1_report.json")  # an L1 report under the L0 name
    assert _status(q1.v1_alignment_report, 0) == model.FAIL
    assert _status(q1.v1_alignment_report, 1) == model.FAIL


def test_reference_provenance_rules_apply_at_every_level(recorded):
    recorded(_panel(reference={"provenance": "SYNTHETIC", "ref": REAL["ref"]}), level=1)
    assert _status(q1.v1_alignment_report, 1) == model.FAIL
    assert _status(q1.v2_panel_discrimination, 1) == model.FAIL


def test_the_build_command_writes_the_per_level_file(tmp_path, monkeypatch):
    monkeypatch.setattr(q1, "PACKAGE", tmp_path)
    monkeypatch.setattr(
        q1, "current_rule_digest", lambda c, r=None: "sha256:" + "a" * 64
    )
    panel = tmp_path / "panel.json"
    panel.write_text(json.dumps(_panel()), encoding="utf-8")
    for level, name in ((0, "q1_report.json"), (2, "q1_report.L2.json")):
        argv = [
            "build",
            "--challenge",
            CHALLENGE,
            "--level",
            str(level),
            "--panel",
            str(panel),
        ]
        assert q1.main(argv) == 0
        written = json.loads((tmp_path / CHALLENGE / name).read_text("utf-8"))
        assert written["level"] == level


# -- score-basis split (Test Lead ruling, 2026-10-12) ---------------------------------------------
PRIMARY = "named frozen-rule score"
OTHER = "unnamed-rule aggregate"
COMMITTED_L1_SOURCE_SHA = (
    "sha256:5b3ba57430ba2a0087626b249ab9afbd576edebed2706187654d5786103dacf7"
)


def _mixed_panel():
    return _panel(_members(("d03", "d07", "d03", "d07", "d03")))


@pytest.fixture
def split(monkeypatch, tmp_path):
    """A mixed-basis source report, its basis evidence and the derived primary report."""
    directory = tmp_path / CHALLENGE
    directory.mkdir()
    monkeypatch.setattr(q1, "PACKAGE", tmp_path)
    monkeypatch.setattr(
        q1, "current_rule_digest", lambda c, r=None: "sha256:" + "a" * 64
    )
    source = q1.build_report(CHALLENGE, 1, _mixed_panel(), "sha256:" + "a" * 64)
    (directory / "q1_report.L1.mixed-basis.json").write_text(
        json.dumps(source), encoding="utf-8"
    )
    evidence = {
        name: {
            "basis": PRIMARY if name in ("m0", "m1", "m2") else OTHER,
            "score": row["score"],
        }
        for name, row in source["members"].items()
    }
    (directory / "q1_basis.L1.json").write_text(json.dumps(evidence), encoding="utf-8")

    def derive():
        return q1.build_primary_report(
            directory / "q1_report.L1.mixed-basis.json",
            directory / "q1_basis.L1.json",
            PRIMARY,
        )

    def write(report):
        (directory / "q1_report.L1.json").write_text(
            json.dumps(report), encoding="utf-8"
        )

    report = derive()
    write(report)
    return directory, report, write, derive


def test_a_derived_primary_report_passes_and_names_the_secondary(split):
    _, report, _, _ = split
    assert sorted(report["members"]) == ["m0", "m1", "m2"]
    assert [e["member"] for e in report["basis_split"]["excluded"]] == ["m3", "m4"]
    result = q1.v1_alignment_report({}, _ctx(1))
    assert result.status == model.PASS
    assert "SECONDARY" in result.detail
    assert "primary_n:3" in result.evidence
    assert "secondary_mixed_basis_n:5" in result.evidence
    assert _status(q1.v2_panel_discrimination, 1) == model.PASS


def test_the_alignment_is_recomputed_on_the_primary_members_only(split):
    _, report, _, _ = split
    assert report["alignment"] == q1._alignment_of(report["members"])
    mixed = json.loads(json.dumps(q1._alignment_of(_mixed_panel()["members"])))
    assert report["alignment"] != mixed


def test_v2_counts_only_primary_members(split):
    directory, _, write, _ = split
    source_path = directory / "q1_report.L1.mixed-basis.json"
    source = json.loads(source_path.read_text())
    for name in ("m0", "m1", "m2"):
        source["members"][name]["decision_outcome"] = "d03"
    source["members"]["m3"]["decision_outcome"] = "d09"
    source_path.write_text(json.dumps(source))
    report = q1.build_primary_report(
        source_path, directory / "q1_basis.L1.json", PRIMARY
    )
    write(report)
    assert _status(q1.v2_panel_discrimination, 1) == model.FAIL


def _rewrite_evidence(directory, report, edit):
    path = directory / "q1_basis.L1.json"
    evidence = json.loads(path.read_text())
    edit(evidence)
    path.write_text(json.dumps(evidence))
    report["basis_split"]["basis_evidence"]["sha256"] = q1.file_sha256(path)


@pytest.mark.parametrize(
    "tamper",
    [
        "row_edited",
        "member_added_from_other_basis",
        "excluded_wrong",
        "secondary_tau_changed",
        "primary_basis_renamed",
        "source_digest",
        "evidence_digest",
        "evidence_basis_missing",
        "evidence_score_differs",
        "source_deleted",
    ],
)
def test_a_split_that_does_not_follow_from_its_committed_files_fails_closed(
    split, tamper
):
    directory, report, write, _ = split
    block = report["basis_split"]
    if tamper == "row_edited":
        report["members"]["m0"]["score"] = 99.0
    elif tamper == "member_added_from_other_basis":
        source = json.loads((directory / "q1_report.L1.mixed-basis.json").read_text())
        report["members"]["m3"] = {**source["members"]["m3"], "basis": PRIMARY}
    elif tamper == "excluded_wrong":
        block["excluded"] = block["excluded"][:1]
    elif tamper == "secondary_tau_changed":
        block["secondary"]["kendall_tau_b"] = 0.99
    elif tamper == "primary_basis_renamed":
        block["primary_basis"] = OTHER
    elif tamper == "source_digest":
        block["source"]["sha256"] = "sha256:" + "0" * 64
    elif tamper == "evidence_digest":
        (directory / "q1_basis.L1.json").write_text("{}")
    elif tamper == "evidence_basis_missing":
        _rewrite_evidence(directory, report, lambda e: e["m4"].pop("basis"))
    elif tamper == "evidence_score_differs":
        _rewrite_evidence(directory, report, lambda e: e["m0"].update(score=5.0))
    elif tamper == "source_deleted":
        (directory / "q1_report.L1.mixed-basis.json").unlink()
    write(report)
    for function in (q1.v1_alignment_report, q1.v2_panel_discrimination):
        result = function({}, _ctx(1))
        assert result.status == model.FAIL
        assert "score-basis split" in result.detail


def test_a_member_with_no_recorded_basis_cannot_be_derived(split):
    directory, _, _, derive = split
    path = directory / "q1_basis.L1.json"
    evidence = json.loads(path.read_text())
    del evidence["m1"]
    path.write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="no recorded score basis"):
        derive()


def test_a_split_file_name_cannot_leave_the_report_folder(split):
    _, report, write, _ = split
    report["basis_split"]["source"]["file"] = "../elsewhere.json"
    write(report)
    assert q1.v1_alignment_report({}, _ctx(1)).status == model.FAIL


def test_a_report_without_a_split_is_read_as_before(recorded):
    recorded(level=1)
    assert _status(q1.v1_alignment_report, 1) == model.PASS


def test_the_committed_level_one_split_follows_from_its_committed_files():
    folder = q1.PACKAGE / "battery-fastcharge-ageing-development-v1"
    report = json.loads((folder / "q1_report.L1.json").read_bytes())
    block = report["basis_split"]
    assert q1.split_problem(report, folder) is None
    assert len(report["members"]) == 14 and block["secondary"]["members"] == 20
    assert all(
        row["basis"] == block["primary_basis"] for row in report["members"].values()
    )
    assert {e["member"][:5] for e in block["excluded"]} == {"miner"}
    # the executor's 20-member file is kept byte-identical, never edited
    source = folder / "q1_report.L1.mixed-basis.json"
    assert q1.file_sha256(source) == COMMITTED_L1_SOURCE_SHA
    assert block["source"]["sha256"] == COMMITTED_L1_SOURCE_SHA
    assert q1._alignment_of(report["members"]) == report["alignment"]


# -- rescoring non-primary members under the primary rule -----------------------------------------
@pytest.fixture
def rescored(split):
    directory, _, write, _ = split
    rows = [{"member": name, "output_digest_matches": True} for name in ("m3", "m4")]
    # the fixture's source scores are 1.0 - 0.1 * i (higher is better): rescore rows carry the positive error
    source = json.loads((directory / "q1_report.L1.mixed-basis.json").read_text())
    for row in rows:
        row["recorded_score"] = -source["members"][row["member"]]["score"]
        row["recomputed_score"] = row["recorded_score"] + 1e-7
    path = directory / "q1_rescore.L1.json"
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")

    def derive(**changes):
        edited = json.loads(path.read_text())
        for key, value in changes.items():
            for row in edited["rows"]:
                row[key] = value
        path.write_text(json.dumps(edited), encoding="utf-8")
        report = q1.build_primary_report(
            directory / "q1_report.L1.mixed-basis.json",
            directory / "q1_basis.L1.json",
            PRIMARY,
            rescore_path=path,
        )
        write(report)
        return report

    return directory, path, write, derive


def test_rescored_members_join_the_primary_with_their_recomputed_score(rescored):
    directory, path, _, derive = rescored
    report = derive()
    assert sorted(report["members"]) == ["m0", "m1", "m2", "m3", "m4"]
    assert report["basis_split"]["excluded"] == []
    assert report["members"]["m3"]["score"] == -(
        json.loads(path.read_text())["rows"][0]["recomputed_score"]
    )
    assert q1.split_problem(report, directory) is None
    assert q1.v1_alignment_report({}, _ctx(1)).status == model.PASS
    assert q1.v2_panel_discrimination({}, _ctx(1)).status == model.PASS


def test_a_rescore_whose_output_digest_was_not_verified_leaves_the_member_excluded(
    rescored,
):
    _, _, _, derive = rescored
    report = derive(output_digest_matches=False)
    assert sorted(report["members"]) == ["m0", "m1", "m2"]
    assert "rescored" not in report["basis_split"]


def test_a_recomputed_score_that_does_not_round_to_the_recorded_one_is_not_accepted(
    rescored,
):
    _, _, _, derive = rescored
    report = derive(recomputed_score=9.9)
    assert sorted(report["members"]) == ["m0", "m1", "m2"]


@pytest.mark.parametrize(
    "tamper", ["score_edited", "rescore_digest", "rescore_row_dropped", "basis_member"]
)
def test_a_rescore_that_does_not_follow_from_its_committed_record_fails_closed(
    rescored, tamper
):
    _, path, write, derive = rescored
    report = derive()
    block = report["basis_split"]
    if tamper == "score_edited":
        report["members"]["m3"]["score"] = 0.123
        block["rescored"][0]["score"] = 0.123
    elif tamper == "rescore_digest":
        block["rescore"]["sha256"] = "sha256:" + "0" * 64
    elif tamper == "rescore_row_dropped":
        document = json.loads(path.read_text())
        document["rows"] = document["rows"][1:]
        path.write_text(json.dumps(document))
        block["rescore"]["sha256"] = q1.file_sha256(path)
    elif tamper == "basis_member":
        block["rescored"].append(
            {"member": "m0", "score": report["members"]["m0"]["score"]}
        )
    write(report)
    result = q1.v1_alignment_report({}, _ctx(1))
    assert result.status == model.FAIL and "score-basis split" in result.detail


def test_the_committed_same_basis_report_follows_from_its_committed_records():
    folder = q1.PACKAGE / "battery-fastcharge-ageing-development-v1"
    report = json.loads((folder / "q1_report.L1.same-basis.json").read_bytes())
    assert q1.split_problem(report, folder) is None
    assert len(report["members"]) == 20 and report["basis_split"]["excluded"] == []
    assert len(report["basis_split"]["rescored"]) == 6
    rescore = json.loads((folder / "q1_rescore.L1.json").read_bytes())
    assert all(r["output_digest_matches"] is True for r in rescore["rows"])
    assert all(
        abs(r["recomputed_score"] - r["recorded_score"]) <= q1.RESCORE_TOLERANCE
        for r in rescore["rows"]
    )
    assert q1._alignment_of(report["members"]) == report["alignment"]
    # the gate's own Level 1 report and the executor's mixed file are untouched by this variant
    assert (
        q1.file_sha256(folder / "q1_report.L1.mixed-basis.json")
        == COMMITTED_L1_SOURCE_SHA
    )
    gate = json.loads((folder / "q1_report.L1.json").read_bytes())
    assert len(gate["members"]) == 14
