"""Authenticated miner's own research projection; never an owner-report dump."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from carbon.development_session.profile import digest
from carbon.development_session.research_agent_policy import LEGACY, binding
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_guidance import context, verify, verify_history
from carbon.development_session.research_ledger import DIMENSIONS, CampaignLedger
from carbon.development_session.research_workspace import CAPABILITY_FIELDS


class RecordsDiffer(ValueError):
    """A campaign's own records disagree with each other or with its row
    (its guidance, its association, a result's digest): it cannot be read
    back consistently, which reloading does not change. Its closed code says
    so (`campaign_readback_unavailable`, LP-PROD-C); any other failure to
    read a campaign may pass and is answered more mildly. A ValueError, as
    before, for every caller that catches one."""

    code = "campaign_readback_unavailable"


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


_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_PUBLIC_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}")


def _public_identity(outcome):
    """A validator outcome's public identity fields - its exam rule, the
    recipe and contract digests, how it was rebuilt, and a refusal's code and
    issues - each in its closed shape; a field in any other shape is left
    out, never echoed. Hidden scores, cases and seeds are none of these."""
    shown = {}
    rule = outcome.get("rule")
    if type(rule) is str and _PUBLIC_CODE.fullmatch(rule):
        shown["rule"] = rule
    for key in ("recipe_digest", "contract_digest"):
        if type(outcome.get(key)) is str and _DIGEST.fullmatch(outcome[key]):
            shown[key] = outcome[key]
    rebuilt = outcome.get("reconstruction")
    if type(rebuilt) is dict and type(rebuilt.get("backend")) is str:
        shown["reconstruction"] = {
            "backend": rebuilt["backend"][:64],
            "validator_path": rebuilt.get("validator_path") is True,
        }
    failure = outcome.get("failure")
    if type(failure) is dict and type(failure.get("code")) is str:
        issues = failure.get("issues") if type(failure.get("issues")) is list else []
        shown["failure"] = {
            "code": failure["code"][:128],
            "issues": [
                {
                    "code": str(issue.get("code", ""))[:128],
                    "path": [
                        item[:128] if type(item) is str else item
                        for item in (
                            issue.get("path") if type(issue.get("path")) is list else []
                        )[:16]
                        if type(item) in (str, int) and not isinstance(item, bool)
                    ],
                }
                for issue in issues[:16]
                if type(issue) is dict
            ],
        }
    return shown


def pointer_exists(directory):
    return (directory / "final/comparison-ref.json").is_file()


#: A direct freeze's selected-recipe schemas (`research_campaign`).
DIRECT_SELECTED_SCHEMAS = frozenset(
    {"carbon.direct-selected-recipe.v1", "carbon.direct-selected-recipe.v2"}
)


def _epoch_outcome(epoch, outcome_path):
    """One epoch's own-research outcome as observe shows it, or
    READBACK_UNAVAILABLE for a file that is not one."""
    try:
        if outcome_path.is_symlink() or outcome_path.stat().st_size > 4 * 1024**2:
            raise ValueError("bounded own-research outcome required")
        outcome = json.loads(outcome_path.read_bytes())
        if (
            type(outcome) is dict
            and outcome.get("schema") in DIRECT_SELECTED_SCHEMAS
            and outcome.get("selected_by") == "miner"
        ):
            # Written before H20 by a direct freeze: its record's
            # schema replaced the outcome's; the epoch is still its
            # own and is checked below.
            outcome = {
                **outcome,
                "schema": "carbon.autoresearch.epoch-outcome.v1",
            }
        if (
            outcome.get("schema") != "carbon.autoresearch.epoch-outcome.v1"
            or outcome.get("epoch") != epoch
            or outcome.get("status")
            not in {"SELECTED", "STOPPED", "RECONCILIATION_REQUIRED"}
        ):
            raise ValueError("research outcome association differs")
        return {
            "epoch": epoch,
            "status": outcome["status"],
            **_text_fields(outcome, {"reason", "stop_evidence"}),
            "used_feedback": (
                outcome.get("used_feedback")
                if type(outcome.get("used_feedback")) is bool
                else None
            ),
            "selected_by": (
                "miner" if outcome.get("selected_by") == "miner" else "agent"
            ),
            "evidence_basis": "AGENT_OR_CONTROLLER_REPORTED_NOT_INDEPENDENT_SCIENCE",
            "final_evidence": False,
        }
    except (OSError, ValueError, TypeError, AttributeError):
        return {
            "epoch": epoch,
            "status": "READBACK_UNAVAILABLE",
            "final_evidence": False,
        }


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
        # A direct campaign's permitted feedback (Motor, Cooling, the
        # direct versions) carries its outcome as `result` beside the Ladder
        # (`exam_feedback`) and no epoch field: its file names the epoch
        # (M1 E2E U53: every direct submit read "readback unavailable").
        direct = (
            type(document) is dict
            and "outcome" not in document
            and {"result", "exam_feedback"} <= set(document)
        )
        outcome = document["result"] if direct else document["outcome"]
        if (
            document.get("schema") not in feedback_schemas()
            or (not direct and document.get("epoch") != epoch)
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
            # The outcome's public identity, as the validator discloses it to
            # this miner under every feedback mode (LAUNCHPAD-ACCEPT-04).
            **_public_identity(outcome),
            # Scored under a rule that seals hidden-batch results: no
            # screening, nomination or finals reach a miner, so none is shown
            # and none is inferred (`intake_client.describe`).
            "sealed": outcome["state"] == "SCORED" and screening is None,
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
        if direct:
            result["grade"] = _grade(
                _latest_ladder(path, document),
                (
                    document.get("recipe_digest")
                    if type(document.get("recipe_digest")) is str
                    else None
                ),
                epoch,
            )
        if type(outcome.get("practice_dual")) is dict:
            # C13: the evaluator's practice dual block, allow-listed.
            from scripts.dev.miner_launchpad.campaign_view import dual_feedback

            result["practice_dual"] = dual_feedback(
                {"practice_dual": outcome["practice_dual"]}
            )
    except (OSError, ValueError, TypeError, KeyError):
        return unavailable
    return {
        "epoch": epoch,
        "mode": "DEVELOPMENT_EVALUATION",
        "status": "VALIDATOR_OUTCOME",
        "result": result,
    }


def _latest_ladder(path, document):
    """The epoch's Ladder as the miner last read it ("Check for result",
    `direct_submission.refresh_exam_feedback`) when that read is of this
    recipe, else the one stored at submit."""
    from carbon.development_session.direct_submission import (
        EXAM_FEEDBACK_FILE,
        EXAM_FEEDBACK_SCHEMA,
    )

    fresh = path.parent / EXAM_FEEDBACK_FILE
    try:
        if not fresh.is_symlink() and 0 < fresh.stat().st_size <= 65536:
            read = json.loads(fresh.read_bytes())
            if (
                type(read) is dict
                and read.get("schema") == EXAM_FEEDBACK_SCHEMA
                and read.get("recipe_digest") == document.get("recipe_digest")
            ):
                return read.get("exam_feedback")
    except (OSError, ValueError):
        pass
    return document["exam_feedback"]


def _grade(ladder, submission=None, epoch=None):
    """The miner's own Ladder for the exam, as the display rule shows it
    (Validator VALUE_SCORE_GAP): one graded total 0..1 per document, its
    A and D as detail, a gate failure as not eligible; None when the
    receiver had no graded result yet."""

    def one(document):
        if type(document) is not dict or document.get("status") not in (
            "IMPROVED",
            "NO_IMPROVEMENT",
            "GATE_FAILED",
            "NOT_SCORED",
        ):
            return None
        shown = {"status": document["status"]}
        for name in ("total", "A", "D"):
            value = document.get(name)
            if (
                type(value) in (int, float)
                and not isinstance(value, bool)
                and math.isfinite(value)
            ):
                shown[name] = float(value)
        if type(document.get("exam_version")) is str:
            shown["exam_version"] = document["exam_version"][:64]
        # Ladder v3 names the submission each document is about (U63).
        if type(document.get("recipe_digest")) is str:
            shown["recipe_digest"] = document["recipe_digest"][:71]
        if type(document.get("epoch")) is int and not isinstance(
            document["epoch"], bool
        ):
            shown["epoch"] = document["epoch"]
        return shown

    if type(ladder) is not dict:
        return None
    latest, best = one(ladder.get("latest")), one(ladder.get("best"))
    # `latest` is this submission's grade only when the document names this
    # submission (Ladder v3, U63). A v2 document names none, and a v3 one may
    # name another: either is the mining key's latest grade on the exam
    # (`other_submission_latest`), never this submit's. M1 E2E R5-1: three submits read
    # "Graded 0.54" although the receiver graded only one of them.
    own = (
        latest
        if latest is not None
        and submission is not None
        and latest.get("recipe_digest") == submission
        # v3 also names the epoch: a document about this recipe's earlier
        # submit (another epoch) is not this one's (Validator, R5-1 note).
        and (epoch is None or latest.get("epoch") in (None, epoch))
        else None
    )
    # M1 E2E R8-1: agents read the key's latest grade as their own, so the
    # answer says in words whether this submission has a grade, and which way
    # the score points (R8-3).
    return {
        "latest": own,
        "this_submission": "graded" if own is not None else "not_graded_yet",
        "other_submission_latest": None if own is not None else latest,
        "best": best,
        "submission": submission,
        "score_direction": "higher_is_better",
    }


def _multi_validator_outcome(epoch, path):
    """Project each independently stored allow-listed result; never aggregate scores."""
    from carbon.challenge_registry.campaigns import campaign_for
    from carbon.challenge_registry.registry import ResolutionError
    from carbon.development_session.intake_targets import (
        MAX_TARGETS,
        result_path,
        validate,
    )
    from scripts.dev.miner_launchpad.supervisor import next_action

    try:
        if path.is_symlink() or path.stat().st_size > (MAX_TARGETS + 1) * 65536:
            return None
        document = json.loads(path.read_bytes())
        composition = campaign_for(document["challenge"])
        if (
            composition.multi_feedback_schema is None
            or composition.intake_code is None
            or document.get("schema") != composition.multi_feedback_schema
            or document.get("epoch") != epoch
        ):
            return None
        rows = document["validators"]
        targets = validate(
            [{k: row[k] for k in ("intake_url", "receiver_hotkey")} for row in rows]
        )
        projected = []
        root = path.parent.parent
        for row, target in zip(rows, targets):
            if row["feedback"] is not None:
                found = _validator_outcome(epoch, result_path(root, target, epoch))
                if (
                    found["status"] != "VALIDATOR_OUTCOME"
                    or found["result"]["state"] != row["state"]
                ):
                    return None
                projected.append(
                    {**target, "state": row["state"], "result": found["result"]}
                )
            else:
                if row["state"] not in {"REFUSED", "FAILED_INFRA", "QUEUED", "PENDING"}:
                    return None
                code = (
                    None
                    if row["state"] == "PENDING"
                    else composition.intake_code(row["code"])
                )
                projected.append(
                    {
                        **target,
                        "state": row["state"],
                        "code": code,
                        "next_step": (
                            "Waiting for this validator's trip to finish."
                            if code is None
                            else next_action(code)
                        ),
                        "result": None,
                    }
                )
        return {
            "epoch": epoch,
            "mode": "DEVELOPMENT_EVALUATION",
            "status": "MULTI_VALIDATOR_OUTCOME",
            "validators": projected,
            "qualification": False,
            "reward": False,
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ResolutionError):
        return None


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
        raise RecordsDiffer("campaign guidance association differs")
    if task is not None:
        value["effective_research_inputs"] = verify_history(
            root, task, manifest.get("agent_policy", binding(LEGACY)), context(manifest)
        )
    if (
        manifest.get("campaign_id") != row["campaign"]
        or manifest.get("principal") != row["principal"]
    ):
        raise RecordsDiffer("campaign projection association differs")
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
        # Graphite is named as setup names it (OWNER-GRAPHITE-MINER-01); an
        # autonomous campaign keeps its historical label.
        agent=AGENT_LABELS.get(manifest.get("agent"), "carbon-autoresearch"),
        reasoning=manifest["provider"].get("model"),
        # Where its practice runs, from its frozen runtime (RSURF-D19):
        # until 2026-10-03 this said CPU for every campaign.
        compute=_compute(manifest.get("runtime")),
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
        result = op["result"] or {}
        if op["actual"] is None:
            target = reserved
        elif (
            result.get("schema") == "carbon.autoresearch.worker-reconciliation.v1"
            # A model call settled at its full reservation: its outcome, and
            # so what the provider charged, is unknown (LP-PROD-W2).
            or result.get("provider_settlement") is not None
        ):
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
    # The model's speed as this campaign observed it (S17), never a recorded
    # or guessed one.
    value["model_speed"] = model_speed(status["operations"], manifest.get("provider"))
    from carbon.development_session.research_campaign import unknown_outcome_calls

    # Model calls whose outcome was unknown: what the miner's Reconcile
    # settled, at what booked charge and with what caveat, and - while the
    # campaign awaits reconciliation - what is still unresolved (LP-PROD-W2).
    # Read from the ledger alone: observing takes no lease.
    value["unknown_outcome_calls"] = unknown_outcome_calls(
        status["operations"], awaiting=value["state"] == "RECONCILIATION_REQUIRED"
    )
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
    from carbon.development_session.research_campaign import practice_provenances
    from carbon.development_session.smoke_practice import is_smoke
    from carbon.development_session.smoke_practice import public_view as smoke_view

    provenances = practice_provenances()

    with ledger.db() as db:
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='research_results' AND type='table'"
        ).fetchone():
            for task, body, pin in db.execute(
                "SELECT task,body,digest FROM research_results WHERE owner=?",
                (manifest["owner"],),
            ):
                if digest(body) != pin:
                    raise RecordsDiffer("research result changed")
                result = json.loads(body)
                if result.get("provenance") in provenances:
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
                                    # The graded dual measurement on the
                                    # public bank (C13), read allow-listed
                                    # by campaign_view.dual_feedback.
                                    "practice_dual",
                                )
                                if k in result
                            },
                            "accepted_improvement": False,
                            "adaptively_seen": True,
                        }
                    )
                elif is_smoke(result):
                    # A smoke practice: status, runtime and truncation only,
                    # never a score (LAUNCHPAD-SMOKE-PRACTICE-01). Listed
                    # apart, so nothing that reads experiments reads it.
                    value.setdefault("smoke_practices", []).append(
                        smoke_view(task, result)
                    )
    # What each run took and what the model calls that chose it cost, from
    # the ledger (M1 E2E U45): the same record for every agent.
    costs = run_costs(
        status["operations"],
        ledger.operation_times(owner=manifest["owner"]),
        calls_models=manifest.get("agent") != "none",
    )
    for experiment in value["experiments"]:
        experiment.update(
            costs.get(
                experiment["id"],
                {
                    "duration": None,
                    "model_cost": None,
                    "model_cost_reason": "not_in_the_ledger",
                },
            )
        )
    value["completed_experiments"] = len(value["experiments"])
    if manifest.get("agent") == "graphite":
        # Graphite's mode, stage, plan, research spend and hunt (S4), read
        # from the frozen plan, S3's view of its own records and the ledger;
        # observe shows the stage.
        value["graphite"] = graphite_progress(manifest, status, root)
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
            value["epoch_outcomes"].append(_epoch_outcome(epoch, outcome_path))
        selected = directory / "selected-recipe.json"
        if selected.is_file():
            selection = json.loads(selected.read_bytes())
            value["candidate_freezes"].append(
                {
                    "epoch": epoch,
                    **{
                        k: selection[k] for k in ("strategy", "reason", "used_feedback")
                    },
                    # A Level-0 strategy's compile identities; a direct
                    # campaign's construction recipe has neither (M1 E2E H10:
                    # every observe after its freeze raised KeyError).
                    **{
                        k: selection.get(k)
                        for k in ("strategy_hash", "construction_plan_digest")
                    },
                    "final_evidence": False,
                }
            )
        feedback = directory / "permitted-final-feedback.json"
        if feedback.is_file() and not pointer_exists(directory):
            value["final_results"].append(
                _multi_validator_outcome(epoch, feedback)
                or _validator_outcome(epoch, feedback)
            )
        elif not pointer_exists(directory):
            from carbon.challenge_registry.campaigns import campaign_for_manifest
            from carbon.challenge_registry.registry import ResolutionError

            try:
                status_name = campaign_for_manifest(manifest).multi_feedback_status
            except ResolutionError:
                status_name = None  # Retired/unknown history has no new multi hook.
            status = directory / status_name if status_name is not None else None
            if status is not None and status.is_file():
                found = _multi_validator_outcome(epoch, status)
                if found is not None:
                    value["final_results"].append(found)
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


#: Who researches, as the projection labels it.
AGENT_LABELS = {"none": "manual", "graphite": "carbon-graphite"}

#: Graphite's own records, as S3's driver keeps them: write-once stage records
#: under `<campaign>/graphite/stages/` (the hunt's carries its report's
#: counts), and the hunt's Reader calls metered as `graphite-reader-<digest>`
#: (`miner.budget.READER_PREFIX`).
GRAPHITE_STAGES = ("graphite", "stages")
READER_PREFIX = "graphite-reader-"
SPEND_KEYS = ("provider_nanodollars", "provider_attempts")
_HUNT_FIELDS = ("fetched", "deduped", "triaged_out", "extracted", "failed_infra")
_STAGE_NAME = re.compile(r"[a-z][a-z0-9_-]{0,31}")
_STAGE_STATES = ("PENDING", "RUNNING", "DONE", "STOPPED", "RETAINED")
_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}")
#: A stage's replies cut at the output cap (`research_loop.OUTPUT_CAP_HIT`),
#: restated so the projection imports no research loop.
OUTPUT_CAP_CAUSE = "turn_hit_output_cap"


def model_speed(operations, provider):
    """The campaign's observed model speed (S17): output tokens per second
    over its completed calls, each timed from dispatch to its whole reply
    (`reply_ms`), and whether a full reply at the plan's output cap fits its
    call timeout at that speed. Carbon records no provider's speed and
    guesses none: before a completed call there is no speed and no warning.
    A plan whose calls stream (`model_provider.record_streams`) is never
    warned: a streamed reply is not cut while tokens arrive."""
    from carbon.development_session.model_provider import record_streams

    tokens = took = calls = 0
    for op in operations:
        result = op.get("result") if type(op.get("result")) is dict else {}
        usage = result.get("usage")
        produced = usage.get("output_tokens") if type(usage) is dict else None
        reply_ms = result.get("reply_ms")
        timed = type(reply_ms) is int and reply_ms > 0
        if timed and type(produced) is int and produced >= 0:
            tokens, took, calls = tokens + produced, took + reply_ms, calls + 1
    settings = provider.get("settings") if type(provider) is dict else None
    settings = settings if type(settings) is dict else {}
    cap, timeout = settings.get("max_output_tokens"), settings.get("timeout_seconds")
    cap = cap if type(cap) is int and cap > 0 else None
    timeout = timeout if type(timeout) is int and timeout > 0 else None
    rate = tokens * 1000 / took if tokens else None
    full = None if rate is None or cap is None else cap / rate
    streams = record_streams(provider)
    return {
        "calls_observed": calls,
        "output_tokens_per_second": None if rate is None else round(rate, 1),
        "streams": streams,
        "max_output_tokens": cap,
        "timeout_seconds": timeout,
        "full_reply_seconds": None if full is None else round(full),
        "warning": (
            not streams and full is not None and timeout is not None and full > timeout
        ),
    }


#: How a run's model cost is attributed: the model calls the campaign's
#: ledger reserved after the previous run started, up to this run's start -
#: the calls that chose it. Restated beside every figure so it never reads as
#: a provider's invoice (the ledger's own cost basis).
MODEL_COST_BASIS = (
    "model calls since the previous run started, up to this run's start; "
    "integer nanodollars, published-rate estimates from provider token usage"
)


def run_costs(operations, times, *, calls_models):
    """Each research trial's duration and model cost, from the campaign's
    ledger alone (M1 E2E U45): {trial id: {"duration", "model_cost"}}.

    Duration: wall seconds from the trial's reservation to its settlement,
    in the ledger's clock (None, with `wall_reason`, for a trial settled
    before settlement times were recorded, or not settled), and worker
    seconds, the worker's own measured run time the ledger settled
    (`numerical_milliseconds`). Model cost: the model calls reserved after
    the previous trial's reservation, up to this one's (`MODEL_COST_BASIS`),
    each at its settled charge; a call still reserved is counted apart, at
    no figure. A campaign whose agent calls no model through Carbon (the
    miner's own agent, or none) has no model cost here: None, with why."""
    rows, pending = {}, []
    for op in operations:
        reservation = op.get("reservation") or {}
        actual = op.get("actual")
        if any(key in reservation for key in SPEND_KEYS):
            pending.append(op)
        if not reservation.get("research_trials"):
            continue
        created, finished = times.get(op["id"], (None, None))
        worker = (actual or {}).get("numerical_milliseconds")
        wall = (
            round(finished - created, 3)
            if finished is not None and created is not None and finished >= created
            else None
        )
        cost = None
        if calls_models:
            settled = [c for c in pending if c.get("actual") is not None]
            cost = {
                "nanodollars": sum(
                    int((c["actual"] or {}).get("provider_nanodollars", 0))
                    for c in settled
                ),
                "calls": len(settled),
                "unsettled_calls": len(pending) - len(settled),
                "basis": MODEL_COST_BASIS,
            }
        rows[op["id"]] = {
            "duration": {
                "wall_seconds": wall,
                "worker_seconds": (
                    worker / 1000 if type(worker) is int and worker >= 0 else None
                ),
                "wall_reason": (
                    None
                    if wall is not None
                    else (
                        "not_settled"
                        if actual is None
                        else "settled_before_times_were_recorded"
                    )
                ),
            },
            "model_cost": cost,
            "model_cost_reason": (
                None if calls_models else "no_model_calls_through_carbon"
            ),
        }
        pending = []
    return rows


def _graphite_view(root, operations):
    """S3's own view of a Graphite campaign (`miner.driver.view`): its stages,
    the current one, the plan its Planner wrote or the miner chose, what its
    research stages spent against the research share, and the hunt's cost.
    A test replaces it."""
    from carbon.agent_campaign.graphite.miner.driver import view

    return view(root, operations=operations)


def _hunt_report(root):
    """The counts of the hunt's report, from its stage record (S3), or None
    before the hunt finished."""
    path = Path(root).joinpath(*GRAPHITE_STAGES, "hunt.json")
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1 << 20:
            return None
        record = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    report = record.get("report") if type(record) is dict else None
    if type(report) is not dict:
        return None
    counts = {}
    for name in _HUNT_FIELDS:
        item = report.get(name)
        if type(item) is bool:
            # S2 says whether arXiv failed; the view counts it (0 or 1).
            counts[name] = int(item)
        elif type(item) is int and item >= 0:
            counts[name] = item
        elif type(item) is list:
            counts[name] = len(item)
        else:
            counts[name] = None
    return counts


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _spend(value):
    value = value if type(value) is dict else {}
    return {key: _count(value.get(key)) for key in SPEND_KEYS}


def _stages(value):
    rows = []
    for row in value if type(value) is list else []:
        if type(row) is not dict or type(row.get("stage")) is not str:
            continue
        if not _STAGE_NAME.fullmatch(row["stage"]):
            continue
        code = row.get("code")
        shown = {
            "stage": row["stage"],
            "state": (row.get("state") if row.get("state") in _STAGE_STATES else None),
            "code": code if type(code) is str and _CODE.fullmatch(code) else None,
        }
        if row.get("cause") == OUTPUT_CAP_CAUSE:
            # Replies cut at the output cap: the cap they hit (S3's view).
            cap = row.get("output_cap")
            shown["cause"] = OUTPUT_CAP_CAUSE
            shown["output_cap"] = cap if type(cap) is int and 0 < cap <= 10**7 else None
        rows.append(shown)
    return rows[:16]


def graphite_progress(manifest, status, root):
    """A Graphite campaign's progress: {edition, mode, stage, stages,
    plan_digest, research_share, research_spent, research_cap, hunt}.

    The frozen plan's `provider.graphite` block gives the edition and mode.
    Everything else is S3's driver's own view of its records
    (`miner.driver.view`): the stages and the current one (None before any,
    `complete` once done), the plan digest - the one the miner chose, or the
    one the campaign's Planner wrote - the research share (FULL only), what
    the research stages (the hunt's Reader and the Planner) spent and the cap
    the share sets. `hunt` is None without a hunt; otherwise the counts of
    its report (None until it finished), how many Reader calls it made and
    what they cost, all of them read live from the ledger. Without the
    driver's view (an unreadable record), only the frozen block's values
    are shown, and nothing is invented."""
    provider = (
        manifest.get("provider") if type(manifest.get("provider")) is dict else {}
    )
    block = provider.get("graphite") if type(provider.get("graphite")) is dict else {}
    operations = status["operations"]
    try:
        seen = _graphite_view(root, operations)
    except Exception:  # noqa: BLE001 - shown as unknown, never as a failure
        seen = None
    seen = seen if type(seen) is dict else {}
    from carbon.development_session import submission_policy

    mode = block.get("mode") if block.get("mode") in GRAPHITE_MODES else None
    share = block.get("research_share")
    plan_digest = seen.get("plan_digest", block.get("plan_digest"))
    stage = seen.get("stage")
    hunt = None
    if block.get("hunt") is not None:
        calls, cost = 0, 0
        for op in operations:
            if not str(op.get("id", "")).startswith(READER_PREFIX):
                continue
            # As the driver's view and the ledger count use: settled where
            # settled, reserved otherwise.
            charge = op.get("actual")
            charge = charge if charge is not None else op.get("reservation")
            amount = (charge if type(charge) is dict else {}).get(
                "provider_nanodollars"
            )
            calls += 1
            cost += amount if type(amount) is int else 0
        hunt = {
            **(_hunt_report(root) or dict.fromkeys(_HUNT_FIELDS)),
            "reader_calls": calls,
            "cost_nanodollars": cost,
        }
    return {
        "edition": block.get("edition") if type(block.get("edition")) is str else None,
        **(
            {submission_policy.FIELD: submission_policy.RETAIN_ONLY}
            if block.get(submission_policy.FIELD) == submission_policy.RETAIN_ONLY
            else {}
        ),
        "mode": mode,
        "stage": stage if type(stage) is str and _STAGE_NAME.fullmatch(stage) else None,
        "stages": _stages(seen.get("stages")),
        "plan_digest": plan_digest if type(plan_digest) is str else None,
        # Of the miner's provider_nanodollars and provider_attempts ceilings;
        # only FULL applies it, and its research stages stop at it
        # (`research_share_reached`).
        "research_share": (
            share if mode == "FULL" and type(share) in (int, float) else None
        ),
        "research_spent": _spend(seen.get("research_spent")),
        "research_cap": (
            _spend(seen["research_cap"])
            if type(seen.get("research_cap")) is dict
            else None
        ),
        "hunt": hunt,
    }


GRAPHITE_MODES = ("RESEARCH", "BUILD", "FULL")


def _compute(runtime):
    """`local-isolated-cpu`, `local-isolated-gpu` or `remote-gpu:<transport>`,
    from a campaign's frozen runtime, as the runner's preflight names them."""
    runtime = runtime if type(runtime) is dict else {}
    remote = runtime.get("remote_gpu")
    if type(remote) is list and remote and type(remote[0]) is dict:
        return "remote-gpu:" + str(remote[0].get("transport"))[:32]
    if "gpu_research" in runtime:
        return "local-isolated-gpu"
    return "local-isolated-cpu"
