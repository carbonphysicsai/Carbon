"""Customer-bound design search for the cold-plate DEVELOPMENT Challenge.

This module turns the existing periodic-cell model into a decision experiment:

* the customer supplies the die-temperature and hydraulic-power limits;
* a model searches a declared grid of channel designs over declared operating
  conditions;
* the fixed baseline selects the predicted-feasible design with the lowest
  worst-case hydraulic power;
* Carbon writes a proposal commitment before calling the independent reference;
* reference failure stays unavailable and a false-feasible proposal is reported.

It deliberately does not widen the physical scope.  The current reference is a
periodic straight-channel cell: no headers, manifolds, plate edges, spanwise
heat map or transient load.  A result is DEVELOPMENT decision evidence, not a
qualified product recommendation or a global optimum.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from carbon.design_search.experiment import SearchAdapter, digest
from carbon.design_search.methods import View

from . import domain, exam, openfoam

CHALLENGE = "chip-cold-plate"
SCOPE = "periodic-straight-channel-cell-v1"
MATERIAL = "DEVELOPMENT"
MODE = "PB-INV"

CONTRACT_SCHEMA = "carbon.cold-plate.customer-decision-contract.v2"
REQUEST_SCHEMA = "carbon.cold-plate.design-search-request.v2"
COMMITMENT_SCHEMA = "carbon.cold-plate.design-search-commitment.v2"
RESULT_SCHEMA = "carbon.cold-plate.design-search-result.v2"

DESIGN_VARIABLES = (
    "channel_width_mm",
    "fin_width_mm",
    "channel_depth_mm",
    "flow_lpm_per_kw",
)
CONDITION_VARIABLES = (
    "inlet_c",
    "heat_load_w",
    "hotspot_ratio",
    "hotspot_center_mm",
    "hotspot_width_mm",
)
MODES = (MODE,)
VERDICTS = ("FEASIBLE", "INFEASIBLE", "REFERENCE_UNAVAILABLE")
REFERENCE_CLASSES = ("ANALYTICAL_FIXTURE", "COUNTED_CFD")
DUPLICATE_QUERY_POLICY = "FORBID_WITHIN_AND_ACROSS_CALLS"
QUERY_ACCOUNTING_UNIT = "ATTEMPTED_MODEL_POINT"
VERIFICATION_ACCOUNTING_UNIT = "CONDITION_EVIDENCE_EVALUATION"
MODEL_RETRY_POLICY = {
    "max_retries_per_point": 0,
    "continuation_after_failure": False,
    "new_oracle_required": True,
}
CODE_PATHS = (
    "carbon/cold_plate/customer_decision.py",
    "carbon/cold_plate/decision_study.py",
    "carbon/cold_plate/domain.py",
    "carbon/cold_plate/exam.py",
    "carbon/cold_plate/analytic.py",
    "carbon/cold_plate/analysis.py",
    "carbon/cold_plate/openfoam.py",
    "carbon/cold_plate/population.py",
    "carbon/learned_baseline.py",
    "scripts/dev/cold_plate/decision_study.py",
    "scripts/dev/cold_plate/reference/run_batch.py",
)
TIE_POLICY = (
    "lowest worst-case predicted hydraulic power among designs predicted to "
    "meet every customer-supplied limit at every declared condition; exact "
    "ties use channel_width_mm, fin_width_mm, channel_depth_mm, then "
    "flow_lpm_per_kw"
)
DECISION = (
    "choose straight-channel geometry and flow control that minimize "
    "worst-case hydraulic power while meeting the supplied die and "
    "hydraulic limits at every declared operating condition"
)
OBJECTIVE = {
    "quantity": "worst_case_hydraulic_power",
    "unit": "W",
    "direction": "MINIMIZE",
}
REFERENCE = {
    "solver_image": openfoam.IMAGE,
    "physical_scope": SCOPE,
    "credibility": "NUMERICAL_VERIFICATION_ONLY",
    "counted_evidence_class": "COUNTED_CFD",
    "fixture_evidence_class": "ANALYTICAL_FIXTURE",
}
CLAIMS = {
    "customer_acceptance": False,
    "global_optimum": False,
    "scientific_qualification": False,
    "production_qualification": False,
}

_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMITMENT_TOKEN = object()
_REFERENCE_SESSION_TOKEN = object()


class DecisionError(ValueError):
    """A customer decision request or evidence record is invalid."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class ModelInfrastructureFailure(DecisionError):
    """Typed model-service failure; it is never a physics result.

    The current study policy permits no in-oracle retry.  ``retryable`` is
    evidence for a future, separately identified study attempt; it does not
    let a caller continue this oracle after catching the exception.
    """

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


