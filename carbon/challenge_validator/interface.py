"""The challenge-neutral validator contract (VALIDATOR-01).

A Challenge joins the validator by supplying one `ChallengeAdapter` per
registered construction contract. The adapter owns everything specific to
the Challenge: its frozen exam rule, its reconstruction backend, its reference
records and its allow-listed miner outcome. The validator owns what is the
same for every Challenge:
- strict parsing of the submission bytes;
- dispatch by construction-contract digest, with a typed refusal for any
  digest it doesn't serve;
- the outcome contract every adapter's miner outcome must satisfy;
- the pinned identities every result carries;
- the reserved seed roles no adapter may prepare;
- the operator-side refusal and attempt ledger.

None of this is scientific, security, network or production qualification.
Every result is DEVELOPMENT evidence: no weights, rewards or chain action
(OD-4b).
"""

from __future__ import annotations

import abc
import hashlib
import json
import re
from dataclasses import dataclass

#: Submission states an adapter's miner outcome may report. Infrastructure
#: states are never scores (invariant 7).
STATES = (
    "ADMITTED",
    "RECONSTRUCTED",
    "SCORED",
    "INVALID_CONSTRUCTION",
    "RECONSTRUCTION_FAILED",
    "FAILED_INFRA",
    "FAILED_INFRA_EXHAUSTED",
)
TERMINAL_STATES = frozenset(
    {
        "SCORED",
        "INVALID_CONSTRUCTION",
        "RECONSTRUCTION_FAILED",
        "FAILED_INFRA_EXHAUSTED",
    }
)
#: Keys every miner outcome carries, whatever the Challenge.
OUTCOME_REQUIRED = (
    "schema",
    "submission_id",
    "challenge",
    "state",
    "evidence",
    "qualification",
    "reward",
)
#: Seed roles whose batches are sealed for a study. Preparing a batch under
#: one regenerates the sealed batch, because a batch's key derives from its
#: role. The list grows by record, never by an adapter:
#: - `ev5-confirmation`: EV5's confirmation set, journal sequence 14
#:   (OWNER-EV5-FREEZE-01);
#: - `graphite-confirmation-v1`: battery's Graphite confirmation set
#:   (OWNER-GRAPHITE-TEST-WAVE-01 item 6).
RESERVED_SEED_ROLES = frozenset({"ev5-confirmation", "graphite-confirmation-v1"})

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def canonical_role(role):
    """A seed role as its draws are keyed: lower-cased, since battery derives a
    batch's inputs from `RoleKey(role.lower())`. Two spellings with one
    canonical form draw the same cases, so every reserved or sealed check
    compares canonical forms. None for a non-string."""
    return role.lower() if type(role) is str else None


def role_reserved(role, sealed=()):
    """Whether `role` is reserved, or sealed outside the pool (`sealed`), in
    any spelling."""
    canonical = canonical_role(role)
    return canonical in RESERVED_SEED_ROLES or canonical in {
        canonical_role(r) for r in sealed
    }


def digest(value):
    """`sha256:` over the canonical JSON of `value`."""
    body = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def is_digest(value):
    return type(value) is str and DIGEST.fullmatch(value) is not None


@dataclass(frozen=True)
class Submission:
    """One submission as an authenticating transport received it.

    `hotkey` is the identity the transport verified, never a field the miner
    typed. `strategy_json` is the strategy exactly as received (str or bytes);
    the validator parses it strictly before any adapter sees it.
    """

    hotkey: str
    receipt: dict
    challenge_id: str
    challenge_version: str
    strategy_json: str | bytes
    contract_digest: str


@dataclass(frozen=True)
class Admitted:
    """A submission that passed the validator's checks, handed to an adapter."""

    hotkey: str
    receipt: dict
    challenge_id: str
    challenge_version: str
    strategy: dict
    contract_digest: str


class Unavailable(RuntimeError):
    """The adapter cannot take this submission now. It is not recorded against
    the miner and is never a score: a missing chain commitment, a backend this
    validator does not serve, a used scoring window.

    `retry` carries only public scheduling facts (for example `next_block`).
    """

    def __init__(self, code, *, retry=None):
        super().__init__(code)
        self.code = code
        self.retry = dict(retry or {})


