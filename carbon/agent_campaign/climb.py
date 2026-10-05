"""The climb harness: matched comparison, ablation and interaction for one level.

Handoff §8 and the climb procedure (`carbon.challenge_pipeline.ladder`,
`CLIMB_PROCEDURE` steps 4-8). Once the construction contract owner has
accepted a level's proposal and Carbon's reconstruction for the level exists,
Carbon runs, for one Challenge and one level:

1. `valid`: the legitimate panel under the previous and the expanded profile;
2. `matched_attacks`: the same attack set, in full, under both profiles;
3. `ablation`: for each new permission, the expanded profile without it, with
   the panel and the attacks again;
4. `interactions`: combined-permission attacks, each pairing a new permission
   with an earlier one, under the expanded profile;
5. `reconstruction`: each valid construction the plan marks promising,
   rebuilt on a clean worker.

The harness owns the order, the matching and the record. The runs are injected
(`Runners`), and the tests use fake runs. It is Challenge-neutral: a Challenge
supplies its profiles (from its contract and the level's reconstruction), its
panel, its attacks, its runners and the rule that marks a result promising.

Rules:
- **Matched budgets.** The attack set runs in full under every profile it runs
  under. The plan refuses a budget that is not the attack set's size.
- **A removed permission must be refused.** A construction or attack that
  needs a permission its profile lacks must come back REFUSED. If it runs, the
  profile's boundary did not hold, and that is a finding.
- **A finding stops the climb** (handoff §16). A finding is an attack whose
  declared violation was reproduced outside the agent, a boundary that did not
  hold, or a rebuild that does not match. Later steps are NOT_RUN with the
  reason, and the finding is kept.
- **Except on a development variant, where it continues and tags**
  (OWNER-GRAPHITE-TEST-WAVE-03 §2, GRAPHITE-DEV-VARIANTS-01). A plan that
  names a registered development-only variant (`development_variant`) runs
  every step past a finding. The finding is kept and named
  (`climb-finding-NNN`); every run recorded after it, and the report, carry
  `conditional_on` with it. Such a report is never unconditional evidence. A
  plan with no variant (the LOCK path) stops exactly as before.
- **Infrastructure failure is not a result.** A run that fails on
  infrastructure is recorded as FAILED_INFRA. It is never a finding and never
  a pass, and it counts against the budget.
- **Untested is not passed.** A new permission that no combined attack
  exercises leaves its interaction NOT_RUN.
- The report never marks a level TESTED and never opens it. A person reads the
  report and records the level's state.
- **The report says what it is conditional on** (OWNER-GRAPHITE-TEST-WAVE-03
  §2). The caller passes the campaign controller's open findings
  (`CampaignController.open_findings()`), and the report carries them as
  `conditional_on` with the policy identity (`conditional-evidence.v1`). A
  report that lists a finding is never TESTED evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass

from carbon.challenge_readiness import conditional_evidence

#: v2: the report carries `conditional_on` and `conditional_policy`.
REPORT_SCHEMA = "carbon.agent-campaign.climb-report.v2"
PROFILE_SCHEMA = "carbon.agent-campaign.climb-profile.v1"
STEPS = ("valid", "matched_attacks", "ablation", "interactions", "reconstruction")
RUN_STATUSES = ("OK", "REFUSED", "FAILED_INFRA")


class ClimbError(ValueError):
    """A climb plan the harness refuses; the code names why."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class Profile:
    """One exact permission state, pinned by digest."""

    name: str
    permissions: frozenset
    digest: str


def profile(name, *, base, permissions, extra=None):
    """A profile over a contract digest (`base`), its permissions and any
    pinned identity of the level's reconstruction (`extra`)."""
    permissions = frozenset(permissions)
    document = {
        "schema": PROFILE_SCHEMA,
        "base": base,
        "permissions": sorted(permissions),
        "extra": extra,
    }
    return Profile(name, permissions, _digest(document))


@dataclass(frozen=True)
class Item:
    """A panel construction or an attack, with the permissions it needs.

    An attack declares, before it runs, the violation that would count as its
    success."""

    item_id: str
    uses: frozenset
    declared_violation: str | None = None


@dataclass(frozen=True)
class Runners:
    #: (profile, item) -> {status, artifact_digest, result}
    construct: Callable
    #: (profile, item) -> {status, violation_reproduced, evidence_digest}
    attack: Callable
    #: (run record) -> {status, matches, rebuilt_digest}
    rebuild: Callable


