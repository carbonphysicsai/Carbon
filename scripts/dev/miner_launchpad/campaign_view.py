"""The campaign's research view: one allow-listed document for every panel.

OWNER-MINER-RESEARCH-SURFACE-01 (RSURF-D1). The Control Center's research
surface and an MCP client's `carbon_campaign_view` read this same document.
Both are generated from the one operations table, so the miner and their
agent see exactly the same thing.

Every field is copied by name from sources that are already allow-listed:
- the miner's own-research projection (`projection.project`);
- the Challenge's research-surface declaration (`research_view`, reached
  through its registered campaign, so this door names no Challenge);
- the Challenge's public description and capability registry;
- the campaign's own journal notes, as bounded untrusted text.

Per-case curves (RSURF-D2) are public PRACTICE cases only, computed on this
machine from the miner's own worker predictions after their digest matches
the ledger's worker record. Anything else fails closed to aggregates with a
reason. No private evaluation data, seed or per-case evaluation error is
read here.

`carbon_note` (RSURF-D5) writes through the existing journal path and starts
no work. Notes are untrusted text: every door shows them as text, never HTML,
and Carbon's own agent is never given them.
"""

from __future__ import annotations

import functools
import json
import re
import time
from pathlib import Path

from carbon.challenge_registry.research_view import (
    Axis,
    bars_chart,
    finite,
    output_chart,
    series_chart,
    validate_chart,
)

