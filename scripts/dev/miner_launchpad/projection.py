"""Authenticated miner's own research projection; never an owner-report dump."""

from __future__ import annotations

import json
from pathlib import Path

from carbon.development_session.profile import digest
from carbon.development_session.research_agent_policy import LEGACY, binding
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_guidance import context, verify, verify_history
from carbon.development_session.research_ledger import DIMENSIONS, CampaignLedger
from carbon.development_session.research_workspace import CAPABILITY_FIELDS


def _text_fields(body, fields):
    if type(body) is not dict:
        return {}
    return {k: body[k][:4096] for k in fields if type(body.get(k)) is str}


def project(row, root):
    value = {
        "schema": "carbon.launchpad.own-research.v1",
        "id": row["id"],
        "campaign_id": row["campaign"],
        "mode": "LIVE_PRACTICE_RESEARCH",
        "execution_label": "Current execution, not qualified LIVE",
        "profile": row["profile"],
        "state": row["state"],
        "experiments": [],
        "hypotheses": [],
        "epoch_outcomes": [],
        "capability_requests": [],
        "decisions": [],
        "final_results": [],
        "official_eligible": False,
    }
    task = verify(
        json.loads(row["research_guidance"])
        if row.get("research_guidance") is not None
        else None
    )
    if task is not None:
        value["research_guidance"] = task
    if not (root / "campaign.sqlite3").exists():
        return value
    ledger = CampaignLedger(root)
    value["state"] = CampaignControl(ledger).status()["state"]
    with ledger.db() as db:
        frozen = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    if frozen is None:
        return value
    manifest = json.loads(frozen[0])
    # Who selects: Carbon's agent, or - with no agent - the miner, through the
    # freeze and submit operations.
    value["selects"] = "miner" if manifest.get("agent") == "none" else "agent"
    # The Challenge this campaign is bound to, as its frozen manifest records
    # it; None for a campaign recorded before a Challenge was named.
    value["challenge"] = manifest.get("challenge")
    if verify(manifest.get("research_guidance")) != task:
        raise ValueError("campaign guidance association differs")
    if task is not None:
        value["effective_research_inputs"] = verify_history(
            root, task, manifest.get("agent_policy", binding(LEGACY)), context(manifest)
        )
    if (
        manifest.get("campaign_id") != row["campaign"]
        or manifest.get("principal") != row["principal"]
    ):
        raise ValueError("campaign projection association differs")
    status = ledger.status(owner=manifest["owner"])
    # A product campaign (C-MLP-02-D11) has no expiry and, unless its miner set
    # one, no elapsed budget; a retired-grant campaign keeps its grant's expiry.
    # Absent bounds are no deadline, never a default one.
    bounds = []
    if row.get("grant_record") is not None:
        bounds.append(json.loads(row["grant_record"])["document"]["expires_unix"])
    if status["started_unix"] and manifest.get("elapsed_seconds") is not None:
        bounds.append(status["started_unix"] + manifest["elapsed_seconds"])
    value.update(
        agent="carbon-autoresearch",
        reasoning=manifest["provider"]["model"],
        compute="local-isolated-cpu",
        runtime_revision=manifest["implementation"]["revision"],
        images=manifest["images"],
        agent_policy=_text_fields(
            manifest.get("agent_policy"),
            {"version", "prompt_digest", "stop_tool_digest"},
        ),
        started_unix=status["started_unix"],
        deadline_unix=min(bounds) if status["started_unix"] and bounds else None,
        admission=(
            "RETIRED_DEVELOPMENT_GRANT"
            if row.get("grant_record") is not None
            else "SUBNET_REGISTRATION"
        ),
    )
    reported = dict.fromkeys(DIMENSIONS, 0)
    reserved = dict(reported)
    uncertain = dict(reported)
    held = dict(reported)
    value["operations"] = []
    for op in status["operations"]:
        # Provider payloads, errors, numerical paths and final outputs stay private.
        value["operations"].append(
            {"id": op["id"], "phase": op["phase"], "state": op["state"]}
        )
        if op["actual"] is None:
            target = reserved
        elif (op["result"] or {}).get(
            "schema"
        ) == "carbon.autoresearch.worker-reconciliation.v1":
            target = uncertain
        else:
            target = reported
        for key, amount in (
            op["actual"] if op["actual"] is not None else op["reservation"]
        ).items():
            target[key] += amount
            if op["state"] == "HELD":
                held[key] += amount
    budget = status.get("budget") or {}
    value["usage"] = {
        # What the miner chose, reported as they set it. An empty budget means
        # they set none, which is a supported state and not a missing value.
        "budget": budget,
        # Only meaningful where a budget exists: without one there is nothing
        # remaining *of*, and a figure here would imply a cap they never set.
        "available": {
            key: (None if cap is None else cap - status["used"][key])
            for key, cap in budget.items()
        },
        # Carbon's infrastructure capacity, never the miner's money.
        "carbon_service_limits": status.get("carbon_service_limits", {}),
        "reserved": reserved,
        "reported": reported,
        "uncertain": uncertain,
        "held_within_reserved": held,
        "cost_basis": "Integer nanodollars; published-rate estimates from provider token usage, not an invoice guarantee",
    }
    value["attempted_experiments"] = status["used"]["research_trials"]
    for note in status["notes"]:
        if note["kind"] == "hypothesis":
            value["current_hypothesis"] = _text_fields(
                note["body"], {"hypothesis", "expected_effect", "task"}
            )
            value["hypotheses"].append(
                {"sequence": note["sequence"], **value["current_hypothesis"]}
            )
        elif note["kind"] == "capability_request":
            value["capability_requests"].append(
                {
                    "sequence": note["sequence"],
                    **_text_fields(note["body"], CAPABILITY_FIELDS),
                    "authority_granted": False,
                }
            )
        elif note["kind"] == "decision":
            value["decisions"].append(
                {
                    "sequence": note["sequence"],
                    **_text_fields(
                        note["body"], {"reason", "stop", "intervention", "evidence"}
                    ),
                }
            )
    with ledger.db() as db:
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='research_results' AND type='table'"
        ).fetchone():
            for task, body, pin in db.execute(
                "SELECT task,body,digest FROM research_results WHERE owner=?",
                (manifest["owner"],),
            ):
                if digest(body) != pin:
                    raise ValueError("research result changed")
                result = json.loads(body)
                if result.get("provenance") == "REAL_JAX_PUBLIC_PRACTICE":
                    value["experiments"].append(
                        {
                            "id": task,
                            "provenance": result["provenance"],
                            **{
                                k: result[k]
                                for k in (
                                    "recipe",
                                    "completed_steps",
                                    "worker_seconds",
                                    "diagnostics",
                                    "inline_curve",
                                    "inline_curve_indices",
                                )
                                if k in result
                            },
                            "accepted_improvement": False,
                            "adaptively_seen": True,
                        }
                    )
    value["completed_experiments"] = len(value["experiments"])
    value["candidate_freezes"] = []
    # Where a miner's own journey stands, from the campaign's files: which
    # committed final epochs are submitted, and whether a frozen candidate is
    # waiting for submission. The same rules freeze and submit enforce.
    from carbon.development_session.research_campaign import FINAL_EPOCHS

    submitted = [
        e
        for e in FINAL_EPOCHS
        if (root / ("epoch-" + str(e)) / "permitted-final-feedback.json").exists()
    ]
    open_epoch = next((e for e in FINAL_EPOCHS if e not in submitted), None)
    value["journey"] = {
        "submitted_epochs": submitted,
        "final_exams_remaining": len(FINAL_EPOCHS) - len(submitted),
        "frozen_awaiting_submission": open_epoch is not None
        and (root / ("epoch-" + str(open_epoch)) / "selected-recipe.json").exists(),
    }
    for epoch in (1, 2):
        directory = root / ("epoch-" + str(epoch))
        outcome_path = directory / "outcome.json"
        if outcome_path.exists():
            try:
                if (
                    outcome_path.is_symlink()
                    or outcome_path.stat().st_size > 4 * 1024**2
                ):
                    raise ValueError("bounded own-research outcome required")
                outcome = json.loads(outcome_path.read_bytes())
                if (
                    outcome.get("schema") != "carbon.autoresearch.epoch-outcome.v1"
                    or outcome.get("epoch") != epoch
                    or outcome.get("status")
                    not in {"SELECTED", "STOPPED", "RECONCILIATION_REQUIRED"}
                ):
                    raise ValueError("research outcome association differs")
                value["epoch_outcomes"].append(
                    {
                        "epoch": epoch,
                        "status": outcome["status"],
                        **_text_fields(outcome, {"reason", "stop_evidence"}),
                        "used_feedback": (
                            outcome.get("used_feedback")
                            if type(outcome.get("used_feedback")) is bool
                            else None
                        ),
                        "selected_by": (
                            "miner"
                            if outcome.get("selected_by") == "miner"
                            else "agent"
                        ),
                        "evidence_basis": "AGENT_OR_CONTROLLER_REPORTED_NOT_INDEPENDENT_SCIENCE",
                        "final_evidence": False,
                    }
                )
            except (OSError, ValueError, TypeError, AttributeError):
                value["epoch_outcomes"].append(
                    {
                        "epoch": epoch,
                        "status": "READBACK_UNAVAILABLE",
                        "final_evidence": False,
                    }
                )
        selected = directory / "selected-recipe.json"
        if selected.is_file():
            selection = json.loads(selected.read_bytes())
            value["candidate_freezes"].append(
                {
                    "epoch": epoch,
                    **{
                        k: selection[k]
                        for k in (
                            "strategy",
                            "strategy_hash",
                            "construction_plan_digest",
                            "reason",
                            "used_feedback",
                        )
                    },
                    "final_evidence": False,
                }
            )
        pointer = directory / "final/comparison-ref.json"
        if pointer.is_file():
            try:
                from carbon.development_comparison.acceptance import (
                    DevelopmentAcceptanceRef,
                )
                from carbon.orchestration.development_feedback import (
                    project_development_acceptance,
                )

                ref = json.loads(pointer.read_bytes())
                expected = directory / "final/comparison"
                if Path(ref["root"]) != expected or expected.resolve() != expected:
                    raise ValueError("comparison root differs")
                result = project_development_acceptance(
                    DevelopmentAcceptanceRef(
                        expected, ref["registration_digest"], ref["report_digest"]
                    )
                )
                value["final_results"].append(
                    {
                        "epoch": epoch,
                        "mode": "DEVELOPMENT_EVALUATION",
                        "status": "VERIFIED_SOURCE",
                        "result": result,
                    }
                )
            except Exception:  # noqa: BLE001 - never substitute stale feedback.
                value["final_results"].append(
                    {
                        "epoch": epoch,
                        "mode": "DEVELOPMENT_EVALUATION",
                        "status": "READBACK_UNAVAILABLE",
                        "result": None,
                    }
                )
    return value
