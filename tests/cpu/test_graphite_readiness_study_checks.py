"""PLT-09 batch 3 known answers and mutations. No solver or sealed data."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from carbon.challenge_pipeline.readiness import checks, model
from carbon.challenge_pipeline.readiness import study_checks as study

CID = "battery-fastcharge-ageing-development-v1"
REPO = Path(__file__).resolve().parents[2]


def git(root, *args):
    return (
        subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE)
        .decode()
        .strip()
    )


def commit(ctx):
    git(ctx.repository, "add", ".")
    if (
        subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=ctx.repository, check=False
        ).returncode
        == 0
    ):
        return
    git(
        ctx.repository,
        "-c",
        "user.name=study-fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "synthetic study fixture",
    )


def write(ctx, path, document):
    target = ctx.repository / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document))
    return target


def record(ctx, item):
    return ctx.data["studies_by_level"][item][str(ctx.level)]


@pytest.fixture(params=[2, 3, 4])
def ctx(tmp_path, request):
    git(tmp_path, "init", "-q")
    data = copy.deepcopy(checks.load_challenge_data(CID))
    context = checks.Context(CID, request.param, repository=tmp_path, data=data)
    named = record(context, "D4")
    for field in ("manifest", "contract", "references", "checksum"):
        target = tmp_path / named[field]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO / named[field]).read_bytes())
    named = record(context, "D5")
    policy = tmp_path / named["policy_record"]
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_bytes((REPO / named["policy_record"]).read_bytes())
    target = tmp_path / named["legacy_report"]
    target.parent.mkdir(parents=True, exist_ok=True)
    # Only the public aggregate is needed; no member data or seed is copied.
    write(
        context,
        named["legacy_report"],
        {"mask": {"common_resolved": 6, "development_scenarios": 12}},
    )
    commit(context)
    return context


def complete_freeze(ctx):
    named = record(ctx, "D1")
    path = ctx.repository / named["manifest"]
    manifest = json.loads(path.read_bytes())
    manifest["groups"] = [
        {
            "name": "fixture-representative",
            "role": "REPRESENTATIVE",
            "cases": ["fixture-a"],
        },
        {"name": "fixture-boundary", "role": "BOUNDARY_STRESS", "cases": ["fixture-b"]},
    ]
    write(ctx, named["manifest"], manifest)
    named["reference_access"] = "access.json"
    access = {
        "challenge": CID,
        "first_access_unix": manifest["frozen_unix"] + 1,
        "reference_digest": model.file_digest(ctx.repository / named["references"]),
    }
    write(ctx, "access.json", access)
    commit(ctx)
    return manifest, access


def test_d1_existing_freeze_has_a_population_label_finding(ctx):
    result = study.frozen_study({}, ctx)
    assert result.status == model.FAIL and "boundary populations" in result.detail


def test_d1_known_answer_verifies_the_freeze_before_access(ctx):
    complete_freeze(ctx)
    assert study.frozen_study({}, ctx).status == model.PASS


@pytest.mark.parametrize(
    "mutation",
    [
        "contract",
        "comparator",
        "duplicate",
        "boundary",
        "access_time",
        "access_digest",
        "access_challenge",
        "missing_time",
    ],
)
def test_d1_population_pin_and_freeze_mutations(ctx, mutation):
    manifest, access = complete_freeze(ctx)
    named = record(ctx, "D1")
    if mutation == "contract":
        manifest["contract_digest"] = "sha256:" + "0" * 64
    elif mutation == "comparator":
        manifest["candidates"] = []
    elif mutation == "duplicate":
        manifest["candidates"].append(manifest["candidates"][0])
    elif mutation == "boundary":
        manifest["groups"].pop()
    elif mutation == "access_time":
        access["first_access_unix"] = manifest["frozen_unix"]
    elif mutation == "access_digest":
        access["reference_digest"] = "sha256:" + "0" * 64
    elif mutation == "access_challenge":
        access["challenge"] = "another-challenge"
    else:
        named["reference_access"] = None
    write(ctx, named["manifest"], manifest)
    write(ctx, "access.json", access)
    commit(ctx)
    assert study.frozen_study({}, ctx).status == model.FAIL


def fake_tests(monkeypatch):
    monkeypatch.setattr(
        checks,
        "run_tests",
        lambda *_, **__: model.Result(
            model.PASS, "wrapper fixture tests", ("fixture-test-id",)
        ),
    )


def review(ctx, item, binding):
    path = "reviews/" + item + ".json"
    document = {
        "schema": "carbon.challenge-pipeline.readiness-review.v1",
        "challenge": CID,
        "level": [2, 3, 4],
        "item": item,
        "decision": model.PASS,
        "reviewer": "Test Lead",
        "date": "2026-10-12",
        "evidence": [{"kind": "test", "ref": "synthetic-wrapper-only"}],
        "binding": binding,
    }
    write(ctx, path, document)
    record(ctx, item)["review"] = path
    commit(ctx)
    return path, document


def test_d2_actual_adapter_and_harness_need_ladder_acceptance(ctx, monkeypatch):
    from carbon.design_search import track_b

    fake_tests(monkeypatch)
    assert study.harness_adapter({}, ctx).status == model.REVIEW_REQUIRED
    review(ctx, "D2", {"ladder_digest": model.digest(list(track_b.DEFAULT_LADDER))})
    assert study.harness_adapter({}, ctx).status == model.PASS


@pytest.mark.parametrize(
    "mutation", ["adapter", "tests", "ladder", "review_level", "review_challenge"]
)
def test_d2_adapter_test_and_review_mutations(ctx, monkeypatch, mutation):
    from carbon.design_search import track_b

    fake_tests(monkeypatch)
    path, reviewed = review(
        ctx, "D2", {"ladder_digest": model.digest(list(track_b.DEFAULT_LADDER))}
    )
    if mutation == "adapter":
        ctx.challenge = "another-challenge"
        record(ctx, "D2")["challenge"] = ctx.challenge
    elif mutation == "tests":
        monkeypatch.setattr(
            checks,
            "run_tests",
            lambda *_, **__: model.Result(model.FAIL, "known harness failure"),
        )
    elif mutation == "ladder":
        reviewed["binding"]["ladder_digest"] = "sha256:" + "0" * 64
    elif mutation == "review_level":
        reviewed["level"] = [0, 1]
    else:
        reviewed["challenge"] = "another-challenge"
    write(ctx, path, reviewed)
    commit(ctx)
    assert study.harness_adapter({}, ctx).status == model.FAIL


def plans(ctx, monkeypatch, registered):
    module = types.ModuleType("readiness_fixture_plans")
    path = ctx.repository / "registry.py"
    path.write_text("# SYNTHETIC unit registry; no execution authority\n")
    module.__file__ = str(path)
    module.PLANS = {CID: registered}
    monkeypatch.setitem(sys.modules, module.__name__, module)
    record(ctx, "D3")["registry"] = module.__name__ + ":PLANS"
    return module


def test_d3_unknown_registry_is_not_a_no_plan_pass(ctx):
    assert study.counted_timing({}, ctx).status == model.NOT_BUILT


def test_d3_absence_declaration_and_new_plan_reopen_calibration(ctx, monkeypatch):
    module = plans(ctx, monkeypatch, [])
    old_review = "reviews/D3-old.json"
    write(
        ctx,
        old_review,
        {
            "challenge": CID,
            "item": "D3",
            "reviewer": "Test Lead",
            "decision": model.PASS,
            "level": [0, 1],
            "notes": "not applicable: no counted plan",
        },
    )
    declaration = {
        "challenge": CID,
        "levels": [2, 3, 4],
        "basis_review": old_review,
        "basis_review_digest": model.file_digest(ctx.repository / old_review),
    }
    write(ctx, "no-plan.json", declaration)
    record(ctx, "D3")["not_applicable"] = "no-plan.json"
    commit(ctx)
    assert study.counted_timing({}, ctx).status == model.PASS
    module.PLANS[CID] = ["new-plan.json"]
    assert study.counted_timing({}, ctx).status == model.NOT_BUILT


@pytest.mark.parametrize("mutation", [None, "timeout", "host", "p95", "n"])
def test_d3_calibration_and_two_p95_timeout(ctx, monkeypatch, mutation):
    plans(ctx, monkeypatch, ["plan.json"])
    timing = {"challenge": CID, "host": "synthetic-host", "n": 10, "p95_seconds": 50.0}
    plan = {"challenge": CID, "host": "synthetic-host", "timeout_s": 100.0}
    if mutation == "timeout":
        plan["timeout_s"] = 99.9
    elif mutation == "host":
        plan["host"] = "other-host"
    elif mutation == "p95":
        timing["p95_seconds"] = None
    elif mutation == "n":
        timing["n"] = 0
    write(ctx, "timing.json", timing)
    write(ctx, "plan.json", plan)
    record(ctx, "D3")["timing"] = "timing.json"
    commit(ctx)
    assert study.counted_timing({}, ctx).status == (
        model.PASS if mutation is None else model.FAIL
    )


def change_references(ctx, mutate):
    named = record(ctx, "D4")
    path = ctx.repository / named["references"]
    rows = [
        json.loads(line)
        for line in gzip.decompress(path.read_bytes()).decode().splitlines()
        if line.strip()
    ]
    mutate(rows)
    plain = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
    path.write_bytes(gzip.compress(plain, mtime=0))
    (ctx.repository / named["checksum"]).write_text(
        hashlib.sha256(plain).hexdigest() + "  decision.jsonl\n"
    )
    commit(ctx)


def test_d4_existing_importer_reads_real_retained_output(ctx):
    result = study.real_import({}, ctx)
    assert result.status == model.PASS
    assert result.evidence[-1]["imported_records"] == 840


@pytest.mark.parametrize(
    "mutation", ["digest", "fixture", "output", "wall", "foreign_case", "provenance"]
)
def test_d4_importer_provenance_and_payload_mutations(ctx, mutation):
    if mutation == "digest":
        (ctx.repository / record(ctx, "D4")["checksum"]).write_text(
            "0" * 64 + "  decision.jsonl\n"
        )
        commit(ctx)
    elif mutation == "provenance":
        record(ctx, "D4")["reference_provenance"] = "SYNTHETIC"
    else:

        def mutate(rows):
            for row in rows:
                if mutation == "fixture":
                    row["fixture"] = True
                elif mutation == "output":
                    row["outputs"] = {}
                elif mutation == "wall":
                    row.pop("wall_s", None)
                else:
                    row["case_id"] = "foreign:" + row["case_id"]

        change_references(ctx, mutate)
    assert study.real_import({}, ctx).status == model.FAIL


def test_d5_reference_recount_is_reported_without_grading_or_reinterpreting_common_mask(
    ctx,
):
    result = study.reference_coverage({}, ctx)
    assert result.status == model.PASS
    report = next(
        entry
        for entry in result.evidence
        if isinstance(entry, dict) and "resolved" in entry
    )
    assert (report["resolved"], report["total"]) == (5, 12)
    assert report["fraction"] == 5 / 12
    assert result.evidence[-1]["historical_panel_common_mask"]["common_resolved"] == 6
    assert result.evidence[-1]["same_measure"] is False


def test_d5_no_reference_is_resolvable_without_successful_solver_evidence(ctx):
    change_references(
        ctx, lambda rows: [row.update(status="REFERENCE_TIMEOUT") for row in rows]
    )
    result = study.reference_coverage({}, ctx)
    assert result.status == model.PASS  # report only; zero is not judged
    report = next(
        entry
        for entry in result.evidence
        if isinstance(entry, dict) and "resolved" in entry
    )
    assert report["resolved"] == 0 and report["fraction"] == 0


def test_d5_duplicate_reference_case_is_a_failure(ctx):
    change_references(ctx, lambda rows: rows.append(rows[0]))
    assert study.reference_coverage({}, ctx).status == model.FAIL


def test_d5_matching_review_must_name_the_registered_refinement_policy(ctx):
    path = "carbon/challenge_pipeline/readiness/" + CID + "/reviews/D5.json"
    reviewed = {
        "schema": "carbon.challenge-pipeline.readiness-review.v1",
        "challenge": CID,
        "level": [2, 3, 4],
        "item": "D5",
        "decision": model.PASS,
        "reviewer": "Test Lead",
        "date": "2026-10-12",
        "evidence": [{"kind": "test", "ref": "fixture-test"}],
    }
    write(ctx, path, reviewed)
    commit(ctx)
    assert study.reference_coverage({}, ctx).status == model.FAIL
    reviewed["evidence"] = [
        {"kind": "decision", "ref": record(ctx, "D5")["policy_decision"]}
    ]
    write(ctx, path, reviewed)
    commit(ctx)
    assert study.reference_coverage({}, ctx).status == model.PASS


def pin_fixture(ctx):
    write(ctx, "manifest.json", {"schema": "synthetic-freeze"})
    source = ctx.repository / "carbon" / "fixture_analysis.py"
    source.parent.mkdir(exist_ok=True)
    source.write_text("from . import fixture_dependency\n")
    dependency = source.with_name("fixture_dependency.py")
    dependency.write_text("# SYNTHETIC source-only dependency\nVALUE = 1\n")
    pins = {
        "schema": "carbon.battery.ev5.run-record.v1",
        "study": "fixture",
        "files": {
            "carbon/fixture_analysis.py": model.file_digest(source),
            "carbon/fixture_dependency.py": model.file_digest(dependency),
        },
        "freeze_manifest": {
            "path": "manifest.json",
            "sha256": model.file_digest(ctx.repository / "manifest.json"),
        },
        "trees": ["carbon"],
        "contract_digest": "sha256:" + "0" * 64,
    }
    write(ctx, "pin-record.json", pins)
    commit(ctx)
    git(ctx.repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    record(ctx, "D6").update(
        run_record="pin-record.json",
        freeze_commit=git(ctx.repository, "rev-parse", "HEAD"),
        analysis_entry="carbon/fixture_analysis.py",
    )
    return pins


def test_d6_closure_includes_relative_dependency_and_preserves_historical_source(
    ctx, monkeypatch
):
    pin_fixture(ctx)
    fake_tests(monkeypatch)
    assert study.analysis_pins({}, ctx).status == model.PASS
    (ctx.repository / "carbon/fixture_dependency.py").write_text("VALUE = 2\n")
    commit(ctx)
    assert (
        study.analysis_pins({}, ctx).status == model.PASS
    )  # old tree is not silently rescored


@pytest.mark.parametrize(
    "mutation",
    [
        "dependency",
        "digest",
        "manifest",
        "entry",
        "test",
        "schema",
        "unmerged",
        "unavailable_import",
    ],
)
def test_d6_pin_and_import_closure_mutations(ctx, monkeypatch, mutation):
    pins = pin_fixture(ctx)
    fake_tests(monkeypatch)
    if mutation == "dependency":
        pins["files"].pop("carbon/fixture_dependency.py")
    elif mutation == "digest":
        pins["files"]["carbon/fixture_dependency.py"] = "sha256:" + "0" * 64
    elif mutation == "manifest":
        pins["freeze_manifest"]["sha256"] = "sha256:" + "0" * 64
    elif mutation == "entry":
        record(ctx, "D6")["analysis_entry"] = "carbon/missing.py"
    elif mutation == "schema":
        pins["schema"] = "wrong-schema"
    elif mutation == "unmerged":
        git(ctx.repository, "update-ref", "-d", "refs/remotes/origin/main")
    elif mutation == "unavailable_import":
        source = ctx.repository / "carbon/fixture_analysis.py"
        source.write_text("import carbon.unavailable_fixture_module\n")
        pins["files"]["carbon/fixture_analysis.py"] = model.file_digest(source)
    else:
        monkeypatch.setattr(
            checks,
            "run_tests",
            lambda *_, **__: model.Result(model.FAIL, "known pin-step failure"),
        )
    if mutation in ("dependency", "digest", "manifest", "schema", "unavailable_import"):
        write(ctx, "pin-record.json", pins)
        commit(ctx)
        git(ctx.repository, "update-ref", "refs/remotes/origin/main", "HEAD")
        record(ctx, "D6")["freeze_commit"] = git(ctx.repository, "rev-parse", "HEAD")
    assert study.analysis_pins({}, ctx).status == model.FAIL


@pytest.mark.parametrize(
    "item,function",
    [
        ("D1", study.frozen_study),
        ("D2", study.harness_adapter),
        ("D3", study.counted_timing),
        ("D4", study.real_import),
        ("D5", study.reference_coverage),
        ("D6", study.analysis_pins),
    ],
)
def test_study_level_and_challenge_registrations_do_not_inherit(ctx, item, function):
    record(ctx, item)["challenge"] = "another-challenge"
    assert function({}, ctx).status == model.FAIL
    ctx.data["studies_by_level"][item].pop(str(ctx.level))
    assert function({}, ctx).status == model.NOT_BUILT


def test_study_check_source_names_no_challenge():
    text = Path(study.__file__).read_text().lower()
    for word in ("battery", "chip-cold-plate", "cooling", "motor"):
        assert word not in text


def test_gate_study_integration_keeps_findings_and_owner_review_visible(
    ctx, monkeypatch
):
    from carbon.challenge_pipeline.readiness import runner

    pin_fixture(ctx)
    fake_tests(monkeypatch)
    monkeypatch.setattr(checks, "load_challenge_data", lambda _: ctx.data)
    report = runner.run_gate(
        CID,
        ctx.level,
        only=["D1", "D2", "D3", "D4", "D5", "D6"],
        repository=ctx.repository,
        root=ctx.repository / "reviews-root",
    )
    statuses = {row["id"]: row["status"] for row in report["items"]}
    assert statuses == {
        "D1": model.FAIL,
        "D2": model.REVIEW_REQUIRED,
        "D3": model.NOT_BUILT,
        "D4": model.PASS,
        "D5": model.REVIEW_REQUIRED,
        "D6": model.PASS,
    }
    assert report["green"] is False and report["launch_ready"] is False
    assert not any(report["claims"].values())
