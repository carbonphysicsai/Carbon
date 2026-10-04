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

CONTRACT_SCHEMA = "carbon.cold-plate.customer-decision-contract.v1"
REQUEST_SCHEMA = "carbon.cold-plate.design-search-request.v1"
COMMITMENT_SCHEMA = "carbon.cold-plate.design-search-commitment.v1"
RESULT_SCHEMA = "carbon.cold-plate.design-search-result.v1"

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
CODE_PATHS = (
    "carbon/cold_plate/customer_decision.py",
    "carbon/cold_plate/domain.py",
    "carbon/cold_plate/exam.py",
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


class DecisionError(ValueError):
    """A customer decision request or evidence record is invalid."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


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
        "die_margin_c": constraints["die_peak_c_max"] - row["die_peak_c"],
        "hydraulic_margin_w": constraints["hydraulic_power_w_max"] - row["hydraulic_w"],
    }


class Oracle:
    """Budgeted model access over only the declared design-condition points."""

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

    @property
    def used(self) -> int:
        return len(self.log)

    def query(self, points):
        points = [
            tuple(_number(value, "query point") for value in point) for point in points
        ]
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
        inputs = {
            f"q{self.used + index:06d}": _point_case(point)
            for index, point in enumerate(points)
        }
        started = time.perf_counter()
        predictions = self.infer(inputs)
        self.elapsed += time.perf_counter() - started
        if type(predictions) is not dict or set(predictions) != set(inputs):
            raise DecisionError("model_results_are_exactly_the_queries")
        rows = []
        for query_id, point in zip(inputs, points):
            row = quantities(self.contract, inputs[query_id], predictions[query_id])
            self.log.append(
                {"query_id": query_id, "point": list(point), "quantities": row}
            )
            rows.append(row)
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
        "queries_used": oracle.used,
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
    jobs = _jobs(document)
    records = reference(jobs) if jobs else {}
    if type(records) is not dict:
        raise DecisionError("reference_results_are_object")
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
        "reference_jobs": len(jobs),
        "verdicts": counts,
        "false_feasible": false_feasible,
        "rows": rows,
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
