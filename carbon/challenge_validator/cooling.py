"""Cooling's public DEVELOPMENT `ChallengeAdapter` (Interface v1).

This adapter wraps existing Cooling authority. It does not define a new
population, gate, scale, recipe or reference:

- construction is the registered Level-0 cold-plate compiler and deterministic
  Gaussian kernel-ridge rebuild;
- the only preparable batch is the digest-pinned public PRACTICE artifact;
- reference ingestion accepts only a record equal to that pinned artifact;
- scoring is `carbon.cold_plate.exam`, using its TRAIN-derived scales, with
  every case asked (`scoring.cover`: a case the construction gives no
  prediction is a schema-gate failure charged to it, never FAILED_INFRA and
  never excluded; GRAPHITE-COVERAGE-PARITY-02); and
- miner disclosure is a small aggregate outcome. Cases, predictions, gates,
  recipes and full identities remain operator-only.

The evidence is public, adaptive DEVELOPMENT evidence. The reserved Cooling
Graphite confirmation role has no set here. Nothing in this module prepares,
loads or scores private/counting/confirmation evidence, and nothing confers
qualification, reward, customer acceptance or LIVE authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.cold_plate import exam
from carbon.cold_plate.challenge import (
    CALIBRATION_SHA256,
    CHALLENGE,
    PRACTICE_SHA256,
    TRAIN_SHA256,
    PublicMaterial,
)
from carbon.cold_plate.compile import compile_recipe, rebuild
from carbon.cold_plate.contracts import implementation_digest as model_digest
from carbon.cold_plate.openfoam import IMAGE
from carbon.development_session.research_catalog import RecipeRejected
from carbon.reconstruction.capability_registry import contract

from .candidate_fault import load_policy as load_candidate_fault_policy
from .interface import Admitted, CandidateFault, ChallengeAdapter, Unavailable, digest
from .public_practice_store import PublicPracticeStore
from .scoring import COVERAGE_RULE, cover

ADAPTER_SCHEMA = "carbon.cold-plate.validator-adapter.v1"
BATCH_SCHEMA = "carbon.cold-plate.validator-public-batch.v1"
OUTCOME_SCHEMA = "carbon.cold-plate.validator-outcome.v1"
SCORE_RECORD_SCHEMA = "carbon.cold-plate.operator-score-record.v1"
STORE_SCHEMA = "carbon.cold-plate.validator-store.v1"
PUBLIC_BATCH_KIND = "public_practice"
EVIDENCE = "DEVELOPMENT_PUBLIC_ADAPTIVE"
MAX_STRATEGY_BYTES = 16_384


class CoolingAdapterError(ValueError):
    """A typed operator/store refusal. Its code contains no submitted data."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _copy(value):
    return json.loads(_canonical(value))


def _sha256_file(path):
    import hashlib

    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def implementation_digest():
    """Pin the adapter and every executable Cooling component it invokes."""

    from carbon import learned_baseline
    from carbon.challenge_validator import public_practice_store
    from carbon.cold_plate import compile as compiler
    from carbon.cold_plate import recipes

    files = {
        "adapter": Path(__file__),
        "compiler": Path(compiler.__file__),
        "exam": Path(exam.__file__),
        "learned_baseline": Path(learned_baseline.__file__),
        "public_practice_store": Path(public_practice_store.__file__),
        "recipes": Path(recipes.__file__),
    }
    return digest(
        {
            "schema": ADAPTER_SCHEMA,
            "files": {name: _sha256_file(path) for name, path in sorted(files.items())},
            "model_implementation_digest": model_digest(),
        }
    )


def rule_document(material):
    """The existing exam rule represented as pinned, finite JSON."""

    return {
        "schema": "carbon.cold-plate.development-exam-rule.v1",
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "evidence": EVIDENCE,
        "gates": [
            {"gate_id": gate.gate_id, "formula": gate.formula, "basis": gate.basis}
            for gate in exam.GATES
        ],
        "components": list(exam.COMPONENTS),
        "aggregate": "mean of three TRAIN-normalized errors; mandatory gate failure is ineligible",
        "important_peak_c": exam.T_IMPORTANT_C,
        "coverage": COVERAGE_RULE,
        "scales": exam.scales_from_train(material.train),
        "public_material": {
            "train_sha256": "sha256:" + TRAIN_SHA256,
            "practice_sha256": "sha256:" + PRACTICE_SHA256,
            "calibration_sha256": "sha256:" + CALIBRATION_SHA256,
        },
    }


