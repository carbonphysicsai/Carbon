"""Break batch-1 protections using public, inert fixtures only."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_pipeline.readiness import checks, model


@pytest.fixture
def context(tmp_path):
    target = "tests/fixture.py::test_assertion"
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/fixture.py").write_text("def test_assertion(): pass\n")
    record = {
        "challenge": "fixture-challenge",
        "levels": [2],
        "basis": "Public scripted Level 2 fixture.",
        "tests": [target],
    }
    return checks.Context(
        "fixture-challenge",
        2,
        tmp_path,
        data={"tests_by_level": {"P3": {"2": record}}},
    )


def pytest_double(monkeypatch, *, level=2, status="", returncode=0, summary=True):
    def run(command, **kwargs):
        assert "--junitxml" in command
        report = Path(command[command.index("--junitxml") + 1])
        report.write_text(
            f'<testsuites><testsuite><testcase name="test_assertion">{status}'
            "</testcase></testsuite></testsuites>"
        )
        output = ""
        if summary:
            output = (
                "READINESS_LEVEL_EVIDENCE "
                + json.dumps(
                    {"item": "P3", "challenge": "fixture-challenge", "level": level}
                )
                + "\n"
            )
        return SimpleNamespace(returncode=returncode, stdout=output + "1 passed\n")

    monkeypatch.setattr(checks.subprocess, "run", run)


def test_a_matching_executed_assertion_records_its_identity(context, monkeypatch):
    pytest_double(monkeypatch)
    result = checks.recorded_tests({"id": "P3"}, context)
    assert result.status == model.PASS
    assert any("tests/fixture.py:" in row for row in result.evidence)
    assert any("READINESS_LEVEL_EVIDENCE" in row for row in result.evidence)


def test_an_unlisted_level_cannot_inherit_legacy_or_neutral_tests(context):
    context.level = 3
    context.data["tests"] = {"P3": ["tests/fixture.py"]}
    item = {"id": "P3", "pending": {"neutral_tests": ["tests/fixture.py"]}}
    assert checks.recorded_tests(item, context).status == model.NOT_BUILT


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        {"challenge": "another"},
        {"levels": [3]},
        {"levels": [True]},
        {"levels": [2, 2]},
        {"basis": ""},
        {"tests": []},
        {"tests": ["tests/../outside.py"]},
        {"tests": ["tests/fixture.txt"]},
    ],
)
def test_malformed_or_mismatched_level_records_fail(context, mutation):
    if mutation is None:
        context.data["tests_by_level"]["P3"]["2"] = None
    else:
        context.data["tests_by_level"]["P3"]["2"].update(mutation)
    assert checks.recorded_tests({"id": "P3"}, context).status == model.FAIL


@pytest.mark.parametrize("status", ["<skipped/>", "<failure/>", "<error/>"])
def test_zero_exit_cannot_hide_a_skipped_or_failed_assertion(
    context, monkeypatch, status
):
    pytest_double(monkeypatch, status=status)
    assert checks.recorded_tests({"id": "P3"}, context).status == model.FAIL


def test_wrong_level_summary_fails(context, monkeypatch):
    pytest_double(monkeypatch, level=1)
    assert checks.recorded_tests({"id": "P3"}, context).status == model.FAIL


def test_missing_summary_cannot_be_disabled_by_the_record(context, monkeypatch):
    context.data["tests_by_level"]["P3"]["2"]["summary"] = False
    pytest_double(monkeypatch, summary=False)
    assert checks.recorded_tests({"id": "P3"}, context).status == model.FAIL


def test_a_nonzero_pytest_exit_fails(context, monkeypatch):
    pytest_double(monkeypatch, returncode=1)
    assert checks.recorded_tests({"id": "P3"}, context).status == model.FAIL


def test_missing_declared_file_fails(context):
    context.data["tests_by_level"]["P3"]["2"]["tests"] = ["tests/absent.py"]
    assert checks.recorded_tests({"id": "P3"}, context).status == model.FAIL


def test_legacy_records_keep_working_without_level_inheritance(context, monkeypatch):
    context.data = {"tests": {"P7": ["tests/fixture.py"]}}
    monkeypatch.setattr(
        checks.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="1 passed"),
    )
    assert checks.recorded_tests({"id": "P7"}, context).status == model.PASS


def test_p3_assertion_detects_an_omitted_level4_stage(tmp_path, capsys, monkeypatch):
    import test_graphite_readiness_level_evidence as assertions

    real = assertions.phase3.dry_run_script
    monkeypatch.setattr(
        assertions.phase3, "dry_run_script", lambda *args, **kwargs: real(*args)
    )
    with pytest.raises(AssertionError):
        assertions.test_phase3_dry_run_at_the_named_level(
            tmp_path, capsys, monkeypatch, 4
        )


def test_r7_assertion_detects_a_false_remaining_budget(tmp_path, monkeypatch):
    import test_graphite_readiness_level_evidence as assertions

    real = assertions.research_loop.budget_status

    def false_budget(*args, **kwargs):
        message = copy.deepcopy(real(*args, **kwargs))
        message["content"] = "0 of 0 provider calls left"
        return message

    monkeypatch.setattr(assertions.research_loop, "budget_status", false_budget)
    with pytest.raises(AssertionError):
        assertions.test_each_roles_turn_text_matches_its_scripted_ledger(
            tmp_path, monkeypatch, 2, assertions.RoleName.CONSTRUCTOR
        )


@pytest.mark.parametrize("fault", ["no_control", "dropped_family", "uncovered_family"])
def test_a2_cannot_drop_a_family_or_its_controls(context, monkeypatch, fault):
    from carbon.agent_campaign.attack import adapter as core
    from carbon.agent_campaign.graphite import phase4

    family = SimpleNamespace(name="fixture-family")
    adapter = SimpleNamespace(
        families=lambda: [family],
        controls=lambda split: (
            [] if fault == "no_control" else [SimpleNamespace(family=family.name)]
        ),
    )
    monkeypatch.setattr(core, "ADAPTERS", {(context.challenge, context.level): adapter})
    row = {"family": family.name, "label": "unreachable"}
    table = {
        "families": [],
        "unreachable": [row] if fault == "uncovered_family" else [],
    }
    monkeypatch.setattr(phase4, "stop_rule_coverage", lambda *a, **k: table)
    assert checks.attack_families({"id": "A2"}, context).status == model.FAIL


def test_a3_assertion_detects_premature_finish(tmp_path, monkeypatch):
    import test_graphite_readiness_level_evidence as assertions

    monkeypatch.setattr(assertions.phase4, "finish_verdict", lambda *a: (True, "done"))
    with pytest.raises(AssertionError):
        assertions.test_the_level_provider_records_its_rule_and_withholds_finish(
            tmp_path, monkeypatch, 2
        )


def test_s2_assertion_detects_ranking_a_gate_failure(monkeypatch):
    import test_graphite_readiness_level_evidence as assertions

    monkeypatch.setattr(assertions.delivery, "best_improvement", lambda rows: rows[0])
    with pytest.raises(AssertionError):
        assertions.test_graphite_filters_gate_failures_before_ranking(2)


@pytest.mark.parametrize("report", ["", "<testsuites/>", "not xml"])
def test_missing_empty_or_malformed_execution_report_fails(
    context, monkeypatch, report
):
    def run(command, **kwargs):
        if report:
            Path(command[command.index("--junitxml") + 1]).write_text(report)
        return SimpleNamespace(returncode=0, stdout="1 passed")

    monkeypatch.setattr(checks.subprocess, "run", run)
    assert checks.recorded_tests({"id": "P3"}, context).status == model.FAIL


def test_deselected_recorded_assertion_cannot_hide_behind_another_pass(
    context, monkeypatch
):
    context.data["tests_by_level"]["P3"]["2"]["tests"].append(
        "tests/fixture.py::test_second"
    )
    pytest_double(monkeypatch)
    assert checks.recorded_tests({"id": "P3"}, context).status == model.FAIL