def _statement(value: object, name: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 500:
        raise DecisionError("statement_required", name)
    return value


def contract(
    *,
    contract_id: str,
    customer_requirement_ref: str,
    die_limit_c: float,
    hydraulic_limit_w: float,
) -> dict[str, object]:
    """Build the exact DEVELOPMENT decision contract supplied by a customer.

    There are intentionally no default limits.  Supplying a requirement ref
    records where the two limits came from; it does not make them scientifically
    or commercially qualified.
    """

    die_limit = _number(die_limit_c, "die_limit_c")
    hydraulic_limit = _number(hydraulic_limit_w, "hydraulic_limit_w")
    if hydraulic_limit < 0:
        raise DecisionError("hydraulic_limit_negative")
    body = {
        "schema": CONTRACT_SCHEMA,
        "contract_id": _token(contract_id, "contract_id"),
        "challenge": CHALLENGE,
        "scope": SCOPE,
        "material": MATERIAL,
        "customer_requirement_ref": _token(
            customer_requirement_ref, "customer_requirement_ref"
        ),
        "decision": DECISION,
        "objective": dict(OBJECTIVE),
        "constraints": {
            "die_peak_c_max": die_limit,
            "hydraulic_power_w_max": hydraulic_limit,
        },
        "tie_policy": TIE_POLICY,
        "reference": dict(REFERENCE),
        "query_policy": {
            "accounting_unit": QUERY_ACCOUNTING_UNIT,
            "duplicate_policy": DUPLICATE_QUERY_POLICY,
            "retry_policy": dict(MODEL_RETRY_POLICY),
        },
        "verification_policy": {
            "accounting_unit": VERIFICATION_ACCOUNTING_UNIT,
            "repeated_commitment": "FORBIDDEN",
            "cache_policy": "CONDITION_EVIDENCE_COUNTS;SOLVER_EXECUTION_DOES_NOT_REPEAT",
        },
        "claims": dict(CLAIMS),
    }
    return {**body, "contract_digest": digest(body)}


def validate_contract(document: object) -> dict[str, object]:
    if type(document) is not dict:
        raise DecisionError("contract_is_object")
    required = {
        "schema",
        "contract_id",
        "challenge",
        "scope",
        "material",
        "customer_requirement_ref",
        "decision",
        "objective",
        "constraints",
        "tie_policy",
        "reference",
        "query_policy",
        "verification_policy",
        "claims",
        "contract_digest",
    }
    if set(document) != required:
        raise DecisionError(
            "contract_fields", ",".join(sorted(set(document) ^ required))
        )
    body = {key: value for key, value in document.items() if key != "contract_digest"}
    if digest(body) != document["contract_digest"]:
        raise DecisionError("contract_digest_mismatch")
    if (
        document["schema"] != CONTRACT_SCHEMA
        or document["challenge"] != CHALLENGE
        or document["scope"] != SCOPE
        or document["material"] != MATERIAL
    ):
        raise DecisionError("contract_identity")
    _token(document["contract_id"], "contract_id")
    _token(document["customer_requirement_ref"], "customer_requirement_ref")
    constraints = document["constraints"]
    if type(constraints) is not dict or set(constraints) != {
        "die_peak_c_max",
        "hydraulic_power_w_max",
    }:
        raise DecisionError("contract_constraints")
    _number(constraints["die_peak_c_max"], "die_peak_c_max")
    if _number(constraints["hydraulic_power_w_max"], "hydraulic_power_w_max") < 0:
        raise DecisionError("hydraulic_limit_negative")
    if document["tie_policy"] != TIE_POLICY:
        raise DecisionError("contract_tie_policy")
    if document["decision"] != DECISION or document["objective"] != OBJECTIVE:
        raise DecisionError("contract_decision")
    if document["reference"] != REFERENCE:
        raise DecisionError("contract_reference")
    if document["query_policy"] != {
        "accounting_unit": QUERY_ACCOUNTING_UNIT,
        "duplicate_policy": DUPLICATE_QUERY_POLICY,
        "retry_policy": MODEL_RETRY_POLICY,
    }:
        raise DecisionError("contract_query_policy")
    if document["verification_policy"] != {
        "accounting_unit": VERIFICATION_ACCOUNTING_UNIT,
        "repeated_commitment": "FORBIDDEN",
        "cache_policy": "CONDITION_EVIDENCE_COUNTS;SOLVER_EXECUTION_DOES_NOT_REPEAT",
    }:
        raise DecisionError("contract_verification_policy")
    if document["claims"] != CLAIMS:
        raise DecisionError("contract_claims")
    return document


def _grid(
    rows: list[dict[str, float]], names: tuple[str, ...]
) -> list[tuple[float, ...]]:
    tuples = [tuple(float(row[name]) for name in names) for row in rows]
    if len(set(tuples)) != len(tuples):
        raise DecisionError("candidate_rows_repeated")
    axes = [sorted({row[index] for row in tuples}) for index in range(len(names))]
    size = math.prod(len(axis) for axis in axes)
    if size != len(tuples):
        raise DecisionError("design_space_is_not_a_full_grid")
    return sorted(tuples)


def _conditions(rows: list[dict[str, float]]) -> list[tuple[float, ...]]:
    tuples = [tuple(float(row[name]) for name in CONDITION_VARIABLES) for row in rows]
    if len(set(tuples)) != len(tuples):
        raise DecisionError("condition_rows_repeated")
    return tuples


def request(
    decision_contract: dict[str, object], neutral: dict[str, object]
) -> tuple[dict[str, object], list[tuple[float, ...]]]:
    """Translate a challenge-neutral request into the cold-plate engine."""

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
    seed_policy = _statement(neutral.get("seed_policy"), "seed_policy")

    designs = neutral.get("designs")
    conditions = neutral.get("conditions")
    if (
        type(designs) is not list
        or type(conditions) is not list
        or not designs
        or not conditions
    ):
        raise DecisionError("designs_and_conditions_required")
    if any(
        type(row) is not dict or set(row) != set(DESIGN_VARIABLES) for row in designs
    ):
        raise DecisionError("design_variables")
    if any(
        type(row) is not dict or set(row) != set(CONDITION_VARIABLES)
        for row in conditions
    ):
        raise DecisionError("condition_variables")

    normalized_designs = [
        {name: _number(row[name], name) for name in DESIGN_VARIABLES} for row in designs
    ]
    normalized_conditions = [
        {name: _number(row[name], name) for name in CONDITION_VARIABLES}
        for row in conditions
    ]
    space = _grid(normalized_designs, DESIGN_VARIABLES)
    condition_space = _conditions(normalized_conditions)
    if neutral["verification_budget"] < len(condition_space):
        raise DecisionError("verification_budget_below_condition_count")
    for design in space:
        for condition in condition_space:
            domain.check_inputs(
                dict(
                    zip(
                        (*DESIGN_VARIABLES, *CONDITION_VARIABLES), (*design, *condition)
                    )
                )
            )

    body = {
        "schema": REQUEST_SCHEMA,
        "challenge": CHALLENGE,
        "scope": SCOPE,
        "material": MATERIAL,
        "mode": MODE,
        "contract_digest": decision_contract["contract_digest"],
        "model": dict(model),
        "designs": normalized_designs,
        "conditions": normalized_conditions,
        "candidate_space_digest": digest(normalized_designs),
        "condition_space_digest": digest(normalized_conditions),
        "query_budget": neutral["query_budget"],
        "verification_budget": neutral["verification_budget"],
        "query_policy": {
            "accounting_unit": QUERY_ACCOUNTING_UNIT,
            "duplicate_policy": DUPLICATE_QUERY_POLICY,
            "retry_policy": dict(MODEL_RETRY_POLICY),
        },
        "verification_policy": {
            "accounting_unit": VERIFICATION_ACCOUNTING_UNIT,
            "repeated_commitment": "FORBIDDEN",
            "cache_policy": "CONDITION_EVIDENCE_COUNTS;SOLVER_EXECUTION_DOES_NOT_REPEAT",
        },
        "method": dict(method),
        "seed_policy": seed_policy,
    }
    return {**body, "request_digest": digest(body)}, space


def _point_case(point: tuple[float, ...]) -> dict[str, float]:
    return domain.check_inputs(
        dict(zip((*DESIGN_VARIABLES, *CONDITION_VARIABLES), point))
    )


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
        "cache_policy": "CONDITION_EVIDENCE_COUNTS;SOLVER_EXECUTION_DOES_NOT_REPEAT",
    }:
        raise DecisionError("request_verification_policy")
    for name in ("query_budget", "verification_budget"):
        if type(req[name]) is not int or req[name] <= 0:
            raise DecisionError("positive_integer_required", name)
    if req["verification_budget"] < len(req["conditions"]):
        raise DecisionError("verification_budget_below_condition_count")
    return req


