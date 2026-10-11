"""Motor's public DEVELOPMENT `ChallengeAdapter` (Interface v1).

Only the registered Level-0 recipe, digest-pinned public TRAIN and PRACTICE
material and existing Motor exam are reachable. This is adaptive public
feedback, not a private/official exam, confirmation set or qualification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from carbon import learned_baseline
from carbon.development_session.research_catalog import RecipeRejected
from carbon.motor import exam
from carbon.motor.challenge import (
    CALIBRATION_SHA256,
    CHALLENGE,
    PRACTICE_SHA256,
    TRAIN_SHA256,
    PublicMaterial,
)
from carbon.motor.compile import NEURAL_FAMILIES, compile_recipe, rebuild
from carbon.motor.contracts import implementation_digest as model_digest
from carbon.reconstruction.capability_registry import contract

from .candidate_fault import load_policy as load_candidate_fault_policy
from .interface import Admitted, CandidateFault, ChallengeAdapter, Unavailable, digest
from .public_practice_store import PublicPracticeStore
from .scoring import COVERAGE_RULE, cover

ADAPTER_SCHEMA = "carbon.motor.validator-adapter.v1"
BATCH_SCHEMA = "carbon.motor.validator-public-batch.v1"
OUTCOME_SCHEMA = "carbon.motor.validator-outcome.v1"
SCORE_RECORD_SCHEMA = "carbon.motor.operator-score-record.v1"
STORE_SCHEMA = "carbon.motor.validator-store.v1"
PUBLIC_BATCH_KIND = "public_practice"
EVIDENCE = "DEVELOPMENT_PUBLIC_ADAPTIVE"
MAX_STRATEGY_BYTES = 16_384
NEURAL_NOT_SERVED = "motor_neural_family_not_served"


class MotorAdapterError(ValueError):
    """Typed operator/store refusal; code contains no submitted content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _copy(value):
    return json.loads(_canonical(value))


def implementation_digest():
    """Pin the adapter and executable Motor pieces used during evaluation."""

    from carbon.challenge_validator import (
        candidate_fault,
        public_practice_store,
        scoring,
    )
    from carbon.motor import compile as compiler
    from carbon.motor import recipes

    files = {
        "adapter": Path(__file__),
        "candidate_fault": Path(candidate_fault.__file__),
        "compiler": Path(compiler.__file__),
        "exam": Path(exam.__file__),
        "learned_baseline": Path(learned_baseline.__file__),
        "public_practice_store": Path(public_practice_store.__file__),
        "recipes": Path(recipes.__file__),
        "scoring": Path(scoring.__file__),
    }
    return digest(
        {
            "schema": ADAPTER_SCHEMA,
            "files": {
                name: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                for name, path in sorted(files.items())
            },
            "model_implementation_digest": model_digest(),
        }
    )


def rule_document(material):
    """Represent only the existing provisional Motor exam as finite JSON."""

    return {
        "schema": "carbon.motor.development-exam-rule.v1",
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "evidence": EVIDENCE,
        "gates": [
            {"gate_id": gate.gate_id, "formula": gate.formula, "basis": gate.basis}
            for gate in exam.GATES
        ],
        "components": list(exam.COMPONENTS),
        "aggregate": "mean of two TRAIN-normalized errors; mandatory gate failure is ineligible",
        "important_current_density_a_mm2": exam.J_IMPORTANT,
        "coverage": COVERAGE_RULE,
        "scales": exam.scales_from_train(material.train),
        "public_material": {
            "train_sha256": "sha256:" + TRAIN_SHA256,
            "practice_sha256": "sha256:" + PRACTICE_SHA256,
            "calibration_sha256": "sha256:" + CALIBRATION_SHA256,
        },
    }


class MotorStore(PublicPracticeStore):
    """Motor-specific identity on the shared owner-only public store."""

    def __init__(self, root):
        super().__init__(
            root, name="motor", schema=STORE_SCHEMA, error_type=MotorAdapterError
        )


class MotorAdapter(ChallengeAdapter):
    """The registered Motor Level-0 contract behind Interface v1."""

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
            raise MotorAdapterError("candidate_fault_policy_version_mismatch")
        self.store = MotorStore(root)
        rule = rule_document(self.material)
        self._identities = {
            "schema": ADAPTER_SCHEMA,
            "contract_digest": self.contract_digest,
            "rule_digest": digest(rule),
            "implementation_digest": implementation_digest(),
            "public_material": rule["public_material"],
            "candidate_fault_policy_digest": self.candidate_fault_policy.digest,
            "evidence": EVIDENCE,
        }
        self._practice = {
            record["case_id"]: _copy(record) for record in self.material.practice
        }

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
        return "motor-" + identity.removeprefix("sha256:")

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
        return [
            {
                "code": issue.code,
                "path": list(issue.path) if type(issue.path) is tuple else issue.path,
            }
            for issue in refused.rejected.issues
        ]

    def evaluate(self, submission):
        if type(submission) is not Admitted:
            raise TypeError("an admitted submission is required")
        fingerprint = self.store.active_pool()
        if fingerprint is None:
            raise Unavailable("motor_public_practice_pool_not_open")
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
        if recipe.family in NEURAL_FAMILIES:
            # MOTOR-NEURAL-01: not served until the validator's neural rebuild
            # is reviewed. Never recorded against the miner, never a score.
            raise Unavailable(NEURAL_NOT_SERVED)

        try:
            model = rebuild(recipe, self.material)
        except Exception as fault:
            raise CandidateFault(
                "rebuild_exception", self.candidate_fault_policy
            ) from fault
        references = self.store.references(fingerprint)
        try:
            predictions = {
                case_id: model.predict(record["inputs"])
                for case_id, record in references.items()
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
            _canonical(
                {"predictions": predictions, "cases": rows, "aggregate": summary}
            )
        except (TypeError, ValueError) as fault:
            raise CandidateFault(
                "non_finite_score", self.candidate_fault_policy
            ) from fault
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
            raise MotorAdapterError("motor_batch_kind_not_served")
        if options:
            raise MotorAdapterError("motor_public_batch_takes_no_options")
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
                "practice_sha256": "sha256:" + PRACTICE_SHA256,
            }
            for case in document["cases"]
            if case["case_id"] not in found
        ]

    def ingest_references(self, fingerprint, records):
        document, _state = self.store.batch(fingerprint)
        cases = {case["case_id"] for case in document["cases"]}
        if type(records) not in (list, tuple):
            raise MotorAdapterError("motor_reference_records_malformed")
        validated = {}
        for record in records:
            if type(record) is not dict or type(record.get("case_id")) is not str:
                raise MotorAdapterError("motor_reference_record_malformed")
            case_id = record["case_id"]
            if case_id in validated:
                raise MotorAdapterError("motor_reference_case_duplicate")
            if case_id not in cases:
                raise MotorAdapterError("motor_reference_case_not_in_batch")
            if _canonical(record) != _canonical(self._practice[case_id]):
                raise MotorAdapterError("motor_reference_record_mismatch")
            validated[case_id] = record
        self.store.ingest(fingerprint, validated)
        return not self.reference_jobs(fingerprint)

    def open_pool(self):
        return self.store.open_pool(len(self.material.practice))

    def status(self):
        return {"schema": STORE_SCHEMA, "evidence": EVIDENCE, **self.store.status()}


__all__ = [
    "EVIDENCE",
    "PUBLIC_BATCH_KIND",
    "MotorAdapter",
    "MotorAdapterError",
    "MotorStore",
    "implementation_digest",
    "rule_document",
]
