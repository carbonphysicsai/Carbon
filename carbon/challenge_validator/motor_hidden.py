"""Motor's hidden pool on validators (VALIDATOR-21; OWNER-MOTOR-HIDDEN-POOL-01).

Carbon's producer draws and solves each hidden motor batch once
(`motor_source.MotorBatchSource`). A validator only imports it through the
answer key, and scores recipes on it with motor's existing exam, unchanged:
- **the hidden rule** (`hidden_rule`), pinned by digest into every
  commitment: the existing exam rule, the population, the pinned solver
  image, which reference statuses are terminal, and the owner's cadence,
  batch size and per-hotkey cap;
- **import** (`import_answer_key`) verifies identities, window, document,
  fingerprint, every reference and the references digest, and refuses a
  published case, before anything is stored;
- **evaluate** scores a recipe on every hidden screening batch active at the
  request's finalized block (`receipt.block`). When no window covers that
  block, the latest active batches keep scoring. A case whose reference
  failed is counted and excluded by `exam.aggregate`, never charged to the
  candidate. With no batch imported, it returns `Unavailable`, never a
  score.

The miner outcome is the allow-listed summary only. Case ids, inputs,
references and per-case rows stay in the operator score record.

    python -m carbon.challenge_validator.motor_hidden init --deployment DEPLOYMENT.json
    python -m carbon.challenge_validator.motor_hidden status --deployment DEPLOYMENT.json [--block N]

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import stat
import sys
from pathlib import Path

from .hidden_batch_store import HiddenBatchStore, HotkeyWindowUsed, references_digest
from .interface import Admitted, CandidateFault, Unavailable, digest
from .motor import (
    MotorAdapter,
    MotorAdapterError,
    implementation_digest,
    rule_document,
)

REPOSITORY = Path(__file__).resolve().parents[2]
RULE_SCHEMA = "carbon.motor.hidden-pool-rule.v1"
DOCUMENT_SCHEMA = "carbon.motor.hidden-batch.v1"
DEPLOYMENT_SCHEMA = "carbon.motor.hidden-deployment.v1"
STORE_SCHEMA = "carbon.motor.hidden-store.v1"
SCORE_RECORD_SCHEMA = "carbon.motor.hidden-score-record.v1"
EVIDENCE = "DEVELOPMENT_HIDDEN_POOL"
AUTHORITY = "OWNER-MOTOR-HIDDEN-POOL-01"
#: The published reference image (OWNER-DATA-MOTOR-01), by digest only.
SOLVER_IMAGE = (
    "ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:"
    "599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05"
)
#: Every reference outcome that ends a case. `FAILED_INFRA` does not: it is
#: retried on the producer, never stored. Only `OK` is scored; the others
#: are counted by `exam.aggregate` and never charged to a candidate (§7.5).
TERMINAL = ("OK", "REFERENCE_INVALID", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")
#: The owner's values (OWNER-MOTOR-HIDDEN-POOL-01), mirroring battery rule v2.
#: Motor has no finals: screening batches only.
KINDS = ("screening",)
ROTATION_EVERY_BLOCKS = 1080
ACTIVE_BATCHES = 3
BATCH_CASES = 30
HOTKEY_WINDOW_BLOCKS = 360
HOTKEY_WINDOW_SCORED = 1


def hidden_rule(material):
    """The hidden pool's rule document; its digest is every commitment's
    `rule_digest`."""
    from carbon.motor.population import POPULATION_VERSION

    from .motor import CHALLENGE

    return {
        "schema": RULE_SCHEMA,
        "authority": AUTHORITY,
        "status": "PROVISIONAL_DEVELOPMENT_NON_QUALIFYING",
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "exam": rule_document(material),
        "population": {
            "version": POPULATION_VERSION,
            "law": "uniform",
            "q_equals_p": True,
        },
        "solver_image": SOLVER_IMAGE,
        "references": {"terminal": list(TERMINAL), "scored": ["OK"]},
        "kinds": list(KINDS),
        "hidden_duplicates": 0,
        "batch_cases": BATCH_CASES,
        "rotation": {"basis": "finalized_block", "every_blocks": ROTATION_EVERY_BLOCKS},
        "active_batches": ACTIVE_BATCHES,
        "per_hotkey": {
            "window_blocks": HOTKEY_WINDOW_BLOCKS,
            "scored": HOTKEY_WINDOW_SCORED,
        },
    }


# --- documents and references ---------------------------------------------------------


def _finite(value):
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def check_document(document):
    """A hidden batch document's shape and admissibility. Returns
    `{case_id: inputs}`; raises ValueError."""
    from carbon.motor.domain import INPUTS
    from carbon.motor.population import admitted

    from .motor import CHALLENGE

    if (
        type(document) is not dict
        or set(document)
        != {"schema", "challenge", "role", "kind", "population", "cases"}
        or document["schema"] != DOCUMENT_SCHEMA
        or document["challenge"]
        != {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version}
        or type(document["role"]) is not str
        or document["kind"] not in KINDS
        or type(document["cases"]) is not list
        or not document["cases"]
    ):
        raise ValueError("document")
    cases = {}
    for case in document["cases"]:
        if (
            type(case) is not dict
            or set(case) != {"case_id", "inputs"}
            or type(case["case_id"]) is not str
            or case["case_id"] in cases
            or type(case["inputs"]) is not dict
            or set(case["inputs"]) != set(INPUTS)
            or not all(_finite(v) for v in case["inputs"].values())
            or not admitted(case["inputs"])
        ):
            raise ValueError("case")
        cases[case["case_id"]] = case["inputs"]
    return cases


def check_reference(record, inputs):
    """One terminal reference record for a case with `inputs`. An `OK`
    record carries a finite torque curve of the exam's length. Raises
    ValueError."""
    from carbon.motor.domain import ANGLE_STEPS

    if (
        type(record) is not dict
        or record.get("status") not in TERMINAL
        or record.get("inputs") != inputs
        or record.get("image") != SOLVER_IMAGE
    ):
        raise ValueError("reference")
    if record["status"] == "OK":
        outputs = record.get("outputs")
        torque = outputs.get("torque_nm") if type(outputs) is dict else None
        if (
            type(torque) is not list
            or len(torque) != ANGLE_STEPS
            or not all(_finite(t) for t in torque)
        ):
            raise ValueError("reference")


def published_keys(repository):
    """Every published motor case, as overlap keys."""
    from .confirmation_sources import source_for
    from .motor import CHALLENGE

    return source_for(CHALLENGE.challenge_id).published(repository)


def overlap_key(inputs):
    from .confirmation_sources import source_for
    from .motor import CHALLENGE

    return source_for(CHALLENGE.challenge_id).key(inputs)


# --- the deployment -------------------------------------------------------------------


def load_deployment(path):
    """`{"schema", "store"}` for a validator, plus `"custody"` for the
    producer. Owner-only, exact keys."""
    path = Path(path)
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise MotorAdapterError("motor_hidden_deployment_not_owner_only")
        config = json.loads(path.read_text())
    except FileNotFoundError:
        raise MotorAdapterError("motor_hidden_deployment_missing") from None
    except ValueError:
        raise MotorAdapterError("motor_hidden_deployment_malformed") from None
    if (
        type(config) is not dict
        or config.get("schema") != DEPLOYMENT_SCHEMA
        or not {"schema", "store"} <= set(config)
        or set(config) - {"schema", "store", "custody"}
        or not all(type(v) is str and v for v in config.values())
    ):
        raise MotorAdapterError("motor_hidden_deployment_malformed")
    return config


def hidden_implementation_digest():
    """The motor adapter's own pin, plus this module and the hidden store."""
    import hashlib

    from . import hidden_batch_store

    files = {"motor_hidden": Path(__file__), "store": Path(hidden_batch_store.__file__)}
    return digest(
        {
            "base": implementation_digest(),
            "files": {
                name: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                for name, path in sorted(files.items())
            },
        }
    )