SCHEMA = "carbon.control-center.campaign-view.v1"
NOTE_SCHEMA = "carbon.research-surface.note.v1"
NOTE_KINDS = ("hypothesis", "plan", "observation")
NOTE_MAX = 2000
#: How much of a campaign the view carries, newest first, so a long campaign
#: stays a bounded document for any client. The export has the rest.
FEED_MAX = 100
EXPERIMENTS_MAX = 50
EVENTS_MAX = 100
PREDICTIONS_MAX_BYTES = 16 * 1024**2
TERMINAL = frozenset({"COMPLETED", "STOPPED", "READBACK_UNAVAILABLE", "EXPIRED"})
HALTED = frozenset(
    {"PAUSED", "PAUSE_REQUESTED", "INTERRUPTED", "RECONCILIATION_REQUIRED"}
)
#: Control characters (newline and tab aside) and bidirectional overrides:
#: refused in a note, stripped from any journal text the view shows.
_UNSAFE = re.compile(
    "[\x00-\x08\x0b-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)
LABELS = {
    "mode": "DEVELOPMENT",
    "network": "testnet",
    "statement": "Practice evidence ≠ qualification",
}
NON_CLAIMS = (
    "Practice evidence is adaptively seen public evidence, not the exam.",
    "No leaderboard, rank, official score, qualification or reward.",
    "No chain write: DEVELOPMENT submit reaches the local validator only.",
    "Spend is your own ledger; your provider bills you. Carbon bills nothing.",
)


def clean_text(value, limit=NOTE_MAX):
    """Journal text as the view shows it: a string, unsafe characters
    removed, bounded; None when there is no text."""
    if type(value) is not str:
        return None
    text = _UNSAFE.sub("", value).strip()
    return text[:limit] if text else None


def note_text(value):
    """A note to post: 1 to NOTE_MAX characters of plain text, or refused."""
    from scripts.dev.miner_launchpad.controller import Rejected

    if type(value) is not str:
        raise Rejected("bounded_note_required")
    text = value.strip()
    if not 1 <= len(text) <= NOTE_MAX or _UNSAFE.search(text):
        raise Rejected("bounded_note_required")
    return text


def _int(value):
    return value if type(value) is int else 0


def _str(value, limit=128):
    return value[:limit] if type(value) is str else None


# ---- The Challenge's declaration and contract, reached through its campaign.


def research_view_for(challenge):
    """The Challenge's research-surface declaration, or None (aggregates)."""
    if type(challenge) is not dict:
        return None
    try:
        from carbon.challenge_registry.campaigns import campaign_for

        build = campaign_for(challenge).research_view
        return build() if build is not None else None
    except Exception:  # noqa: BLE001 - no declaration means aggregates only
        return None


@functools.lru_cache(maxsize=8)
def _contract(challenge_id, version):
    from carbon.challenge_registry import registry
    from carbon.reconstruction.capability_registry import public_registry

    described = registry.describe(challenge_id, version)
    capabilities = public_registry(challenge_id)
    models = described.get("models") or {}
    exam = described.get("exam") or {}
    material = described.get("public_material") or {}
    feedback = described.get("feedback") or {}
    rule = exam.get("rule") or {}
    controls = {}
    for name, control in (models.get("controls") or {}).items():
        controls[str(name)] = {
            key: control.get(key)
            for key in (
                "group",
                "type",
                "minimum_or_choices",
                "maximum",
                "default",
                "families",
            )
        }
    listed = [
        {
            key: item.get(key)
            for key in ("id", "dimension", "summary", "status", "blocker", "selector")
        }
        for item in capabilities.get("capabilities", [])
    ]
    by_status = {}
    for item in listed:
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
    return json.loads(
        json.dumps(
            {
                "challenge": {
                    "id": challenge_id,
                    "version": version,
                    "title": described.get("title"),
                    "identity": described.get("identity"),
                },
                "contract_digest": described.get("contract_digest"),
                "exam": {
                    "gates": list(exam.get("gates") or []),
                    "components": list(exam.get("components") or []),
                    "rule": {
                        key: rule.get(key)
                        for key in ("status", "authority", "promotable")
                        if key in rule
                    },
                },
                "rebuildable_models": [
                    {key: m.get(key) for key in ("id", "selector", "summary")}
                    for m in models.get("rebuildable") or []
                ],
                "controls": controls,
                "capabilities": listed,
                "capability_counts": by_status,
                "status_meaning": capabilities.get("status_meaning", {}),
                "never_disclosed": list(material.get("never_disclosed") or []),
                "feedback": {
                    "practice_schema": feedback.get("practice"),
                    "evaluation_fields": list(feedback.get("evaluation_fields") or []),
                    "screening_fields": list(feedback.get("screening_fields") or []),
                },
                "limits": described.get("limits") or {},
                "authority": described.get("authority"),
                # RSURF-D10: filled from data when the construction ladder is
                # merged; empty until then, never inferred.
                "construction_level": {
                    "level": None,
                    "status": "NOT_YET_DEFINED",
                    "basis": (
                        "The construction ladder is not part of this build. "
                        "This slot is filled from the Challenge's data when it is."
                    ),
                },
            },
            allow_nan=False,
        )
    )


def contract_section(challenge, feedback_mode, offered_modes=()):
    if type(challenge) is not dict or type(challenge.get("id")) is not str:
        return None
    try:
        value = json.loads(
            json.dumps(_contract(challenge["id"], challenge.get("version")))
        )
    except Exception:  # noqa: BLE001 - an unreadable contract is shown as such
        return {"status": "UNAVAILABLE", "challenge": dict(challenge)}
    value["feedback_mode"] = {
        "frozen": feedback_mode,
        "offered": list(offered_modes),
        "basis": (
            "Frozen when the campaign was created. The DEVELOPMENT outcome is "
            "shown through it, to you and to any agent reading this view."
        ),
    }
    return value


# ---- Sections built from the own-research projection.


def experiment_rows(own, view):
    keys = [k for k, _ in view.components] if view is not None else None
    rows = []
    for index, experiment in enumerate(own.get("experiments") or [], 1):
        summary = (
            experiment.get("summary") if type(experiment.get("summary")) is dict else {}
        )
        fit = experiment.get("fit") if type(experiment.get("fit")) is dict else {}
        backend = (
            experiment.get("backend") if type(experiment.get("backend")) is dict else {}
        )
        diagnostics = (
            experiment.get("diagnostics")
            if type(experiment.get("diagnostics")) is dict
            else {}
        )
        components = (
            summary.get("components") if type(summary.get("components")) is dict else {}
        )
        recipe = experiment.get("recipe")
        if type(recipe) is not dict or len(json.dumps(recipe, default=str)) > 4096:
            recipe = None
        score = summary.get("score", diagnostics.get("descriptive_score"))
        failures = summary.get("gate_failures")
        rows.append(
            {
                "index": index,
                "id": _str(experiment.get("id")),
                "backbone": _str(experiment.get("backbone"))
                or _str((recipe or {}).get("backbone")),
                "recipe_digest": _str(experiment.get("recipe_digest")),
                "recipe": recipe,
                "eligible": summary.get("eligible")
                if type(summary.get("eligible")) is bool
                else None,
                "score": finite(score),
                "important_score": finite(summary.get("important_score")),
                "components": {
                    str(k): finite(components.get(k))
                    for k in (keys if keys is not None else sorted(components))
                },
                "gate_failures": {
                    str(k): v
                    for k, v in (failures.items() if type(failures) is dict else ())
                    if type(v) is int and v
                },
                "cases": {
                    key: summary.get(name) if type(summary.get(name)) is int else None
                    for key, name in (
                        ("total", "n_cases"),
                        ("scored", "n_scored"),
                        ("reference_invalid", "n_reference_invalid"),
                        ("failed_infra", "n_failed_infra"),
                    )
                },
                "fit": {
                    "final_loss": finite(fit.get("final_loss")),
                    "n_params": fit.get("n_params")
                    if type(fit.get("n_params")) is int
                    else None,
                    "train_s": finite(fit.get("train_s")),
                },
                "backend": _str(backend.get("kind"), 64),
                "learning_curve": _curve(experiment) is not None,
                "accepted_improvement": False,
            }
        )
    return rows


def _curve(experiment):
    """A recorded training curve (`inline_curve`), or None."""
    points = experiment.get("inline_curve")
    if type(points) is not list or not 2 <= len(points) <= 4096:
        return None
    steps, losses = [], []
    for point in points:
        if type(point) is not dict:
            return None
        step, loss = point.get("step"), finite(point.get("data_loss"))
        if type(step) is not int or loss is None or loss < 0:
            return None
        if steps and step <= steps[-1]:
            return None
        steps.append(step)
        losses.append(loss)
    return steps, losses


def comparison(rows, view):
    """The current practice run against the previous one, metric by metric."""
    if not rows:
        return None
    current = rows[-1]
    previous = rows[-2] if len(rows) > 1 else None
    lower = view is None or view.direction == "lower_is_better"
    metrics = [("score", "Practice score", lambda r: r["score"])]
    labels = dict(view.components) if view is not None else {}
    for key in current["components"]:
        metrics.append(
            (
                "components." + key,
                labels.get(key, key),
                lambda r, key=key: r["components"].get(key),
            )
        )
    items = []
    for key, label, read in metrics:
        now = read(current)
        then = read(previous) if previous is not None else None
        delta = finite(now - then) if now is not None and then is not None else None
        items.append(
            {
                "metric": key,
                "label": label,
                "previous": then,
                "current": now,
                "delta": delta,
                "better": None if not delta else (delta < 0) == lower,
            }
        )
    return {
        "current": current["index"],
        "previous": previous["index"] if previous else None,
        "direction": "lower_is_better" if lower else "higher_is_better",
        "metrics": items,
        "basis": "Descriptive practice on public cases; not an accepted improvement.",
    }


def charts(rows, own, view):
    found = []
    if rows and view is not None:
        current, previous = rows[-1], (rows[-2] if len(rows) > 1 else None)
        labels = [label for _, label in view.components]
        series = []
        if previous is not None:
            series.append(
                (
                    "Run " + str(previous["index"]),
                    "previous",
                    [previous["components"].get(k) for k, _ in view.components],
                )
            )
        series.append(
            (
                "Run " + str(current["index"]),
                "current",
                [current["components"].get(k) for k, _ in view.components],
            )
        )
        found.append(
            bars_chart(
                "components",
                "Practice components, this run against the previous",
                labels,
                series,
            )
        )
    if rows:
        runs = Axis("practice run", None, tuple(r["index"] for r in rows))
        found.append(
            series_chart(
                "trend_score",
                "Practice score by run",
                runs,
                [("Score", "current", [r["score"] for r in rows])],
            )
        )
        if view is not None and view.components:
            values = [
                [r["components"].get(k) for r in rows] for k, _ in view.components
            ]
            positive = all(v is None or v > 0 for row in values for v in row)
            found.append(
                series_chart(
                    "trend_components",
                    "Practice components by run",
                    runs,
                    [
                        (label, "series", row)
                        for (_, label), row in zip(view.components, values, strict=True)
                    ],
                    log=positive,
                )
            )
    experiments = own.get("experiments") or []
    curve = _curve(experiments[-1]) if experiments else None
    if curve is not None:
        steps, losses = curve
        found.append(
            series_chart(
                "learning_curve",
                "Training data loss, this run (TRAIN data)",
                Axis("optimizer update", None, tuple(steps)),
                [("Data loss", "current", losses)],
                log=all(v > 0 for v in losses),
            )
        )
    return [validate_chart(chart) for chart in found]


def learning_curve_status(own, view):
    experiments = own.get("experiments") or []
    if experiments and _curve(experiments[-1]) is not None:
        return {"status": "RECORDED", "chart": "learning_curve"}
    basis = (
        view.learning_curve.get("basis")
        if view is not None
        else "This Challenge declares no research view."
    )
    return {"status": "NOT_RECORDED", "basis": basis}


def stages(own):
    """The real lifecycle (RSURF-D9), each stage's state from the records."""
    experiments = own.get("experiments") or []
    freezes = own.get("candidate_freezes") or []
    results = own.get("final_results") or []
    journey = own.get("journey") if type(own.get("journey")) is dict else {}
    state = str(own.get("state") or "UNKNOWN")
    terminal = state in TERMINAL
    awaiting = journey.get("frozen_awaiting_submission") is True
    done = {
        "research": own.get("started_unix") is not None or bool(experiments),
        "practice": bool(experiments),
        "candidate": bool(freezes),
        "submit": bool(results),
    }
    if terminal:
        current = None
    elif state == "SUBMITTING" or awaiting:
        current = "submit"
    elif state == "FREEZING":
        current = "candidate"
    elif experiments or state == "PRACTICING":
        current = "practice"
    else:
        current = "research"
    remaining = journey.get("final_exams_remaining")
    details = {
        "research": "Started" if done["research"] else "Not started",
        "practice": str(len(experiments)) + " done",
        "candidate": (
            ", ".join("epoch " + str(f.get("epoch")) for f in freezes) + " frozen"
            if freezes
            else "None frozen"
        ),
        "submit": (
            str(len(results))
            + " DEVELOPMENT outcome"
            + ("" if len(results) == 1 else "s")
            if results
            else "Not submitted"
        )
        + (
            " · "
            + str(remaining)
            + " final exam"
            + ("" if remaining == 1 else "s")
            + " left"
            if type(remaining) is int
            else ""
        ),
    }
    labels = {
        "research": "Research",
        "practice": "Practice runs",
        "candidate": "Candidate frozen",
        "submit": "DEVELOPMENT submit",
    }
    out = []
    for key in ("research", "practice", "candidate", "submit"):
        if key == current:
            status = "halted" if state in HALTED else "current"
        elif done[key]:
            status = "done"
        else:
            status = "not_reached" if terminal else "waiting"
        out.append(
            {
                "id": key,
                "label": labels[key],
                "state": status,
                "detail": details[key],
                **({"count": len(experiments)} if key == "practice" else {}),
            }
        )
    return out


def controls(own, *, fixture):
    state = str(own.get("state") or "UNKNOWN")
    actions = []
    for action, label in (
        ("pause", "Pause"),
        ("resume", "Resume"),
        ("stop", "Stop"),
        ("reconcile", "Reconcile"),
    ):
        reason = None
        if fixture:
            reason = "A fixture runs nothing: controls are shown, not active."
        elif state in TERMINAL:
            reason = "This campaign is " + state + "; export still gives its record."
        elif action == "resume" and state not in {"PAUSED", "INTERRUPTED"}:
            reason = "Resume continues a paused or interrupted campaign."
        elif action == "pause" and state in {"PAUSED", "PAUSE_REQUESTED"}:
            reason = "Already paused."
        actions.append(
            {
                "action": action,
                "label": label,
                "operation": "resume" if action == "resume" else "halt",
                "available": reason is None,
                "reason": reason,
            }
        )
    return actions


def tiles(own, rows, now):
    usage = own.get("usage") if type(own.get("usage")) is dict else None
    started = own.get("started_unix")
    started = started if isinstance(started, (int, float)) else None
    active = str(own.get("state")) not in TERMINAL
    value = {
        "started_unix": started,
        "deadline_unix": own.get("deadline_unix")
        if isinstance(own.get("deadline_unix"), (int, float))
        else None,
        "now_unix": int(now),
        "elapsed_seconds": int(now - started) if started and active else None,
        "practice_runs": {
            "completed": len(own.get("experiments") or []),
            "attempted": own.get("attempted_experiments")
            if type(own.get("attempted_experiments")) is int
            else None,
        },
        "spend": None,
        "trials": None,
        "compute": {
            "lane": _str(own.get("compute"), 64),
            "backend": rows[-1]["backend"] if rows else None,
            "numerical_seconds": None,
        },
    }
    if usage is not None:
        reported = usage.get("reported") or {}
        reserved = usage.get("reserved") or {}
        uncertain = usage.get("uncertain") or {}
        budget = usage.get("budget") or {}
        ceilings = (
            budget.get("ceilings") if type(budget.get("ceilings")) is dict else budget
        )

        def used(key):
            return _int(reported.get(key)) + _int(uncertain.get(key))

        def ceiling(key):
            cap = ceilings.get(key) if type(ceilings) is dict else None
            return cap if type(cap) is int else None

        value["spend"] = {
            "used_nanodollars": used("provider_nanodollars"),
            "reserved_nanodollars": _int(reserved.get("provider_nanodollars")),
            "ceiling_nanodollars": ceiling("provider_nanodollars"),
            "basis": _str(usage.get("cost_basis"), 256),
            "payer": "You, to your own model provider. Carbon caps and bills nothing.",
        }
        value["trials"] = {
            "used": used("research_trials") + _int(reserved.get("research_trials")),
            "ceiling": ceiling("research_trials"),
        }
        value["compute"]["numerical_seconds"] = round(
            used("numerical_milliseconds") / 1000, 1
        )
    return value


def feed(own, notes):
    """The journal, newest first: what was posted and what was recorded."""
    entries = []
    for item in own.get("hypotheses") or []:
        entries.append(
            {
                "sequence": item.get("sequence"),
                "kind": "hypothesis",
                "via": "trial",
                "text": clean_text(item.get("hypothesis")),
                "detail": clean_text(item.get("expected_effect")),
            }
        )
    for item in own.get("decisions") or []:
        entries.append(
            {
                "sequence": item.get("sequence"),
                "kind": "decision",
                "via": "agent_or_controller",
                "text": clean_text(item.get("reason")) or "Decision recorded.",
                "detail": clean_text(item.get("evidence")),
            }
        )
    for item in own.get("capability_requests") or []:
        entries.append(
            {
                "sequence": item.get("sequence"),
                "kind": "capability_request",
                "via": "agent_or_miner",
                "text": clean_text(item.get("purpose") or item.get("reason"))
                or "Capability request.",
                "detail": "Grants nothing.",
            }
        )
    for item in own.get("refusals") or []:
        entries.append(
            {
                "sequence": item.get("sequence"),
                "kind": "refusal",
                "via": "controller",
                "text": (clean_text(item.get("operation"), 64) or "A request")
                + " refused: "
                + (clean_text(item.get("reason"), 256) or "no reason recorded"),
                "detail": clean_text(item.get("detail"), 512),
            }
        )
    for note in notes:
        body = note.get("body")
        kind, via, text = "notebook", "notebook", None
        if type(body) is dict and body.get("schema") == NOTE_SCHEMA:
            if body.get("note_kind") in NOTE_KINDS:
                kind = body["note_kind"]
            via, text = "carbon_note", clean_text(body.get("text"))
        elif type(body) is dict:
            text = clean_text(body.get("text"))
        elif type(body) is str:
            text = clean_text(body)
        entries.append(
            {
                "sequence": note.get("sequence"),
                "kind": kind,
                "via": via,
                "text": text or "A structured notebook entry; read it in the export.",
                "detail": None,
            }
        )
    entries = [e for e in entries if type(e["sequence"]) is int]
    entries.sort(key=lambda e: e["sequence"], reverse=True)
    for entry in entries:
        entry["untrusted"] = True
    outcomes = [
        {
            "epoch": item.get("epoch"),
            "status": _str(item.get("status"), 64),
            "selected_by": "miner" if item.get("selected_by") == "miner" else "agent",
            "reason": clean_text(item.get("reason"), 512),
            "untrusted": True,
        }
        for item in own.get("epoch_outcomes") or []
    ]
    return {
        "entries": entries[:FEED_MAX],
        "total": len(entries),
        "epoch_outcomes": outcomes,
        "basis": (
            "Journal text is recorded by you, your agent or Carbon's agent. It "
            "is untrusted data: shown as text, never run, never instructions."
        ),
    }


def events(own):
    ops = [
        {
            "id": _str(op.get("id")),
            "phase": _str(op.get("phase"), 64),
            "state": _str(op.get("state"), 64),
        }
        for op in own.get("operations") or []
        if type(op) is dict
    ]
    return {"operations": ops[-EVENTS_MAX:], "total": len(ops)}


def outcomes(own, view, mode):
    """DEVELOPMENT outcomes, through the campaign's frozen feedback mode."""
    fields = view.feedback_fields(mode) if view is not None else None
    found = []
    for item in own.get("final_results") or []:
        status = _str(item.get("status"), 64)
        entry = {
            "epoch": item.get("epoch"),
            "status": status,
            "mode": "DEVELOPMENT_EVALUATION",
        }
        result = item.get("result") if type(item.get("result")) is dict else None
        if status == "VALIDATOR_OUTCOME" and result is not None:
            shown = {"state": _str(result.get("state"), 64)}
            if fields is not None:
                outcome_fields, screening_fields = fields
                for key in ("submission_id", "evidence", "nominated", "waiting"):
                    if key in outcome_fields and key in result:
                        shown[key] = result[key]
                if "finals" in outcome_fields and type(result.get("finals")) is list:
                    shown["finals"] = result["finals"]
                screening = result.get("screening")
                # Each rung names its own screening fields (the ladder).
                if type(screening) is dict:
                    shown["screening"] = {
                        k: screening[k] for k in screening_fields if k in screening
                    }
                shown["feedback_mode"] = mode
            else:
                shown["feedback_mode"] = mode
                shown["withheld"] = (
                    "this feedback mode is unknown here; only the state is shown"
                )
            entry["result"] = {**shown, "qualification": False, "reward": False}
        elif status == "VERIFIED_SOURCE" and result is not None:
            entry["result"] = {
                "disposition": _str(result.get("disposition"), 64),
                "accepted_development_improvement": result.get(
                    "accepted_development_improvement"
                )
                if type(result.get("accepted_development_improvement")) is bool
                else None,
                "qualification": False,
                "reward": False,
            }
        found.append(entry)
    return found


def candidates(own):
    return [
        {
            "epoch": item.get("epoch"),
            "strategy": item.get("strategy")
            if type(item.get("strategy")) is dict
            else None,
            "strategy_hash": _str(item.get("strategy_hash")),
            "reason": clean_text(item.get("reason"), 1024),
            "used_feedback": item.get("used_feedback")
            if type(item.get("used_feedback")) is bool
            else None,
            "final_evidence": False,
        }
        for item in own.get("candidate_freezes") or []
    ]


def per_case_section(view, rows, predictions, practice_case=None, experiment=None):
    """Predicted-vs-reference curves for one public PRACTICE case (RSURF-D2)."""
    from scripts.dev.miner_launchpad.controller import Rejected

    if view is None:
        return {
            "status": "UNAVAILABLE",
            "reason": "no_research_view_for_this_challenge",
        }
    if not view.per_case.allowed:
        return {
            "status": "WITHHELD",
            "reason": "not_disclosed",
            "basis": view.per_case.basis,
        }
    if view.case_ids is None or view.reference is None:
        return {"status": "UNAVAILABLE", "reason": "no_public_practice_references"}
    if not rows:
        return {
            "status": "UNAVAILABLE",
            "reason": "no_practice_run_yet",
            "basis": view.per_case.basis,
        }
    ids = [r["id"] for r in rows]
    if experiment is not None and experiment not in ids:
        raise Rejected("unknown_experiment", 404)
    at = ids.index(experiment) if experiment is not None else len(ids) - 1
    current, previous = rows[at], rows[at - 1] if at > 0 else None
    mine, reason = predictions(current["id"])
    if mine is None:
        return {
            "status": "UNAVAILABLE",
            "reason": reason,
            "experiment": current["id"],
            "basis": view.per_case.basis,
        }
    before = predictions(previous["id"])[0] if previous is not None else None
    case_ids = [str(c) for c in view.case_ids()][:1000]
    if practice_case is not None and practice_case not in case_ids:
        raise Rejected("unknown_practice_case", 404)
    case = practice_case if practice_case is not None else case_ids[0]
    reference = view.reference(case) or {}
    outputs = reference.get("outputs") or {}
    predicted = mine.get(case) if type(mine.get(case)) is dict else {}
    earlier = (
        before.get(case)
        if type(before) is dict and type(before.get(case)) is dict
        else None
    )
    drawn = []
    for output in view.outputs:
        series = [
            ("Reference (public practice)", "reference", outputs.get(output.name)),
            ("Run " + str(current["index"]), "current", predicted.get(output.name)),
        ]
        if earlier is not None:
            series.append(
                ("Run " + str(previous["index"]), "previous", earlier.get(output.name))
            )
        drawn.append(
            validate_chart(output_chart(output, series, chart_id="case_" + output.name))
        )
    return {
        "status": "AVAILABLE",
        "basis": view.per_case.basis,
        "population": "public PRACTICE",
        "experiment": current["id"],
        "experiment_index": current["index"],
        "previous_experiment": previous["id"]
        if previous and earlier is not None
        else None,
        "case_ids": case_ids,
        "selected": {
            "case_id": case,
            "inputs": {
                str(k): finite(v) for k, v in (reference.get("inputs") or {}).items()
            },
            "charts": drawn,
        },
        "computed_on": "this machine, from your own practice predictions",
    }


def build(
    own,
    *,
    view,
    contract,
    notes,
    feedback_mode,
    predictions,
    practice_case=None,
    experiment=None,
    now=None,
    fixture=False,
):
    """The campaign view document. Every field is named here."""
    from carbon.chain.models import CARBON_NETUID

    now = time.time() if now is None else now
    rows = experiment_rows(own, view)
    shown = rows[-EXPERIMENTS_MAX:]
    challenge = own.get("challenge") if type(own.get("challenge")) is dict else None
    document = {
        "schema": SCHEMA,
        "campaign": {
            "id": _str(own.get("id")),
            "state": _str(own.get("state"), 64),
            "selects": own.get("selects")
            if own.get("selects") in ("miner", "agent")
            else None,
            "agent": _str(own.get("agent"), 64),
            "model": _str(own.get("reasoning"), 128),
            "challenge": {
                "id": _str(challenge.get("id")),
                "version": _str(challenge.get("version"), 32),
                "title": (contract or {}).get("challenge", {}).get("title"),
            }
            if challenge
            else None,
            "admission": _str(own.get("admission"), 64),
            "runtime_revision": _str(own.get("runtime_revision")),
            "execution_label": _str(own.get("execution_label"), 128),
        },
        "labels": {
            **LABELS,
            "netuid": CARBON_NETUID,
            "evidence": "SYNTHETIC_FIXTURE"
            if fixture
            else "PRACTICE_NOT_QUALIFICATION",
        },
        "fixture": bool(fixture),
        "stages": stages(own),
        "controls": controls(own, fixture=fixture),
        "tiles": tiles(own, rows, now),
        "current_operation": next(
            (
                {"id": _str(op.get("id")), "phase": _str(op.get("phase"), 64)}
                for op in reversed(own.get("operations") or [])
                if type(op) is dict and op.get("state") == "RESERVED"
            ),
            None,
        ),
        "hypothesis": clean_text(
            (own.get("current_hypothesis") or {}).get("hypothesis")
        ),
        "experiments": {"rows": shown, "total": len(rows)},
        "comparison": comparison(rows, view),
        "charts": charts(rows, own, view),
        "learning_curve": learning_curve_status(own, view),
        "per_case": per_case_section(
            view, rows, predictions, practice_case, experiment
        ),
        "journal": feed(own, notes),
        "candidates": candidates(own),
        "journey": {
            key: (own.get("journey") or {}).get(key)
            for key in (
                "submitted_epochs",
                "final_exams_remaining",
                "frozen_awaiting_submission",
            )
        }
        if type(own.get("journey")) is dict
        else None,
        "outcomes": outcomes(own, view, feedback_mode),
        "events": events(own),
        "declaration": view.document() if view is not None else None,
        "contract": contract,
        "non_claims": list(NON_CLAIMS),
        "official_eligible": False,
        "qualification": False,
        "reward": False,
    }
    return json.loads(json.dumps(document, allow_nan=False))


# ---- The ledger door: a campaign on this machine.


def _ledger_facts(root):
    from carbon.development_session.profile import digest
    from carbon.development_session.research_ledger import CampaignLedger

    empty = {"feedback_mode": "FULL", "notes": [], "workers": {}, "practice": {}}
    if not (root / "campaign.sqlite3").is_file():
        return empty
    ledger = CampaignLedger(root)
    with ledger.db() as db:
        frozen = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    if frozen is None:
        return empty
    manifest = json.loads(frozen[0])
    owner = manifest["owner"]
    status = ledger.status(owner=owner)
    workers = {}
    for op in status["operations"]:
        result = op.get("result") or {}
        if (
            result.get("schema") == "carbon.autoresearch.worker-result.v1"
            and type(result.get("operation")) is str
            and type(result.get("files")) is dict
        ):
            workers[result["operation"]] = result["files"]
    practice = {}
    with ledger.db() as db:
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='research_results' AND type='table'"
        ).fetchone():
            for task, body, pin in db.execute(
                "SELECT task,body,digest FROM research_results WHERE owner=?", (owner,)
            ):
                if digest(body) != pin:
                    raise ValueError("research result changed")
                worker = json.loads(body).get("worker")
                if type(worker) is dict and type(worker.get("operation")) is str:
                    practice[task] = worker["operation"]
    return {
        "feedback_mode": manifest.get("feedback_mode", "FULL"),
        "notes": [n for n in status["notes"] if n["kind"] == "notebook"],
        "workers": workers,
        "practice": practice,
        "manifest": manifest,
    }