def quantities(
    decision_contract: dict[str, object], case: dict[str, float], outputs: object
) -> dict[str, object]:
    """Decision quantities from one model or reference output."""

    if type(outputs) is not dict or set(outputs) != set(exam.SHAPES):
        raise DecisionError("prediction_outputs_are_exact")
    verdicts = exam.gates(outputs, case)
    failed = sorted(name for name, verdict in verdicts.items() if verdict == exam.FAIL)
    if failed:
        raise DecisionError("prediction_failed_physical_gate", ",".join(failed))
    constraints = decision_contract["constraints"]
    row = exam.feasibility(
        case,
        outputs,
        die_limit_c=constraints["die_peak_c_max"],
        hydraulic_limit_w=constraints["hydraulic_power_w_max"],
    )
    return {
        **row,
        "prediction_validity_gates": dict(verdicts),
        "die_margin_c": constraints["die_peak_c_max"] - row["die_peak_c"],
        "hydraulic_margin_w": constraints["hydraulic_power_w_max"] - row["hydraulic_w"],
    }


class Oracle:
    """Fail-closed model access over declared, unique design-condition points.

    The budget unit is an attempted model point.  A batch is reserved in the
    log before inference, so infrastructure failure, malformed output, and a
    failed prediction-validity gate still consume the requested points.  Any
    failed batch seals the oracle; a caller cannot catch an exception and
    continue an ostensibly valid study.
    """

    def __init__(self, decision_contract, infer, req, space):
        validate_contract(decision_contract)
        _validate_request(req, decision_contract["contract_digest"])
        declared_space = _grid(req["designs"], DESIGN_VARIABLES)
        if list(space) != declared_space:
            raise DecisionError("oracle_space_mismatch")
        self.contract = decision_contract
        self.infer = infer
        self.budget = req["query_budget"]
        self.request_digest = req["request_digest"]
        self.designs = set(space)
        self.conditions = {
            tuple(float(row[name]) for name in CONDITION_VARIABLES)
            for row in req["conditions"]
        }
        self.log: list[dict[str, object]] = []
        self.elapsed = 0.0
        self._attempted_points: set[tuple[float, ...]] = set()
        self._terminal_failure: dict[str, object] | None = None

    @property
    def used(self) -> int:
        return len(self.log)

    @property
    def successful(self) -> int:
        return sum(row["status"] == "OK" for row in self.log)

    @property
    def terminal_failure(self):
        return None if self._terminal_failure is None else dict(self._terminal_failure)

    def _seal(self, code, *, detail="", query_ids=()):
        self._terminal_failure = {
            "code": code,
            "detail": detail,
            "query_ids": list(query_ids),
        }

    def _require_open(self):
        if self._terminal_failure is not None:
            raise DecisionError(
                "oracle_sealed_after_failed_batch", self._terminal_failure["code"]
            )

    def query(self, points):
        self._require_open()
        try:
            points = [
                tuple(_number(value, "query point") for value in point)
                for point in points
            ]
            if not points:
                raise DecisionError("query_batch_empty")
            if len(set(points)) != len(points):
                raise DecisionError("duplicate_query_within_batch")
            if any(point in self._attempted_points for point in points):
                raise DecisionError("duplicate_query_across_calls")
            if self.used + len(points) > self.budget:
                raise DecisionError("query_budget_exhausted")
            for point in points:
                if len(point) != len(DESIGN_VARIABLES) + len(CONDITION_VARIABLES):
                    raise DecisionError("query_point_width")
                design = point[: len(DESIGN_VARIABLES)]
                condition = point[len(DESIGN_VARIABLES) :]
                if design not in self.designs:
                    raise DecisionError("undeclared_design_queried")
                if condition not in self.conditions:
                    raise DecisionError("undeclared_condition_queried")
        except DecisionError as error:
            self._seal(error.code, detail=str(error))
            raise

        start = self.used
        inputs = {
            f"q{start + index:06d}": _point_case(point)
            for index, point in enumerate(points)
        }
        batch = []
        for query_id, point in zip(inputs, points):
            entry = {
                "query_id": query_id,
                "point": list(point),
                "status": "ATTEMPTED",
                "quantities": None,
            }
            self.log.append(entry)
            batch.append(entry)
            self._attempted_points.add(point)

        started = time.perf_counter()
        try:
            predictions = self.infer(inputs)
        except ModelInfrastructureFailure as error:
            self.elapsed += time.perf_counter() - started
            for entry in batch:
                entry["status"] = "FAILED_INFRA"
                entry["failure_code"] = error.code
            self._seal(error.code, detail=error.cause, query_ids=inputs)
            raise
        except Exception as error:
            self.elapsed += time.perf_counter() - started
            failure = ModelInfrastructureFailure(type(error).__name__)
            for entry in batch:
                entry["status"] = "FAILED_INFRA"
                entry["failure_code"] = failure.code
            self._seal(failure.code, detail=failure.cause, query_ids=inputs)
            raise failure from error
        self.elapsed += time.perf_counter() - started

        try:
            if type(predictions) is not dict or set(predictions) != set(inputs):
                raise DecisionError("model_results_are_exactly_the_queries")
            rows = [
                quantities(self.contract, inputs[query_id], predictions[query_id])
                for query_id in inputs
            ]
        except DecisionError as error:
            status = (
                "FAILED_PHYSICS"
                if error.code == "prediction_failed_physical_gate"
                else "FAILED_PROTOCOL"
            )
            for entry in batch:
                entry["status"] = status
                entry["failure_code"] = error.code
            self._seal(error.code, detail=str(error), query_ids=inputs)
            raise

        for entry, row in zip(batch, rows):
            entry["status"] = "OK"
            entry["quantities"] = row
        return rows