@dataclass(frozen=True)
class ClimbPlan:
    challenge: str
    level: int
    previous: Profile
    expanded: Profile
    new_permissions: tuple
    panel: tuple
    attacks: tuple
    attack_budget: int
    combined: tuple
    #: (run record) -> True when a valid result is worth a clean rebuild. The
    #: rule is the Challenge's, declared before the climb runs.
    promising: Callable
    #: The registered development-only variant the expanded profile runs
    #: under, by digest, or None (the LOCK path). A development climb
    #: continues past a finding and tags what follows it.
    development_variant: str | None = None

    def __post_init__(self):
        if not (type(self.level) is int and 1 <= self.level <= 5):
            raise ClimbError("level_is_1_to_5")
        if self.development_variant is not None:
            from carbon.reconstruction import development_variants

            try:
                found = development_variants.registered(
                    self.development_variant, self.challenge
                )
            except development_variants.VariantRefused as refused:
                raise ClimbError(refused.code) from None
            if found.level != self.level:
                raise ClimbError("development_variant_is_another_level")
        new = frozenset(self.new_permissions)
        if not new or new & self.previous.permissions:
            raise ClimbError("new_permissions_are_new")
        if self.expanded.permissions != self.previous.permissions | new:
            raise ClimbError("expanded_is_previous_plus_the_new_permissions")
        if not self.panel:
            raise ClimbError("a_legitimate_panel_is_required")
        if type(self.attack_budget) is not int or self.attack_budget != len(
            self.attacks
        ):
            raise ClimbError(
                "attack_budget_must_match_the_attack_set",
                f"{len(self.attacks)} attacks, budget {self.attack_budget}",
            )
        for item in (*self.attacks, *self.combined):
            if not (type(item.declared_violation) is str and item.declared_violation):
                raise ClimbError("an_attack_declares_its_violation", item.item_id)
        ids = [i.item_id for i in (*self.panel, *self.attacks, *self.combined)]
        if len(ids) != len(set(ids)):
            raise ClimbError("item_ids_are_unique")

    def ablated(self, permission):
        return Profile(
            f"ablated:{permission}",
            self.expanded.permissions - {permission},
            _digest({"ablated_from": self.expanded.digest, "removed": permission}),
        )


class _Record:
    def __init__(self, development=False, open_findings=()):
        self.steps = {}
        self.findings = []
        self.development = development
        self.open_findings = list(open_findings)

    def stopped(self):
        """A finding stops the climb, except on a development variant."""
        return bool(self.findings) and not self.development

    def add_finding(self, finding):
        if self.development:
            # Named so what follows it can say it is conditional on it.
            finding = {"id": f"climb-finding-{len(self.findings) + 1:03d}", **finding}
        self.findings.append(finding)

    def conditional(self):
        """The tag: the controller's open findings, and on a development
        climb every finding the climb itself has recorded so far."""
        own = (
            [conditional_evidence.reference(f) for f in self.findings]
            if self.development
            else []
        )
        return conditional_evidence.tag([*self.open_findings, *own])

    def tag_after_finding(self, entry):
        """A development run recorded after an in-climb finding carries it."""
        if self.development and self.findings:
            entry.update(self.conditional())
        return entry


def _run(record, step, kind, profile, item, runners):
    expected_refusal = not item.uses <= profile.permissions
    call = runners.construct if kind == "construction" else runners.attack
    outcome = call(profile, item)
    status = outcome.get("status")
    if status not in RUN_STATUSES:
        raise ClimbError("runner_status_unknown", str(status))
    run = {
        "step": step,
        "kind": kind,
        "profile": profile.name,
        "profile_digest": profile.digest,
        "item_id": item.item_id,
        "status": status,
        "expected_refusal": expected_refusal,
        "outcome": outcome,
    }
    record.steps[step]["runs"].append(record.tag_after_finding(run))
    if expected_refusal and status == "OK":
        record.add_finding(
            {
                "kind": "permission_not_enforced",
                "step": step,
                "profile": profile.name,
                "item_id": item.item_id,
                "evidence": outcome,
            }
        )
    if kind == "attack" and status == "OK" and outcome.get("violation_reproduced"):
        record.add_finding(
            {
                "kind": "attack_violation_reproduced",
                "step": step,
                "profile": profile.name,
                "item_id": item.item_id,
                "declared_violation": item.declared_violation,
                "evidence": outcome,
            }
        )
    return run


