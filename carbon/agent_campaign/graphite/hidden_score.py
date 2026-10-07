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
- whether the pool version's rotation was overdue;
- the near-limit quiz's measures, when the active batches carry a quiz
  (VALIDATOR-19 slice Q), reported per pool version and gating nothing.

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

    def __init__(self, target, *, run_id, clock, variant=None, score_variant=None):
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
        # The near-limit quiz's operator-only measures (VALIDATOR-19 slice Q):
        # reported beside each hidden score, gating nothing.
        from carbon.challenge_validator.battery_quiz import install

        install(target)
        self.run_id = run_id
        self.clock = clock
        self.challenge_id = self.adapter.challenge_id
        self.challenge_version = self.adapter.challenge_version
        self.contract_digest = target.identities()["contract_digest"]
        self.variant = variant
        #: A development score variant (VALIDATOR-09), applied operator-side
        #: to every hidden score beside the rule's own. Only on a deployment
        #: that opted in (`development_only`), which never sets weights, so
        #: a variant result never reaches weights, the allow-list or rule
        #: v2's record.
        self.score_variant = score_variant
        if score_variant is not None:
            if not getattr(target, "development_only", False):
                raise HiddenPoolRefused(
                    "hidden_score_variant_needs_development_deployment"
                )
            if score_variant.challenge_id != self.challenge_id:
                raise HiddenPoolRefused("hidden_score_variant_other_challenge")
        if variant is not None:
            # A development level (owner, 2026-10-06): only on a deployment
            # that opted in (`development_only`), only a registered variant,
            # compiled by the variant module on this side, never the daemon's.
            from carbon.reconstruction import development_variants as dv

            if not getattr(target, "development_only", False):
                raise HiddenPoolRefused(
                    "hidden_level_needs_a_development_only_deployment"
                )
            if dv.registered(variant.digest, self.challenge_id) != variant:
                raise HiddenPoolRefused("hidden_variant_unregistered")
            target.development_compiler = _development_compiler
            self.contract_digest = variant.digest

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
            "level": 0 if self.variant is None else self.variant.level,
            "variant_digest": None if self.variant is None else self.variant.digest,
            "overdue_margin_blocks": (
                self._overdue_margin(version, block) if overdue else None
            ),
            "replay": "REPRODUCED",
            "score_variant": self._variant_result(full),
            # The near-limit quiz (VALIDATOR-19 slice Q): reported, gating
            # nothing; None when no active batch carried one.
            "quiz": full.get("quiz"),
            "score_record_digest": digest(canonical(full)),
        }

    def _variant_result(self, full):
        if self.score_variant is None:
            return None
        from . import score_variant as sv

        return sv.hidden_result(self.score_variant, self.target, full)

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


def _variant_ranking(records):
    """One pool version's records ranked under their score variant: a gate
    FAIL last, then score, closest to 1 first; one ranking per cutoff for a
    gate sweep. Empty when no record carries a variant result."""
    results = [(r, r.get("score_variant")) for r in records]
    results = [(r, v) for r, v in results if v]
    if not results:
        return {}

    def ranked(entries):
        def key(item):
            _record, result = item
            score = result.get("score")
            return (result.get("gate") == "FAIL", score is None, -(score or 0.0))

        return [
            {
                "proposal_id": record.get("proposal_id"),
                "kind": record.get("kind"),
                "submission_id": record["submission_id"],
                "score": result.get("score"),
                "gate": result.get("gate"),
            }
            for record, result in sorted(entries, key=key)
        ]

    first = results[0][1]
    out = {"score_variant": first.get("score_variant")}
    if "by_cutoff" in first:
        out["by_cutoff"] = {
            cutoff: ranked([(r, v["by_cutoff"][cutoff]) for r, v in results])
            for cutoff in sorted(first["by_cutoff"])
        }
    else:
        out["ranking"] = ranked(results)
    return out


