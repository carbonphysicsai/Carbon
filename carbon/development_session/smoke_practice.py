"""A bounded smoke practice: proof that a recipe runs, which the freeze accepts.

LAUNCHPAD-SMOKE-PRACTICE-01. The practice gate exists to prove a recipe is
runnable, not to train it fully. A recipe too heavy to finish its full
practice inside the practice budget (600 s on CPU) could otherwise never be
frozen, and the budget is not scaled with recipe size: that is a cost and an
abuse risk.

So a miner may ask for a SMOKE practice of a recipe. One rule for every
Challenge and level:

- the exact recipe runs through the same practice callback as a full
  practice, with its training steps truncated by its Challenge's hook so it
  fits the existing budget. A Challenge without the hook refuses smoke
  practice (`smoke_practice_unavailable`);
- the result records the ORIGINAL recipe as `recipe`, the truncation beside
  it (`smoke`), its runtime, `outcome` SMOKE and `status` PASSED or FAILED;
- it carries no score, metrics or diagnostics: the full practice result is
  discarded in memory, and any trial file the practice put in the miner's
  workspace is replaced by the smoke result (invariant 12: the free loop
  stays intentionally incomplete);
- the freeze accepts a full practice or a PASSED smoke practice of the same
  strategy (`research_campaign.trial_supports_selection`). PASSED means the
  practice completed with finite outputs and no failure, as the Challenge's
  hook judges its own result.

Submission and rebuild are unchanged: validators rebuild the full recipe.
Smoke only unlocks the freeze.

How the mode reaches the practice: the campaign's own practice path
(`research_campaign.practice_recipe`) records a smoke request for its trial
identity before it starts the research task; the executor reads it back by
the task's idempotency key. The research protocol's task spec is unchanged,
and an agent's own research tools cannot ask for one.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from .profile import canonical, digest

#: The request modes of a practice. FULL is the default and is unchanged.
FULL, SMOKE = "full", "smoke"
MODES = (FULL, SMOKE)
#: The provenance of a smoke practice result. Deliberately not one of
#: `research_campaign.practice_provenances()`: nothing that counts or reads
#: practice scores ever reads a smoke result as one.
SMOKE_PROVENANCE = "SMOKE_PUBLIC_PRACTICE"
SMOKE_RESULT_SCHEMA = "carbon.autoresearch.smoke-practice-result.v1"
SMOKE_REQUEST_SCHEMA = "carbon.autoresearch.smoke-practice-request.v1"
#: The outcome label every smoke result carries.
OUTCOME = "SMOKE"
PASSED, FAILED = "PASSED", "FAILED"
#: Closed refusal codes.
UNAVAILABLE = "smoke_practice_unavailable"
MODE_INVALID = "practice_mode_invalid"
#: The step a full practice that ended FAILED_INFRA at its time budget names
#: as its last refusal: its next step is a smoke practice of the same recipe.
TIME_BUDGET_REACHED = "practice_time_budget_reached"
#: How close to its time budget a failed full practice must have run to be
#: read as having reached it. The carrier stops the worker 45 s before the
#: budget; an engineering margin, not a scientific value.
BUDGET_MARGIN_SECONDS = 60
#: The result fields a smoke result may hold: nothing else is ever written.
RESULT_FIELDS = frozenset(
    {
        "schema",
        "provenance",
        "outcome",
        "status",
        "failure",
        "recipe",
        "runtime_seconds",
        "smoke",
        "construction_level",
        "adaptively_seen",
        "final_exam",
        "official_eligible",
        "scientific_qualification",
    }
)
_TABLE = (
    "CREATE TABLE IF NOT EXISTS smoke_practice_requests(owner TEXT NOT NULL,"
    "identity TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,"
    "PRIMARY KEY(owner,identity))"
)


class SmokeUnavailable(ValueError):
    """A smoke practice refused by its closed code."""

    def __init__(self, code=UNAVAILABLE):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SmokeHook:
    """A Challenge's smoke practice: how its recipe is truncated and how its
    own practice result is judged. Registered on its `ChallengeCampaign`
    (`smoke_practice`); a Challenge without one refuses smoke."""

    #: (strategy, compile) -> (truncated strategy, {"field", "steps_requested",
    #: "steps_run"}). `compile` is the campaign's practice compile (at its
    #: construction level, if any); the truncated strategy must compile there.
    truncate: Callable
    #: (practice result) -> None when the practice completed with finite
    #: outputs and no failure, else a closed failure code. Reads the result
    #: only; nothing it reads is disclosed.
    failure: Callable


def mode_of(value):
    """A practice request's mode: FULL when omitted; refused when not one."""
    if value is None:
        return FULL
    if value not in MODES:
        raise SmokeUnavailable(MODE_INVALID)
    return value


def hook_of(campaign):
    """The campaign's smoke hook, or `smoke_practice_unavailable`."""
    build = getattr(campaign, "smoke_practice", None)
    hook = build() if callable(build) else None
    if type(hook) is not SmokeHook:
        raise SmokeUnavailable()
    return hook


def _resolve(challenge):
    from carbon.challenge_registry.campaigns import campaign_for

    return campaign_for(challenge)


#: The campaign for a recorded `{id, version}`: the registry's, exactly.
#: Tests replace it with a fixture campaign.
RESOLVE = _resolve


