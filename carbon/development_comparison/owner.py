"""Sanitized owner accounting from existing journals, not provider error bodies."""

from __future__ import annotations

import math
from pathlib import Path

from carbon.development_session.budget import SessionBudget
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from .experiment import LIMITS, check_storage, load_contract
from .report import ComparisonRef, resolve_report
from .sources import read_json


def accounting(root: Path):
    operations = SessionBudget(root / "budget.sqlite3").summary()
    provider = [row for row in operations if row["kind"] == "provider_usd"]
    workers = [row for row in operations if row["kind"] == "worker"]
    inputs = outputs = cached = 0
    tools = []
    for path in sorted(root.glob("provider-*-response.json")):
        response = read_json(path)
        usage = response.get("usage", {})
        if (
            type(usage.get("input_tokens")) is int
            and type(usage.get("output_tokens")) is int
        ):
            inputs += usage["input_tokens"]
            outputs += usage["output_tokens"]
            cache = usage.get("input_tokens_details", {}).get("cached_tokens", 0)
            if type(cache) is not int or not 0 <= cache <= usage["input_tokens"]:
                raise ValueError("invalid retained provider usage")
            cached += cache
        tools.extend(
            item["name"]
            for item in response.get("output", [])
            if item.get("type") == "function_call"
        )
    from carbon.execution import DurableWorkerLaunchStore

    observations = []
    training = []
    for path in root.glob("evaluations/*/replica-*-reconstruction-observation.json"):
        training.append(read_json(path))
    for path in root.glob("evaluations/*/reconstruction/launches.sqlite3"):
        for row in DurableWorkerLaunchStore(path).all_statuses():
            if row["resource_observation"] is not None:
                observations.append(row["resource_observation"])
    for path in root.glob("evaluations/*/prediction-*/controls-and-resources.json"):
        observations.append(read_json(path)["resources"])
    for path in root.glob("evaluations/*/measurement/launches/*.json"):
        row = read_json(path)
        if row.get("resource_observation") is not None:
            observations.append(row["resource_observation"])
    return {
        "provider_calls_including_failures": len(provider),
        "input_tokens": inputs,
        "cached_input_tokens": cached,
        "output_tokens": outputs,
        "priced_usage_usd": ((inputs - cached) * 0.25 + cached * 0.025 + outputs * 2.0)
        / 1_000_000,
        "conservative_charged_or_reserved_usd": math.fsum(
            row["elapsed"] if row["elapsed"] is not None else row["reserved"]
            for row in provider
        ),
        "ambiguous_provider_reservations": sum(
            row["state"] == "RESERVED" for row in provider
        ),
        "worker_operations_including_failures": len(workers),
        "observed_worker_wall_seconds": math.fsum(
            row["elapsed"] or 0 for row in workers
        ),
        "worker_charged_or_reserved_seconds": math.fsum(
            row["elapsed"] if row["elapsed"] is not None else row["reserved"]
            for row in workers
        ),
        "worker_resource_observation_count": len(observations),
        "observed_worker_cpu_seconds": math.fsum(
            row["cpu"]["usage_usec"] for row in observations
        )
        / 1_000_000,
        "max_worker_memory_peak_bytes": max(
            (row["memory"]["peak_bytes"] for row in observations), default=0
        ),
        "observed_worker_oom_kills": sum(
            row["memory"]["events"]["oom_kill"] for row in observations
        ),
        "resource_scope": "POST_EXPORT_PRE_TERMINATION; incomplete workers may lack resource observations",
        "retained_bytes": check_storage(root),
        "read_own_prior_feedback": "get_prior" in tools,
        "read_completed_feedback": "get_submission_result" in tools,
        "tool_sequence": tools,
        "failed_or_pending_operations": [
            row for row in operations if row["state"] != "COMPLETE"
        ],
        "training_runs_with_retained_outcome": len(training),
        "training_runs_complete": sum(row["status"] == "COMPLETE" for row in training),
        "training_updates_observed": sum(row["completed_steps"] for row in training),
        "training_operations_without_retained_outcome": sum(
            "-train-" in row["id"] for row in workers
        )
        - len(training),
        "budget_digest": digest(canonical(operations)),
        "new_reference_runs": 0,
        "reused_historical_references": 36,
        "chain_transactions": 0,
        "test_tao_spent": 0,
    }


