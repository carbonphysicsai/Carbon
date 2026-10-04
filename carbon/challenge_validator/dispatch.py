"""Dispatch by construction-contract digest, behind two separate surfaces.

`Validator` is the miner-facing surface: it evaluates a submission and reports
a submission's outcome. Every result it returns is a `carbon.challenge-
validator.result.v1` envelope holding only the adapter's allow-listed outcome,
the pinned identities and a typed result kind. It has no path to an operator
score record, a seed or a hidden case.

`Operator` is the operator surface: score records, batch preparation and
references, status and the attempt ledger. It is never handed to a transport.

Both are built over one `Adapters` registry. A submission's contract digest
selects its adapter. A digest the registry doesn't hold is refused by name
(`contract_not_served`) and recorded, never scored.
"""

from __future__ import annotations

from .interface import (
    Admitted,
    ChallengeAdapter,
    OutcomeContractViolation,
    ReservedRole,
    Submission,
    Unavailable,
    check_outcome,
    is_digest,
)
from .ledger import AttemptLedger
from .strict_json import MalformedStrategy, parse_strategy

RESULT_SCHEMA = "carbon.challenge-validator.result.v1"
SCORE_RECORD_SCHEMA = "carbon.challenge-validator.score-record.v1"
#: Engineering limits on the identity fields a transport passes through.
MAX_FIELD = 128
MAX_RECEIPT_KEYS = 16


class Adapters:
    """The adapters this validator serves, keyed by contract digest."""

    def __init__(self, adapters):
        self._by_digest = {}
        for adapter in adapters:
            if not isinstance(adapter, ChallengeAdapter):
                raise TypeError("a ChallengeAdapter is required")
            served = adapter.contract_digest
            if not is_digest(served):
                raise ValueError("an adapter serves one sha256 contract digest")
            if served in self._by_digest:
                raise ValueError("two adapters serve one contract digest")
            pinned = adapter.pinned()
            if pinned["contract_digest"] != served:
                raise ValueError("adapter identities name another contract digest")
            if not all(is_digest(v) for v in pinned.values()):
                raise ValueError("adapter identities are not pinned digests")
            self._registered(adapter)
            self._by_digest[served] = adapter

    @staticmethod
    def _registered(adapter):
        """The digest must be the one the capability registry holds for the
        adapter's Challenge: an adapter cannot invent a contract."""
        from carbon.reconstruction.capability_registry import (
            UnknownChallenge,
            contract,
        )

        try:
            registered = contract(adapter.challenge_id)
        except UnknownChallenge:
            raise ValueError(
                "the adapter's challenge has no registered contract"
            ) from None
        if (registered.digest, registered.version) != (
            adapter.contract_digest,
            adapter.challenge_version,
        ):
            raise ValueError("the adapter's digest is not the registered contract")

    def get(self, contract_digest):
        return self._by_digest.get(contract_digest)

    def digests(self):
        return sorted(self._by_digest)


def _result(kind, *, code=None, adapter=None, outcome=None, retry=None):
    out = {
        "schema": RESULT_SCHEMA,
        "kind": kind,
        "code": code,
        "pinned": None if adapter is None else adapter.pinned(),
        "outcome": outcome,
        "evidence": "DEVELOPMENT",
        "qualification": False,
        "reward": False,
    }
    if retry:
        out["retry"] = dict(retry)
    return out


def _short_text(value):
    return type(value) is str and 0 < len(value) <= MAX_FIELD and value.isprintable()


def _well_formed(submission):
    if type(submission) is not Submission:
        return False
    if not all(
        _short_text(v)
        for v in (
            submission.hotkey,
            submission.challenge_id,
            submission.challenge_version,
        )
    ):
        return False
    receipt = submission.receipt
    if type(receipt) is not dict or len(receipt) > MAX_RECEIPT_KEYS:
        return False
    for key, value in receipt.items():
        if type(key) is not str or len(key) > MAX_FIELD:
            return False
        if value is not None and type(value) not in (int, str):
            return False
        if type(value) is str and len(value) > MAX_FIELD:
            return False
    return True