class CoolingStore(PublicPracticeStore):
    """Cooling-compatible owner-only custody backed by the neutral store."""

    def __init__(self, root):
        super().__init__(
            root, name="cooling", schema=STORE_SCHEMA, error_type=CoolingAdapterError
        )


class CoolingAdapter(ChallengeAdapter):
    """The registered Cooling Level-0 contract behind Interface v1."""

    challenge_id = CHALLENGE.challenge_id
    challenge_version = CHALLENGE.version
    contract_digest = contract(CHALLENGE.challenge_id).digest
    max_strategy_bytes = MAX_STRATEGY_BYTES
    disclosure_fields = frozenset(
        {"score", "eligible", "n_cases", "n_scored", "n_gate_failed"}
    )

    def __init__(self, root, *, repository="."):
        self.repository = Path(repository)
        self.material = PublicMaterial.load(self.repository)
        self.candidate_fault_policy = load_candidate_fault_policy(self.challenge_id)
        if self.candidate_fault_policy.challenge_version != self.challenge_version:
            raise CoolingAdapterError("candidate_fault_policy_version_mismatch")
        self.store = CoolingStore(root)
        rule = rule_document(self.material)
        self._identities = {
            "schema": ADAPTER_SCHEMA,
            "contract_digest": self.contract_digest,
            "rule_digest": digest(rule),
            "implementation_digest": implementation_digest(),
            "public_material": rule["public_material"],
            "reference_solver_image": IMAGE,
            "evidence": EVIDENCE,
        }
        self._practice = {
            record["case_id"]: _copy(record) for record in self.material.practice
        }

    def _candidate_fault(self, fault):
        return CandidateFault(fault, self.candidate_fault_policy)

    def identities(self):
        return _copy(self._identities)

    def disclosure_budget(self):
        return None

    def _submission_id(self, submission):
        identity = digest(
            {
                "hotkey": submission.hotkey,
                "receipt": submission.receipt,
                "challenge_id": submission.challenge_id,
                "challenge_version": submission.challenge_version,
                "strategy": submission.strategy,
                "contract_digest": submission.contract_digest,
            }
        )
        return "cooling-" + identity.removeprefix("sha256:")

    def _outcome(self, submission_id, state, *, failure=None, summary=None):
        outcome = {
            "schema": OUTCOME_SCHEMA,
            "submission_id": submission_id,
            "challenge": {"id": self.challenge_id, "version": self.challenge_version},
            "state": state,
            "evidence": EVIDENCE,
            "qualification": False,
            "reward": False,
        }
        if failure is not None:
            outcome["failure"] = failure
        if summary is not None:
            outcome.update(
                score=summary["score"],
                eligible=summary["eligible"],
                n_cases=summary["n_cases"],
                n_scored=summary["n_scored"],
                n_gate_failed=summary["n_gate_failed"],
            )
        return outcome

    @staticmethod
    def _issues(refused):
        issues = []
        for issue in refused.rejected.issues:
            path = issue.path
            if type(path) is tuple:
                path = list(path)
            issues.append({"code": issue.code, "path": path})
        return issues

    def evaluate(self, submission):
        if type(submission) is not Admitted:
            raise TypeError("an admitted submission is required")
        fingerprint = self.store.active_pool()
        if fingerprint is None:
            raise Unavailable("cooling_public_practice_pool_not_open")
        submission_id = self._submission_id(submission)
        existing = self.store.submission(submission_id)
        if existing is not None:
            return existing["outcome"]
        try:
            _compiled, recipe = compile_recipe(submission.strategy)
        except RecipeRejected as refused:
            outcome = self._outcome(
                submission_id,
                "INVALID_CONSTRUCTION",
                failure={"code": "recipe_rejected", "issues": self._issues(refused)},
            )
            self.store.record_submission(
                submission_id, submission.hotkey, submission.strategy, outcome, None
            )
            return outcome

        try:
            model = rebuild(recipe, self.material)
        except Exception as fault:
            raise self._candidate_fault("rebuild_exception") from fault
        references = self.store.references(fingerprint)
        try:
            predictions = {
                case_id: model.predict(record["inputs"])
                for case_id, record in references.items()
            }
        except Exception as fault:
            raise self._candidate_fault("predict_exception") from fault
        scales = exam.scales_from_train(self.material.train)
        # A case without a prediction fails the schema gate (`cover`).
        asked, missing = cover(predictions, sorted(references))
        rows = [
            exam.score_case(asked[case_id], references[case_id], scales)
            for case_id in sorted(references)
        ]
        summary = {**exam.aggregate(rows), "n_missing": len(missing)}
        try:
            _canonical(
                {"predictions": predictions, "cases": rows, "aggregate": summary}
            )
        except ValueError:
            raise self._candidate_fault("non_finite_score")
        outcome = self._outcome(submission_id, "SCORED", summary=summary)
        score_record = {
            "schema": SCORE_RECORD_SCHEMA,
            "submission_id": submission_id,
            "pool_fingerprint": fingerprint,
            "rule_digest": self._identities["rule_digest"],
            "implementation_digest": self._identities["implementation_digest"],
            "recipe": recipe.document(),
            "recipe_digest": recipe.recipe_digest,
            "aggregate": summary,
            "cases": rows,
            "predictions": predictions,
        }
        self.store.record_submission(
            submission_id, submission.hotkey, submission.strategy, outcome, score_record
        )
        return outcome

    def outcome(self, submission_id):
        record = self.store.submission(submission_id)
        if record is None:
            raise LookupError("unknown_submission")
        return record["outcome"]

    def owner(self, submission_id):
        record = self.store.submission(submission_id)
        return None if record is None else record["hotkey"]

    def advance(self):
        return 0

    def score_record(self, submission_id):
        record = self.store.submission(submission_id)
        if record is None or record["score_record"] is None:
            raise LookupError("not_scored")
        return record["score_record"]

    def sealed_roles(self):
        return set()

    def _prepare_batch(self, role, *, kind, **options):
        if kind != PUBLIC_BATCH_KIND:
            raise CoolingAdapterError("cooling_batch_kind_not_served")
        if options:
            raise CoolingAdapterError("cooling_public_batch_takes_no_options")
        document = {
            "schema": BATCH_SCHEMA,
            "challenge": {"id": self.challenge_id, "version": self.challenge_version},
            "role": role,
            "kind": kind,
            "evidence": EVIDENCE,
            "practice_sha256": "sha256:" + PRACTICE_SHA256,
            "cases": [
                {"case_id": record["case_id"], "inputs": record["inputs"]}
                for record in self.material.practice
            ],
        }
        return self.store.prepare(role, kind, document)

    def reference_jobs(self, fingerprint):
        document, _state = self.store.batch(fingerprint)
        found = self.store.references(fingerprint)
        return [
            {
                "case_id": case["case_id"],
                "inputs": case["inputs"],
                "reference": "PINNED_PUBLIC_PRACTICE",
                "solver_image": IMAGE,
            }
            for case in document["cases"]
            if case["case_id"] not in found
        ]

    def ingest_references(self, fingerprint, records):
        document, _state = self.store.batch(fingerprint)
        cases = {case["case_id"] for case in document["cases"]}
        if type(records) not in (list, tuple):
            raise CoolingAdapterError("cooling_reference_records_malformed")
        validated = {}
        for record in records:
            if type(record) is not dict or type(record.get("case_id")) is not str:
                raise CoolingAdapterError("cooling_reference_record_malformed")
            case_id = record["case_id"]
            if case_id in validated:
                raise CoolingAdapterError("cooling_reference_case_duplicate")
            if case_id not in cases:
                raise CoolingAdapterError("cooling_reference_case_not_in_batch")
            if _canonical(record) != _canonical(self._practice[case_id]):
                raise CoolingAdapterError("cooling_reference_record_mismatch")
            validated[case_id] = record
        self.store.ingest(fingerprint, validated)
        return not self.reference_jobs(fingerprint)

    def open_pool(self):
        return self.store.open_pool(len(self.material.practice))

    def status(self):
        return {
            "schema": STORE_SCHEMA,
            "evidence": EVIDENCE,
            **self.store.status(),
        }


__all__ = [
    "EVIDENCE",
    "PUBLIC_BATCH_KIND",
    "CoolingAdapter",
    "CoolingAdapterError",
    "CoolingStore",
    "implementation_digest",
    "rule_document",
]
