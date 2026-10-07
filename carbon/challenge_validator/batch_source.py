"""The producer's Challenge-neutral contract (VALIDATOR-19): the batch
source interface, the commitment's schema and served kinds, and the quiz's
committed digests.

Kept apart from `producer` so a validator surface (the battery adapter, the
answer-key import) depends on this contract only, never on the producer's
own module and what it may load. DEVELOPMENT only: no qualification, weight,
reward or LIVE authority.
"""

from __future__ import annotations

import abc
import hashlib
import json

COMMITMENT_SCHEMA = "carbon.challenge-validator.batch-commitment.v1"

#: Batch kinds a validator scores with. Producer-only sets (tuning,
#: confirmation) are sealed by their own tools and never drawn here.
SERVED_KINDS = ("screening", "finalist")


class ProducerRefused(ValueError):
    """A typed refusal; its code carries no private case, input or output."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


# --- one Challenge's batches ----------------------------------------------------------


class BatchSource(abc.ABC):
    """One Challenge's batches, as the producer drives them.

    Subclasses set `challenge_id`. Every method takes and returns public
    values, except `jobs`, whose cases go only to the truth solves.
    """

    challenge_id: str

    @abc.abstractmethod
    def identities(self):
        """Public identities every commitment binds: `contract_digest`,
        `rule_digest` and `seed_pin`."""

    @abc.abstractmethod
    def draw(self, role, *, kind, size=None):
        """Draw and journal-commit one batch (idempotent by role); return its
        fingerprint."""

    @abc.abstractmethod
    def jobs(self, fingerprint):
        """The distinct cases the truth solves need. Private."""

    @abc.abstractmethod
    def solve(self, work, **options):
        """Run the pinned truth solves of `work/jobs.json` into
        `work/records.jsonl`."""

    @abc.abstractmethod
    def ingest(self, fingerprint, records):
        """Store terminal reference records; return whether the batch is
        complete. Refuses (`producer_references_changed`) when a stored record
        no longer matches the digest it completed with."""

    @abc.abstractmethod
    def sealed(self, fingerprint):
        """The batch's public identity once its references are complete:
        `role`, `kind`, `journal_sequence`, `cases` and `references_digest`.
        None while any reference is pending."""

    def kinds(self):
        """The served kinds this Challenge's validators use. The producer
        draws and rotates only these: a Challenge without finals is never
        given finalist batches it would solve and never score."""
        return SERVED_KINDS

    def cadence(self):
        """`{"every_blocks", "active"}` from the Challenge's own registered
        rule, or None: then no batch is scheduled (the cadence is
        HUMAN_INPUT until the rule names one)."""
        return

    @abc.abstractmethod
    def export(self, fingerprint):
        """A sealed batch's payload for its answer-key package: the batch
        document and its reference records. Private."""

    @abc.abstractmethod
    def check(self, fingerprint):
        """Refuse unless the stored batch still matches its seed-journal
        commitment. Raises `ProducerRefused`."""

    # --- the quiz (slice Q, part 2); a source without one keeps the defaults ---

    def quiz_draw(self, fingerprint, round_):
        """Round `round_` of a screening batch's quiz draws, from the batch's
        own role: a private, deterministic value. A later round extends an
        earlier one. Refused (`producer_quiz_unsupported`) by a source with
        no quiz."""
        raise ProducerRefused("producer_quiz_unsupported")

    def quiz_jobs(self, draws):
        """The truth solves `draws` need, shaped as `jobs`. Private."""
        raise ProducerRefused("producer_quiz_unsupported")

    def quiz_select(self, draws, records, *, panel, cache):
        """The quiz from its solved draws: `{"document", "references"}`; or
        `{"next_round": N}` when round N must be drawn and solved first; or
        `{"refine": jobs}` when these further solves (shaped as `jobs`) must
        be solved first; or
        `{"pending": code}` when it cannot be selected yet (unsolved, or the
        panel's infrastructure failed). `panel` is the configured panel file
        and `cache` an owner-only directory the source may keep its panel
        in. The document must carry `panel_version`. Private."""
        raise ProducerRefused("producer_quiz_unsupported")


def _canonical_digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def quiz_digests(quiz):
    """A quiz's committed digests, over its document and its references, as
    the producer computes them and every validator re-derives them."""
    return {
        "quiz_digest": _canonical_digest(quiz["document"]),
        "quiz_references_digest": _canonical_digest(quiz["references"]),
    }


#: The quiz commitment fields: all three, or none (a batch without a quiz).
QUIZ_COMMITMENT_FIELDS = ("quiz_digest", "quiz_references_digest", "quiz_panel_version")
