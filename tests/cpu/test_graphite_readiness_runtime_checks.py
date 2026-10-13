"""PLT-09 batch 2 wrapper mutations. Fakes here earn no host readiness PASS."""

from __future__ import annotations

import copy
import dataclasses
import json
import subprocess
from pathlib import Path

import pytest

from carbon.challenge_pipeline.readiness import checks, model
from carbon.challenge_pipeline.readiness import runtime_checks as runtime

CID = "battery-fastcharge-ageing-development-v1"
REPO = Path(__file__).resolve().parents[2]
SHA = "sha256:" + "a" * 64


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
    return result.stdout.decode().strip()


def commit(root):
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=readiness-fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "synthetic readiness fixture",
    )
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")


@pytest.fixture(params=[2, 3, 4])
def ctx(tmp_path, request):
    # A local synthetic Git repository, no network or shared root mutations.
    git(tmp_path, "init", "-q")
    data = copy.deepcopy(checks.load_challenge_data(CID))
    record = data["runtime_by_level"][str(request.param)]
    for named in record["roles"].values():
        target = tmp_path / named["grant_file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO / named["grant_file"]).read_bytes())
    commit(tmp_path)
    return checks.Context(CID, request.param, repository=tmp_path, data=data)


def registration(ctx):
    return ctx.data["runtime_by_level"][str(ctx.level)]


def containment_report():
    from carbon.development_session import containment_check as carrier

    return {
        "schema": carrier.SCHEMA,
        "status": model.PASS,
        "lane": runtime.ANALYSIS_LANE,
        "code": None,
        "image_id": SHA,
        "create_arguments_digest": SHA,
        "operation": "wrapper-fixture",
        "isolation": {"network": "none"},
        "canary": {"removed": True},
        "claims": {"security_acceptance": False},
        "probes": [{"probe": name, "status": model.PASS} for name in carrier.PROBES],
    }


def install_probe(ctx, monkeypatch, report):
    from carbon.development_session import containment_check as carrier
    from carbon.development_session import research_image

    manifest = ctx.repository / "analysis-image.json"
    manifest.write_text('{"fixture":"not a real image"}')
    monkeypatch.setattr(
        checks, "_analysis_image_manifest", lambda: (str(manifest), None)
    )
    monkeypatch.setattr(
        research_image,
        "load_analysis_image",
        lambda _: type("ImageFixture", (), {"image_id": SHA})(),
    )
    monkeypatch.setattr(carrier, "containment_check", lambda **_: copy.deepcopy(report))
    return manifest


def test_r2_runs_a_probe_and_binds_manifest_bytes(ctx, monkeypatch):
    install_probe(ctx, monkeypatch, containment_report())
    result = runtime.containment({}, ctx)
    assert result.status == model.PASS  # wrapper only, no Docker claim
    assert result.evidence[0]["manifest_digest"].startswith("sha256:")
    assert len(result.evidence[1]["probe_ids"]) == 6
    assert all("host_home" not in entry for entry in result.evidence)


@pytest.mark.parametrize(
    "mutation",
    [
        "synthetic",
        "probe_fail",
        "probe_missing",
        "stale_image",
        "canary",
        "launch",
        "isolation",
        "claims",
        "schema",
        "lane",
        "code",
    ],
)
def test_r2_refuses_contradictory_or_synthetic_probe_evidence(
    ctx, monkeypatch, mutation
):
    report = containment_report()
    if mutation == "synthetic":
        report["synthetic_test_double"] = True
    elif mutation == "probe_fail":
        report["probes"][0]["status"] = model.FAIL
    elif mutation == "probe_missing":
        report["probes"].pop()
    elif mutation == "stale_image":
        report["image_id"] = "sha256:" + "b" * 64
    elif mutation == "canary":
        report["canary"]["removed"] = False
    elif mutation == "launch":
        report.pop("create_arguments_digest")
    elif mutation == "isolation":
        report["isolation"] = None
    elif mutation == "claims":
        report["claims"]["security_acceptance"] = True
    elif mutation == "lane":
        report["lane"] = "another-lane"
    elif mutation == "code":
        report["code"] = "containment_check_failed"
    else:
        report["schema"] = "old"
    install_probe(ctx, monkeypatch, report)
    assert runtime.containment({}, ctx).status == model.FAIL


def test_r2_cannot_pass_a_changed_manifest(ctx, monkeypatch):
    from carbon.development_session import containment_check as carrier

    manifest = install_probe(ctx, monkeypatch, containment_report())

    def changing(**_):
        manifest.write_text("changed")
        return containment_report()

    monkeypatch.setattr(carrier, "containment_check", changing)
    assert (
        runtime.containment({}, ctx).detail
        == "containment_manifest_changed_during_probe"
    )


def test_r2_missing_manifest_and_unavailable_docker_are_failures(ctx, monkeypatch):
    monkeypatch.delenv(checks.ANALYSIS_IMAGE_ENV, raising=False)
    assert runtime.containment({}, ctx).status == model.FAIL
    report = {
        "schema": "carbon.carrier-containment-check.v1",
        "status": model.FAIL,
        "reason": "docker_unavailable",
    }
    from carbon.development_session import containment_check as carrier

    report["schema"] = carrier.SCHEMA
    install_probe(ctx, monkeypatch, report)
    result = runtime.containment({}, ctx)
    assert result.status == model.FAIL and "docker_unavailable" in result.detail


def test_r2_no_check_capable_lane_is_not_built_and_pods_cannot_pass(ctx):
    registration(ctx)["containment_lanes"] = []
    assert runtime.containment({}, ctx).status == model.NOT_BUILT
    registration(ctx)["containment_lanes"] = ["rented-pod"]
    assert runtime.containment({}, ctx).status == model.FAIL


def models(ctx):
    from carbon.agent_campaign.graphite import readiness_models

    bound, _ = runtime._grants(ctx, registration(ctx))
    return readiness_models.produce(
        ctx.repository / "model-fixture",
        challenge=CID,
        level=ctx.level,
        grants=bound,
        commit=git(ctx.repository, "rev-parse", "HEAD"),
    )


def test_r4_reads_actual_frozen_grant_start_model_without_calling_it(ctx):
    report = models(ctx)
    assert report["worker_ran"] is False
    for role in ("constructor", "attacker"):
        block = report[role + "_model"]
        assert block["model"] == "kimi-k3"
        assert block["max_input_tokens"] == 1048576
        assert block["recorded_context_tokens"] == 1113088
        assert block["charge_reporting"] is True
    for opened in (ctx.repository / "model-fixture").glob("*/runs/*/session-open.json"):
        assert json.loads(opened.read_bytes())["live_inference"] is False
        assert not (opened.parent / "ledger").exists()
    result = runtime.model_settings({}, ctx)
    assert result.status == model.FAIL and "recorded context 1113088" in result.detail


def valid_blocks(ctx, monkeypatch):
    from carbon.agent_campaign.graphite import readiness_models

    report = models(ctx)
    for role in ("constructor", "attacker"):
        report[role + "_model"]["max_input_tokens"] = report[role + "_model"][
            "recorded_context_tokens"
        ]
    monkeypatch.setattr(
        readiness_models, "produce", lambda *_, **__: copy.deepcopy(report)
    )
    return report


def review(ctx, item, *, report=None):
    bound, _ = runtime._grants(ctx, registration(ctx))
    roles = {
        role: {"grant_digest": model.digest(grant.document())}
        for role, grant in bound.items()
    }
    if report is not None:
        for role, accepted in roles.items():
            block = report[role + "_model"]
            accepted.update(
                model=block["model"],
                max_output_tokens=block["max_output_tokens"],
                sizing_rule="SYNTHETIC wrapper rule; no production adoption",
            )
    document = {
        "schema": runtime.REVIEW_SCHEMA,
        "item": item,
        "challenge": CID,
        "level": ctx.level,
        "decision": model.PASS,
        "reviewer": "Test Engineer" if item == "R4" else "Test Lead",
        "date": "2026-10-12",
        "basis": "synthetic wrapper review",
        "roles": roles,
    }
    relative = "reviews/" + item + ".json"
    target = ctx.repository / relative
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(document))
    registration(ctx).setdefault("reviews", {})[item] = relative
    commit(ctx.repository)
    return target, document