def fixed_grid(decision_contract, oracle, req, space):
    """Exhaustive customer baseline: feasible everywhere, then least pumping."""

    conditions = [
        tuple(float(row[name]) for name in CONDITION_VARIABLES)
        for row in req["conditions"]
    ]
    points = [(*design, *condition) for design in space for condition in conditions]
    rows = oracle.query(points)
    table = dict(zip(points, rows))
    ranked = []
    for design in space:
        values = [table[(*design, *condition)] for condition in conditions]
        if all(row["feasible"] for row in values):
            ranked.append((max(row["hydraulic_w"] for row in values), design))
    if not ranked:
        return []
    worst, design = min(ranked)
    return [
        {
            **dict(zip(DESIGN_VARIABLES, design)),
            "predicted_worst_hydraulic_w": worst,
        }
    ]


@dataclass(frozen=True, slots=True, init=False)
class Commitment:
    """A proposal that can exist only after its write-once file exists."""

    _path: Path
    _encoded: bytes

    def __init__(self, token, path, encoded):
        if token is not _COMMITMENT_TOKEN:
            raise DecisionError("commitment_only_from_commit")
        object.__setattr__(self, "_path", Path(path))
        object.__setattr__(self, "_encoded", bytes(encoded))

    @property
    def path(self):
        return self._path

    @property
    def document(self):
        return json.loads(self._encoded)