@functools.lru_cache(maxsize=4)
def _read_predictions(path, size, mtime_ns, expected):
    from carbon.development_session.profile import digest

    body = Path(path).read_bytes()
    if len(body) != size or digest(body) != expected:
        return None
    value = json.loads(body)
    return value if type(value) is dict else None


def verified_predictions(root, view, facts, task):
    """The miner's own practice predictions for one trial, or (None, reason).
    Read only when the file's digest equals the ledger's worker record."""
    operation = facts["practice"].get(task)
    files = facts["workers"].get(operation) if operation else None
    if view is None or not operation or files is None:
        return None, "no_worker_record"
    expected = files.get(view.prediction_file)
    if type(expected) is not str or not re.fullmatch(
        r"[A-Za-z0-9._-]{1,128}", operation
    ):
        return None, "no_worker_record"
    path = root / operation / "snapshot" / view.prediction_file
    try:
        if path.is_symlink() or not path.is_file():
            return None, "predictions_missing"
        if not path.resolve().is_relative_to(root.resolve()):
            return None, "predictions_unverified"
        stat = path.stat()
        if not 0 < stat.st_size <= PREDICTIONS_MAX_BYTES:
            return None, "predictions_unverified"
        value = _read_predictions(str(path), stat.st_size, stat.st_mtime_ns, expected)
    except (OSError, ValueError):
        return None, "predictions_unverified"
    if value is None:
        return None, "predictions_digest_differs"
    return value, None


