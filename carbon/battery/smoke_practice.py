"""Battery's smoke practice hook (LAUNCHPAD-SMOKE-PRACTICE-01).

The Challenge-neutral rule is `carbon.development_session.smoke_practice`.
What is battery's own: which field its training loop reads for the step
budget (`parameters.steps`, split evenly across ensemble members), how far a
smoke practice truncates it, and what a battery practice result must show to
pass (every PRACTICE case predicted, finite outputs, a finite loss).

Nothing here edits a recipe module or the practice: the truncation is applied
to a copy of the strategy before the campaign's own practice compiles it,
and the digest-pinned battery modules (`research.implementation_files`) are
unchanged.
"""

from __future__ import annotations

import json

from carbon.development_session.smoke_practice import SmokeHook

#: The most training steps a smoke practice runs, summed over ensemble
#: members as `parameters.steps` is. An ENGINEERING DEFAULT, not a
#: scientific value: chosen so a heavy recipe's smoke practice fits the 600 s
#: CPU practice budget with a wide margin (see the PR that introduced it for
#: the measurement). A recipe at or under it runs its own steps.
SMOKE_STEPS = 2000
FIELD = "parameters.steps"
#: The fewest steps each member trains; `compile.MIN_MEMBER_STEPS`, restated
#: so this module imports no recipe code. A test pins the two equal.
MIN_MEMBER_STEPS = 16


def _steps_run(settings):
    requested = settings["steps"]
    members = max(1, int(settings.get("ensemble_members", 1)))
    polish = int(settings.get("polish_steps", 0) or 0)
    warmup = int(settings.get("warmup_steps", 0) or 0)
    # The compile's own rules on each member's share: at least
    # MIN_MEMBER_STEPS before polish, and more than its warmup.
    least = max(MIN_MEMBER_STEPS, polish + MIN_MEMBER_STEPS)
    if warmup:
        least = max(least, polish + warmup + 1)
    member = min(requested // members, max(SMOKE_STEPS // members, least))
    return requested, member * members


def truncate(strategy, compile):
    """`strategy` with its training steps capped at `SMOKE_STEPS`, and the
    record of the cut. A family with no training steps runs as it is."""
    _compiled, recipe = compile(strategy)
    settings = recipe.settings
    if "steps" not in settings:
        return strategy, {"field": FIELD, "steps_requested": None, "steps_run": None}
    requested, run = _steps_run(settings)
    if run >= requested:
        return strategy, {
            "field": FIELD,
            "steps_requested": requested,
            "steps_run": requested,
        }
    value = json.loads(json.dumps(strategy))
    value.setdefault("parameters", {})["steps"] = run
    # Fail closed: the cut must compile, here, to exactly that many steps.
    _compiled, cut = compile(value)
    if cut.settings.get("steps") != run or cut.family != recipe.family:
        raise ValueError("smoke truncation did not compile as cut")
    return value, {"field": FIELD, "steps_requested": requested, "steps_run": run}


def failure(result):
    """None when a battery practice completed with every PRACTICE case
    predicted, finite outputs and a finite loss; else a closed code."""
    summary = result.get("summary")
    if type(summary) is not dict:
        return "outputs_missing"
    cases = summary.get("n_cases")
    if type(cases) is not int or cases <= 0 or summary.get("n_failed_infra") != 0:
        return "outputs_missing"
    gates = summary.get("gate_failures")
    if type(gates) is not dict or gates.get("schema_finite", 0):
        return "outputs_not_finite"
    fit = result.get("fit")
    if type(fit) is not dict:
        return "outputs_missing"
    # Practice feedback writes a non-finite value as None.
    if "final_loss" in fit and fit["final_loss"] is None:
        return "outputs_not_finite"
    return None


def hook():
    return SmokeHook(truncate=truncate, failure=failure)