def test_r4_machine_pass_needs_an_exact_sizing_review(ctx, monkeypatch):
    report = valid_blocks(ctx, monkeypatch)
    assert runtime.model_settings({}, ctx).status == model.REVIEW_REQUIRED
    review(ctx, "R4", report=report)
    assert runtime.model_settings({}, ctx).status == model.PASS


@pytest.mark.parametrize(
    "mutation",
    [
        "default_context",
        "charge",
        "output_missing",
        "output_high",
        "provider",
        "maximum",
        "scope",
        "selection",
    ],
)
def test_r4_mutations_refuse_settings_even_with_a_review(ctx, monkeypatch, mutation):
    report = valid_blocks(ctx, monkeypatch)
    review(ctx, "R4", report=report)
    block = report["constructor_model"]
    if mutation == "default_context":
        block["max_input_tokens"] = 65536
    elif mutation == "charge":
        block["charge_reporting"] = False
    elif mutation == "output_missing":
        block.pop("max_output_tokens")
    elif mutation == "output_high":
        block["max_output_tokens"] = (
            block["recorded_output_maximum"]["max_output_tokens"] + 1
        )
    elif mutation == "provider":
        block["provider"] = "spur"
    elif mutation == "maximum":
        block["recorded_output_maximum"] = None
    elif mutation == "selection":
        block["selection_digest"] = "bad"
    else:
        report["level"] = 0
    assert runtime.model_settings({}, ctx).status == model.FAIL