def _selection_point(selection):
    return tuple(_number(selection[name], name) for name in DESIGN_VARIABLES)


def commit(req, selections, oracle, directory):
    """Validate and write a proposal before any reference can be called."""

    if req.get("request_digest") != oracle.request_digest:
        raise DecisionError("oracle_request_mismatch")
    _validate_request(req, oracle.contract["contract_digest"])
    oracle._require_open()
    if type(selections) is not list or len(selections) > 1:
        raise DecisionError("pb_inv_commits_at_most_one_design")
    if selections:
        selection = selections[0]
        if type(selection) is not dict or set(selection) != {
            *DESIGN_VARIABLES,
            "predicted_worst_hydraulic_w",
        }:
            raise DecisionError("selection_fields")
        design = _selection_point(selection)
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
        worst = max(rows[point]["hydraulic_w"] for point in expected)
        if selection["predicted_worst_hydraulic_w"] != worst:
            raise DecisionError("selection_objective_mismatch")

    body = {
        "schema": COMMITMENT_SCHEMA,
        "request": req,
        "query_accounting_unit": QUERY_ACCOUNTING_UNIT,
        "query_attempts": oracle.used,
        "query_successes": oracle.successful,
        "query_log_digest": digest(oracle.log),
        "selections": [dict(selection) for selection in selections],
        "status": "PROPOSAL" if selections else "ABSTAIN",
    }
    document = {**body, "commitment_digest": digest(body)}
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (
        req["request_digest"].removeprefix("sha256:") + ".commitment.json"
    )
    encoded = (json.dumps(document, sort_keys=True, indent=1) + "\n").encode()
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
    on_disk = json.loads(encoded)
    body = {key: value for key, value in on_disk.items() if key != "commitment_digest"}
    if digest(body) != on_disk.get("commitment_digest"):
        raise DecisionError("commitment_digest_mismatch")
    return on_disk