def _not_run(record, step, reason):
    record.steps[step] = {"state": "NOT_RUN", "reason": reason, "runs": []}


def climb(plan, runners, *, open_findings=()):
    """Run the climb's steps in order; returns the report, tagged with the
    findings open when the climb ran (`open_findings`, as `{id, digest}`)."""
    if type(plan) is not ClimbPlan or type(runners) is not Runners:
        raise TypeError("exact ClimbPlan and Runners required")
    conditional_evidence.tag(open_findings)  # well-formed before anything runs
    development = plan.development_variant is not None
    record = _Record(development, open_findings)
    coverage = {}

    def step(name, body):
        if record.stopped():
            _not_run(record, name, "stopped_on_finding")
            return
        record.steps[name] = {"state": "RUN", "reason": None, "runs": []}
        body(name)

    def valid(name):
        for p in (plan.previous, plan.expanded):
            for item in plan.panel:
                _run(record, name, "construction", p, item, runners)

    def matched(name):
        for p in (plan.previous, plan.expanded):
            for item in plan.attacks:
                _run(record, name, "attack", p, item, runners)

    def ablation(name):
        for permission in sorted(plan.new_permissions):
            p = plan.ablated(permission)
            for item in plan.panel:
                _run(record, name, "construction", p, item, runners)
            for item in plan.attacks:
                _run(record, name, "attack", p, item, runners)

    def interactions(name):
        for permission in sorted(plan.new_permissions):
            pairing = [
                i
                for i in plan.combined
                if permission in i.uses and i.uses & plan.previous.permissions
            ]
            coverage[permission] = [i.item_id for i in pairing] or "NOT_RUN"
            for item in pairing:
                _run(record, name, "attack", plan.expanded, item, runners)

    def reconstruction(name):
        valid_runs = record.steps["valid"]["runs"]
        for run in valid_runs:
            if not (
                run["profile"] == plan.expanded.name
                and run["status"] == "OK"
                and plan.promising(run)
            ):
                continue
            rebuilt = runners.rebuild(run)
            status = rebuilt.get("status")
            if status not in ("OK", "FAILED_INFRA"):
                raise ClimbError("rebuild_status_unknown", str(status))
            entry = {
                "step": name,
                "kind": "rebuild",
                "profile": run["profile"],
                "profile_digest": run["profile_digest"],
                "item_id": run["item_id"],
                "status": status,
                "outcome": rebuilt,
            }
            record.steps[name]["runs"].append(record.tag_after_finding(entry))
            if status == "OK" and not rebuilt.get("matches"):
                record.add_finding(
                    {
                        "kind": "reconstruction_mismatch",
                        "step": name,
                        "profile": run["profile"],
                        "item_id": run["item_id"],
                        "evidence": rebuilt,
                    }
                )

    for name, body in zip(
        STEPS, (valid, matched, ablation, interactions, reconstruction)
    ):
        step(name, body)
    runs = [r for s in record.steps.values() for r in s["runs"]]
    if development:
        status = "COMPLETED_CONDITIONAL" if record.findings else "COMPLETED"
        extra = {"development_variant": plan.development_variant}
    else:
        status = "STOPPED_ON_FINDING" if record.findings else "COMPLETED"
        extra = {}
    return {
        "schema": REPORT_SCHEMA,
        "challenge": plan.challenge,
        "level": plan.level,
        "profiles": {
            p.name: p.digest
            for p in (
                plan.previous,
                plan.expanded,
                *(plan.ablated(n) for n in sorted(plan.new_permissions)),
            )
        },
        "new_permissions": sorted(plan.new_permissions),
        "attack_budget_per_profile": plan.attack_budget,
        "steps": record.steps,
        "interaction_coverage": {
            n: coverage.get(n, "NOT_RUN") for n in sorted(plan.new_permissions)
        },
        "infrastructure_failures": sum(r["status"] == "FAILED_INFRA" for r in runs),
        "findings": record.findings,
        "status": status,
        "claims": {
            "level_tested": False,
            "level_open_to_miners": False,
            "qualification": False,
        },
        **extra,
        **record.conditional(),
    }