def test_r4_absent_block_is_not_built_but_does_not_hide_another_failure(
    ctx, monkeypatch
):
    report = valid_blocks(ctx, monkeypatch)
    report.pop("attacker_model")
    assert runtime.model_settings({}, ctx).status == model.NOT_BUILT
    report["constructor_model"]["charge_reporting"] = False
    assert runtime.model_settings({}, ctx).status == model.FAIL


def no_pod_attacker(monkeypatch):
    from carbon.agent_campaign.graphite import phase4

    original = phase4.attacker_budget
    monkeypatch.setattr(
        phase4,
        "attacker_budget",
        lambda grant, scoring: dataclasses.replace(
            original(grant, scoring), max_pods=0
        ),
    )


def test_r5_existing_attacker_pod_allowance_is_a_finding_not_a_pass(ctx):
    result = checks.grant_binding({}, ctx)
    assert result.status == model.FAIL
    assert "no-pod run carries a pod allowance" in result.detail
    evidence = json.dumps(result.evidence)
    assert "account" not in evidence and "spend" not in evidence
    assert "monetary_ceiling" not in evidence


def test_r5_machine_pass_without_amount_review_requires_review(ctx, monkeypatch):
    no_pod_attacker(monkeypatch)
    assert runtime.grants({}, ctx).status == model.REVIEW_REQUIRED
    review(ctx, "R5")
    assert runtime.grants({}, ctx).status == model.PASS


@pytest.mark.parametrize(
    "mutation",
    [
        "grant_binding",
        "role",
        "level",
        "working_copy",
        "main_blob",
        "arithmetic",
        "per_run_cap",
        "weekly_cap",
        "tokens_only",
    ],
)
def test_r5_grant_and_budget_mutations_fail_closed(ctx, monkeypatch, mutation):
    from carbon.agent_campaign import grant_runs

    no_pod_attacker(monkeypatch)
    review(ctx, "R5")
    record = registration(ctx)
    named = record["roles"]["constructor"]
    path = ctx.repository / named["grant_file"]
    if mutation == "grant_binding":
        named["grant_file"] = record["roles"]["attacker"]["grant_file"]
    elif mutation == "role":
        named["grant_id"] = record["roles"]["attacker"]["grant_id"]
    elif mutation == "level":
        record["level"] = 0
    elif mutation in ("working_copy", "main_blob", "arithmetic"):
        document = json.loads(path.read_bytes())
        document["permitted_runs"] += 1
        path.write_text(json.dumps(document))
        if mutation == "main_blob":
            old_main = git(ctx.repository, "rev-parse", "origin/main")
            commit(ctx.repository)
            git(ctx.repository, "update-ref", "refs/remotes/origin/main", old_main)
        elif mutation == "arithmetic":
            commit(ctx.repository)
    elif mutation == "per_run_cap":
        monkeypatch.setattr(grant_runs, "PER_RUN_CAP_USD", 1)
    elif mutation == "weekly_cap":
        monkeypatch.setattr(grant_runs, "WEEKLY_CAP_USD", 1)
    else:
        from carbon.agent_campaign.graphite import experiment

        original = experiment.phase3_budget
        monkeypatch.setattr(
            experiment,
            "phase3_budget",
            lambda *args: dataclasses.replace(
                original(*args), tokens_only=True, token_share_usd=None
            ),
        )
        # tokens_only=True must structurally remove the pod allowance.
        # Mutate that property to simulate a regression in the actual budget producer.
        monkeypatch.setattr(
            experiment.Phase3Budget, "pod_allowance_usd", property(lambda _: 1)
        )
    assert runtime.grants({}, ctx).status == model.FAIL


