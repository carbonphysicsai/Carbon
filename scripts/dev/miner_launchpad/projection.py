"""Authenticated miner's own research projection; never an owner-report dump."""

from __future__ import annotations

import json
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
                                )
                                if k in result
                            },
                            "accepted_improvement": False,
                            "adaptively_seen": True,
                        }
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
_STAGE_STATES = ("PENDING", "RUNNING", "DONE", "STOPPED")
_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}")


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
        rows.append(
            {
                "stage": row["stage"],
                "state": (
                    row.get("state") if row.get("state") in _STAGE_STATES else None
                ),
                "code": code if type(code) is str and _CODE.fullmatch(code) else None,
            }
        )
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
