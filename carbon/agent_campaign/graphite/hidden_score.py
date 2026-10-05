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
OPERATOR_SCHEMA = "carbon.graphite.hidden-score-operator.v1"
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
        return _view("SCORED", outcome=outcome), self._operator_record(outcome)

    def _operator_record(self, outcome):
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
            "rotation_overdue": overdue,
            "replay": "REPRODUCED",
            "score_record_digest": digest(canonical(full)),
        }

    def standing(self):
        """The deployment's incumbent: the validator's own leader, decided by
        its nomination and finals, never by Graphite's ranking."""
        incumbent = self.target.store.incumbent()
        return None if incumbent is None else dict(incumbent)


def _view(state, **fields):
    if state not in STATES:
        raise ValueError(state)
    return {"schema": VIEW_SCHEMA, "evidence": EVIDENCE, "state": state, **fields}
