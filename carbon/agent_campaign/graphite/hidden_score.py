"""Graphite constructions scored on hidden batches through battery's real
validator (VALIDATOR-13).

Graphite scores each construction on the public PRACTICE references
(`experiment.py` step 4): adaptive development feedback on cases the agent
has seen. This module adds the mainnet evidence. The same admitted recipe is
submitted to an operator battery deployment through `deployment.evaluate`,
battery's only evaluation path, unchanged. The validator then rebuilds on its
own backend and scores on its hidden screening pool.

**The rule.** The deployment must run a rule that seals hidden-batch results
from miners (battery rule v2, OWNER-BATTERY-3B-AND-EXPOSURE-01;
OWNER-VALIDATOR-MAINNET-PARITY-01 item 2). Any other rule is refused, so no
number computed from a hidden batch can reach the agent.

**What the agent sees.** Only `agent_view`:
- the evidence class;
- a typed state;
- the validator's own miner outcome, which under v2 is the allow-list
  (state, refusal codes, digests);
- for a used hotkey window, the next block.

That is exactly what a mainnet miner sees.

**What the operator sees.** `operator_record`:
- the replay-verified aggregate;
- the pool version and active batch fingerprints;
- the nomination;
- whether the pool version's rotation was overdue.

It is written only under the run's private root. Cases and predictions stay
in the validator's own state.

**Identity.** A run is one development identity (`graphite-dev:<run>`), never
a chain hotkey, so it gets one hidden score per tempo, like a single miner.
Carbon's baseline has its own identity, so it never uses the constructor's
window. A used window is `WINDOW_USED`, not a refusal.

**Infrastructure.** Validator unavailability is `UNAVAILABLE` with its code.
It is never a candidate failure (invariant 7).

No pod is involved: no hidden case, seed, fingerprint or prediction is ever
staged to rented compute. DEVELOPMENT evidence only: no qualification,
weight, reward or LIVE authority.
"""

from __future__ import annotations

import hashlib

from carbon.development_session.profile import canonical, digest

VIEW_SCHEMA = "carbon.graphite.hidden-score.v1"
#: v2 records carry `rebuild` (TORCH-GPU-01); a v1 record reads as the
#: legacy CPU identity.
OPERATOR_SCHEMA = "carbon.graphite.hidden-score-operator.v2"
RERUN_SCHEMA = "carbon.graphite.hidden-fresh-rerun.v1"
#: v2 ranks within one pool version and one device class.
REPORT_SCHEMA = "carbon.graphite.hidden-pool-report.v2"
#: Rerun states that are final; any other is retried later.
RERUN_FINAL = ("SCORED", "CANDIDATE_FAILED")
EVIDENCE = "DEVELOPMENT_HIDDEN_POOL"
STATES = ("SCORED", "NOT_SCORED", "WINDOW_USED", "UNAVAILABLE")