def open_store(directory):
    return HiddenBatchStore(
        directory, name="motor", schema=STORE_SCHEMA, error_type=MotorAdapterError
    )


# --- the validator --------------------------------------------------------------------


class MotorHiddenAdapter(MotorAdapter):
    """Motor's validator on producer batches, behind Interface v1. It never
    draws or solves: batches arrive only through the answer key."""

    def __init__(self, store_root, *, repository=REPOSITORY):
        from carbon.motor.challenge import PublicMaterial

        from .candidate_fault import load_policy

        self.repository = Path(repository)
        self.material = PublicMaterial.load(self.repository)
        self.candidate_fault_policy = load_policy(self.challenge_id)
        if self.candidate_fault_policy.challenge_version != self.challenge_version:
            raise MotorAdapterError("candidate_fault_policy_version_mismatch")
        self.store = open_store(store_root)
        self.rule = hidden_rule(self.material)
        self._identities = {
            "schema": "carbon.motor.hidden-validator-adapter.v1",
            "contract_digest": self.contract_digest,
            "rule_digest": digest(self.rule),
            "implementation_digest": hidden_implementation_digest(),
            "candidate_fault_policy_digest": self.candidate_fault_policy.digest,
            "evidence": EVIDENCE,
        }
        self._published = None

    @classmethod
    def from_deployment(cls, path, *, repository=REPOSITORY):
        return cls(load_deployment(path)["store"], repository=repository)

    def _outcome(self, submission_id, state, *, failure=None, summary=None):
        outcome = super()._outcome(
            submission_id, state, failure=failure, summary=summary
        )
        outcome["evidence"] = EVIDENCE
        return outcome

    @staticmethod
    def _block(submission):
        block = submission.receipt.get("block")
        if type(block) is not int or block < 0:
            raise Unavailable("receipt_block_missing")
        return block

    def _hotkey_window(self, block):
        start = block - block % HOTKEY_WINDOW_BLOCKS
        return start, start + HOTKEY_WINDOW_BLOCKS, HOTKEY_WINDOW_SCORED

    def evaluate(self, submission):
        from carbon.development_session.research_catalog import RecipeRejected
        from carbon.motor import exam
        from carbon.motor.compile import compile_recipe, rebuild

        from .scoring import cover

        if type(submission) is not Admitted:
            raise TypeError("an admitted submission is required")
        block = self._block(submission)
        submission_id = self._submission_id(submission)
        existing = self.store.submission(submission_id)
        if existing is not None:
            return existing["outcome"]
        active = self.store.latest_active(block)
        if not active:
            raise Unavailable("motor_hidden_pool_not_open")
        window = self._hotkey_window(block)
        if self.store.used(submission.hotkey, window[0], window[1]) >= window[2]:
            raise Unavailable("hotkey_window_used", retry={"next_block": window[1]})
        try:
            _compiled, recipe = compile_recipe(submission.strategy)
        except RecipeRejected as refused:
            outcome = self._outcome(
                submission_id,
                "INVALID_CONSTRUCTION",
                failure={"code": "recipe_rejected", "issues": self._issues(refused)},
            )
            # An invalid construction does not use the hotkey's window.
            self.store.record_submission(
                submission_id,
                submission.hotkey,
                submission.strategy,
                outcome,
                None,
                block=block,
            )
            return outcome
        references = {}
        for fingerprint in active:
            references.update(self.store.references(fingerprint))
        try:
            model = rebuild(recipe, self.material)
        except Exception as fault:
            raise CandidateFault(
                "rebuild_exception", self.candidate_fault_policy
            ) from fault
        try:
            predictions = {
                case_id: model.predict(record["inputs"])
                for case_id, record in sorted(references.items())
            }
        except Exception as fault:
            raise CandidateFault(
                "predict_exception", self.candidate_fault_policy
            ) from fault
        scales = exam.scales_from_train(self.material.train)
        asked, missing = cover(predictions, sorted(references))
        rows = [
            exam.score_case(asked[case_id], references[case_id], scales)
            for case_id in sorted(references)
        ]
        summary = {**exam.aggregate(rows), "n_missing": len(missing)}
        try:
            json.dumps(
                {"predictions": predictions, "cases": rows, "aggregate": summary},
                allow_nan=False,
            )
        except (TypeError, ValueError) as fault:
            raise CandidateFault(
                "non_finite_score", self.candidate_fault_policy
            ) from fault
        outcome = self._outcome(submission_id, "SCORED", summary=summary)
        score_record = {
            "schema": SCORE_RECORD_SCHEMA,
            "submission_id": submission_id,
            "block": block,
            "batches": active,
            "rule_digest": self._identities["rule_digest"],
            "implementation_digest": self._identities["implementation_digest"],
            "recipe": recipe.document(),
            "recipe_digest": recipe.recipe_digest,
            "aggregate": summary,
            "cases": rows,
            "predictions": predictions,
        }
        try:
            self.store.record_submission(
                submission_id,
                submission.hotkey,
                submission.strategy,
                outcome,
                score_record,
                block=block,
                window=window,
            )
        except HotkeyWindowUsed as used:
            raise Unavailable(
                "hotkey_window_used", retry={"next_block": used.next_block}
            ) from None
        return outcome

    # --- the validator never draws or solves ------------------------------------

    def sealed_roles(self):
        return set()

    def _prepare_batch(self, role, *, kind, **options):
        raise MotorAdapterError("motor_hidden_import_only")

    def reference_jobs(self, fingerprint):
        raise MotorAdapterError("motor_hidden_import_only")

    def ingest_references(self, fingerprint, records):
        raise MotorAdapterError("motor_hidden_import_only")

    def open_pool(self):
        raise MotorAdapterError("motor_hidden_import_only")

    def status(self, block=None):
        return {
            "schema": STORE_SCHEMA,
            "evidence": EVIDENCE,
            **self.store.status(block),
        }

    # --- the answer key -----------------------------------------------------------

    def holds_answer_key(self, commitment):
        try:
            batch = self.store.batch(commitment["fingerprint"])
        except MotorAdapterError:
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
        except MotorAdapterError as refused:
            raise AnswerKeyRefused(
                "answer_key_" + refused.code.removeprefix("motor_")
            ) from None

    def import_answer_key(self, commitment, payload):
        """Import one producer batch, verified in full first:
        - the commitment's contract and rule are this validator's;
        - the window is well formed;
        - the document is a motor hidden batch of admissible cases, and it
          reproduces the committed fingerprint, role, kind and case count;
        - no case repeats a published motor case;
        - the references are exactly the batch's cases, each terminal, for
          its own inputs, from the pinned image, and digest to the committed
          references digest.
        Only then is it stored, with its window."""
        from .answer_key import AnswerKeyRefused

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
            cases = check_document(document)
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
            self._published = published_keys(self.repository)
        if any(overlap_key(inputs) in self._published for inputs in cases.values()):
            raise AnswerKeyRefused("answer_key_published_case")
        if type(references) is not dict or set(references) != set(cases):
            raise AnswerKeyRefused("answer_key_references_mismatch")
        try:
            for case_id, record in references.items():
                if record.get("case_id") != case_id:
                    raise ValueError
                check_reference(record, cases[case_id])
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
                fingerprint, list(references.values()), terminal=TERMINAL
            )
            self.store.set_window(fingerprint, window)
        except MotorAdapterError as refused:
            raise AnswerKeyRefused(
                "answer_key_" + refused.code.removeprefix("motor_")
            ) from None
        if not complete or not self.holds_answer_key(commitment):
            raise AnswerKeyRefused("answer_key_references_mismatch")
        return fingerprint


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.motor_hidden")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").add_argument("--deployment", required=True)
    status = sub.add_parser("status")
    status.add_argument("--deployment", required=True)
    status.add_argument("--block", type=int)
    args = parser.parse_args(argv)
    try:
        adapter = MotorHiddenAdapter.from_deployment(args.deployment)
        if args.command == "init":
            result = {"identities": adapter.identities(), **adapter.status()}
        else:
            result = adapter.status(args.block)
    except MotorAdapterError as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    import sys

    from carbon.challenge_validator.motor_hidden import main as _main

    sys.exit(_main())


__all__ = [
    "DOCUMENT_SCHEMA",
    "EVIDENCE",
    "SOLVER_IMAGE",
    "TERMINAL",
    "MotorHiddenAdapter",
    "check_document",
    "check_reference",
    "hidden_rule",
    "load_deployment",
    "open_store",
]
