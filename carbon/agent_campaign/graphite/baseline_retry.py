"""When a session's failed baseline is run once more (GRAPHITE-POD-LOGS-RETRY-01).

One flaky baseline pod used to leave every later scored proposal of the
session `NO_BASELINE`, never promotable. The retry rule is a **versioned,
registered policy** in the style of `pod_outcome`: a data document in
`baseline_policies/`, pinned by digest in `baseline_policies/registry.json`.
Changing it is a new document and a registry entry, never an edit here.

It applies to the **session's baseline only**: Carbon's own recipe
(`ChallengeScoring.baseline_strategy`, registered in the session's brief),
with Carbon's own seed, run by Carbon before any proposal's pod. No agent
authors, chooses or seeds it, so a retry of it cannot be bought by a
proposal. An agent proposal's outcome is typed by `pod_outcome` (#573)
unchanged and is never retried here.

What no policy may change (checked when it loads; it fails closed):
- it applies to the session's baseline and to nothing else;
- `FAILED_INFRA` is retried only for listed reasons, and never a launch the
  pod launch gate refused, one whose outcome is unknown, or a process death;
- the only candidate-attributed outcome that may be retried is the
  baseline's program crash (`CANDIDATE_FAILED`, `program`; the owner's
  direction of 2026-10-04); `CANDIDATE_RESOURCE_EXCEEDED` never is;
- at most one retry;
- the retry is held to every existing limit: the session's pod limit, the
  run's money cap (tokens and pods together), the remaining elapsed time and
  the pod launch gate.

The decision itself is `decide`: a pure function of the failed baseline's
record and what the run can still afford. `Experiment` records it once,
write-once, in the run's records, the pod ledger and the session's events.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .pod_outcome import CANDIDATE_FAILED, CANDIDATE_RESOURCE_EXCEEDED, FAILED_INFRA

POLICY_DIR = Path(__file__).with_name("baseline_policies")
POLICY_SCHEMA = "carbon.graphite.baseline-retry-policy.v1"
REGISTRY_SCHEMA = "carbon.graphite.baseline-retry-registry.v1"
DECISION_SCHEMA = "carbon.graphite.phase3.baseline-retry-decision.v1"
#: The session baseline's proposal id and kind (`Experiment.run`).
BASELINE_ID = "baseline"
#: The retried baseline's proposal id.
RETRY_ID = "baseline-retry-1"
#: What a policy may apply to: the session's baseline, nothing else.
APPLIES_TO = "session_baseline"
_KEYS = {
    "schema",
    "version",
    "authority",
    "status",
    "applies_to",
    "max_retries",
    "retry_on_status",
    "retry_on_reasons",
    "candidate_retry_on",
    "never_on_status",
    "seed",
    "pods_required",
    "limits",
    "earlier_scored_results",
    "notes",
}
#: The limits this module enforces; a policy naming fewer or others is refused.
LIMITS = frozenset(
    {
        "pod_launch_gate",
        "remaining_elapsed_time",
        "run_cap_tokens_plus_pods",
        "session_pod_limit",
    }
)
#: Outcomes that are not a pod failing: never retried by any version.
NEVER_REASONS = frozenset(
    {"launch_refused", "launch_unresolved", "interrupted_not_rerun"}
)
#: The only candidate-attributed outcomes any version may retry: the
#: baseline's program crash (owner, 2026-10-04: "Yes, retry baseline crashes").
ALLOWED_CANDIDATE_RETRIES = frozenset({(CANDIDATE_FAILED, "program")})
#: Statuses no version may retry.
NEVER_STATUSES = frozenset({CANDIDATE_RESOURCE_EXCEEDED})
SEEDS = frozenset({"same_as_failed_baseline"})
EARLIER = frozenset({"not_recompared"})

RETRIED = "retried"
#: Reason codes a decision not to retry carries.
NOT_THE_BASELINE = "not_retried:not_the_session_baseline"
NOT_RETRYABLE_STATUS = "not_retried:status_not_retryable"
NOT_RETRYABLE_REASON = "not_retried:reason_not_retryable"
CANDIDATE_ATTRIBUTED = "not_retried:candidate_attributed"
ALREADY_RETRIED = "not_retried:retry_already_used"
NO_TIME = "not_retried:retry_cannot_fit_remaining_time"
#: The baseline already had its extra pod from an environment relaunch
#: (`pod-attribution-v2`, GRAPHITE-POD-GPU-PROBE-01): the two rules together
#: give the session's baseline at most one extra pod.
ENVIRONMENT_RELAUNCH_USED = "not_retried:environment_relaunch_used"


class PolicyRefused(ValueError):
    """A baseline-retry policy that is unregistered, altered or unsafe."""


def _pairs(value):
    if type(value) is not list or not all(
        type(pair) is list
        and len(pair) == 2
        and all(type(item) is str and item for item in pair)
        for pair in value
    ):
        raise PolicyRefused("candidate_retry_on is [[status, reason_code], ...]")
    return frozenset(tuple(pair) for pair in value)


@dataclass(frozen=True)
class RetryPolicy:
    version: str
    digest: str
    max_retries: int
    retry_on_reasons: frozenset
    candidate_retry_on: frozenset
    never_on_status: frozenset
    pods_required: int

    @staticmethod
    def from_document(document, digest):
        if type(document) is not dict or set(document) != _KEYS:
            raise PolicyRefused("policy fields")
        if document["schema"] != POLICY_SCHEMA:
            raise PolicyRefused("policy schema")
        if document["applies_to"] != APPLIES_TO:
            raise PolicyRefused("a policy applies to the session's baseline only")
        retries = document["max_retries"]
        if type(retries) is not int or retries not in (0, 1):
            raise PolicyRefused("max_retries is 0 or 1")
        if document["retry_on_status"] != FAILED_INFRA:
            raise PolicyRefused("retry_on_status is FAILED_INFRA")
        reasons = document["retry_on_reasons"]
        if type(reasons) is not list or not all(type(r) is str and r for r in reasons):
            raise PolicyRefused("retry_on_reasons are reason codes")
        if NEVER_REASONS & set(reasons):
            raise PolicyRefused("a launch-gate refusal or unknown launch is retried")
        candidates = _pairs(document["candidate_retry_on"])
        if not candidates <= ALLOWED_CANDIDATE_RETRIES:
            raise PolicyRefused(
                "a candidate outcome other than the baseline's program crash is retried"
            )
        never = document["never_on_status"]
        if type(never) is not list or not NEVER_STATUSES <= set(never):
            raise PolicyRefused("CANDIDATE_RESOURCE_EXCEEDED is never retried")
        if FAILED_INFRA in never or {status for status, _ in candidates} & set(never):
            raise PolicyRefused("never_on_status names a retried status")
        pods = document["pods_required"]
        if type(pods) is not int or pods < 1:
            raise PolicyRefused("pods_required counts at least the retry's pod")
        if set(document["limits"]) != LIMITS or len(document["limits"]) != len(LIMITS):
            raise PolicyRefused("limits are exactly the ones this module enforces")
        if document["seed"] not in SEEDS:
            raise PolicyRefused("seed rule this module does not implement")
        if document["earlier_scored_results"] not in EARLIER:
            raise PolicyRefused("earlier-result rule this module does not implement")
        return RetryPolicy(
            version=document["version"],
            digest=digest,
            max_retries=retries,
            retry_on_reasons=frozenset(reasons),
            candidate_retry_on=candidates,
            never_on_status=frozenset(never),
            pods_required=pods,
        )

    def record(self):
        return {"version": self.version, "digest": self.digest}


def _digest(document):
    body = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def _registry(directory):
    try:
        registry = json.loads((Path(directory) / "registry.json").read_text())
    except (OSError, ValueError):
        raise PolicyRefused("baseline-retry registry unreadable") from None
    if (
        type(registry) is not dict
        or registry.get("schema") != REGISTRY_SCHEMA
        or type(registry.get("versions")) is not dict
        or registry.get("current") not in registry["versions"]
    ):
        raise PolicyRefused("baseline-retry registry malformed")
    return registry


def registered_policies(directory=None):
    return list(_registry(POLICY_DIR if directory is None else directory)["versions"])


def load_policy(version=None, directory=None):
    """The registered policy `version` (the registry's current one when None),
    refused unless its document's digest is the one the registry pins."""
    directory = POLICY_DIR if directory is None else directory
    registry = _registry(directory)
    version = registry["current"] if version is None else version
    pinned = registry["versions"].get(version)
    if pinned is None:
        raise PolicyRefused("baseline-retry policy not registered: " + str(version))
    try:
        document = json.loads((Path(directory) / f"{version}.json").read_text())
    except (OSError, ValueError):
        raise PolicyRefused("baseline-retry policy unreadable: " + version) from None
    digest = _digest(document)
    if digest != pinned:
        raise PolicyRefused("baseline-retry policy altered: " + version)
    if document.get("version") != version:
        raise PolicyRefused("baseline-retry policy names another version")
    return RetryPolicy.from_document(document, digest)


def decide(
    *,
    policy,
    first,
    retries_used,
    budget_refusal,
    time_fits,
    environment_relaunched=False,
):
    """Whether to retry the failed baseline `first` (its result record).

    `retries_used` counts retries already run; `budget_refusal` is None when
    the session's pod limit and the run's money cap hold `policy.pods_required`
    more pods, else the refusal code; `time_fits` is whether those pods can
    finish within the run's remaining elapsed time; `environment_relaunched`
    is whether the baseline's own run already used an environment relaunch.
    Returns `(retry, reason_code)`; the checks run in a fixed order, the
    cheapest first."""
    if type(policy) is not RetryPolicy:
        raise TypeError("a registered RetryPolicy is required")
    if not is_session_baseline(first):
        return False, NOT_THE_BASELINE
    if not retryable(first, policy):
        return False, why_not(first, policy)
    if environment_relaunched:
        return False, ENVIRONMENT_RELAUNCH_USED
    if not retry_left(retries_used, policy):
        return False, ALREADY_RETRIED
    if budget_refusal is not None:
        return False, "not_retried:" + budget_refusal
    if not time_fits:
        return False, NO_TIME
    return True, RETRIED


def is_session_baseline(first):
    """The record is the session's own baseline: Carbon's recipe, never an
    agent proposal, an ablation or a retry."""
    return first.get("proposal_id") == BASELINE_ID and first.get("kind") == "baseline"


def retryable(first, policy):
    """The failed baseline's outcome is one the policy retries: a pod that
    ran and ended in infrastructure, or the baseline's program crash; never a
    launch-gate refusal, an unknown launch or a resource outcome."""
    status, reason = first.get("status"), first.get("reason_code")
    if reason in NEVER_REASONS:
        return False
    if status == FAILED_INFRA:
        return reason in policy.retry_on_reasons
    return candidate_retryable(status, reason, policy)


def candidate_retryable(status, reason, policy):
    """A candidate-attributed outcome the policy retries for the baseline:
    listed by the policy, allowed by this module and not a never status."""
    return (
        status not in policy.never_on_status
        and (status, reason) in policy.candidate_retry_on
        and (status, reason) in ALLOWED_CANDIDATE_RETRIES
    )


def why_not(first, policy):
    status = first.get("status")
    if status in (CANDIDATE_FAILED, CANDIDATE_RESOURCE_EXCEEDED):
        return CANDIDATE_ATTRIBUTED
    if status != FAILED_INFRA:
        return NOT_RETRYABLE_STATUS
    return NOT_RETRYABLE_REASON


def retry_left(retries_used, policy):
    return retries_used < policy.max_retries


__all__ = [
    "ALLOWED_CANDIDATE_RETRIES",
    "ALREADY_RETRIED",
    "APPLIES_TO",
    "BASELINE_ID",
    "CANDIDATE_ATTRIBUTED",
    "DECISION_SCHEMA",
    "ENVIRONMENT_RELAUNCH_USED",
    "NEVER_STATUSES",
    "NOT_RETRYABLE_REASON",
    "NOT_RETRYABLE_STATUS",
    "NOT_THE_BASELINE",
    "NO_TIME",
    "POLICY_DIR",
    "RETRIED",
    "RETRY_ID",
    "PolicyRefused",
    "RetryPolicy",
    "candidate_retryable",
    "decide",
    "is_session_baseline",
    "load_policy",
    "registered_policies",
    "retry_left",
    "retryable",
    "why_not",
]
