"""The import-only half of a reference family's validator (VALIDATOR-28).

A family's hidden batches are drawn and solved once on Carbon's producer
(`family_source`, producer-only) and reach a validator only through the
answer key. What a validator does with them before scoring is the same for
every family, so it lives here, generalized from motor's (VALIDATOR-21):

- **import** (`import_answer_key`) verifies, before anything is stored:
  the commitment's contract and rule are this validator's; the window is
  well formed; the document is the family's hidden batch of admissible cases
  and reproduces the committed fingerprint, role, kind and case count; no
  case repeats a published case; and the references are exactly the batch's
  cases, each terminal, for its own inputs, checked by the family, and
  digest to the committed references digest;
- **holds, withdraws and status**, over the family's hidden batch store;
- **never draws or solves**: every producer path is refused.

Scoring (`evaluate`) stays the family's own adapter's. A family's adapter
mixes this in ahead of its base adapter and names its `HiddenFamily`.
This is a validator module: it imports nothing producer-side.
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .hidden_batch_store import references_digest
from .interface import Unavailable, digest


@dataclass(frozen=True)
class HiddenFamily:
    """A family's validator-side values. No defaults: each is the family's."""

    #: Short name: the prefix of the family's error codes.
    name: str
    store_schema: str
    evidence: str
    terminal: tuple
    #: The family's errors (`code` starting `<name>_`).
    error_type: type
    #: Per-hotkey cap: at most `window_scored` scored submissions in each
    #: `window_blocks` of finalized blocks.
    window_blocks: int
    window_scored: int
    check_document: Callable[[dict], dict]
    check_reference: Callable[[dict, dict], None]
    published_keys: Callable[..., set]
    overlap_key: Callable[[dict], object]


class FamilyHiddenImport:
    """Mixed in ahead of a family's base adapter, which sets `hidden` (its
    `HiddenFamily`), `store` (its hidden batch store) and `repository`."""

    hidden: HiddenFamily

    def _refused(self, code):
        return self.hidden.error_type(f"{self.hidden.name}_{code}")

    def _answer_key_code(self, refused):
        return "answer_key_" + refused.code.removeprefix(self.hidden.name + "_")

    def _outcome(self, submission_id, state, *, failure=None, summary=None):
        outcome = super()._outcome(
            submission_id, state, failure=failure, summary=summary
        )
        outcome["evidence"] = self.hidden.evidence
        return outcome

    @staticmethod
    def _block(submission):
        block = submission.receipt.get("block")
        if type(block) is not int or block < 0:
            raise Unavailable("receipt_block_missing")
        return block

    def _hotkey_window(self, block):
        blocks = self.hidden.window_blocks
        start = block - block % blocks
        return start, start + blocks, self.hidden.window_scored

    # --- the validator never draws or solves ------------------------------------

    def sealed_roles(self):
        return set()

    def _prepare_batch(self, role, *, kind, **options):
        raise self._refused("hidden_import_only")

    def reference_jobs(self, fingerprint):
        raise self._refused("hidden_import_only")

    def ingest_references(self, fingerprint, records):
        raise self._refused("hidden_import_only")

    def open_pool(self):
        raise self._refused("hidden_import_only")

    def status(self, block=None):
        return {
            "schema": self.hidden.store_schema,
            "evidence": self.hidden.evidence,
            **self.store.status(block),
        }

    # --- the answer key -----------------------------------------------------------

    def holds_answer_key(self, commitment):
        try:
            batch = self.store.batch(commitment["fingerprint"])
        except self.hidden.error_type:
            return False
        return (
            batch["state"] == "COMPLETE"
            and batch["references_digest"] == commitment["references_digest"]
            and self.store.complete_digest(commitment["fingerprint"])
            == commitment["references_digest"]
            and self.store.window(commitment["fingerprint"]) == commitment.get("window")
        )

    def withdraw_answer_key(self, manifest):
        """Apply a verified producer withdrawal (VALIDATOR-24)."""
        from .answer_key import AnswerKeyRefused

        try:
            return self.store.withdraw(
                manifest["fingerprint"], manifest["reason"], manifest["block"]
            )
        except self.hidden.error_type as refused:
            raise AnswerKeyRefused(self._answer_key_code(refused)) from None

    def import_answer_key(self, commitment, payload):
        """Import one producer batch, verified in full first (the module
        docstring lists every check). Only then is it stored, with its
        window."""
        from .answer_key import AnswerKeyRefused

        hidden = self.hidden
        identities = self.identities()
        if (
            commitment["contract_digest"] != identities["contract_digest"]
            or commitment["rule_digest"] != identities["rule_digest"]
        ):
            raise AnswerKeyRefused("answer_key_identity_mismatch")
        if self.store.withdrawn(commitment["fingerprint"]):
            raise AnswerKeyRefused("answer_key_withdrawn")
        window = commitment.get("window")
        if (
            type(window) is not dict
            or set(window) != {"slot", "activate_block", "retire_block"}
            or any(type(v) is not int or v < 0 for v in window.values())
            or window["activate_block"] >= window["retire_block"]
        ):
            raise AnswerKeyRefused("answer_key_no_window")
        if type(payload) is not dict or set(payload) != {"document", "references"}:
            raise AnswerKeyRefused("answer_key_malformed")
        document, references = payload["document"], payload["references"]
        try:
            cases = hidden.check_document(document)
        except ValueError:
            raise AnswerKeyRefused("answer_key_malformed") from None
        if (
            digest(document) != commitment["fingerprint"]
            or len(cases) != commitment["cases"]
            or document["role"] != commitment["role"]
            or document["kind"] != commitment["kind"]
        ):
            raise AnswerKeyRefused("answer_key_fingerprint_mismatch")
        if self._published is None:
            self._published = hidden.published_keys(self.repository)
        if any(
            hidden.overlap_key(inputs) in self._published for inputs in cases.values()
        ):
            raise AnswerKeyRefused("answer_key_published_case")
        if type(references) is not dict or set(references) != set(cases):
            raise AnswerKeyRefused("answer_key_references_mismatch")
        try:
            for case_id, record in references.items():
                if record.get("case_id") != case_id:
                    raise ValueError
                hidden.check_reference(record, cases[case_id])
        except (AttributeError, ValueError):
            raise AnswerKeyRefused("answer_key_references_mismatch") from None
        if references_digest(references) != commitment["references_digest"]:
            raise AnswerKeyRefused("answer_key_references_mismatch")
        try:
            fingerprint = self.store.add(
                document,
                role=document["role"],
                kind=document["kind"],
                sequence=commitment["journal_sequence"],
            )
            complete = self.store.ingest(
                fingerprint, list(references.values()), terminal=hidden.terminal
            )
            self.store.set_window(fingerprint, window)
        except hidden.error_type as refused:
            raise AnswerKeyRefused(self._answer_key_code(refused)) from None
        if not complete or not self.holds_answer_key(commitment):
            raise AnswerKeyRefused("answer_key_references_mismatch")
        return fingerprint


__all__ = ["FamilyHiddenImport", "HiddenFamily"]