def ledger_view(host, admitted, request):
    """`campaign_view` for a campaign on this machine (`RunnerAdapter`)."""
    from carbon.challenge_registry.campaigns import campaign_for

    identity = admitted.campaign["id"]
    own = host.get(identity)
    root = Path(admitted.campaign["root"])
    facts = _ledger_facts(root)
    challenge = own.get("challenge")
    view = research_view_for(challenge)
    try:
        offered = campaign_for(challenge).feedback_modes if challenge else ()
    except Exception:  # noqa: BLE001 - the contract view shows what is known
        offered = ()
    return build(
        own,
        view=view,
        contract=contract_section(challenge, facts["feedback_mode"], offered),
        notes=facts["notes"],
        feedback_mode=facts["feedback_mode"],
        predictions=lambda task: verified_predictions(root, view, facts, task),
        practice_case=request.get("practice_case"),
        experiment=request.get("experiment"),
    )


def post_note(host, admitted, request):
    """`note`: one journal entry through the existing journal path (RSURF-D5)."""
    from carbon.development_session.research_ledger import CampaignLedger
    from scripts.dev.miner_launchpad.controller import Rejected

    kind = request["note_kind"]
    if kind not in NOTE_KINDS:
        raise Rejected("note_kind_unknown")
    text = note_text(request["note"])
    if admitted.campaign["kind"] != "product":
        raise Rejected("retired_grant_campaign", 409)
    root = Path(admitted.campaign["root"])
    if not (root / "campaign.sqlite3").is_file():
        raise Rejected("campaign_journal_not_ready", 409)
    ledger = CampaignLedger(root)
    with ledger.db() as db:
        frozen = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    if frozen is None:
        raise Rejected("campaign_journal_not_ready", 409)
    try:
        ledger.note(
            owner=json.loads(frozen[0])["owner"],
            kind="notebook",
            body={"schema": NOTE_SCHEMA, "note_kind": kind, "text": text},
        )
    except ValueError:
        raise Rejected("note_not_retained", 409) from None
    return {
        "posted": True,
        "note_kind": kind,
        "characters": len(text),
        "shown_as": "untrusted text",
    }
