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

#: What a refusal shows: which operation, why, and the correction if any.
REFUSAL_FIELDS = {
    "operation",
    "purpose",
    "hypothesis",
    "status",
    "reason",
    "detail",
    "correction_code",
    "field",
}


def _text_fields(body, fields):
    if type(body) is not dict:
        return {}
    return {k: body[k][:4096] for k in fields if type(body.get(k)) is str}


def feedback_schemas():
    """The permitted-feedback schemas the implemented Challenges' validators
    return, each read from its own campaign (C-MLP-04)."""
    from carbon.challenge_registry.campaigns import implemented_campaigns

    return {
        campaign.feedback_schema
        for _entry, campaign in implemented_campaigns()
        if campaign.feedback_schema is not None
    }


#: What the Submission view shows of a validator outcome: only fields the
#: permitted feedback already carries for this miner, never more.
_SCREENING_FIELDS = (
    "eligible",
    "gates_failed",
    "cases",
    "score",
    "important_score",
    "pool_version",
)


def pointer_exists(directory):
    return (directory / "final/comparison-ref.json").is_file()


def _validator_outcome(epoch, path):
    """The validator's outcome for one submitted epoch, from the campaign's
    permitted feedback (the same allow-listed view the agent receives), or
    READBACK_UNAVAILABLE. Nothing is inferred from a file that differs."""
    unavailable = {
        "epoch": epoch,
        "mode": "DEVELOPMENT_EVALUATION",
        "status": "READBACK_UNAVAILABLE",
        "result": None,
    }
    try:
        if path.is_symlink() or path.stat().st_size > 65536:
            return unavailable
        document = json.loads(path.read_bytes())
        outcome = document["outcome"]
        if (
            document.get("schema") not in feedback_schemas()
            or document.get("epoch") != epoch
            or type(outcome) is not dict
            or type(outcome.get("state")) is not str
        ):
            return unavailable
        screening = outcome.get("screening")
        finals = outcome.get("finals")
        result = {
            "state": outcome["state"][:64],
            "submission_id": str(outcome.get("submission_id", ""))[:128],
            "evidence": str(outcome.get("evidence", ""))[:64],
            "nominated": (
                outcome.get("nominated")
                if type(outcome.get("nominated")) is bool
                else None
            ),
            "waiting": (
                outcome.get("waiting") if type(outcome.get("waiting")) is str else None
            ),
            "screening": (
                {k: screening[k] for k in _SCREENING_FIELDS if k in screening}
                if type(screening) is dict
                else None
            ),
            "finals": [
                {
                    "state": str(item.get("state", ""))[:64],
                    "promoted": item.get("promoted") is True,
                }
                for item in (finals if type(finals) is list else [])
                if type(item) is dict
            ][:8],
            "qualification": False,
            "reward": False,
        }
    except (OSError, ValueError, TypeError, KeyError):
        return unavailable
    return {
        "epoch": epoch,
        "mode": "DEVELOPMENT_EVALUATION",
        "status": "VALIDATOR_OUTCOME",
        "result": result,
    }


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
        "refusals": [],
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
        # A campaign with no agent calls no model: say so, never a default.
        agent="manual" if manifest.get("agent") == "none" else "carbon-autoresearch",
        reasoning=manifest["provider"].get("model"),
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
        elif note["kind"] == "refusal":
            value["refusals"].append(
                {
                    "sequence": note["sequence"],
                    **_text_fields(note["body"], REFUSAL_FIELDS),
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
    from carbon.development_session.research_campaign import PRACTICE_PROVENANCES

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
                if result.get("provenance") in PRACTICE_PROVENANCES:
                    value["experiments"].append(
                        {
                            "id": task,
                            "provenance": result["provenance"],
                            **{
                                k: result[k]
                                for k in (
                                    "recipe",
                                    # A Challenge's own measured practice
                                    # feedback, as recorded; absent is absent.
                                    "challenge",
                                    "backbone",
                                    "recipe_digest",
                                    "summary",
                                    "fit",
                                    "backend",
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
    # The same cap the campaign runs under (research_campaign: a miner's
    # epochs ceiling narrows the committed final epochs), so the count shown
    # is the count that can actually be used.
    cap = (manifest.get("ceilings") or {}).get("epochs")
    allowed = FINAL_EPOCHS if type(cap) is not int else FINAL_EPOCHS[:cap]
    open_epoch = next((e for e in allowed if e not in submitted), None)
    value["journey"] = {
        "submitted_epochs": submitted,
        "final_exams_remaining": max(0, len(allowed) - len(submitted)),
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
        feedback = directory / "permitted-final-feedback.json"
        if feedback.is_file() and not pointer_exists(directory):
            value["final_results"].append(_validator_outcome(epoch, feedback))
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