def _case_id(case):
    return "cold-plate-decision:" + digest(case).removeprefix("sha256:")


def _jobs(document):
    if not document["selections"]:
        return []
    design = {name: document["selections"][0][name] for name in DESIGN_VARIABLES}
    jobs = []
    for condition in document["request"]["conditions"]:
        case = domain.check_inputs({**design, **condition})
        jobs.append({"case_id": _case_id(case), "inputs": case})
    return jobs


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
        raise DecisionError("counted_cfd_record_fields")
    provenance = record["provenance"]
    if type(provenance) is not dict or set(provenance) != _COUNTED_PROVENANCE_FIELDS:
        raise DecisionError("counted_cfd_provenance_fields")
    if (
        provenance["evidence_class"] != "COUNTED_CFD"
        or provenance["solver_image"] != openfoam.IMAGE
    ):
        raise DecisionError("counted_cfd_identity")
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
    for name in ("artifact_count", "artifact_bytes", "execution_count", "cpu_limit"):
        if type(provenance[name]) is not int or provenance[name] <= 0:
            raise DecisionError("counted_cfd_positive_integer", name)
    if (
        type(provenance["retry_count"]) is not int
        or provenance["retry_count"] < 0
        or provenance["retry_count"] >= provenance["execution_count"]
    ):
        raise DecisionError("counted_cfd_retry_count")
    if _number(provenance["wall_s"], "wall_s") < 0:
        raise DecisionError("counted_cfd_wall_time")
    body = {
        **record,
        "provenance": {
            key: value for key, value in provenance.items() if key != "record_digest"
        },
    }
    if digest(body) != provenance["record_digest"]:
        raise DecisionError("counted_cfd_record_digest_mismatch")
    domain.check_inputs(record["inputs"])
    if type(record["status"]) is not str or not record["status"]:
        raise DecisionError("counted_cfd_status")
    if record["status"] == "OK" and (
        type(record["outputs"]) is not dict or type(record["checks"]) is not dict
    ):
        raise DecisionError("counted_cfd_success_evidence")
    return record


