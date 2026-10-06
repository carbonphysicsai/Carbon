"""Battery as the first `ChallengeAdapter` (VALIDATOR-01, KEEP + WRAP).

The adapter only delegates. Battery's validator (`carbon.battery.daemon`),
its deployment and single-writer lock (`deployment.py`), its seed journal
(`seeds.py`) and its exam (`exam.py`) are unchanged:
- evaluation is `deployment.evaluate`, called exactly as the campaign path
  calls it, so admission, screening, nomination and finals are battery's own;
- the miner outcome is `BatteryValidator.outcome`, byte for byte;
- the operator score record re-derives the per-case rows from the stored
  predictions with `exam.evaluate`, and refuses to return them unless they
  reproduce the stored score exactly.

What the adapter adds is the neutral contract: pinned identities, the reserved
and sealed seed-role guard, and an operator-only score record.
"""

from __future__ import annotations

import json

from .interface import ChallengeAdapter, Unavailable
from .producer import BatchSource, ProducerRefused

SCORE_RECORD_SCHEMA = "carbon.battery.operator-score-record.v1"


def _plain(value):
    """`value` as plain JSON data (numpy scalars and arrays included)."""
    import numpy as np

    def default(item):
        if isinstance(item, np.generic):
            return item.item()
        if isinstance(item, np.ndarray):
            return item.tolist()
        raise TypeError(type(item).__name__)

    return json.loads(json.dumps(value, default=default, allow_nan=False))


class ScoreReplayMismatch(RuntimeError):
    """Re-deriving a stored score from its stored predictions did not
    reproduce it. Nothing is returned."""


class BatteryAdapter(ChallengeAdapter):
    """One battery deployment's validator, behind the neutral contract."""

    def __init__(self, target):
        from carbon.battery.challenge import CHALLENGE
        from carbon.battery.daemon import BatteryValidator
        from carbon.battery.research import EVALUATION_FEEDBACK_FIELDS
        from carbon.transport.models import MAX_BODY

        if type(target) is not BatteryValidator:
            raise TypeError("a BatteryValidator is required")
        if not getattr(target, "lock_path", None):
            raise TypeError("the validator needs its deployment's writer lock")
        self.target = target
        self.challenge_id = CHALLENGE.challenge_id
        self.challenge_version = CHALLENGE.version
        # The strategy arrives inside one transport body, so no strategy the
        # battery path accepts today is larger.
        self.max_strategy_bytes = MAX_BODY
        self.disclosure_fields = frozenset(EVALUATION_FEEDBACK_FIELDS)
        # Bound once: the adapter evaluates under these identities for its
        # whole life (`BatteryValidator.start` refuses a changed binding).
        self._identities = _plain(target.identities())
        self.contract_digest = self._identities["contract_digest"]

    @classmethod
    def from_deployment(cls, config_path, *, repository):
        """The adapter over an operator's deployment configuration."""
        from carbon.battery import deployment

        return cls(deployment.validator(config_path, repository=repository))

    def _writer(self):
        from carbon.battery.deployment import writer

        return writer(self.target)

    # --- identities ---------------------------------------------------------

    def identities(self):
        return json.loads(json.dumps(self._identities))

    def disclosure_budget(self):
        per_hotkey = self.target.rule.get("per_hotkey")
        if per_hotkey is None:
            return None
        return {"source": "exam_rule.per_hotkey", **_plain(per_hotkey)}

    # --- miner side ---------------------------------------------------------

    def evaluate(self, submission):
        from carbon.battery.daemon import AuthenticatedSubmission
        from carbon.battery.deployment import EvaluationUnavailable, evaluate

        authenticated = AuthenticatedSubmission(
            hotkey=submission.hotkey,
            receipt=dict(submission.receipt),
            challenge_id=submission.challenge_id,
            challenge_version=submission.challenge_version,
            strategy=submission.strategy,
            contract_digest=submission.contract_digest,
        )
        try:
            return evaluate(self.target, authenticated)
        except EvaluationUnavailable as unavailable:
            next_block = getattr(unavailable, "next_block", None)
            raise Unavailable(
                unavailable.code,
                retry=None if next_block is None else {"next_block": next_block},
            ) from None

    def outcome(self, submission_id):
        return self.target.outcome(submission_id)

    def owner(self, submission_id):
        from carbon.battery.pool_store import StateError

        try:
            return self.target.store.submission(submission_id)["hotkey"]
        except (StateError, KeyError, TypeError):
            return None

    def advance(self):
        with self._writer():
            return len(self.target.run_pending() or ())

    # --- operator side ------------------------------------------------------

    def score_record(self, submission_id):
        from carbon.battery import exam

        store = self.target.store
        score = store.score(submission_id)
        if score is None:
            raise LookupError("not_scored")
        record = score["record"]
        batches = list(record["active_batches"])
        case_ids = [
            case["case_id"]
            for fingerprint in batches
            for case in store.batch(fingerprint)["document"]["cases"]
        ]
        predictions = store.predictions(submission_id, case_ids)
        rows, aggregate = exam.evaluate(
            predictions, case_ids, self.target._case_store(batches)
        )
        aggregate = _plain(aggregate)
        if any(record.get(k) != v for k, v in aggregate.items()):
            raise ScoreReplayMismatch(submission_id)
        return {
            "schema": SCORE_RECORD_SCHEMA,
            "submission_id": submission_id,
            "pool_version": record["pool_version"],
            "rule_digest": record["rule_digest"],
            "references": record["references"],
            "active_batches": batches,
            "aggregate": aggregate,
            "nomination": record["nomination"],
            "cases": _plain(rows),
            "predictions": _plain(predictions),
        }

    def sealed_roles(self):
        return self.target.sealed_roles()

    def _prepare_batch(self, role, *, kind, **options):
        with self._writer():
            return self.target.prepare_batch(role, kind=kind, **options)

    def reference_jobs(self, fingerprint):
        return self.target.reference_jobs(fingerprint)

    def ingest_references(self, fingerprint, records):
        with self._writer():
            return self.target.ingest_references(fingerprint, records)

    def open_pool(self):
        with self._writer():
            return self.target.open_pool()

    def status(self):
        return _plain(self.target.status())