class HiddenPoolRefused(ValueError):
    """The deployment cannot serve Graphite's hidden scoring. Its code names
    why; nothing was submitted."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class HiddenPool:
    """One run's hidden scoring on one battery deployment.

    `target` is a started `BatteryValidator` from `deployment.build`, carrying
    its deployment's writer lock. `clock()` returns the finalized block the
    submission is received at: testnet's in operation, a fixed one in tests.
    """

    def __init__(self, target, *, run_id, clock):
        from carbon.battery import exam
        from carbon.battery.daemon import BatteryValidator
        from carbon.challenge_validator.battery import BatteryAdapter

        if type(target) is not BatteryValidator:
            raise HiddenPoolRefused("hidden_pool_not_battery")
        if getattr(target, "readonly", False):
            raise HiddenPoolRefused("hidden_pool_readonly")
        if not exam.sealed(target.rule):
            # A rule that discloses hidden-batch results would hand the agent
            # what a mainnet miner never sees.
            raise HiddenPoolRefused("hidden_rule_not_sealed")
        if type(run_id) is not str or not run_id:
            raise HiddenPoolRefused("hidden_run_id_missing")
        self.target = target
        self.adapter = BatteryAdapter(target)  # refuses a target without its lock
        self.run_id = run_id
        self.clock = clock
        self.challenge_id = self.adapter.challenge_id
        self.challenge_version = self.adapter.challenge_version
        self.contract_digest = target.identities()["contract_digest"]

    def identity(self, kind):
        """The development identity a proposal of `kind` submits under."""
        role = "baseline" if kind == "baseline" else "constructor"
        return f"graphite-dev:{self.run_id}:{role}"

    def _submission(self, kind, strategy, block):
        from carbon.battery.daemon import AuthenticatedSubmission

        hotkey = self.identity(kind)
        body = canonical({"hotkey": hotkey, "block": block, "strategy": strategy})
        return AuthenticatedSubmission(
            hotkey=hotkey,
            receipt={
                "sequence": block,
                "digest": hashlib.sha256(body).hexdigest(),
                "block": block,
            },
            challenge_id=self.challenge_id,
            challenge_version=self.challenge_version,
            strategy=strategy,
            contract_digest=self.contract_digest,
        )

    def submit(self, kind, strategy):
        """Submit one admitted strategy. Returns `(agent_view, operator_record)`;
        the record is None unless the validator scored it."""
        from carbon.battery import deployment
        from carbon.battery.pool_store import StateError

        block = self.clock()
        if type(block) is not int or block < 0:
            return _view("UNAVAILABLE", code="hidden_clock_unavailable"), None
        try:
            outcome = deployment.evaluate(
                self.target, self._submission(kind, strategy, block)
            )
        except deployment.EvaluationUnavailable as refused:
            if refused.code == "hotkey_window_used":
                return _view("WINDOW_USED", next_block=refused.next_block), None
            return _view("UNAVAILABLE", code=refused.code), None
        except StateError as moved:
            return _view("UNAVAILABLE", code="hidden_state_" + moved.code), None
        if outcome["state"] != "SCORED":
            return _view("NOT_SCORED", outcome=outcome), None
        return _view("SCORED", outcome=outcome), self._operator_record(outcome, block)

    def _overdue_margin(self, version, block):
        """Blocks past the due rotation when this score was taken, or None when
        the pool has since moved on and the margin is no longer known."""
        store = self.target.store
        started = store.pool_started_block()
        if store.pool()["version"] != version or started is None:
            return None
        return block - started - self.target.rule["rotation"]["every_blocks"]

    def _operator_record(self, outcome, block):
        from carbon.challenge_validator.battery import ScoreReplayMismatch

        sid = outcome["submission_id"]
        try:
            full = self.adapter.score_record(sid)
        except ScoreReplayMismatch:
            # The stored score did not reproduce from its stored predictions:
            # an integrity finding for the operator, never a ranked result.
            return {
                "schema": OPERATOR_SCHEMA,
                "evidence": EVIDENCE,
                "submission_id": sid,
                "replay": "MISMATCH",
            }
        version = full["pool_version"]
        overdue = any(
            event["body"].get("version") == version
            for event in self.target.store.events("rotation_overdue")
        )
        return {
            "schema": OPERATOR_SCHEMA,
            "evidence": EVIDENCE,
            "submission_id": sid,
            "pool_version": version,
            "rule_digest": full["rule_digest"],
            "references": full["references"],
            "active_batches": full["active_batches"],
            "aggregate": full["aggregate"],
            "nomination": full["nomination"],
            "rebuild": full["rebuild"],
            "rotation_overdue": overdue,
            "overdue_margin_blocks": (
                self._overdue_margin(version, block) if overdue else None
            ),
            "replay": "REPRODUCED",
            "score_record_digest": digest(canonical(full)),
        }

    def fresh_rerun(self, submission_id):
        """Re-score a hidden-scored submission once on a fresh hidden batch,
        consumed by this use (`BatteryValidator.fresh_rerun`), under the
        deployment's writer lock. Operator-only. The Challenge's one-shot
        confirmation set is never used here."""
        from carbon.battery import deployment

        with deployment.writer(self.target):
            result = self.target.fresh_rerun(submission_id)
        return {"schema": RERUN_SCHEMA, "evidence": EVIDENCE, **result}

    def standing(self):
        """The deployment's incumbent: the validator's own leader, decided by
        its nomination and finals, never by Graphite's ranking."""
        incumbent = self.target.store.incumbent()
        return None if incumbent is None else dict(incumbent)


def report(records):
    """A run's hidden-pool report from its operator records (in proposal
    order).

    Scores are comparable only within one pool version and one rebuild
    device class (TORCH-GPU-01: CPU and GPU rebuilds differ), so the primary
    ranking is per pool version and device class: eligible first, then by
    score (lower is better). A record without a device class is the legacy
    CPU class (`carbon.battery.rebuild_identity`). A score taken on an overdue pool was adaptively over-exposed
    (the Test Lead's ruling of 2026-10-05). Such scores are reported
    separately, counted, with their overdue margin, as descriptive evidence
    only. They never enter the primary ranking, an alignment result or a
    promotion claim. A record whose score did not replay is listed by
    submission and never ranked.
    """
    from carbon.battery.rebuild_identity import device_class

    reproduced = [r for r in records if r.get("replay") == "REPRODUCED"]
    primary = {}
    for record in reproduced:
        if not record["rotation_overdue"]:
            primary.setdefault(str(record["pool_version"]), {}).setdefault(
                device_class(record), []
            ).append(record)

    def rank_key(record):
        score = record["aggregate"].get("score")
        return (not record["aggregate"].get("eligible"), score is None, score or 0)

    def row(record):
        aggregate = record["aggregate"]
        return {
            "proposal_id": record.get("proposal_id"),
            "kind": record.get("kind"),
            "submission_id": record["submission_id"],
            "eligible": bool(aggregate.get("eligible")),
            "score": aggregate.get("score"),
            "important_score": aggregate.get("important_score"),
        }

    overdue = [r for r in reproduced if r["rotation_overdue"]]
    return {
        "schema": REPORT_SCHEMA,
        "evidence": EVIDENCE,
        "primary": {
            "by_pool_version": {
                version: {
                    cls: [row(r) for r in sorted(rows, key=rank_key)]
                    for cls, rows in sorted(classes.items())
                }
                for version, classes in sorted(primary.items(), key=lambda i: int(i[0]))
            },
        },
        "overdue": {
            "descriptive_only": True,
            "count": len(overdue),
            "records": [
                {
                    **row(r),
                    "pool_version": r["pool_version"],
                    "device_class": device_class(r),
                    "overdue_margin_blocks": r.get("overdue_margin_blocks"),
                }
                for r in overdue
            ],
        },
        "replay_mismatch": [
            r["submission_id"] for r in records if r.get("replay") == "MISMATCH"
        ],
    }


def _view(state, **fields):
    if state not in STATES:
        raise ValueError(state)
    return {"schema": VIEW_SCHEMA, "evidence": EVIDENCE, "state": state, **fields}
