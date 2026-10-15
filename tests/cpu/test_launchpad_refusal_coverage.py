"""T03 static inventory controls; these do not execute application refusals."""

from __future__ import annotations

import ast
import builtins
import json
import os
import subprocess

import pytest

from scripts.dev import launchpad_refusal_coverage as coverage

CATALOG = "scripts/dev/miner_launchpad/supervisor.py"
DOOR = "carbon/miner_mcp/door.py"
TEST = "tests/cpu/test_refusal_example.py"


def sample(*, catalog="old_gap", test=None, raised=None):
    files = {CATALOG: f"NEXT_ACTIONS = {{{catalog!r}: 'Next step'}}\n"}
    if test:
        files[TEST] = f"def test_refusal():\n    assert result.code == {test!r}\n"
    if raised:
        files[DOOR] = f"def door():\n    raise Rejected({raised!r})\n"
    return files


def test_catalog_table_raise_response_and_exact_test_pointers():
    files = sample(
        catalog="named_refusal", test="named_refusal", raised="named_refusal"
    )
    files[DOOR] += "answer = {'error': 'another_refusal'}\n"
    files[CATALOG] += "REFUSAL_FIELDS = {'table_refusal': ('field',)}\n"
    result = coverage.inventory(files)
    assert set(result["codes"]) == {"named_refusal", "another_refusal", "table_refusal"}
    row = result["codes"]["named_refusal"]
    assert {site["kind"] for site in row["sources"]} == {"catalog", "raise"}
    assert row["tests"] == [{"path": TEST, "line": 2}]
    assert coverage.unreached(result) == {"another_refusal", "table_refusal"}


def test_comments_and_docstrings_are_not_test_references():
    files = sample(catalog="named_refusal")
    files[TEST] = (
        '"""named_refusal"""\n'
        "# named_refusal\n"
        "def test_case():\n"
        '    """named_refusal"""\n'
        "    assert True\n"
    )
    files["tests/browser/test.js"] = "'named_refusal';"
    assert coverage.unreached(coverage.inventory(files)) == {"named_refusal"}


def test_reference_measure_does_not_claim_an_executed_refusal():
    files = sample(catalog="named_refusal")
    files[TEST] = "fixture_only = 'named_refusal'\n"
    result = coverage.inventory(files)
    assert not coverage.unreached(result)
    text = coverage.render(result, coverage.baseline(result, "a" * 40))
    assert "not executed refusal reachability" in text
    assert "fixture data or an unexecuted branch" in text


@pytest.mark.parametrize("site", ["catalog", "raise", "response"])
def test_new_unreached_code_refuses_in_each_inventory_source(site):
    before = coverage.inventory(sample())
    files = sample()
    if site == "catalog":
        files[CATALOG] += "NEXT_ACTIONS = {'new_gap': 'Next step'}\n"
    elif site == "raise":
        files[DOOR] = "raise SetupRefused('consent', 'new_gap')\n"
    else:
        files[DOOR] = "answer = {'refused': 'new_gap'}\n"
    result = coverage.regressions(coverage.inventory(files), before)
    assert result["new_unreached"] == ["new_gap"]
    assert result["unreached_increased"] is True


def test_same_count_cannot_exchange_an_old_gap_for_a_new_one():
    result = coverage.regressions(
        coverage.inventory(sample(catalog="new_gap")), coverage.inventory(sample())
    )
    assert result["unreached_increased"] is False
    assert result["new_unreached"] == ["new_gap"]


@pytest.mark.parametrize(
    "statement",
    [
        "NEXT_ACTIONS['new_gap'] = 'Next step'",
        "NEXT_ACTIONS.update({'new_gap': 'Next step'})",
        "NEXT_ACTIONS.setdefault('new_gap', 'Next step')",
        "NEXT_ACTIONS |= {'new_gap': 'Next step'}",
        "NEXT_ACTIONS.update(new_gap='Next step')",
        "raise NewDoorRefused('new_gap')",
    ],
)
def test_catalog_extension_and_new_typed_constructor_do_not_escape_check(statement):
    files = sample()
    files[CATALOG] += statement + "\n"
    result = coverage.regressions(
        coverage.inventory(files), coverage.inventory(sample())
    )
    assert result["new_unreached"] == ["new_gap"]


@pytest.mark.parametrize(
    "call",
    [
        "SetupRefused('consent', 'new_gap')",
        "SetupRefused('consent', code='new_gap')",
        "SetupRefused(field='consent', code='new_gap')",
        "environment_setup.SetupRefused(code='new_gap', field='consent')",
        "Rejected(code='new_gap')",
        "AttachRefused(code='new_gap', message='fixed')",
    ],
)
def test_real_code_argument_position_and_keywords_refuse_unreferenced_code(call):
    files = sample()
    # Existing test references to a field must never hide a new setup refusal.
    files[TEST] = "expected_field = 'consent'\n"
    before = coverage.inventory(files)
    files[DOOR] = f"raise {call}\n"
    after = coverage.inventory(files)
    assert "consent" not in after["codes"]
    assert coverage.regressions(after, before)["new_unreached"] == ["new_gap"]
    files[TEST] += "expected_code = 'new_gap'\n"
    assert not any(coverage.regressions(coverage.inventory(files), before).values())