class Validator:
    """The miner-facing validator."""

    def __init__(self, adapters, ledger):
        if type(adapters) is not Adapters:
            raise TypeError("an Adapters registry is required")
        if type(ledger) is not AttemptLedger:
            raise TypeError("an AttemptLedger is required")
        self._adapters = adapters
        self._ledger = ledger

    def served(self):
        """The contract digests this validator serves (public)."""
        return self._adapters.digests()

    def evaluate(self, submission):
        """Evaluate one authenticated submission; return a result envelope."""
        ledger = self._ledger

        def refuse(code, adapter=None):
            ledger.record(submission, kind="REFUSED", code=code)
            return _result("REFUSED", code=code, adapter=adapter)

        if not _well_formed(submission):
            return refuse("malformed_submission")
        if not is_digest(submission.contract_digest):
            return refuse("contract_digest_malformed")
        adapter = self._adapters.get(submission.contract_digest)
        if adapter is None:
            return refuse("contract_not_served")
        if (submission.challenge_id, submission.challenge_version) != (
            adapter.challenge_id,
            adapter.challenge_version,
        ):
            return refuse("challenge_mismatch", adapter)
        try:
            strategy = parse_strategy(
                submission.strategy_json, max_bytes=adapter.max_strategy_bytes
            )
        except MalformedStrategy as malformed:
            return refuse(malformed.code, adapter)
        if strategy.get("challenge_id") != adapter.challenge_id:
            return refuse("challenge_mismatch", adapter)
        admitted = Admitted(
            hotkey=submission.hotkey,
            receipt=dict(submission.receipt),
            challenge_id=submission.challenge_id,
            challenge_version=submission.challenge_version,
            strategy=strategy,
            contract_digest=submission.contract_digest,
        )
        try:
            outcome = check_outcome(adapter.evaluate(admitted), adapter)
        except Unavailable as unavailable:
            ledger.record(submission, kind="UNAVAILABLE", code=unavailable.code)
            return _result(
                "UNAVAILABLE",
                code=unavailable.code,
                adapter=adapter,
                retry=unavailable.retry,
            )
        except OutcomeContractViolation:
            return self._infra(submission, adapter, "outcome_contract_violation")
        except Exception:  # noqa: BLE001 - any adapter fault is infrastructure
            return self._infra(submission, adapter, "adapter_failure")
        ledger.record(
            submission,
            kind="OUTCOME",
            submission_id=outcome["submission_id"],
            state=outcome["state"],
        )
        return _result("OUTCOME", adapter=adapter, outcome=outcome)

    def _infra(self, submission, adapter, code):
        # Infrastructure, never a score (invariant 7). Only the code is kept:
        # an exception's text may carry private state.
        self._ledger.record(submission, kind="FAILED_INFRA", code=code)
        return _result("FAILED_INFRA", code=code, adapter=adapter)

    def outcome(self, contract_digest, submission_id, hotkey):
        """A submission's outcome, for the hotkey that submitted it only.

        An unknown submission and another hotkey's submission get the same
        answer, so the call is no oracle for which submissions exist.
        """
        if not is_digest(contract_digest):
            return _result("REFUSED", code="contract_digest_malformed")
        adapter = self._adapters.get(contract_digest)
        if adapter is None:
            return _result("REFUSED", code="contract_not_served")
        if not (_short_text(submission_id) and _short_text(hotkey)):
            return _result("REFUSED", code="unknown_submission", adapter=adapter)
        try:
            if adapter.owner(submission_id) != hotkey:
                return _result("REFUSED", code="unknown_submission", adapter=adapter)
            outcome = check_outcome(adapter.outcome(submission_id), adapter)
        except OutcomeContractViolation:
            return _result(
                "FAILED_INFRA", code="outcome_contract_violation", adapter=adapter
            )
        except Exception:  # noqa: BLE001
            return _result("FAILED_INFRA", code="adapter_failure", adapter=adapter)
        return _result("OUTCOME", adapter=adapter, outcome=outcome)


class Operator:
    """The operator surface. Never handed to a transport or a miner."""

    def __init__(self, adapters, ledger):
        if type(adapters) is not Adapters:
            raise TypeError("an Adapters registry is required")
        if type(ledger) is not AttemptLedger:
            raise TypeError("an AttemptLedger is required")
        self._adapters = adapters
        self.ledger = ledger

    def adapter(self, contract_digest):
        adapter = self._adapters.get(contract_digest)
        if adapter is None:
            raise KeyError("contract_not_served")
        return adapter

    def score_record(self, contract_digest, submission_id):
        adapter = self.adapter(contract_digest)
        return {
            "schema": SCORE_RECORD_SCHEMA,
            "audience": "OPERATOR_ONLY",
            "evidence": "DEVELOPMENT",
            "pinned": adapter.pinned(),
            "identities": adapter.identities(),
            "record": adapter.score_record(submission_id),
        }

    def prepare_batch(self, contract_digest, role, *, kind, **options):
        adapter = self.adapter(contract_digest)
        try:
            return adapter.prepare_batch(role, kind=kind, **options)
        except ReservedRole as refused:
            self.ledger.record_operator_refusal(
                "prepare_batch", refused.code, contract_digest
            )
            raise

    def reference_jobs(self, contract_digest, fingerprint):
        return self.adapter(contract_digest).reference_jobs(fingerprint)

    def ingest_references(self, contract_digest, fingerprint, records):
        return self.adapter(contract_digest).ingest_references(fingerprint, records)

    def open_pool(self, contract_digest):
        return self.adapter(contract_digest).open_pool()

    def advance(self):
        return {d: self.adapter(d).advance() for d in self._adapters.digests()}

    def status(self):
        return {
            d: {
                "pinned": self.adapter(d).pinned(),
                "disclosure_budget": self.adapter(d).disclosure_budget(),
                "status": self.adapter(d).status(),
            }
            for d in self._adapters.digests()
        }

    def attempt_counts(self, hotkey):
        return self.ledger.attempt_counts(hotkey)


__all__ = [
    "RESULT_SCHEMA",
    "SCORE_RECORD_SCHEMA",
    "Adapters",
    "Operator",
    "Validator",
]