def _seal_counted_record(token, *, status, inputs, outputs, checks, provenance):
    """Seal a normalized record produced by the artifact-verifying importer."""

    if token is not _REFERENCE_SESSION_TOKEN:
        raise DecisionError("counted_cfd_only_from_artifact_importer")
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
        *,
        evidence_class,
        source,
        condition_budget,
        session_id,
        campaign_wall_s=0.0,
    ):
        if token is not _REFERENCE_SESSION_TOKEN:
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
        self.used = 0
        self.cache: dict[str, dict[str, object]] = {}
        self._verification_keys: set[str] = set()
        self.source_calls = 0
        self.solver_executions = 0
        self.retries = 0
        self.solver_wall_s = 0.0

    def acquire(self, verification_key, jobs, per_commitment_budget):
        _tagged_digest(verification_key, "verification_key")
        if verification_key in self._verification_keys:
            raise DecisionError("commitment_already_verified")
        if type(per_commitment_budget) is not int or per_commitment_budget < len(jobs):
            raise DecisionError("verification_budget_exhausted")
        if self.used + len(jobs) > self.condition_budget:
            raise DecisionError("reference_session_budget_exhausted")

        # Reserve before touching the source.  A source failure cannot be caught
        # and replayed for free under the same commitment.
        self._verification_keys.add(verification_key)
        self.used += len(jobs)
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
                if self.evidence_class == "COUNTED_CFD":
                    try:
                        _validate_counted_record(record)
                    except (DecisionError, TypeError, ValueError):
                        record = {
                            "status": "REFERENCE_PROVENANCE_INVALID",
                            "inputs": job["inputs"],
                            "outputs": None,
                            "checks": {},
                            "provenance": {
                                "evidence_class": "COUNTED_CFD",
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
                            "counted_cfd": False,
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


def analytical_fixture_reference(source, *, condition_budget, session_id):
    """Wrap a callback as explicitly non-counted analytical fixture evidence."""

    return ReferenceSession(
        _REFERENCE_SESSION_TOKEN,
        evidence_class="ANALYTICAL_FIXTURE",
        source=source,
        condition_budget=condition_budget,
        session_id=session_id,
    )


def counted_cfd_reference(
    records, *, condition_budget, session_id, campaign_wall_s=0.0
):
    """Build a counted session from records already sealed by the importer."""

    if type(records) is not dict:
        raise DecisionError("counted_cfd_records_object")
    for record in records.values():
        _validate_counted_record(record)

    def source(jobs):
        return {
            job["case_id"]: records[job["case_id"]]
            for job in jobs
            if job["case_id"] in records
        }

    return ReferenceSession(
        _REFERENCE_SESSION_TOKEN,
        evidence_class="COUNTED_CFD",
        source=source,
        condition_budget=condition_budget,
        session_id=session_id,
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
    outputs = record.get("outputs")
    if type(outputs) is not dict:
        return "REFERENCE_UNAVAILABLE", None, "REFERENCE_INVALID"
    predicted = {name: outputs.get(name) for name in exam.SHAPES}
    try:
        row = quantities(decision_contract, inputs, predicted)
    except DecisionError:
        return "REFERENCE_UNAVAILABLE", None, "REFERENCE_INVALID"
    verdict = "FEASIBLE" if row["feasible"] else "INFEASIBLE"
    return verdict, row, "OK"


def verify(decision_contract, commitment, reference):
    """Reference-check the already committed design and report every case."""

    validate_contract(decision_contract)
    document = _load_commitment(commitment)
    if document["request"]["contract_digest"] != decision_contract["contract_digest"]:
        raise DecisionError("contract_mismatch")
    if type(reference) is not ReferenceSession:
        raise DecisionError("classified_reference_session_required")
    jobs = _jobs(document)
    records, accounting = reference.acquire(
        document["commitment_digest"],
        jobs,
        document["request"]["verification_budget"],
    )
    rows = []
    counts = {verdict: 0 for verdict in VERDICTS}
    for job in jobs:
        verdict, values, reference_status = _reference_verdict(
            decision_contract, job, records.get(job["case_id"])
        )
        counts[verdict] += 1
        rows.append(
            {
                "case_id": job["case_id"],
                "verdict": verdict,
                "reference_status": reference_status,
                "reference_provenance": (
                    records.get(job["case_id"], {}).get("provenance")
                    if type(records.get(job["case_id"])) is dict
                    else None
                ),
                "reference": values,
            }
        )
    false_feasible = counts["INFEASIBLE"] > 0
    return {
        "schema": RESULT_SCHEMA,
        "challenge": CHALLENGE,
        "scope": SCOPE,
        "material": MATERIAL,
        "contract_digest": decision_contract["contract_digest"],
        "request_digest": document["request"]["request_digest"],
        "commitment_digest": document["commitment_digest"],
        "status": document["status"],
        "reference_evidence_class": reference.evidence_class,
        "counted_cfd_evidence": reference.evidence_class == "COUNTED_CFD",
        "verification_accounting": accounting,
        "reference_jobs": len(jobs),
        "verdicts": counts,
        "false_feasible": false_feasible,
        "rows": rows,
        "reference_session_metrics": reference.metrics(),
        "claims": {
            "best_design_is_global_optimum": False,
            "customer_acceptance": False,
            "scientific_qualification": False,
            "production_qualification": False,
            "unavailable_counted_as_feasible_or_infeasible": False,
        },
    }


def adapter(decision_contract):
    """The cold plate's adapter for Carbon's challenge-neutral search."""

    validate_contract(decision_contract)

    def engine_request(neutral):
        return request(decision_contract, neutral)

    def view(req, space):
        conditions = tuple(
            tuple(float(row[name]) for name in CONDITION_VARIABLES)
            for row in req["conditions"]
        )
        return View(
            mode=MODE,
            designs=tuple(space),
            conditions=conditions,
            verification_budget=req["verification_budget"],
            passes=lambda row: row["feasible"],
            objective=lambda row: row["hydraulic_w"],
            margin=lambda row: min(
                row["die_margin_c"]
                / max(1.0, abs(decision_contract["constraints"]["die_peak_c_max"])),
                row["hydraulic_margin_w"]
                / max(
                    1.0,
                    abs(decision_contract["constraints"]["hydraulic_power_w_max"]),
                ),
            ),
            select_design=lambda design, worst: {
                **dict(zip(DESIGN_VARIABLES, design)),
                "predicted_worst_hydraulic_w": worst,
            },
            select_point=lambda *_: (_ for _ in ()).throw(
                DecisionError("pb_adv_not_served")
            ),
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
