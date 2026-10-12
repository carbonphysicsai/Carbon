"""Campaign orchestration on three synthetic jobs; never a reference solve."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from test_design_search_adaptive_arms import _panel as adaptive_fixture
from test_evidence_pipeline import bundle

from carbon.design_search import adaptive_arms, budget_registration, equal_budget
from carbon.development_comparison import campaign_entrypoints
from carbon.development_comparison import evidence_campaign as campaign

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = (
    ROOT / "docs/development/challenge_pipeline/equal-budget-registration-v1.json"
)
RULE = ROOT / "docs/development/challenge_pipeline/value-bar-v1.json"


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"path": path.name, "sha256": campaign._sha(path.read_bytes())}


def _adaptive(documents, registration, family):
    example, _ = adaptive_fixture(battery=family == "battery-v3", f02=family == "f02")
    policy = adaptive_arms.seal(
        {
            **{k: v for k, v in example["policy"].items() if k != "policy_digest"},
            "decision_rule_id": documents["replay"]["decision_rule_id"],
        },
        "policy_digest",
    )
    jobs = []
    for base in documents["replay"]["jobs"]:
        candidates = base["candidates"]
        actions = []
        for index, candidate in enumerate(candidates):
            verdict = candidate["reference"]
            if family == "battery-v3":
                margins = {
                    band: {
                        "limit_a": -1.0 if row["status"] == "INFEASIBLE" else 1.0,
                        "limit_b": 1.0,
                    }
                    for band, row in verdict["per_index"].items()
                }
            else:
                margins = {
                    "limit_a": -1.0 if verdict["status"] == "INFEASIBLE" else 1.0,
                    "limit_b": 1.0,
                }
            actions.append(
                {
                    "design_id": candidate["design_id"],
                    "branch": "synthetic-branch",
                    "coordinates": {"setting": index},
                    "margins": margins,
                    "reference_cause": None,
                    "warm_start_from": None,
                    "attempts": [
                        {
                            "kind": "final",
                            "cost": candidate["solve_cost"],
                            "planning_bound": candidate["planning_bound"],
                            "peak_ram_bytes": 1024,
                        }
                    ],
                }
            )
        jobs.append(
            {
                "job_id": base["job_id"],
                "axes": [
                    {
                        "name": "setting",
                        "type": "ordinal",
                        "values": list(range(len(actions))),
                    }
                ],
                "actions": actions,
                "starts": [actions[0]["design_id"]],
                "common_cache": [],
                "cache_source": None,
                "condition_panel_digest": "sha256:" + "e" * 64,
                "cache_acquisition": {"wall_s": 0, "core_s": 0},
                "cache_acquisition_peak_ram_bytes": 0,
            }
        )
    panel = adaptive_arms.seal(
        {
            "schema": adaptive_arms.SCHEMA,
            "base_panel": documents["replay"],
            "policy": policy,
            "jobs": jobs,
        },
        "adaptive_digest",
    )
    adaptive_arms.validate(panel, registration)
    return panel


def _fixture(tmp_path):
    registration = json.loads(REGISTRATION.read_text(encoding="utf-8"))
    rule = json.loads(RULE.read_text(encoding="utf-8"))
    reg_file = tmp_path / "registration.json"
    rule_file = tmp_path / "value-rule.json"
    _write(reg_file, registration)
    _write(rule_file, rule)
    readiness, cost_pilots, stages = {}, {}, []
    module = ROOT / "carbon/development_comparison/campaign_fixture.py"
    module_sha = campaign._sha(module.read_bytes())
    for family in campaign.FAMILIES:
        source = tmp_path / family
        manifest, docs = bundle(family, full_f02=family == "f02")
        replay = copy.deepcopy(docs["replay"])
        body = {k: v for k, v in replay.items() if k != "panel_digest"}
        body["budgets"] = [
            budget_registration.validate(registration).cap(family, tier).time_compute
            for tier in budget_registration.TIERS
        ]
        body["registrations"]["cost_plan"] = budget_registration.REGISTRATION_ID
        docs["replay"] = equal_budget.seal(body)
        panel = _adaptive(docs, registration, family)
        for role, document in docs.items():
            if document is None:
                manifest["files"][role] = None
            else:
                descriptor = _write(source / (role + ".json"), document)
                manifest["files"][role] = descriptor
        _write(source / "manifest.json", manifest)
        _write(source / "adaptive_panel.json", panel)
        receipt = {
            "schema": campaign.READINESS,
            "challenge": family,
            "main": "a" * 40,
            "observed_at": "2026-10-11T00:00:00+00:00",
            "items": [
                {
                    "item": i,
                    "label": label,
                    "state": "YES",
                    "basis": "SYNTHETIC FIXTURE ONLY",
                    "owner": "fixture",
                    "pointers": ["fixture"],
                }
                for i, label in enumerate(campaign.READINESS_LABELS, 1)
            ],
            "yes_count": 7,
            "all_prerequisites_yes": True,
            "spend_authorized": False,
            "qualified": False,
            "paid_run_output_exception": "none",
            "examined_sources": {},
        }
        readiness_file = tmp_path / (family + "-readiness.json")
        readiness[family] = _write(readiness_file, receipt)
        pilot = campaign.seal(
            {
                "schema": campaign.PILOT,
                "scope": "SYNTHETIC_FIXTURE",
                "family": family,
                "host_id": "synthetic-32-vcpu",
                "cap_eur": 10.0,
                "observed_eur": 0.5,
                "stage_samples": [
                    {"phase": "reference", "attempts": 1, "wall_s": 1.0, "core_s": 1.0},
                    {"phase": "train", "attempts": 1, "wall_s": 1.0, "core_s": 1.0},
                ],
            },
            "pilot_digest",
        )
        cost_pilots[family] = _write(tmp_path / (family + "-pilot.json"), pilot)
        for phase in ("reference", "train", "assemble"):
            shards = 2 if phase == "reference" else 1
            for shard in range(shards):
                inputs = (
                    {
                        "manifest": {
                            "path": f"{family}/manifest.json",
                            "sha256": campaign._sha(
                                (source / "manifest.json").read_bytes()
                            ),
                            "role": "SYNTHETIC_FIXTURE",
                        },
                        "adaptive_panel": {
                            "path": f"{family}/adaptive_panel.json",
                            "sha256": campaign._sha(
                                (source / "adaptive_panel.json").read_bytes()
                            ),
                            "role": "SYNTHETIC_FIXTURE",
                        },
                    }
                    if phase == "assemble"
                    else {}
                )
                stages.append(
                    {
                        "family": family,
                        "phase": phase,
                        "shard": shard,
                        "shards": shards,
                        "module": "carbon.development_comparison.campaign_fixture",
                        "module_sha256": module_sha,
                        "vcpus": 1,
                        "peak_ram_gb": 1.0,
                        "planned_wall_s": 30,
                        "planned_core_s": 1,
                        "inputs": inputs,
                    }
                )
        if family == "battery-v3":
            stages.append(
                {
                    "family": family,
                    "phase": "score",
                    "shard": 0,
                    "shards": 1,
                    "module": "carbon.development_comparison.campaign_fixture",
                    "module_sha256": module_sha,
                    "vcpus": 1,
                    "peak_ram_gb": 1.0,
                    "planned_wall_s": 30,
                    "planned_core_s": 1,
                    "inputs": {},
                }
            )
    plan = campaign.seal(
        {
            "schema": campaign.SCHEMA,
            "scope": "SYNTHETIC_FIXTURE",
            "campaign_id": "synthetic-three-challenge",
            "readiness": readiness,
            "cost_pilots": cost_pilots,
            "budget_registration": {
                "path": reg_file.name,
                "sha256": campaign._sha(reg_file.read_bytes()),
            },
            "value_rule": {
                "path": rule_file.name,
                "sha256": campaign._sha(rule_file.read_bytes()),
            },
            "entrypoint_registration_digest": campaign_entrypoints.digest(),
            "stages": stages,
            "host": {
                "host_id": "synthetic-32-vcpu",
                "vcpus": 32,
                "ram_gb": 256.0,
                "usd_per_hour": 1.76,
                "usd_to_eur": 0.9,
                "fixed_eur": 0.1,
                "basis": "ASSUMPTION",
                "source": "synthetic-fixture",
            },
            "hard_cap_eur": 1.0,
            "hard_wall_s": 3600.0,
            "analysis": {"bootstrap_replicates": 100, "confidence": 0.95, "seed": 7},
            "analysis_reserve": {
                family: {"wall_s": 60, "core_s": 60, "peak_ram_gb": 1.0}
                for family in campaign.FAMILIES
            },
        },
        "plan_digest",
    )
    plan_path = tmp_path / "plan.json"
    _write(plan_path, plan)
    return plan, plan_path


def _public_plan(plan, tmp_path):
    plan["scope"] = "PUBLIC_DEVELOPMENT"
    for family in campaign.FAMILIES:
        descriptor = plan["cost_pilots"][family]
        path = tmp_path / descriptor["path"]
        pilot = json.loads(path.read_text(encoding="utf-8"))
        pilot["scope"] = "PUBLIC_DEVELOPMENT"
        pilot = campaign.seal(
            {k: v for k, v in pilot.items() if k != "pilot_digest"}, "pilot_digest"
        )
        descriptor["sha256"] = _write(path, pilot)["sha256"]
    return campaign.seal(
        {k: v for k, v in plan.items() if k != "plan_digest"}, "plan_digest"
    )


def test_three_challenge_dry_run_and_resume(tmp_path):
    plan, path = _fixture(tmp_path)
    workspace = tmp_path / "work"
    (workspace / "motor/reference/0/attempt-1").mkdir(parents=True)
    (workspace / "motor/evidence-pack.attempt-interrupted").mkdir()
    result = campaign.run(plan, tmp_path, workspace, dry_run=True)
    assert set(result["challenges"]) == set(campaign.FAMILIES)
    assert all(
        row["value_status"] == "INSUFFICIENT_EVIDENCE"
        for row in result["challenges"].values()
    )
    assert all(row["adaptive_status"] == "OK" for row in result["challenges"].values())
    assert result["sheet"]["planned_cpu_hours"] > 0
    assert (
        json.loads((workspace / "owner-server-sheet.json").read_text())["by_challenge"][
            "motor"
        ]["pilot"]["observed_eur"]
        == 0.5
    )
    assert result["challenges"]["battery-v3"]["score_plugin"] == "RECORDED_NOT_ADOPTED"
    assert result["challenges"]["f02"]["score_plugin"] == "NOT_REGISTERED"
    assert (workspace / "battery-v3/evidence-pack/score-plugin.json").is_file()
    context = json.loads(
        (workspace / "f02/reference/0/attempt-1/context.json").read_text()
    )
    assert context["vcpus"] == 1
    for family in campaign.FAMILIES:
        assert (
            "SYNTHETIC FIXTURE"
            in (workspace / family / "evidence-pack/evidence.md").read_text()
        )
    assert (
        campaign.run(plan, tmp_path, workspace, dry_run=True)["challenges"]
        == result["challenges"]
    )
    assert path.is_file()
    checkpoint = workspace / "checkpoint.json"
    original_state = checkpoint.read_bytes()
    assert json.loads(original_state)["completed"]["motor/reference/0"][
        "attempt_dir"
    ].endswith("attempt-2")
    altered_state = json.loads(original_state)
    altered_state["billed_wall_s"] = 0
    checkpoint.write_text(json.dumps(altered_state), encoding="utf-8")
    with pytest.raises(campaign.CampaignRefused, match="PLAN_IDENTITY_MISMATCH"):
        campaign.run(plan, tmp_path, workspace, dry_run=True)
    checkpoint.write_bytes(original_state)
    assembly = json.loads((workspace / "checkpoint.json").read_text())["completed"][
        "motor/assemble/0"
    ]
    manifest = workspace / assembly["attempt_dir"] / "manifest.json"
    manifest.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(campaign.CampaignRefused, match="BYTE_PIN_MISMATCH"):
        campaign.run(plan, tmp_path, workspace, dry_run=True)


def test_stage_shutdown_sends_term_then_escalates_after_grace(monkeypatch):
    if campaign.os.name != "posix":
        pytest.skip("process-group signals are a Linux runner property")
    calls = []

    class Process:
        pid = 12345

        def poll(self):
            return None

        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            if timeout is not None:
                raise campaign.subprocess.TimeoutExpired(["fixture"], timeout)
            return -9

    monkeypatch.setattr(
        campaign.os, "killpg", lambda pid, sig: calls.append((pid, sig))
    )
    campaign._terminate(Process())
    assert calls == [
        (12345, campaign.signal.SIGTERM),
        ("wait", campaign.TERMINATION_GRACE_S),
        (12345, campaign.signal.SIGKILL),
        ("wait", None),
    ]


def test_stage_shutdown_sweeps_children_after_leader_exits(monkeypatch):
    if campaign.os.name != "posix":
        pytest.skip("process-group signals are a Linux runner property")
    calls = []

    class Process:
        pid = 12345

        def poll(self):
            return None

        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            return 0

    monkeypatch.setattr(
        campaign.os, "killpg", lambda pid, sig: calls.append((pid, sig))
    )
    campaign._terminate(Process())
    assert calls == [
        (12345, campaign.signal.SIGTERM),
        ("wait", campaign.TERMINATION_GRACE_S),
        (12345, campaign.signal.SIGKILL),
        ("wait", None),
    ]


def test_pilot_receipt_must_be_capped_and_digest_bound(tmp_path):
    plan, _ = _fixture(tmp_path)
    descriptor = plan["cost_pilots"]["motor"]
    path = tmp_path / descriptor["path"]
    original = json.loads(path.read_text(encoding="utf-8"))
    over_cap = campaign.seal(
        {
            **{k: v for k, v in original.items() if k != "pilot_digest"},
            "observed_eur": 10.01,
        },
        "pilot_digest",
    )
    descriptor["sha256"] = _write(path, over_cap)["sha256"]
    plan = campaign.seal(
        {k: v for k, v in plan.items() if k != "plan_digest"}, "plan_digest"
    )
    with pytest.raises(campaign.CampaignRefused, match="TEN_EURO_PILOT_CAP_EXCEEDED"):
        campaign.validate(plan, tmp_path)
    descriptor["sha256"] = _write(path, original)["sha256"]
    tampered = {**original, "observed_eur": 1.0}
    descriptor["sha256"] = _write(path, tampered)["sha256"]
    plan = campaign.seal(
        {k: v for k, v in plan.items() if k != "plan_digest"}, "plan_digest"
    )
    with pytest.raises(campaign.CampaignRefused, match="PILOT_IDENTITY_MISMATCH"):
        campaign.validate(plan, tmp_path)


def test_readiness_and_cap_fail_before_dispatch(tmp_path):
    plan, _ = _fixture(tmp_path)
    receipt_path = tmp_path / "motor-readiness.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["items"][3]["state"] = "NO"
    receipt["yes_count"] = 6
    receipt["all_prerequisites_yes"] = False
    _write(receipt_path, receipt)
    plan["readiness"]["motor"]["sha256"] = campaign._sha(receipt_path.read_bytes())
    plan = campaign.seal(
        {k: v for k, v in plan.items() if k != "plan_digest"}, "plan_digest"
    )
    with pytest.raises(campaign.CampaignRefused, match="ITEM_NOT_YES"):
        campaign.run(plan, tmp_path, tmp_path / "blocked", dry_run=True)
    assert not (tmp_path / "blocked").exists()
    _, _, tasks = campaign.validate(plan, tmp_path, require_ready=False)
    assert (
        campaign.server_sheet(plan, tasks)["by_challenge"]["f02"]["planned_cpu_hours"]
        > 0
    )


def test_cap_and_train_role_refuse_before_dispatch(tmp_path):
    plan, _ = _fixture(tmp_path)
    tiny = copy.deepcopy(plan)
    tiny["hard_cap_eur"] = 0.100001
    tiny = campaign.seal(
        {k: v for k, v in tiny.items() if k != "plan_digest"}, "plan_digest"
    )
    with pytest.raises(
        campaign.CampaignRefused, match="PLANNED_CAMPAIGN_EXCEEDS_HARD_CAP"
    ):
        campaign.run(tiny, tmp_path, tmp_path / "over-cap", dry_run=True)
    assert not (tmp_path / "over-cap").exists()

    heldout = tmp_path / "heldout.json"
    _write(heldout, {"synthetic": True})
    invalid = copy.deepcopy(plan)
    next(task for task in invalid["stages"] if task["phase"] == "train")["inputs"] = {
        "forbidden": {
            "path": heldout.name,
            "sha256": campaign._sha(heldout.read_bytes()),
            "role": "HELDOUT_REFERENCE",
        }
    }
    invalid = campaign.seal(
        {k: v for k, v in invalid.items() if k != "plan_digest"}, "plan_digest"
    )
    with pytest.raises(campaign.CampaignRefused, match="TRAIN_MAY_NOT_READ_HELDOUT"):
        campaign.run(invalid, tmp_path, tmp_path / "heldout-blocked", dry_run=True)


def test_public_execution_requires_approval_and_registered_adapter(tmp_path):
    plan, _ = _fixture(tmp_path)
    fixture_escape = copy.deepcopy(plan)
    fixture_escape["stages"][0]["module"] = "scripts.dev.evidence_runs.f02"
    fixture_escape = campaign.seal(
        {k: v for k, v in fixture_escape.items() if k != "plan_digest"},
        "plan_digest",
    )
    with pytest.raises(campaign.CampaignRefused, match="TRUSTED_MODULE_REQUIRED"):
        campaign.run(
            fixture_escape, tmp_path, tmp_path / "fixture-escape", dry_run=True
        )
    assert not (tmp_path / "fixture-escape").exists()

    plan = _public_plan(plan, tmp_path)
    with pytest.raises(
        campaign.CampaignRefused, match="PRODUCER_REGISTRATION_INCOMPLETE"
    ):
        campaign.run(plan, tmp_path, tmp_path / "work", dry_run=False)


def test_sheet_can_be_planned_with_unregistered_public_stages(tmp_path):
    plan, _ = _fixture(tmp_path)
    plan = _public_plan(plan, tmp_path)
    for task in plan["stages"]:
        task["module"] = "HUMAN_INPUT_DATA_COLLECTION_REGISTRATION"
        for input_file in task["inputs"].values():
            input_file["role"] = "PUBLIC_INPUT"
    plan = campaign.seal(
        {k: v for k, v in plan.items() if k != "plan_digest"}, "plan_digest"
    )
    _, _, tasks = campaign.validate(
        plan, tmp_path, require_ready=False, require_modules=False
    )
    assert campaign.server_sheet(plan, tasks)["total"]["eur_estimate"] > 0
    with pytest.raises(
        campaign.CampaignRefused, match="PRODUCER_REGISTRATION_INCOMPLETE"
    ):
        campaign.run(plan, tmp_path, tmp_path / "blocked", dry_run=False)
    assert not (tmp_path / "blocked").exists()


def test_one_command_sheet_lists_registration_gaps(tmp_path, capsys):
    plan, path = _fixture(tmp_path)
    plan = _public_plan(plan, tmp_path)
    for task in plan["stages"]:
        task["module"] = "HUMAN_INPUT_DATA_COLLECTION_REGISTRATION"
        for input_file in task["inputs"].values():
            input_file["role"] = "PUBLIC_INPUT"
    plan = campaign.seal(
        {k: v for k, v in plan.items() if k != "plan_digest"}, "plan_digest"
    )
    _write(path, plan)
    assert (
        campaign.main(
            [
                "--plan",
                str(path),
                "--plan-sha256",
                campaign._sha(path.read_bytes()),
                "--workspace",
                str(tmp_path / "unused"),
                "--sheet-only",
            ]
        )
        == 0
    )
    sheet = json.loads(capsys.readouterr().out)
    assert sheet["planning_only"] is True
    assert sheet["dispatch_authorized"] is False
    assert sheet["registration_gap_owner"] == "Data Collection"
    # the motor reference stage is registered (#1114); the assembler is not yet
    assert not any(
        "reference entrypoint" in gap for gap in sheet["registration_gaps"]["motor"]
    )
    assert any(
        "comparison entrypoint" in gap for gap in sheet["registration_gaps"]["motor"]
    )
    assert sheet["total"]["eur_estimate"] > 0


def test_host_quotes_change_sheet_without_claiming_measured_throughput(tmp_path):
    plan, _ = _fixture(tmp_path)
    _, _, tasks = campaign.validate(plan, tmp_path)
    runpod = campaign.server_sheet(plan, tasks)
    assert runpod["host"]["host_id"] == "synthetic-32-vcpu"
    assert runpod["total"]["node_usd_estimate"] == pytest.approx(
        runpod["total"]["planned_wall_hours"] * 1.76
    )
    assert runpod["total"]["node_eur_estimate"] == pytest.approx(
        runpod["total"]["node_usd_estimate"] * 0.9
    )

    owner_host = copy.deepcopy(plan)
    owner_host["host"].update(
        host_id="synthetic-owner-host",
        vcpus=8,
        ram_gb=16.0,
        usd_per_hour=0.0,
        usd_to_eur=1.0,
        fixed_eur=0.0,
        source="synthetic fixture; no AX42 access",
    )
    owner_host = campaign.seal(
        {k: v for k, v in owner_host.items() if k != "plan_digest"}, "plan_digest"
    )
    _, _, tasks = campaign.validate(owner_host, tmp_path)
    free_sheet = campaign.server_sheet(owner_host, tasks)
    assert free_sheet["host"]["vcpus"] == 8
    assert free_sheet["total"]["eur_estimate"] == 0

    future = copy.deepcopy(owner_host)
    future["host"].update(
        host_id="synthetic-future-server",
        vcpus=64,
        ram_gb=512.0,
        usd_per_hour=2.4,
        usd_to_eur=0.8,
    )
    future = campaign.seal(
        {k: v for k, v in future.items() if k != "plan_digest"}, "plan_digest"
    )
    _, _, tasks = campaign.validate(future, tmp_path)
    assert campaign.server_sheet(future, tasks)["host"]["vcpus"] == 64


def test_ram_slots_and_host_limits_refuse_unaffordable_plan(tmp_path):
    plan, _ = _fixture(tmp_path)
    _, _, tasks = campaign.validate(plan, tmp_path)
    spacious = campaign.server_sheet(plan, tasks)
    ram_bound = copy.deepcopy(plan)
    ram_bound["host"]["ram_gb"] = 1.0
    ram_bound = campaign.seal(
        {k: v for k, v in ram_bound.items() if k != "plan_digest"}, "plan_digest"
    )
    _, _, tasks = campaign.validate(ram_bound, tmp_path)
    assert (
        campaign.server_sheet(ram_bound, tasks)["total"]["planned_wall_hours"]
        > spacious["total"]["planned_wall_hours"]
    )
    refused = copy.deepcopy(ram_bound)
    refused["stages"][0]["peak_ram_gb"] = 2.0
    refused = campaign.seal(
        {k: v for k, v in refused.items() if k != "plan_digest"}, "plan_digest"
    )
    with pytest.raises(campaign.CampaignRefused, match="HOST_RAM_EXCEEDED"):
        campaign.validate(refused, tmp_path)


def test_paid_host_requires_explicit_fx_and_free_host_still_needs_wall_cap(tmp_path):
    plan, _ = _fixture(tmp_path)
    invalid = copy.deepcopy(plan)
    invalid["host"]["usd_to_eur"] = 0
    invalid = campaign.seal(
        {k: v for k, v in invalid.items() if k != "plan_digest"}, "plan_digest"
    )
    with pytest.raises(campaign.CampaignRefused, match="POSITIVE_NUMBER_REQUIRED"):
        campaign.validate(invalid, tmp_path)
    invalid = copy.deepcopy(plan)
    invalid["host"]["usd_per_hour"] = 0
    invalid["hard_wall_s"] = 0
    invalid = campaign.seal(
        {k: v for k, v in invalid.items() if k != "plan_digest"}, "plan_digest"
    )
    with pytest.raises(campaign.CampaignRefused, match="POSITIVE_NUMBER_REQUIRED"):
        campaign.validate(invalid, tmp_path)


def test_merged_entrypoint_bindings_and_comparison_receipt_are_strict():
    inspected = campaign_entrypoints.inspect()
    assert (
        inspected["battery-v3"]["reference"]
        == "REGISTERED_FILES_ONLY_IMAGE_NOT_CHECKED"
    )
    assert inspected["motor"]["train"] == "REGISTERED_FILES_ONLY_IMAGE_NOT_CHECKED"
    assert inspected["motor"]["reference"] == "REGISTERED_FILES_ONLY_IMAGE_NOT_CHECKED"
    assert inspected["f02"]["train"] == "REGISTERED_FILES_ONLY_IMAGE_NOT_CHECKED"
    assert all(
        rows["comparison"] == "ASSEMBLER_NOT_REGISTERED" for rows in inspected.values()
    )

    pins = {"reference": ["sha256:" + "a" * 64], "train": ["sha256:" + "b" * 64]}
    body = {
        "schema": campaign_entrypoints.BRIDGE_SCHEMA,
        "family": "battery-v3",
        "scope": "SYNTHETIC_FIXTURE",
        "entrypoint_registration_digest": campaign_entrypoints.digest(),
        "producer_receipts": pins,
        "manifest_sha256": "sha256:" + "c" * 64,
        "adaptive_panel_sha256": "sha256:" + "d" * 64,
        "export_digest": "sha256:" + "e" * 64,
    }
    bridge = campaign_entrypoints.seal_bridge(body)
    campaign_entrypoints.verify_bridge(
        bridge,
        family="battery-v3",
        scope="SYNTHETIC_FIXTURE",
        manifest_sha256=body["manifest_sha256"],
        adaptive_panel_sha256=body["adaptive_panel_sha256"],
        export_digest=body["export_digest"],
        producer_receipts=pins,
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        campaign_entrypoints.verify_bridge(
            bridge,
            family="battery-v3",
            scope="SYNTHETIC_FIXTURE",
            manifest_sha256=body["manifest_sha256"],
            adaptive_panel_sha256=body["adaptive_panel_sha256"],
            export_digest="sha256:" + "f" * 64,
            producer_receipts=pins,
        )
    tampered = copy.deepcopy(bridge)
    tampered["producer_receipts"]["train"] = ["sha256:" + "f" * 64]
    with pytest.raises(ValueError, match="digest mismatch"):
        campaign_entrypoints.verify_bridge(
            tampered,
            family="battery-v3",
            scope="SYNTHETIC_FIXTURE",
            manifest_sha256=body["manifest_sha256"],
            adaptive_panel_sha256=body["adaptive_panel_sha256"],
            export_digest=body["export_digest"],
            producer_receipts=tampered["producer_receipts"],
        )