class ReservedRole(PermissionError):
    """A seed role that is reserved or already sealed outside the pool."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class OutcomeContractViolation(RuntimeError):
    """An adapter returned a miner outcome outside the outcome contract."""


class ChallengeAdapter(abc.ABC):
    """One registered construction contract's validator.

    Subclasses set `challenge_id`, `challenge_version`, `contract_digest`,
    `max_strategy_bytes` and `disclosure_fields`, and implement the abstract
    methods. One instance serves exactly one contract digest.
    """

    challenge_id: str
    challenge_version: str
    contract_digest: str
    #: An engineering admission limit on the strategy's bytes, not a
    #: scientific value.
    max_strategy_bytes: int
    #: Miner-outcome keys this adapter may return beyond `OUTCOME_REQUIRED`
    #: and `failure`.
    disclosure_fields: frozenset = frozenset()

    # --- identities ---------------------------------------------------------

    @abc.abstractmethod
    def identities(self):
        """The pinned material identities this adapter evaluates under.

        Must include `contract_digest`, `rule_digest` and
        `implementation_digest`. Never a private value.
        """

    def pinned(self):
        """What every result carries: the three named digests and a digest of
        the whole identity document."""
        identities = self.identities()
        return {
            "contract_digest": identities["contract_digest"],
            "rule_digest": identities["rule_digest"],
            "implementation_digest": identities["implementation_digest"],
            "identities_digest": digest(identities),
        }

    def disclosure_budget(self):
        """The disclosure budget this Challenge's rule declares, or None.

        The validator records attempts per hotkey; it never invents a budget.
        """

    # --- miner side ---------------------------------------------------------

    @abc.abstractmethod
    def evaluate(self, submission):
        """Admit and advance one `Admitted` submission; return its outcome.

        May raise `Unavailable`. A refused construction is an outcome
        (`INVALID_CONSTRUCTION`), not an exception.
        """

    @abc.abstractmethod
    def outcome(self, submission_id):
        """The allow-listed miner outcome for one submission."""

    @abc.abstractmethod
    def owner(self, submission_id):
        """The hotkey that submitted `submission_id`, or None if unknown."""

    @abc.abstractmethod
    def advance(self):
        """Advance every queued submission; return how many moved."""

    # --- operator side ------------------------------------------------------

    @abc.abstractmethod
    def score_record(self, submission_id):
        """The operator-only score record: per-case predictions, errors and
        gate verdicts, and the rule and identity digests. Never miner-facing.
        """

    @abc.abstractmethod
    def sealed_roles(self):
        """Seed roles already committed for a batch that is outside the pool."""

    def prepare_batch(self, role, *, kind, **options):
        """Prepare one private batch, refusing reserved and sealed roles."""
        if type(role) is not str or not role:
            raise ReservedRole("seed_role_malformed")
        if role_reserved(role):
            raise ReservedRole("seed_role_reserved")
        if role_reserved(role, self.sealed_roles()):
            raise ReservedRole("seed_role_sealed")
        return self._prepare_batch(role, kind=kind, **options)

    @abc.abstractmethod
    def _prepare_batch(self, role, *, kind, **options):
        """Prepare a batch under a role `prepare_batch` has cleared."""

    @abc.abstractmethod
    def reference_jobs(self, fingerprint):
        """What the truth service must solve for a batch."""

    @abc.abstractmethod
    def ingest_references(self, fingerprint, records):
        """Store reference records; return whether the batch is complete."""

    @abc.abstractmethod
    def open_pool(self):
        """Open the scoring pool once its batches are ready."""

    @abc.abstractmethod
    def status(self):
        """Counts and identities only."""


def check_outcome(outcome, adapter):
    """Raise `OutcomeContractViolation` unless `outcome` meets the contract."""

    def fail(why):
        raise OutcomeContractViolation(why)

    if type(outcome) is not dict:
        fail("outcome is not an object")
    missing = [k for k in OUTCOME_REQUIRED if k not in outcome]
    if missing:
        fail("outcome lacks " + ",".join(missing))
    extra = (
        set(outcome)
        - set(OUTCOME_REQUIRED)
        - {"failure"}
        - set(adapter.disclosure_fields)
    )
    if extra:
        fail("outcome field outside the disclosure allow-list")
    if outcome["state"] not in STATES:
        fail("unknown outcome state")
    if type(outcome["evidence"]) is not str or not outcome["evidence"].startswith(
        "DEVELOPMENT"
    ):
        fail("outcome evidence is not DEVELOPMENT")
    if outcome["qualification"] is not False or outcome["reward"] is not False:
        fail("outcome claims qualification or reward")
    if outcome["challenge"] != {
        "id": adapter.challenge_id,
        "version": adapter.challenge_version,
    }:
        fail("outcome names another challenge")
    if "failure" in outcome:
        failure = outcome["failure"]
        if type(failure) is not dict or set(failure) - {"code", "issues"}:
            fail("outcome failure outside {code, issues}")
    try:
        json.dumps(outcome, allow_nan=False)
    except (TypeError, ValueError):
        fail("outcome is not finite JSON")
    return outcome


__all__ = [
    "OUTCOME_REQUIRED",
    "RESERVED_SEED_ROLES",
    "STATES",
    "TERMINAL_STATES",
    "Admitted",
    "ChallengeAdapter",
    "OutcomeContractViolation",
    "ReservedRole",
    "Submission",
    "Unavailable",
    "canonical_role",
    "check_outcome",
    "digest",
    "is_digest",
    "role_reserved",
]
