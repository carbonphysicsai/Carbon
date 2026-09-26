"""The Engineering Value Contract: one versioned, machine-readable decision.

Schema `carbon.engineering-value-contract.v1`. The contract records:
- the decision and its intended use;
- the design variables and their allowed values;
- the operating-condition envelope and the frozen scenarios;
- the objective and its units, and the constraints;
- the minimum useful improvement and the cost of each kind of mistake;
- the reference identity and its measurement limits;
- the baseline method and the tie rule;
- the model reconstruction policy;
- the scoring candidates and the acceptance rule;
- the budgets, the data scope and the authority.

The schema is independent of any browser or agent, so the Workbench can
later collect the same fields (`carbon.scientific_tasks.workbench_value`).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from carbon.challenge_registry import resolve

from ..challenge import CHALLENGE
from ..domain import INPUT_BOUNDS

SCHEMA = "carbon.engineering-value-contract.v1"
CONTRACTS = Path(__file__).resolve().parent / "contracts"
REQUIRED = {
    "schema",
    "contract_id",
    "version",
    "status",
    "challenge",
    "decision",
    "design_variables",
    "operating_conditions",
    "scenarios",
    "objective",
    "constraints",
    "preferences_status",
    "minimum_useful_improvement_s",
    "mistake_costs",
    "baseline",
    "tie_rule",
    "reference",
    "models",
    "scoring_candidates",
    "acceptance",
    "budgets",
    "data_scope",
    "authority",
}
CONSTRAINT_QUANTITIES = {
    "reach_cv_in_window": "time_to_cv_onset_s",
    "no_plating_onset": "plating_margin_v",
    "peak_temperature": "peak_temperature_c",
}


class ContractError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def _within(value, bounds):
    return bounds[0] <= value <= bounds[1]


def validate(document):
    """Validate a contract document; returns it unchanged, or raises by name."""
    from carbon.scoring.weight_profile import parse

    if type(document) is not dict or document.get("schema") != SCHEMA:
        raise ContractError("contract_schema")
    missing = REQUIRED - set(document)
    if missing:
        raise ContractError("contract_fields", ",".join(sorted(missing)))
    challenge = document["challenge"]
    resolve(challenge["id"], challenge["version"], "cpu_research")
    if (challenge["id"], challenge["version"]) != (
        CHALLENGE.challenge_id,
        CHALLENGE.version,
    ):
        raise ContractError("contract_challenge", "this runner serves battery only")
    design = document["design_variables"]
    if set(design) != {"c1", "c2"}:
        raise ContractError("design_variables", "exactly c1 and c2")
    for name, spec in design.items():
        allowed = spec["allowed"]
        if not allowed or len(set(allowed)) != len(allowed):
            raise ContractError("design_values", name)
        if not all(_within(float(v), INPUT_BOUNDS[name]) for v in allowed):
            raise ContractError("design_outside_generator", name)
    envelope = document["operating_conditions"]["envelope"]
    for name in ("t_amb_c", "soc0"):
        low, high = envelope[name]
        if not (INPUT_BOUNDS[name][0] <= low <= high <= INPUT_BOUNDS[name][1]):
            raise ContractError("envelope_outside_generator", name)
    scenario_ids = set()
    for split in ("development", "verification"):
        for scenario in document["scenarios"][split]:
            if scenario["id"] in scenario_ids:
                raise ContractError("scenario_duplicate", scenario["id"])
            scenario_ids.add(scenario["id"])
            if not scenario["conditions"]:
                raise ContractError("scenario_empty", scenario["id"])
            for t_amb, soc0 in scenario["conditions"]:
                if not (
                    _within(t_amb, envelope["t_amb_c"])
                    and _within(soc0, envelope["soc0"])
                ):
                    raise ContractError("condition_outside_envelope", scenario["id"])
    if {c["id"] for c in document["constraints"]} != set(CONSTRAINT_QUANTITIES):
        raise ContractError("constraints", "the EV1 constraint set")
    baseline = document["baseline"]["protocol"]
    if (
        baseline["c1"] not in design["c1"]["allowed"]
        or baseline["c2"] not in design["c2"]["allowed"]
    ):
        raise ContractError("baseline_outside_candidates")
    for profile in document["scoring_candidates"]["weight_profiles"]:
        parse(profile)
    if document["data_scope"]["classification"] != "PUBLIC_SYNTHETIC":
        # Client studies need the private execution route; this public runner
        # never accepts client material (GOAL-WORKBENCH-15 E8).
        raise ContractError("data_scope", "only PUBLIC_SYNTHETIC here")
    authority = document["authority"]
    if any(
        authority.get(k)
        for k in ("chain", "reward", "changes_testnet_rule", "qualification")
    ):
        raise ContractError("authority", "DEVELOPMENT evidence only")
    return document


def load(path=None):
    """The contract and its digest (over the canonical document)."""
    path = Path(path) if path else CONTRACTS / "ev1-charge-protocol-selection.v1.json"
    document = validate(json.loads(path.read_bytes()))
    return document, digest(document)


def candidates(contract):
    """The frozen candidate set, in the declared (c1, c2) order."""
    design = contract["design_variables"]
    return [
        {"id": f"c1={c1:g},c2={c2:g}", "c1": float(c1), "c2": float(c2)}
        for c1 in sorted(design["c1"]["allowed"])
        for c2 in sorted(design["c2"]["allowed"])
    ]


def candidate_id(protocol):
    return f"c1={protocol['c1']:g},c2={protocol['c2']:g}"


def scenarios(contract, split=None):
    splits = ("development", "verification") if split is None else (split,)
    return [
        {**scenario, "split": s}
        for s in splits
        for scenario in contract["scenarios"][s]
    ]


def decision_cases(contract, split=None):
    """Every (scenario, candidate, condition) the decision needs, as reference
    jobs. Case ids carry no reference information."""
    jobs = []
    for scenario in scenarios(contract, split):
        for candidate in candidates(contract):
            for index, (t_amb, soc0) in enumerate(scenario["conditions"]):
                jobs.append(
                    {
                        "case_id": f"ev1:{scenario['id']}:{candidate['id']}:{index}",
                        "scenario": scenario["id"],
                        "candidate": candidate["id"],
                        "condition": index,
                        "c1": candidate["c1"],
                        "c2": candidate["c2"],
                        "t_amb_c": float(t_amb),
                        "soc0": float(soc0),
                    }
                )
    return jobs
