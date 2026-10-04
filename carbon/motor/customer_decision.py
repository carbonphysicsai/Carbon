"""Customer-decision commitments for the motor DEVELOPMENT Challenge.

The existing motor exam measures prediction quality.  This module asks the
separate engineering question: which declared motor geometry should be used
over a declared set of current commands when a supplied mean-torque floor and
torque-ripple limit must both hold?

The scope remains the registered 2D, 8-pole/24-slot periodic cross-section.
Limits have no defaults: they must come from an identified synthetic or
customer requirement.  Model proposals are committed before any reference is
consulted. Analytical fixtures remain available for lifecycle tests, while
counted GetDP evidence can enter only through the artifact-verifying campaign
importer.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from carbon.design_search.experiment import SearchAdapter, digest
from carbon.design_search.methods import View

from . import analytic, domain, exam

CHALLENGE = "electric-motor-magnetics"
SCOPE = "2d-8-pole-24-slot-periodic-cross-section-v1"
MATERIAL = "DEVELOPMENT"
MODE = "PB-INV"

CONTRACT_SCHEMA = "carbon.motor.customer-decision-contract.v1"
REQUEST_SCHEMA = "carbon.motor.design-search-request.v1"
COMMITMENT_SCHEMA = "carbon.motor.design-search-commitment.v1"
RESULT_SCHEMA = "carbon.motor.design-search-result.v1"
REFERENCE_CLASSES = ("ANALYTICAL_FIXTURE", "COUNTED_GETDP")
VERDICTS = ("FEASIBLE", "INFEASIBLE", "REFERENCE_UNAVAILABLE")

DESIGN_VARIABLES = domain.INPUTS[:6]
CONDITION_VARIABLES = domain.INPUTS[6:]
MODES = (MODE,)
PROPOSAL_OUTCOMES = (
    "CONFIRMED_INFEASIBLE",
    "CONFIRMED_FEASIBLE",
    "UNRESOLVED",
    "ABSTAIN",
)
DUPLICATE_QUERY_POLICY = "FORBID_WITHIN_AND_ACROSS_CALLS"
QUERY_ACCOUNTING_UNIT = "ATTEMPTED_MODEL_POINT"
VERIFICATION_ACCOUNTING_UNIT = "CONDITION_EVIDENCE_EVALUATION"
MODEL_RETRY_POLICY = {
    "max_retries_per_point": 0,
    "continuation_after_failure": False,
    "new_oracle_required": True,
}
TIE_POLICY = (
    "lowest worst-case predicted peak-to-peak torque-ripple fraction among "
    "designs predicted to satisfy the supplied mean-torque floor and ripple "
    "limit at every condition; ties use higher worst-condition mean torque, "
    "then the lower frozen design ID (the declared design order)"
)
DECISION = (
    "choose a bounded 2D motor geometry that minimizes worst-case torque "
    "ripple fraction while meeting the supplied mean-torque floor and ripple "
    "limit at every declared current command"
)
OBJECTIVE = {
    "quantity": "worst_case_torque_ripple_fraction",
    "unit": "fraction_of_period_mean_torque",
    "direction": "MINIMIZE",
}
CLAIMS = {
    "customer_acceptance": False,
    "global_optimum": False,
    "scientific_qualification": False,
    "production_qualification": False,
    "three_dimensional_motor_performance": False,
    "thermal_or_efficiency_performance": False,
}
CODE_PATHS = (
    "carbon/motor/customer_decision.py",
    "carbon/motor/decision_study.py",
    "carbon/motor/domain.py",
    "carbon/motor/exam.py",
    "carbon/motor/analytic.py",
    "carbon/motor/mesh.py",
    "carbon/motor/getdp.py",
    "carbon/motor/reference_campaign.py",
    "carbon/learned_baseline.py",
    "carbon/design_search/aggregate_methods.py",
    "carbon/design_search/campaign.py",
    "carbon/design_search/reference_comparison.py",
    "scripts/dev/motor/decision_study.py",
    "scripts/dev/motor/reference/run_batch.py",
)

_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMITMENT_TOKEN = object()
_REFERENCE_TOKEN = object()


class DecisionError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class ModelInfrastructureFailure(DecisionError):
    """Typed model-service failure, never a motor-physics result."""

    def __init__(self, cause: str = "MODEL_SERVICE_UNAVAILABLE", *, retryable=True):
        super().__init__("model_infrastructure_failure", cause)
        self.cause = _token(cause, "infrastructure cause")
        self.retryable = bool(retryable)


def _number(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise DecisionError("finite_number_required", name)
    return float(value)


def _token(value: object, name: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise DecisionError("token_required", name)
    return value


def _tagged_digest(value: object, name: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise DecisionError("tagged_sha256_required", name)
    return value


def contract(
    *,
    contract_id: str,
    requirement_ref: str,
    min_mean_torque_nm: float,
    max_ripple_fraction: float,
) -> dict[str, object]:
    """Build a DEVELOPMENT contract; scientific limits are never defaulted."""

    torque = _number(min_mean_torque_nm, "min_mean_torque_nm")
    ripple = _number(max_ripple_fraction, "max_ripple_fraction")
    if torque < 0:
        raise DecisionError("mean_torque_floor_negative")
    if ripple < 0:
        raise DecisionError("ripple_limit_negative")
    body = {
        "schema": CONTRACT_SCHEMA,
        "contract_id": _token(contract_id, "contract_id"),
        "challenge": CHALLENGE,
        "scope": SCOPE,
        "material": MATERIAL,
        "requirement_ref": _token(requirement_ref, "requirement_ref"),
        "decision": DECISION,
        "objective": dict(OBJECTIVE),
        "constraints": {
            "min_mean_torque_nm": torque,
            "max_ripple_fraction": ripple,
        },
        "tie_policy": TIE_POLICY,
        "query_policy": {
            "accounting_unit": QUERY_ACCOUNTING_UNIT,
            "duplicate_policy": DUPLICATE_QUERY_POLICY,
            "retry_policy": dict(MODEL_RETRY_POLICY),
        },
        "verification_policy": {
            "accounting_unit": VERIFICATION_ACCOUNTING_UNIT,
            "repeated_commitment": "FORBIDDEN",
            "reference_classes": list(REFERENCE_CLASSES),
            "counted_reference_admission": (
                "ARTIFACT_VERIFIED_PINNED_GETDP_CAMPAIGN_ONLY"
            ),
        },
        "claims": dict(CLAIMS),
    }
    return {**body, "contract_digest": digest(body)}


def validate_contract(document: object) -> dict[str, object]:
    if type(document) is not dict:
        raise DecisionError("contract_is_object")
    expected = {
        "schema",
        "contract_id",
        "challenge",
        "scope",
        "material",
        "requirement_ref",
        "decision",
        "objective",
        "constraints",
        "tie_policy",
        "query_policy",
        "verification_policy",
        "claims",
        "contract_digest",
    }
    if set(document) != expected:
        raise DecisionError("contract_fields")
    body = {key: value for key, value in document.items() if key != "contract_digest"}
    if digest(body) != document["contract_digest"]:
        raise DecisionError("contract_digest_mismatch")
    if (
        document["schema"] != CONTRACT_SCHEMA
        or document["challenge"] != CHALLENGE
        or document["scope"] != SCOPE
        or document["material"] != MATERIAL
        or document["decision"] != DECISION
        or document["objective"] != OBJECTIVE
        or document["tie_policy"] != TIE_POLICY
        or document["claims"] != CLAIMS
    ):
        raise DecisionError("contract_identity")
    _token(document["contract_id"], "contract_id")
    _token(document["requirement_ref"], "requirement_ref")
    constraints = document["constraints"]
    if type(constraints) is not dict or set(constraints) != {
        "min_mean_torque_nm",
        "max_ripple_fraction",
    }:
        raise DecisionError("contract_constraints")
    if _number(constraints["min_mean_torque_nm"], "min_mean_torque_nm") < 0:
        raise DecisionError("mean_torque_floor_negative")
    if _number(constraints["max_ripple_fraction"], "max_ripple_fraction") < 0:
        raise DecisionError("ripple_limit_negative")
    if document["query_policy"] != {
        "accounting_unit": QUERY_ACCOUNTING_UNIT,
        "duplicate_policy": DUPLICATE_QUERY_POLICY,
        "retry_policy": MODEL_RETRY_POLICY,
    }:
        raise DecisionError("contract_query_policy")
    if document["verification_policy"] != {
        "accounting_unit": VERIFICATION_ACCOUNTING_UNIT,
        "repeated_commitment": "FORBIDDEN",
        "reference_classes": list(REFERENCE_CLASSES),
        "counted_reference_admission": ("ARTIFACT_VERIFIED_PINNED_GETDP_CAMPAIGN_ONLY"),
    }:
        raise DecisionError("contract_verification_policy")
    return document


def _rows(rows, names, code):
    if type(rows) is not list or not rows:
        raise DecisionError(code)
    normalized = []
    for row in rows:
        if type(row) is not dict or set(row) != set(names):
            raise DecisionError(code)
        normalized.append({name: _number(row[name], name) for name in names})
    tuples = [tuple(row[name] for name in names) for row in normalized]
    if len(tuples) != len(set(tuples)):
        raise DecisionError(code + "_repeated")
    return normalized, tuples


def _require_full_grid(designs):
    axes = [
        sorted({row[index] for row in designs})
        for index in range(len(DESIGN_VARIABLES))
    ]
    if math.prod(len(axis) for axis in axes) != len(designs):
        raise DecisionError("design_space_is_not_a_full_grid")


def request(decision_contract, neutral):
    validate_contract(decision_contract)
    if neutral.get("material") != MATERIAL:
        raise DecisionError("development_material_only")
    if neutral.get("mode") != MODE:
        raise DecisionError("unknown_mode")
    model = neutral.get("model")
    if type(model) is not dict or set(model) != {"member", "recipe_digest", "seed"}:
        raise DecisionError("model_identity_fields")
    _token(model["member"], "model.member")
    _tagged_digest(model["recipe_digest"], "model.recipe_digest")
    if type(model["seed"]) is not int:
        raise DecisionError("model_seed_integer")
    method = neutral.get("method")
    if type(method) is not dict or set(method) != {
        "name",
        "code_digest",
        "configuration_digest",
    }:
        raise DecisionError("method_identity_fields")
    _token(method["name"], "method.name")
    _tagged_digest(method["code_digest"], "method.code_digest")
    _tagged_digest(method["configuration_digest"], "method.configuration_digest")
    for name in ("query_budget", "verification_budget"):
        if type(neutral.get(name)) is not int or neutral[name] <= 0:
            raise DecisionError("positive_integer_required", name)
    designs, space = _rows(neutral.get("designs"), DESIGN_VARIABLES, "designs")
    conditions, condition_space = _rows(
        neutral.get("conditions"), CONDITION_VARIABLES, "conditions"
    )
    _require_full_grid(space)
    if neutral["verification_budget"] < len(condition_space):
        raise DecisionError("verification_budget_below_condition_count")
    for design in space:
        for condition in condition_space:
            inputs = dict(zip(domain.INPUTS, (*design, *condition)))
            domain.check_inputs(inputs)
            if domain.validity(inputs):
                raise DecisionError("unbuildable_declared_design", repr(design))
    body = {
        "schema": REQUEST_SCHEMA,
        "challenge": CHALLENGE,
        "scope": SCOPE,
        "material": MATERIAL,
        "mode": MODE,
        "contract_digest": decision_contract["contract_digest"],
        "model": dict(model),
        "designs": designs,
        "conditions": conditions,
        "candidate_space_digest": digest(designs),
        "condition_space_digest": digest(conditions),
        "query_budget": neutral["query_budget"],
        "verification_budget": neutral["verification_budget"],
        "query_policy": dict(decision_contract["query_policy"]),
        "verification_policy": dict(decision_contract["verification_policy"]),
        "method": dict(method),
        "seed_policy": str(neutral.get("seed_policy", "")),
    }
    return {**body, "request_digest": digest(body)}, sorted(space)


def _validate_request(req, contract_digest=None):
    required = {
        "schema",
        "challenge",
        "scope",
        "material",
        "mode",
        "contract_digest",
        "model",
        "designs",
        "conditions",
        "candidate_space_digest",
        "condition_space_digest",
        "query_budget",
        "verification_budget",
        "query_policy",
        "verification_policy",
        "method",
        "seed_policy",
        "request_digest",
    }
    if type(req) is not dict or set(req) != required:
        raise DecisionError("request_fields")
    body = {key: value for key, value in req.items() if key != "request_digest"}
    if digest(body) != req["request_digest"]:
        raise DecisionError("request_digest_mismatch")
    if (
        req["schema"] != REQUEST_SCHEMA
        or req["challenge"] != CHALLENGE
        or req["scope"] != SCOPE
        or req["material"] != MATERIAL
        or req["mode"] != MODE
    ):
        raise DecisionError("request_identity")
    if contract_digest is not None and req["contract_digest"] != contract_digest:
        raise DecisionError("request_contract_mismatch")
    if digest(req["designs"]) != req["candidate_space_digest"]:
        raise DecisionError("candidate_space_digest_mismatch")
    if digest(req["conditions"]) != req["condition_space_digest"]:
        raise DecisionError("condition_space_digest_mismatch")
    if req["query_policy"] != {
        "accounting_unit": QUERY_ACCOUNTING_UNIT,
        "duplicate_policy": DUPLICATE_QUERY_POLICY,
        "retry_policy": MODEL_RETRY_POLICY,
    }:
        raise DecisionError("request_query_policy")
    if req["verification_policy"] != {
        "accounting_unit": VERIFICATION_ACCOUNTING_UNIT,
        "repeated_commitment": "FORBIDDEN",
        "reference_classes": list(REFERENCE_CLASSES),
        "counted_reference_admission": ("ARTIFACT_VERIFIED_PINNED_GETDP_CAMPAIGN_ONLY"),
    }:
        raise DecisionError("request_verification_policy")
    model = req["model"]
    if type(model) is not dict or set(model) != {"member", "recipe_digest", "seed"}:
        raise DecisionError("model_identity_fields")
    _token(model["member"], "model.member")
    _tagged_digest(model["recipe_digest"], "model.recipe_digest")
    if type(model["seed"]) is not int:
        raise DecisionError("model_seed_integer")
    method = req["method"]
    if type(method) is not dict or set(method) != {
        "name",
        "code_digest",
        "configuration_digest",
    }:
        raise DecisionError("method_identity_fields")
    _token(method["name"], "method.name")
    _tagged_digest(method["code_digest"], "method.code_digest")
    _tagged_digest(method["configuration_digest"], "method.configuration_digest")
    for name in ("query_budget", "verification_budget"):
        if type(req[name]) is not int or req[name] <= 0:
            raise DecisionError("positive_integer_required", name)
    if req["verification_budget"] < len(req["conditions"]):
        raise DecisionError("verification_budget_below_condition_count")
    designs, space = _rows(req["designs"], DESIGN_VARIABLES, "designs")
    conditions, condition_space = _rows(
        req["conditions"], CONDITION_VARIABLES, "conditions"
    )
    if designs != req["designs"] or conditions != req["conditions"]:
        raise DecisionError("request_rows_not_normalized")
    _require_full_grid(space)
    for design in space:
        for condition in condition_space:
            inputs = dict(zip(domain.INPUTS, (*design, *condition)))
            domain.check_inputs(inputs)
            if domain.validity(inputs):
                raise DecisionError("unbuildable_declared_design", repr(design))
    if type(req["seed_policy"]) is not str or not req["seed_policy"].strip():
        raise DecisionError("seed_policy_required")
    return req


def _point_case(point):
    return domain.check_inputs(dict(zip(domain.INPUTS, point)))


def quantities(decision_contract, outputs):
    """Derive the selection quantities from a valid 60-angle curve."""

    gates = exam.gates(outputs)
    failed = sorted(name for name, verdict in gates.items() if verdict == exam.FAIL)
    if failed:
        raise DecisionError("prediction_failed_validity_gate", ",".join(failed))
    constraints = decision_contract["constraints"]
    values = exam.feasibility(
        outputs,
        min_torque_nm=constraints["min_mean_torque_nm"],
        max_ripple_fraction=constraints["max_ripple_fraction"],
    )
    mean = values["mean_nm"]
    ripple_fraction = values["ripple_pk_pk_nm"] / mean if mean > 0 else math.inf
    return {
        **values,
        "ripple_fraction": ripple_fraction,
        "mean_torque_margin_nm": mean - constraints["min_mean_torque_nm"],
        "ripple_fraction_margin": constraints["max_ripple_fraction"] - ripple_fraction,
        "prediction_validity_gates": gates,
    }


class Oracle:
    """Budget attempted model points and seal after any evaluation failure."""

    def __init__(self, decision_contract, infer, req, space):
        validate_contract(decision_contract)
        _validate_request(req, decision_contract["contract_digest"])
        self.contract = decision_contract
        self.infer = infer
        self.budget = req["query_budget"]
        self.request_digest = req["request_digest"]
        self.designs = {
            tuple(row[name] for name in DESIGN_VARIABLES) for row in req["designs"]
        }
        self.conditions = {
            tuple(row[name] for name in CONDITION_VARIABLES)
            for row in req["conditions"]
        }
        if list(space) != sorted(self.designs):
            raise DecisionError("oracle_space_mismatch")
        self.log = []
        self.elapsed = 0.0
        self._seen = set()
        self._terminal_failure = None

    @property
    def used(self):
        return len(self.log)

    @property
    def successful(self):
        return sum(row["status"] == "OK" for row in self.log)

    @property
    def terminal_failure(self):
        return self._terminal_failure

    def _seal(self, code, detail=""):
        self._terminal_failure = {"code": code, "detail": detail}

    def _require_open(self):
        if self._terminal_failure is not None:
            raise DecisionError(
                "oracle_sealed_after_failure", self._terminal_failure["code"]
            )

    def query(self, points):
        self._require_open()
        try:
            normalized = [
                tuple(_number(value, "query_point") for value in point)
                for point in points
            ]
            if not normalized:
                raise DecisionError("query_batch_empty")
            if len(normalized) != len(set(normalized)) or any(
                point in self._seen for point in normalized
            ):
                raise DecisionError("duplicate_query_forbidden")
            if self.used + len(normalized) > self.budget:
                raise DecisionError("query_budget_exhausted")
            for point in normalized:
                if len(point) != len(DESIGN_VARIABLES) + len(CONDITION_VARIABLES):
                    raise DecisionError("query_point_width")
                if point[:6] not in self.designs or point[6:] not in self.conditions:
                    raise DecisionError("undeclared_design_or_condition")
        except DecisionError as error:
            self._seal(error.code, str(error))
            raise
        query_ids = [f"q{self.used + index:06d}" for index in range(len(normalized))]
        inputs = {key: _point_case(point) for key, point in zip(query_ids, normalized)}
        batch = []
        for key, point in zip(query_ids, normalized):
            entry = {
                "query_id": key,
                "point": list(point),
                "status": "ATTEMPTED",
                "quantities": None,
            }
            self.log.append(entry)
            batch.append(entry)
        self._seen.update(normalized)
        started = time.perf_counter()
        try:
            outputs = self.infer(inputs)
        except ModelInfrastructureFailure as error:
            self.elapsed += time.perf_counter() - started
            for entry in batch:
                entry["status"] = "FAILED_INFRA"
                entry["failure_code"] = error.code
            self._seal(error.code, error.cause)
            raise
        except Exception as error:
            self.elapsed += time.perf_counter() - started
            failure = ModelInfrastructureFailure(type(error).__name__)
            for entry in batch:
                entry["status"] = "FAILED_INFRA"
                entry["failure_code"] = failure.code
            self._seal(failure.code, failure.cause)
            raise failure from error
        self.elapsed += time.perf_counter() - started
        try:
            if type(outputs) is not dict or set(outputs) != set(query_ids):
                raise DecisionError("malformed_model_batch")
            result = [quantities(self.contract, outputs[key]) for key in query_ids]
        except DecisionError as error:
            status = (
                "FAILED_PHYSICS"
                if error.code == "prediction_failed_validity_gate"
                else "FAILED_PROTOCOL"
            )
            for entry in batch:
                entry["status"] = status
                entry["failure_code"] = error.code
            self._seal(error.code, str(error))
            raise
        for entry, row in zip(batch, result):
            entry["status"] = "OK"
            entry["quantities"] = row
        return result


def _passes(row):
    return bool(row["feasible"])


def _margin(contract_document, row):
    limits = contract_document["constraints"]
    mean_scale = max(limits["min_mean_torque_nm"], 1.0)
    ripple_scale = max(limits["max_ripple_fraction"], 1e-12)
    return min(
        row["mean_torque_margin_nm"] / mean_scale,
        row["ripple_fraction_margin"] / ripple_scale,
    )


def fixed_grid(decision_contract, oracle, req, space):
    conditions = [
        tuple(row[name] for name in CONDITION_VARIABLES) for row in req["conditions"]
    ]
    points = [(*design, *condition) for design in space for condition in conditions]
    rows = oracle.query(points)
    table = dict(zip(points, rows))
    best = None
    for design in space:
        values = [table[(*design, *condition)] for condition in conditions]
        if all(_passes(row) for row in values):
            key = (
                max(row["ripple_fraction"] for row in values),
                -min(row["mean_nm"] for row in values),
                *design,
            )
            if best is None or key < best:
                best = key
    if best is None:
        return []
    return [
        {
            **dict(zip(DESIGN_VARIABLES, best[2:])),
            "predicted_worst_ripple_fraction": best[0],
            "predicted_worst_condition_mean_torque_nm": -best[1],
        }
    ]


@dataclass(frozen=True, slots=True, init=False)
class Commitment:
    _path: Path
    _encoded: bytes

    def __init__(self, token, path, encoded):
        if token is not _COMMITMENT_TOKEN:
            raise DecisionError("commitment_only_from_commit")
        object.__setattr__(self, "_path", Path(path))
        object.__setattr__(self, "_encoded", encoded)

    @property
    def path(self):
        return self._path

    @property
    def document(self):
        return json.loads(self._encoded)


def commit(req, selections, oracle, directory):
    _validate_request(req, oracle.contract["contract_digest"])
    if req["request_digest"] != oracle.request_digest:
        raise DecisionError("oracle_request_mismatch")
    oracle._require_open()
    if type(selections) is not list or len(selections) > 1:
        raise DecisionError("pb_inv_commits_at_most_one_design")
    if selections:
        selection = selections[0]
        if type(selection) is not dict or set(selection) != {
            *DESIGN_VARIABLES,
            "predicted_worst_ripple_fraction",
            "predicted_worst_condition_mean_torque_nm",
        }:
            raise DecisionError("selection_fields")
        design = tuple(_number(selection[name], name) for name in DESIGN_VARIABLES)
        if design not in oracle.designs:
            raise DecisionError("selection_outside_candidate_space")
        rows = {
            tuple(row["point"]): row["quantities"]
            for row in oracle.log
            if row["status"] == "OK"
            if tuple(row["point"][: len(DESIGN_VARIABLES)]) == design
        }
        expected = {(*design, *condition) for condition in oracle.conditions}
        if set(rows) != expected or not all(
            rows[point]["feasible"] for point in expected
        ):
            raise DecisionError("selection_not_verified_by_model_at_every_condition")
        worst_ripple = max(rows[point]["ripple_fraction"] for point in expected)
        worst_mean = min(rows[point]["mean_nm"] for point in expected)
        if (
            _number(
                selection["predicted_worst_ripple_fraction"],
                "predicted_worst_ripple_fraction",
            )
            != worst_ripple
            or _number(
                selection["predicted_worst_condition_mean_torque_nm"],
                "predicted_worst_condition_mean_torque_nm",
            )
            != worst_mean
        ):
            raise DecisionError("selection_objective_mismatch")
    body = {
        "schema": COMMITMENT_SCHEMA,
        "request": req,
        "query_accounting_unit": QUERY_ACCOUNTING_UNIT,
        "queries_attempted": oracle.used,
        "queries_successful": oracle.successful,
        "query_log_digest": digest(oracle.log),
        "selections": [dict(row) for row in selections],
        "status": "PROPOSAL" if selections else "ABSTAIN",
    }
    document = {**body, "commitment_digest": digest(body)}
    encoded = (json.dumps(document, sort_keys=True, indent=1) + "\n").encode()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (
        req["request_digest"].removeprefix("sha256:") + ".commitment.json"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
    return Commitment(_COMMITMENT_TOKEN, path, encoded)


def _load_commitment(commitment):
    if type(commitment) is not Commitment:
        raise DecisionError("commitment_only_from_commit")
    encoded = commitment.path.read_bytes()
    if encoded != commitment._encoded:
        raise DecisionError("commitment_changed_after_commit")
    document = json.loads(encoded)
    body = {key: value for key, value in document.items() if key != "commitment_digest"}
    if digest(body) != document.get("commitment_digest"):
        raise DecisionError("commitment_digest_mismatch")
    return document


def _restore_commitment(path, *, expected_digest, expected_file_sha256):
    """Restore exact construction bytes without regenerating a proposal."""

    path = Path(path)
    try:
        encoded = path.read_bytes()
    except OSError as error:
        raise DecisionError("committed_proposal_unavailable", str(path)) from error
    actual_sha256 = "sha256:" + hashlib.sha256(encoded).hexdigest()
    if actual_sha256 != expected_file_sha256:
        raise DecisionError("committed_proposal_file_digest_mismatch", str(path))
    try:
        document = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DecisionError("committed_proposal_invalid_json", str(path)) from error
    if document.get("schema") != COMMITMENT_SCHEMA:
        raise DecisionError("committed_proposal_schema", str(path))
    body = {key: value for key, value in document.items() if key != "commitment_digest"}
    actual_digest = digest(body)
    if actual_digest != document.get("commitment_digest"):
        raise DecisionError("commitment_digest_mismatch")
    if actual_digest != expected_digest:
        raise DecisionError("construction_commitment_digest_mismatch", str(path))
    return Commitment(_COMMITMENT_TOKEN, path, encoded)


def _case_id(inputs):
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    return "motor-decision:" + hashlib.sha256(encoded).hexdigest()[:20]


_COUNTED_PROVENANCE_FIELDS = {
    "evidence_class",
    "solver_image",
    "configuration_digest",
    "mesh_digest",
    "convergence_evidence_digest",
    "applicability_evidence_digest",
    "run_identity",
    "artifact_manifest_digest",
    "artifact_count",
    "artifact_bytes",
    "execution_count",
    "retry_count",
    "wall_s",
    "cpu_limit",
    "record_digest",
}


def _validate_counted_record(record):
    if type(record) is not dict or set(record) != {
        "status",
        "inputs",
        "outputs",
        "checks",
        "provenance",
    }:
        raise DecisionError("counted_getdp_record_fields")
    provenance = record["provenance"]
    if type(provenance) is not dict or set(provenance) != _COUNTED_PROVENANCE_FIELDS:
        raise DecisionError("counted_getdp_provenance_fields")
    image = provenance["solver_image"]
    image_digest = image.rsplit("@sha256:", 1)[1] if "@sha256:" in image else ""
    if (
        provenance["evidence_class"] != "COUNTED_GETDP"
        or len(image_digest) != 64
        or any(character not in "0123456789abcdef" for character in image_digest)
    ):
        raise DecisionError("counted_getdp_identity")
    for name in (
        "configuration_digest",
        "mesh_digest",
        "convergence_evidence_digest",
        "applicability_evidence_digest",
        "artifact_manifest_digest",
        "record_digest",
    ):
        _tagged_digest(provenance[name], name)
    _token(provenance["run_identity"], "run_identity")
    for name in ("artifact_count", "artifact_bytes", "execution_count"):
        if type(provenance[name]) is not int or provenance[name] <= 0:
            raise DecisionError("counted_getdp_positive_integer", name)
    if (
        type(provenance["cpu_limit"]) not in (int, float)
        or provenance["cpu_limit"] <= 0
    ):
        raise DecisionError("counted_getdp_cpu_limit")
    if (
        type(provenance["retry_count"]) is not int
        or provenance["retry_count"] < 0
        or provenance["retry_count"] >= provenance["execution_count"]
    ):
        raise DecisionError("counted_getdp_retry_count")
    if _number(provenance["wall_s"], "wall_s") < 0:
        raise DecisionError("counted_getdp_wall_time")
    body = {
        **record,
        "provenance": {
            key: value for key, value in provenance.items() if key != "record_digest"
        },
    }
    if digest(body) != provenance["record_digest"]:
        raise DecisionError("counted_getdp_record_digest_mismatch")
    domain.check_inputs(record["inputs"])
    if type(record["status"]) is not str or not record["status"]:
        raise DecisionError("counted_getdp_status")
    if record["status"] == "OK" and (
        type(record["outputs"]) is not dict or type(record["checks"]) is not dict
    ):
        raise DecisionError("counted_getdp_success_evidence")
    return record


def _seal_counted_record(token, *, status, inputs, outputs, checks, provenance):
    if token is not _REFERENCE_TOKEN:
        raise DecisionError("counted_getdp_only_from_artifact_importer")
    provenance = dict(provenance)
    body = {
        "status": status,
        "inputs": domain.check_inputs(inputs),
        "outputs": outputs,
        "checks": checks,
        "provenance": provenance,
    }
    provenance["record_digest"] = digest(body)
    return _validate_counted_record({**body, "provenance": provenance})


class ReferenceSession:
    """Classified, budgeted reference evidence with replay-safe accounting."""

    def __init__(
        self,
        token,
        source,
        *,
        evidence_class,
        condition_budget,
        session_id,
        campaign_wall_s=0.0,
        construction_identity_digest=None,
    ):
        if token is not _REFERENCE_TOKEN:
            raise DecisionError("reference_session_from_factory_only")
        if evidence_class not in REFERENCE_CLASSES:
            raise DecisionError("reference_class_unknown")
        if not callable(source):
            raise DecisionError("reference_source_callable")
        if type(condition_budget) is not int or condition_budget < 0:
            raise DecisionError("reference_condition_budget")
        self.evidence_class = evidence_class
        self.source = source
        self.condition_budget = condition_budget
        self.session_id = _token(session_id, "reference_session_id")
        self.campaign_wall_s = _number(campaign_wall_s, "campaign_wall_s")
        if self.campaign_wall_s < 0:
            raise DecisionError("reference_campaign_wall_time")
        if construction_identity_digest is not None:
            _tagged_digest(construction_identity_digest, "construction_identity_digest")
        self.construction_identity_digest = construction_identity_digest
        self.used = 0
        self.cache = {}
        self._verified = set()
        self.source_calls = 0
        self.solver_executions = 0
        self.retries = 0
        self.solver_wall_s = 0.0

    def acquire(self, verification_key, jobs, per_commitment_budget=None):
        _tagged_digest(verification_key, "verification_key")
        if verification_key in self._verified:
            raise DecisionError("commitment_already_verified")
        if per_commitment_budget is not None and (
            type(per_commitment_budget) is not int or per_commitment_budget < len(jobs)
        ):
            raise DecisionError("verification_budget_exhausted")
        if self.used + len(jobs) > self.condition_budget:
            raise DecisionError("reference_session_budget_exhausted")
        self.used += len(jobs)
        self._verified.add(verification_key)
        missing = [job for job in jobs if job["case_id"] not in self.cache]
        cache_hits = len(jobs) - len(missing)
        if missing:
            self.source_calls += 1
            try:
                supplied = self.source(missing)
            except Exception as error:  # noqa: BLE001 - reference failure is evidence
                supplied = {
                    job["case_id"]: {
                        "status": "REFERENCE_INFRA_FAILURE",
                        "inputs": job["inputs"],
                        "outputs": None,
                        "checks": {"source_exception": type(error).__name__},
                    }
                    for job in missing
                }
            if type(supplied) is not dict:
                supplied = {}
            for job in missing:
                record = supplied.get(job["case_id"])
                if self.evidence_class == "COUNTED_GETDP":
                    try:
                        _validate_counted_record(record)
                    except (DecisionError, TypeError, ValueError):
                        record = {
                            "status": "REFERENCE_PROVENANCE_INVALID",
                            "inputs": job["inputs"],
                            "outputs": None,
                            "checks": {},
                            "provenance": {
                                "evidence_class": "COUNTED_GETDP",
                                "valid": False,
                            },
                        }
                    else:
                        provenance = record["provenance"]
                        self.solver_executions += provenance["execution_count"]
                        self.retries += provenance["retry_count"]
                        self.solver_wall_s += provenance["wall_s"]
                else:
                    if type(record) is not dict:
                        record = {
                            "status": "REFERENCE_MISSING",
                            "inputs": job["inputs"],
                            "outputs": None,
                            "checks": {},
                        }
                    record = {
                        **record,
                        "provenance": {
                            "evidence_class": "ANALYTICAL_FIXTURE",
                            "session_id": self.session_id,
                            "counted_getdp": False,
                        },
                    }
                self.cache[job["case_id"]] = record
        return (
            {job["case_id"]: self.cache[job["case_id"]] for job in jobs},
            {
                "accounting_unit": VERIFICATION_ACCOUNTING_UNIT,
                "condition_evaluations": len(jobs),
                "cache_hits": cache_hits,
                "cache_misses": len(missing),
            },
        )

    def metrics(self):
        return {
            "evidence_class": self.evidence_class,
            "condition_budget": self.condition_budget,
            "condition_evaluations": self.used,
            "source_calls": self.source_calls,
            "cached_cases": len(self.cache),
            "solver_executions": self.solver_executions,
            "retries": self.retries,
            "solver_wall_s": self.solver_wall_s,
            "campaign_wall_s": self.campaign_wall_s,
        }


def analytical_fixture_reference(*, condition_budget, session_id="motor-fixture-v1"):
    def source(jobs):
        return {
            job["case_id"]: {
                "status": "OK",
                "inputs": dict(job["inputs"]),
                "outputs": {"torque_nm": analytic.predict(job["inputs"])["torque_nm"]},
                "checks": {"fixture": True},
            }
            for job in jobs
        }

    return ReferenceSession(
        _REFERENCE_TOKEN,
        source,
        evidence_class="ANALYTICAL_FIXTURE",
        condition_budget=condition_budget,
        session_id=session_id,
    )


def fixture_reference(source, *, condition_budget, session_id):
    """Test-only/custom analytical fixture; never counted as GetDP evidence."""

    def batch(jobs):
        return {job["case_id"]: source(dict(job)) for job in jobs}

    return ReferenceSession(
        _REFERENCE_TOKEN,
        batch,
        evidence_class="ANALYTICAL_FIXTURE",
        condition_budget=condition_budget,
        session_id=session_id,
    )


def counted_getdp_reference(
    records,
    *,
    condition_budget,
    session_id,
    construction_identity_digest,
    campaign_wall_s=0.0,
):
    """Build counted evidence only from importer-sealed GetDP records."""

    if type(records) is not dict:
        raise DecisionError("counted_getdp_records_object")
    for record in records.values():
        _validate_counted_record(record)

    def source(jobs):
        return {
            job["case_id"]: records[job["case_id"]]
            for job in jobs
            if job["case_id"] in records
        }

    return ReferenceSession(
        _REFERENCE_TOKEN,
        source,
        evidence_class="COUNTED_GETDP",
        condition_budget=condition_budget,
        session_id=session_id,
        construction_identity_digest=construction_identity_digest,
        campaign_wall_s=campaign_wall_s,
    )


def _reference_verdict(decision_contract, job, record):
    if type(record) is not dict or record.get("status") != "OK":
        status = record.get("status") if type(record) is dict else "MISSING"
        return "REFERENCE_UNAVAILABLE", None, status
    try:
        inputs = domain.check_inputs(record.get("inputs"))
    except (TypeError, ValueError):
        return "REFERENCE_UNAVAILABLE", None, "REFERENCE_INVALID"
    if inputs != job["inputs"]:
        return "REFERENCE_UNAVAILABLE", None, "REFERENCE_INVALID"
    try:
        values = quantities(decision_contract, record.get("outputs"))
    except (DecisionError, TypeError, ValueError):
        return "REFERENCE_UNAVAILABLE", None, "REFERENCE_INVALID"
    return ("FEASIBLE" if values["feasible"] else "INFEASIBLE"), values, "OK"


def verify(decision_contract, commitment, reference):
    validate_contract(decision_contract)
    document = _load_commitment(commitment)
    if document.get("schema") != COMMITMENT_SCHEMA:
        raise DecisionError("commitment_identity")
    _validate_request(document.get("request"), decision_contract["contract_digest"])
    if type(reference) is not ReferenceSession:
        raise DecisionError("classified_reference_session_required")
    if not document["selections"]:
        return {
            "schema": RESULT_SCHEMA,
            "challenge": CHALLENGE,
            "commitment_digest": document["commitment_digest"],
            "status": "ABSTAIN",
            "proposal_outcome": "ABSTAIN",
            "reference_evidence_class": reference.evidence_class,
            "reference_availability": {"available": 0, "unavailable": 0},
            "verdicts": {},
            "accounting": {
                "accounting_unit": VERIFICATION_ACCOUNTING_UNIT,
                "condition_evaluations": 0,
                "cache_hits": 0,
                "cache_misses": 0,
            },
            "rows": [],
            "claims": dict(CLAIMS),
        }
    selection = document["selections"][0]
    request_document = document["request"]
    jobs = []
    for condition in request_document["conditions"]:
        inputs = {
            **{name: selection[name] for name in DESIGN_VARIABLES},
            **condition,
        }
        jobs.append({"case_id": _case_id(inputs), "inputs": inputs})
    records, accounting = reference.acquire(
        document["commitment_digest"],
        jobs,
        document["request"]["verification_budget"],
    )
    rows = []
    for job in jobs:
        verdict, values, status = _reference_verdict(
            decision_contract, job, records.get(job["case_id"])
        )
        rows.append(
            {
                **job,
                "verdict": verdict,
                "reference_status": status,
                "reference": values,
            }
        )
    verdicts = {
        verdict: sum(row["verdict"] == verdict for row in rows) for verdict in VERDICTS
    }
    if verdicts["INFEASIBLE"]:
        status = "CONFIRMED_INFEASIBLE"
    elif verdicts["REFERENCE_UNAVAILABLE"]:
        status = "UNRESOLVED"
    else:
        status = "CONFIRMED_FEASIBLE"
    return {
        "schema": RESULT_SCHEMA,
        "challenge": CHALLENGE,
        "commitment_digest": document["commitment_digest"],
        "status": status,
        "proposal_outcome": status,
        "reference_evidence_class": reference.evidence_class,
        "reference_availability": {
            "available": len(rows) - verdicts["REFERENCE_UNAVAILABLE"],
            "unavailable": verdicts["REFERENCE_UNAVAILABLE"],
        },
        "verdicts": verdicts,
        "accounting": accounting,
        "rows": rows,
        "claims": dict(CLAIMS),
    }


def adapter(decision_contract):
    validate_contract(decision_contract)

    def engine_request(neutral):
        return request(decision_contract, neutral)

    def view(req, space):
        conditions = tuple(
            tuple(row[name] for name in CONDITION_VARIABLES)
            for row in req["conditions"]
        )
        return View(
            mode=MODE,
            designs=tuple(space),
            conditions=conditions,
            verification_budget=req["verification_budget"],
            passes=_passes,
            objective=lambda row: (row["ripple_fraction"], -row["mean_nm"]),
            margin=lambda row: _margin(decision_contract, row),
            select_design=lambda design, worst: {
                **dict(zip(DESIGN_VARIABLES, design)),
                "predicted_worst_ripple_fraction": worst[0],
                "predicted_worst_condition_mean_torque_nm": -worst[1],
            },
            select_point=lambda *_: None,
        )

    return SearchAdapter(
        challenge=CHALLENGE,
        design_variables=DESIGN_VARIABLES,
        condition_variables=CONDITION_VARIABLES,
        contract_digest=decision_contract["contract_digest"],
        modes=MODES,
        request=engine_request,
        oracle=lambda req, space, infer: Oracle(decision_contract, infer, req, space),
        baseline=lambda oracle, req, space: fixed_grid(
            decision_contract, oracle, req, space
        ),
        view=view,
        commit=commit,
        verify=lambda commitment, reference: verify(
            decision_contract, commitment, reference
        ),
        code_paths=CODE_PATHS,
        tie_policy=TIE_POLICY,
    )