class BatteryBatchSource(BatchSource):
    """Battery's batches for the producer (VALIDATOR-19 slice 1, WRAP).

    Drawing, journal commitment and the references digest are the battery
    validator's own (`prepare_batch`, `SeedJournal`, `complete_references`),
    so a producer batch is exactly what a validator would have drawn and
    solved. Solves run in the pinned truth image with no network.
    """

    def __init__(self, adapter, *, overlay=None, repository=None, runner=None):
        if type(adapter) is not BatteryAdapter:
            raise TypeError("a BatteryAdapter is required")
        self.adapter = adapter
        self.challenge_id = adapter.challenge_id
        self.overlay = overlay
        self.repository = repository or adapter.target.repository
        self.runner = runner

    @classmethod
    def from_deployment(cls, config_path, *, overlay=None, repository):
        return cls(
            BatteryAdapter.from_deployment(config_path, repository=repository),
            overlay=overlay,
            repository=repository,
        )

    def identities(self):
        identities = self.adapter.identities()
        return {
            k: identities[k] for k in ("contract_digest", "rule_digest", "seed_pin")
        }

    def _row(self, fingerprint):
        from carbon.battery.pool_store import StateError

        try:
            return self.adapter.target.store.batch(fingerprint)
        except StateError:
            raise ProducerRefused("producer_unknown_batch") from None

    def draw(self, role, *, kind, size=None):
        from carbon.battery.pool_store import StateError

        from .interface import ReservedRole

        try:
            return self.adapter.prepare_batch(role, kind=kind, count=size)
        except (ReservedRole, StateError) as refused:
            raise ProducerRefused(refused.code) from None

    def jobs(self, fingerprint):
        self._row(fingerprint)
        return self.adapter.reference_jobs(fingerprint)

    def solve(self, work, *, workers=7, timeout_s=1200.0):
        import subprocess

        from carbon.battery import truth_env

        if self.overlay is None:
            raise ProducerRefused("producer_no_truth_overlay")
        command = truth_env.solve_command(
            self.overlay,
            work,
            repository=self.repository,
            workers=workers,
            timeout_s=timeout_s,
        )
        completed = (self.runner or subprocess.run)(command, check=False)
        return {"returncode": completed.returncode}

    def ingest(self, fingerprint, records):
        from carbon.battery.pool_store import StateError

        self._row(fingerprint)
        try:
            # `complete_references` recomputes the digest over the stored
            # records each time, and refuses one that changed after the batch
            # completed.
            return self.adapter.ingest_references(fingerprint, records)
        except StateError as refused:
            # The code only: a detail may name a case.
            if refused.code == "reference_records_changed":
                raise ProducerRefused("producer_references_changed") from None
            raise ProducerRefused(refused.code) from None

    def sealed(self, fingerprint):
        row = self._row(fingerprint)
        if row["references_state"] != "COMPLETE":
            return None
        return {
            "role": row["role"],
            "kind": row["kind"],
            "journal_sequence": row["sequence"],
            "cases": len(row["document"]["cases"]),
            "references_digest": row["references_digest"],
        }

    def check(self, fingerprint):
        from carbon.battery.seeds import PrivateBatch

        row = self._row(fingerprint)
        target = self.adapter.target
        batch = PrivateBatch.from_document(row["document"])
        if batch.fingerprint != fingerprint:
            raise ProducerRefused("producer_fingerprint_mismatch")
        try:
            committed = target.journal.recall(batch)
        except ValueError:
            raise ProducerRefused("producer_not_committed") from None
        if committed.sequence != row["sequence"]:
            raise ProducerRefused("producer_sequence_mismatch")


__all__ = ["BatteryAdapter", "BatteryBatchSource", "ScoreReplayMismatch"]