def write_owner_report(root: Path):
    contract = load_contract(root)
    reports = []
    for path in sorted(root.glob("comparison-*.json")):
        if path.name == "comparison-contract.json":
            continue
        ref = ComparisonRef(path, digest(path.read_bytes()))
        reports.append((path, resolve_report(root, ref)))
    if (
        not (root / "agent-report.json").exists()
        and not (root / "agent-stopped-report.json").exists()
    ):
        raise ValueError(
            "session outcome required before sealing owner report; use status during execution"
        )
    if (root / "owner-report.json").exists():
        prior = read_json(root / "owner-report.json")
        if prior["contract_digest"] != digest(canonical(contract)) or prior["totals"][
            "budget_digest"
        ] != digest(canonical(SessionBudget(root / "budget.sqlite3").summary())):
            raise ValueError("owner report accounting changed; reconciliation required")
        return prior
    proposed = [read_json(path) for path in sorted(root.glob("proposal-*.json"))]
    totals = accounting(root)
    report_path = root / "agent-report.json"
    run = read_json(report_path) if report_path.exists() else None
    completed = len(reports)
    value = {
        "schema": "carbon.cw1.development-comparison-owner-report.v1",
        "contract_digest": digest(canonical(contract)),
        "status": "COMPLETED" if run else "STOPPED_OR_INCOMPLETE",
        "baseline_strategy": contract["baseline_strategy"],
        "proposals_retained": proposed,
        "completed_evaluations": completed,
        "training_runs_completed": totals["training_runs_complete"],
        "training_updates_completed": totals["training_updates_observed"],
        "measurement_reports_completed": 72 * completed,
        "wall_seconds": run["wall_seconds"] if run else None,
        "revised_after_new_feedback": len(proposed) > 1
        and totals["read_completed_feedback"],
        "changed_from_historical_strategy": any(
            strategy != contract["baseline_strategy"] for strategy in proposed
        ),
        "totals": totals,
        "limits": LIMITS,
        "comparisons": [
            {"path": str(path), "disposition": report["disposition"]}
            for path, report in reports
        ],
        "accepted_improvement": None,
        "next_prerequisite": "AUTHORIZED_DEVELOPMENT_ACCEPTANCE_AND_SCORE_RULE_BEFORE_REAL_WINNER_REWARD_ADMISSION",
    }
    write_once(root / "owner-report.json", canonical(value))
    lines = [
        "# Carbon non-paying DEVELOPMENT experiment",
        "",
        f"Status: **{value['status']}**. Comparisons: **INDETERMINATE_NO_ACCEPTANCE_RULE**.",
        "",
        "## Work and adaptation",
        "",
        f"Historical baseline: `{contract['baseline_strategy']}`.",
        f"Proposed strategies: `{proposed}`.",
        f"Completed: {completed} evaluations, {value['training_runs_completed']} reconstruction replicas, {value['training_updates_completed']} training updates, {value['measurement_reports_completed']} measurements.",
        f"Read permitted own-prior feedback: {totals['read_own_prior_feedback']}; read new feedback: {totals['read_completed_feedback']}; revised after new feedback: {value['revised_after_new_feedback']}.",
        "",
        "## Actual accounting",
        "",
        "| Item | Observed |",
        "|---|---:|",
        f"| Provider calls, including failures | {totals['provider_calls_including_failures']} / 24 |",
        f"| Input / cached input / output tokens | {totals['input_tokens']} / {totals['cached_input_tokens']} / {totals['output_tokens']} |",
        f"| Priced provider usage | USD {totals['priced_usage_usd']:.8f} |",
        f"| Conservative charge plus unresolved reservations | USD {totals['conservative_charged_or_reserved_usd']:.8f} / 1.00 |",
        f"| Worker operations | {totals['worker_operations_including_failures']} / 156 |",
        f"| Worker wall time | {totals['observed_worker_wall_seconds']:.3f} s |",
        f"| Observed worker CPU | {totals['observed_worker_cpu_seconds']:.3f} s |",
        f"| Maximum worker peak memory | {totals['max_worker_memory_peak_bytes']} bytes |",
        f"| Retained session storage | {totals['retained_bytes']} bytes |",
        "| Public-network transactions / test TAO | 0 / 0 |",
        "",
        "Provider usage is calculated from retained usage and published rates; it is not an invoice. Reservations remain charged for ambiguous responses. Worker observations are post-export/pre-termination; incomplete workers can lack observations. All known partial and failed work stays in the budget journal.",
        "",
        f"Failed or pending operations: `{totals['failed_or_pending_operations']}`.",
        "",
        "## Measurements",
        "",
        "All ten metrics are reported for EVAL and STRESS separately. The cohort's earlier results were seen. Lower error on this subset does not establish a better physics model, an accepted improvement, equivalence or qualification.",
    ]
    for path, report in reports:
        lines += [
            "",
            f"### Proposal {report['proposal_number']}",
            "",
            f"[Detailed comparison]({path.with_suffix('.md')})",
            "",
            "| Role | Field error, baseline | Field error, challenger | Difference |",
            "|---|---:|---:|---:|",
        ]
        for role, cohort in report["cohorts"].items():
            metric = cohort["metrics"]["field_phase_rms"]
            lines.append(
                f"| {role} | {metric['baseline']['mean']:.8g} | {metric['challenger']['mean']:.8g} | {metric['difference_challenger_minus_baseline']:+.8g} |"
            )
    lines += [
        "",
        "## Status and evidence",
        "",
        "```bash",
        "cd /home/carbon/Carbon",
        f".venv/bin/python -m carbon.development_comparison status --root {root}",
        "```",
        "",
        f"Agent report: {root / 'agent-report.json'}",
        f"Accounting and attempts: {root / 'budget.sqlite3'}",
        f"Frozen contract: {root / 'comparison-contract.json'}",
        "",
        "Next: the owner must supply an authorized DEVELOPMENT acceptance/scoring rule before real winner admission. Reward parameters, finalized miner identity mapping, winner-capable publication and separate transaction authority follow. This session creates no paying or public-network effect.",
        "",
    ]
    write_once(root / "owner-report.md", "\n".join(lines).encode())
    return value