@pytest.mark.parametrize(
    "mutation", ["challenge", "level", "digest", "owner", "uncommitted", "missing_role"]
)
@pytest.mark.parametrize("item", ["R4", "R5"])
def test_owner_reviews_cannot_be_borrowed_or_stale(ctx, monkeypatch, mutation, item):
    report = valid_blocks(ctx, monkeypatch) if item == "R4" else None
    no_pod_attacker(monkeypatch)
    target, document = review(ctx, item, report=report)
    if mutation == "challenge":
        document["challenge"] = "unrelated-development-v1"
    elif mutation == "level":
        document["level"] = 1
    elif mutation == "digest":
        document["roles"]["attacker"]["grant_digest"] = SHA
    elif mutation == "owner":
        document["reviewer"] = "Executor"
    elif mutation == "missing_role":
        document["roles"].pop("attacker")
    else:
        document["basis"] = "uncommitted change"
    target.write_text(json.dumps(document))
    if mutation != "uncommitted":
        commit(ctx.repository)
    check = runtime.model_settings if item == "R4" else runtime.grants
    assert check({}, ctx).status == model.FAIL


def test_unregistered_level_never_inherits_runtime_evidence(ctx):
    ctx.data["runtime_by_level"].pop(str(ctx.level))
    for check in (runtime.containment, runtime.model_settings, runtime.grants):
        assert check({}, ctx).status == model.NOT_BUILT


def test_r5_no_role_grant_is_no_grant_for_level(ctx):
    registration(ctx)["roles"] = {}
    result = runtime.grants({}, ctx)
    assert result.status == model.FAIL and "NO_GRANT_FOR_LEVEL" in result.detail


@pytest.mark.parametrize(
    "mutation", ["wrong_stage", "unsafe_path", "symlink", "bad_json"]
)
def test_registered_grant_artifacts_are_fail_closed(ctx, monkeypatch, mutation):
    no_pod_attacker(monkeypatch)
    named = registration(ctx)["roles"]["constructor"]
    target = ctx.repository / named["grant_file"]
    if mutation == "wrong_stage":
        stage = "C" if ctx.level != 4 else "B"
        grant_id = "GRAPHITE-GRANT-STAGE-" + stage + "-CONSTRUCTOR"
        relative = "docs/development/graphite/grants/" + grant_id + ".json"
        (ctx.repository / relative).write_bytes((REPO / relative).read_bytes())
        named.update(grant_id=grant_id, grant_file=relative)
        commit(ctx.repository)
    elif mutation == "unsafe_path":
        named["grant_file"] = "../outside.json"
    elif mutation == "symlink":
        original = target.with_suffix(".original")
        target.rename(original)
        target.symlink_to(original)
    else:
        target.write_text("{")
        commit(ctx.repository)
    assert runtime.grants({}, ctx).status == model.FAIL


def test_sizing_review_requires_a_rule_matching_the_actual_output_cap(ctx, monkeypatch):
    report = valid_blocks(ctx, monkeypatch)
    target, document = review(ctx, "R4", report=report)
    document["roles"]["constructor"]["sizing_rule"] = "HUMAN_INPUT"
    target.write_text(json.dumps(document))
    commit(ctx.repository)
    assert runtime.model_settings({}, ctx).status == model.FAIL


def test_a_committed_review_with_duplicate_fields_is_malformed(ctx, monkeypatch):
    no_pod_attacker(monkeypatch)
    target, document = review(ctx, "R5")
    target.write_text('{"decision":"FAIL",' + json.dumps(document)[1:])
    commit(ctx.repository)
    result = runtime.grants({}, ctx)
    assert result.status == model.FAIL
    assert "repeats_a_field" in result.detail


def test_gate_integration_keeps_runtime_findings_and_authority_flags_false(
    ctx, monkeypatch
):
    from carbon.challenge_pipeline.readiness import runner

    monkeypatch.delenv(checks.ANALYSIS_IMAGE_ENV, raising=False)
    report = runner.run_gate(
        CID,
        ctx.level,
        only=["R2", "R4", "R5"],
        repository=ctx.repository,
        root=ctx.repository / "gate-output",
    )
    rows = {row["id"]: row for row in report["items"]}
    assert {row["status"] for row in rows.values()} == {model.FAIL}
    assert "manifest" in rows["R2"]["detail"]
    assert "recorded context 1113088" in rows["R4"]["detail"]
    assert "no-pod run carries a pod allowance" in rows["R5"]["detail"]
    assert report["green"] is False and report["launch_ready"] is False
    assert not any(report["claims"].values())
    assert all(row["evidence_digest"].startswith("sha256:") for row in rows.values())