def report(records):
    """A run's hidden-pool report from its operator records (in proposal
    order).

    Scores are comparable only within one pool version and one rebuild
    device class (TORCH-GPU-01: CPU and GPU rebuilds differ), so the primary
    ranking is per pool version and device class: eligible first, then by
    score (lower is better). A record without a device class is the legacy
    CPU class (`carbon.battery.rebuild_identity`). A development level's
    table is keyed the same way under its level: nothing is ranked across
    levels, pool versions or device classes. A score taken on an overdue
    pool was adaptively over-exposed
    (the Test Lead's ruling of 2026-10-05). Such scores are reported
    separately, counted, with their overdue margin, as descriptive evidence
    only. They never enter the primary ranking, an alignment result or a
    promotion claim. A record whose score did not replay is listed by
    submission and never ranked.
    """
    from carbon.battery.rebuild_identity import device_class

    reproduced = [r for r in records if r.get("replay") == "REPRODUCED"]
    primary, development = {}, {}
    for record in reproduced:
        if record["rotation_overdue"]:
            continue
        # Never ranked across levels, pool versions or device classes.
        cls = device_class(record)
        if record.get("level", 0):
            # A development level is its own table: never ranked with Level 0.
            development.setdefault(str(record["level"]), {}).setdefault(
                str(record["pool_version"]), {}
            ).setdefault(cls, []).append(record)
        else:
            primary.setdefault(str(record["pool_version"]), {}).setdefault(
                cls, []
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
    # Like the primary ranking, never across pool versions or device classes.
    variant = {
        version: {
            cls: ranking
            for cls, rows in sorted(classes.items())
            if (ranking := _variant_ranking(rows))
        }
        for version, classes in sorted(primary.items())
    }
    return {
        "schema": REPORT_SCHEMA,
        "evidence": EVIDENCE,
        # Under the run's development score variant, beside the rule's own
        # ranking, per pool version and device class: closest to 1 best, a
        # gate FAIL last (the EV5 ruling). Empty without a variant.
        "score_variant": {k: v for k, v in variant.items() if v},
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
        "development_levels": {
            level: {
                "never_ranked_with_level_0": True,
                "by_pool_version": {
                    version: {
                        cls: [
                            {
                                **row(r),
                                "pool_version": r["pool_version"],
                                "variant_digest": r.get("variant_digest"),
                            }
                            for r in sorted(rows, key=rank_key)
                        ]
                        for cls, rows in sorted(classes.items())
                    }
                    for version, classes in sorted(
                        versions.items(), key=lambda i: int(i[0])
                    )
                },
            }
            for level, versions in sorted(development.items())
        },
        "quiz": _quiz_table(reproduced),
        "replay_mismatch": [
            r["submission_id"] for r in records if r.get("replay") == "MISMATCH"
        ],
    }


def _quiz_table(records):
    """The quiz measures per pool version (VALIDATOR-19 slice Q): one row per
    record whose active batches carried a quiz, in proposal order. Descriptive
    only: never ranked and never a gate until the owner adopts rule v3. A
    quiz that could not be measured is listed with its state and code."""
    table = {}
    for record in records:
        quiz = record.get("quiz")
        if not quiz:
            continue
        pooled = quiz.get("pooled") or {}
        q3 = pooled.get("q3") or {}
        table.setdefault(str(record["pool_version"]), []).append(
            {
                "proposal_id": record.get("proposal_id"),
                "kind": record.get("kind"),
                "submission_id": record["submission_id"],
                "level": record.get("level", 0),
                "state": quiz.get("state"),
                "code": quiz.get("code"),
                "panel_versions": sorted(
                    {b["panel_version"] for b in quiz.get("batches", {}).values()}
                ),
                "q2": pooled.get("q2"),
                "q3": (
                    {k: q3.get(k) for k in ("false_feasible", "regret", "over_caution")}
                    if q3
                    else None
                ),
            }
        )
    return {
        "descriptive_only": True,
        "gates": "NONE",
        "by_pool_version": dict(sorted(table.items(), key=lambda i: int(i[0]))),
    }


def _development_compiler(strategy, variant_digest):
    """The development compile the battery daemon calls for a registered
    variant (it never imports the variant module itself)."""
    from carbon.reconstruction import development_variants as dv

    return dv.compile_development(strategy, dv.registered(variant_digest))


def _view(state, **fields):
    if state not in STATES:
        raise ValueError(state)
    return {"schema": VIEW_SCHEMA, "evidence": EVIDENCE, "state": state, **fields}
