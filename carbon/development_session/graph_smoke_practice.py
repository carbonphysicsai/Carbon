"""Smoke practice for a direct GRAPH recipe: the same rule as every other smoke.

The Challenge-neutral rule is `carbon.development_session.smoke_practice`:
practice-only, never official, never grades a sealed exam, never counts toward
an exam slot, and the result is typed SMOKE (provenance, outcome, no score).
This module is only the graph recipe's truncation and its pass rule.

What it caps: the training steps, through the recipe's own
`procedure.configuration.training.steps` (and each ensemble member's own
`training.steps` where the adapter has members), at the same engineering cap
every other recipe's smoke practice uses (`carbon.battery.smoke_practice.
SMOKE_STEPS`), split evenly over the members as that rule splits it. The graph
itself, its constants and the TRAIN rows are untouched: a fixed-batch trainer's
cost is steps times batch, not the row count, and no smoke practice has ever
capped rows, so no row cap value exists to reuse and none is invented here.
The query side is not truncated either: the practice grades the same exposed
bank rows as a full practice, and a result is only judged finite and complete.

Served adapters: graph route v1 (F08 1.4, F02 2.3) and graph route v2. Any
other graph adapter, and any catalog recipe, refuses smoke practice
(`smoke_practice_unavailable`) rather than run untruncated.
"""

from __future__ import annotations

import json
import math

from .smoke_practice import SmokeHook, SmokeUnavailable

FIELD = "procedure.configuration.training.steps"


def _is_steps(value):
    return type(value) is int


def _served_module(strategy):
    """The v1 or v2 graph adapter serving `strategy`, or SmokeUnavailable."""
    from . import graph_adapters, physical_graph_adapter, physical_graph_adapter_v2

    challenge = strategy.get("challenge") if type(strategy) is dict else None
    source = strategy.get("source") if type(strategy) is dict else None
    if (
        type(challenge) is not dict
        or type(source) is not dict
        or source.get("kind") != "graph"
        or type(challenge.get("id")) is not str
        or type(challenge.get("version")) is not str
    ):
        raise SmokeUnavailable()
    module = graph_adapters.for_version(challenge["id"], challenge["version"])
    if module not in (physical_graph_adapter, physical_graph_adapter_v2):
        raise SmokeUnavailable()
    return module


def _effective(config, module, default):
    """The training steps of each member (one for a single model), or None when
    a value is not an integer: the practice then refuses it by its own code."""
    base = (config.get("training") or {}).get("steps", default)
    if not _is_steps(base):
        return None, None
    ensemble = config.get("ensemble") if module.__name__.endswith("_v2") else None
    members = ensemble.get("members") if type(ensemble) is dict else None
    if type(members) is not list or not members:
        return base, [base]
    steps = []
    for member in members:
        own = member.get("training") if type(member) is dict else None
        value = own.get("steps", base) if type(own) is dict else base
        if not _is_steps(value):
            return None, None
        steps.append(value)
    return base, steps


def truncate(strategy, compile=None):
    """`strategy` with its training steps capped at the smoke cap, and the
    record of the cut. `compile` is unused: a graph recipe has no compile."""
    from carbon.battery.smoke_practice import SMOKE_STEPS

    module = _served_module(strategy)
    row = module.TRAIN_SURFACES["steps"]
    low, default = row[1], row[-1]
    procedure = strategy.get("procedure")
    config = procedure.get("configuration") if type(procedure) is dict else None
    if type(config) is not dict:
        return strategy, {"field": FIELD, "steps_requested": None, "steps_run": None}
    base, steps = _effective(config, module, default)
    if steps is None:
        return strategy, {"field": FIELD, "steps_requested": None, "steps_run": None}
    share = max(SMOKE_STEPS // len(steps), low)
    requested, run = sum(steps), sum(min(s, share) for s in steps)
    if run >= requested:
        return strategy, {
            "field": FIELD,
            "steps_requested": requested,
            "steps_run": requested,
        }
    value = json.loads(json.dumps(strategy))
    cut = value["procedure"]["configuration"]
    training = cut.get("training")
    if type(training) is not dict:
        training = cut["training"] = {}
    if base > share:
        training["steps"] = share
    for member in (cut.get("ensemble") or {}).get("members", []):
        own = member.get("training") if type(member) is dict else None
        if type(own) is dict and own.get("steps", 0) > share:
            own["steps"] = share
    # Fail closed: the cut must resolve to exactly the steps recorded.
    again = _effective(cut, module, default)[1]
    if again is None or sum(again) != run:
        raise ValueError("smoke truncation did not take")
    return value, {"field": FIELD, "steps_requested": requested, "steps_run": run}


def _error_keys():
    """Each family's own finite-result key in its practice summary: F08 / F02
    (`direct_campaign.practice.summary`) and Battery (`catalog_version.practice_summary`)
    write ``aggregate_error``; Motor and Cooling (`exam.aggregate`) write ``score``, the
    same mean error (None when no case was scorable). No new value."""
    from carbon.challenge_kit import served_versions as sv

    return {
        sv.F08: "aggregate_error",
        sv.F02: "aggregate_error",
        sv.BATTERY: "aggregate_error",
        sv.MOTOR: "score",
        sv.COOLING: "score",
    }


def failure(result):
    """None when a direct graph practice completed with its rows predicted and
    a finite error; else a closed code. Reads the result only. The error is read
    under the family's own key (`_error_keys`); a family with no registered key
    fails closed."""
    summary = result.get("summary")
    if type(summary) is not dict:
        return "outputs_missing"
    cases = summary.get("n_cases")
    fit = result.get("fit")
    if (
        type(cases) is not int
        or cases <= 0
        or type(fit) is not dict
        or type(fit.get("state_digest")) is not str
    ):
        return "outputs_missing"
    challenge = result.get("challenge")
    key = _error_keys().get(challenge.get("id") if type(challenge) is dict else None)
    if key is None:
        return "error_key_unregistered"
    error = summary.get(key)
    if type(error) not in (int, float) or not math.isfinite(error):
        return "outputs_not_finite"
    return None


def hook():
    return SmokeHook(truncate=truncate, failure=failure)