def record_request(ledger, owner, identity, strategy, challenge):
    """Record that the practice under `identity` is a smoke practice of
    `strategy`, for `challenge`. Written once; the same request again is a
    no-op and another under the same identity is refused."""
    body = canonical(
        {
            "schema": SMOKE_REQUEST_SCHEMA,
            "mode": SMOKE,
            "challenge": challenge,
            "strategy_digest": digest(canonical(strategy)),
        }
    )
    with ledger.db() as db:
        db.execute(_TABLE)
        prior = db.execute(
            "SELECT body FROM smoke_practice_requests WHERE owner=? AND identity=?",
            (owner, identity),
        ).fetchone()
        if prior is not None:
            if prior[0] != body:
                raise ValueError("smoke practice request replay conflict")
            return
        db.execute(
            "INSERT INTO smoke_practice_requests VALUES(?,?,?,?)",
            (owner, identity, body, digest(body)),
        )


def requested(ledger, owner, identity):
    """The smoke request recorded for `identity`, or None for a full
    practice. A record that changed is refused, never read as full."""
    with ledger.db() as db:
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='smoke_practice_requests' "
            "AND type='table'"
        ).fetchone():
            return None
        row = db.execute(
            "SELECT body,digest FROM smoke_practice_requests "
            "WHERE owner=? AND identity=?",
            (owner, identity),
        ).fetchone()
    if row is None:
        return None
    if digest(row[0]) != row[1]:
        raise ValueError("smoke practice request changed")
    value = json.loads(row[0])
    if value.get("schema") != SMOKE_REQUEST_SCHEMA or value.get("mode") != SMOKE:
        raise ValueError("smoke practice request shape differs")
    return value


def _trial_prefix(identity):
    # Every Challenge's practice names its trial file so (`trial-` and the
    # identity's digest), whatever follows.
    return "trial-" + digest(identity.encode())[7:23] + "-"


def run(practice, identity, strategy, request, *, workspace):
    """One smoke practice of `strategy`: its Challenge's truncation, the
    campaign's own practice callback, and the smoke result. Raises as the
    practice raises: an infrastructure failure stays one, never a FAILED
    smoke result."""
    if request.get("strategy_digest") != digest(canonical(strategy)):
        raise ValueError("smoke practice request names another recipe")
    hook = hook_of(RESOLVE(request.get("challenge")))
    truncated, cut = hook.truncate(strategy, practice.compile)
    smoke = _smoke_record(cut)
    before = {item["name"]: item["digest"] for item in workspace.inventory()}
    started = time.monotonic()
    full = practice(identity, truncated)
    runtime = round(time.monotonic() - started, 1)
    failure = hook.failure(full) if type(full) is dict else "result_missing"
    if failure is not None and (type(failure) is not str or not failure):
        failure = "practice_failed"
    result = {
        "schema": SMOKE_RESULT_SCHEMA,
        "provenance": SMOKE_PROVENANCE,
        "outcome": OUTCOME,
        "status": PASSED if failure is None else FAILED,
        "failure": failure,
        # The ORIGINAL recipe: the one the freeze compares and the validator
        # rebuilds in full.
        "recipe": strategy,
        "runtime_seconds": runtime,
        "smoke": smoke,
        "adaptively_seen": True,
        "final_exam": False,
        "official_eligible": False,
        "scientific_qualification": False,
    }
    label = full.get("construction_level") if type(full) is dict else None
    if type(label) is dict:
        result["construction_level"] = label
    _replace_trial_files(workspace, identity, before, result)
    return result


def _smoke_record(cut):
    if type(cut) is not dict:
        raise ValueError("smoke truncation record required")
    field = cut.get("field")
    requested_steps, run_steps = cut.get("steps_requested"), cut.get("steps_run")
    if type(field) is str and requested_steps is None and run_steps is None:
        # A recipe with no training steps runs as it is.
        return {
            "field": field,
            "steps_requested": None,
            "steps_run": None,
            "truncated": False,
        }
    if (
        type(field) is not str
        or type(requested_steps) is not int
        or type(run_steps) is not int
        or not 0 < run_steps <= requested_steps
    ):
        raise ValueError("smoke truncation record differs")
    return {
        "field": field,
        "steps_requested": requested_steps,
        "steps_run": run_steps,
        "truncated": run_steps < requested_steps,
    }


def _replace_trial_files(workspace, identity, before, result):
    """Whatever trial file this practice put in the miner's workspace now
    holds the smoke result: the full result it held is never readable there."""
    body = canonical(result)
    prefix = _trial_prefix(identity)
    for item in workspace.inventory():
        name = item["name"]
        if name.startswith(prefix) and before.get(name) != item["digest"]:
            workspace.put(name, body, expected_digest=item["digest"])


def is_passed(result):
    """Whether a retained result is a PASSED smoke practice."""
    return (
        type(result) is dict
        and result.get("schema") == SMOKE_RESULT_SCHEMA
        and result.get("provenance") == SMOKE_PROVENANCE
        and result.get("outcome") == OUTCOME
        and result.get("status") == PASSED
        and result.get("failure") is None
    )


def is_smoke(result):
    return type(result) is dict and result.get("provenance") == SMOKE_PROVENANCE


def public_view(task, result):
    """A smoke result as observe lists it: its own allow-listed fields."""
    return {"id": task, **{k: result[k] for k in sorted(RESULT_FIELDS) if k in result}}


def reached_time_budget(answer, elapsed, seconds):
    """Whether a full practice's answer is FAILED_INFRA after running to
    within `BUDGET_MARGIN_SECONDS` of its `seconds` budget."""
    if type(seconds) not in (int, float) or not math.isfinite(seconds):
        return False
    task = answer.get("terminal_task") if type(answer) is dict else None
    state = task.get("state") if type(task) is dict else None
    return state == "FAILED_INFRA" and elapsed >= seconds - BUDGET_MARGIN_SECONDS