def test_setup_argument_rule_matches_actual_public_constructor_signature():
    source = coverage.ROOT / "scripts/dev/miner_launchpad/environment_setup.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    setup = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SetupRefused"
    )
    init = next(
        node
        for node in setup.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    arguments = [arg.arg for arg in init.args.args[1:]]
    assert arguments.index("code") == coverage.CODE_ARGUMENTS["SetupRefused"]


def test_removing_an_existing_test_reference_refuses():
    result = coverage.regressions(
        coverage.inventory(sample()), coverage.inventory(sample(test="old_gap"))
    )
    assert result["lost_references"] == ["old_gap"]


def test_reference_addition_and_backlog_reduction_are_allowed():
    before = coverage.inventory(sample())
    files = sample(test="old_gap", raised="new_referenced")
    files[TEST] += "expected = 'new_referenced'\n"
    assert not any(coverage.regressions(coverage.inventory(files), before).values())


def test_dynamic_expressions_are_reported_without_guessing_a_code():
    files = sample()
    files[DOOR] = "raise Rejected(exception.code)\n"
    result = coverage.inventory(files)
    assert set(result["codes"]) == {"old_gap"}
    assert result["dynamic_sites"] == [
        {"path": DOOR, "line": 1, "constructor": "Rejected"}
    ]


def test_inventory_does_not_import_or_run_the_inventoried_application(monkeypatch):
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.startswith(("carbon", "scripts.dev.miner_launchpad")):
            raise AssertionError("application import refused")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    files = sample(test="old_gap")
    files[DOOR] = "raise RuntimeError('this source must never execute')\n"
    assert not coverage.unreached(coverage.inventory(files))


def test_report_is_deterministic_and_each_gap_has_a_prioritized_child_ticket():
    files = sample(raised="door_gap")
    first = coverage.inventory(files)
    second = coverage.inventory(dict(reversed(list(files.items()))))
    initial = coverage.baseline(first, "a" * 40)
    assert coverage.render(first, initial) == coverage.render(second, initial)
    report = coverage.render(first, initial)
    assert "T03-REFUSAL-door_gap" in report
    assert "T03-REFUSAL-old_gap" in report
    assert "/ P1" in report and "/ P2" in report


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def put(root, files):
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")


def test_cli_compares_actual_git_base_not_an_inflated_allowance(tmp_path, capsys):
    git(tmp_path, "init", "-q")
    files = sample()
    files[DOOR] = ""
    files[TEST] = ""
    put(tmp_path, files)
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "-qm",
        "public fixture base",
    )
    revision = git(tmp_path, "rev-parse", "HEAD")
    # Editing the baseline cannot hide a new, unreferenced production refusal.
    files[DOOR] = "raise Rejected('new_gap')\n"
    put(tmp_path, files)
    allowance = coverage.baseline(coverage.inventory(files), revision)
    put(tmp_path, {coverage.BASELINE: json.dumps(allowance)})
    args = ["--root", str(tmp_path), "--check", "--base-ref", revision]
    assert coverage.main(args) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["new_unreached"] == ["new_gap"]
    put(tmp_path, {TEST: "expected = 'new_gap'\n"})
    assert coverage.main(args) == 0
    assert json.loads(capsys.readouterr().out)["new_unreached"] == []
    with pytest.raises(subprocess.CalledProcessError):
        coverage.main([*args[:-1], "missing-comparison-ref"])


def test_baseline_validation_refuses_unknown_fields_and_duplicate_codes(tmp_path):
    path = tmp_path / "baseline.json"
    value = coverage.baseline(coverage.inventory(sample()), "a" * 40)
    path.write_text(json.dumps({**value, "allow_new_gaps": True}))
    with pytest.raises(ValueError, match="invalid_refusal_reference_baseline"):
        coverage.read_baseline(path)
    value["codes"].append("old_gap")
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="invalid_refusal_reference_baseline"):
        coverage.read_baseline(path)


def test_initial_backlog_is_exactly_the_recorded_public_revision():
    initial = coverage.read_baseline(coverage.ROOT / coverage.BASELINE)
    revision, files = coverage.git_files(coverage.ROOT, initial["revision"])
    assert initial == coverage.baseline(coverage.inventory(files), revision)


def test_repository_has_no_new_unreached_refusal_codes():
    """Normal canonical CPU collection runs the actual comparison gate."""
    current = coverage.inventory(coverage.working_files(coverage.ROOT))
    ref = os.environ.get("QUALITY_BASE_SHA", "origin/main")
    revision, files = coverage.git_files(coverage.ROOT, ref)
    previous = coverage.inventory(files)
    result = coverage.regressions(current, previous)
    assert not any(result.values()), json.dumps(
        {
            "base": revision,
            "current_unreached": len(coverage.unreached(current)),
            **result,
        },
        sort_keys=True,
    )
