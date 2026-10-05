"""Track B adapter for the motor torque-ripple decision (TRACK-B-HARNESS-01).

It wraps the registered motor study (``MOTOR_SYNTHETIC_DECISION_V2``, which
adopted the counted V1 campaign under OWNER-MOTOR-COUNTED-ADOPT-01) for
``carbon.design_search.track_b`` without changing it:

- the ``Problem``: its eight designs, its six conditions with their groups,
  and its decision rule. A design is feasible when the mean torque meets the
  study's synthetic floor and the ripple fraction stays within its limit. The
  objective is the ripple fraction, lower is better, worst case over
  conditions;
- predictors: the registered analytical model, the registered KRR
  reconstruction, a nearest-neighbour interpolation over the public TRAIN
  pool, and the solver through a replay of the counted GetDP records;
- a replay table built from the counted records (``build_replay``). The
  repository keeps the table, not the raw records.

The decision rule here is Track B's neutral PB-INV rule: ties go to the lower
design. The registered study breaks ties by higher mean torque first. The two
rules differ only on an exact tie, but the analytical model predicts zero
ripple everywhere, so it ties on every design: Track B picks d01, the study
d07. Both are reference-infeasible. The registered search methods are pinned,
so Track B does not adopt the study's tie-break.

One-time costs are the TRAIN pool's recorded solve time, by route, plus the
measured fitting CPU. As for cooling, the TRAIN pool ran partly on the
operator host and partly on RunPod CPU pods whose flavor was not recorded, so
a host-only unit reports those arms as UNPRICED_MIXED_HARDWARE.

DEVELOPMENT only.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

from carbon.design_search import cost, track_b

from . import customer_decision as cd
from . import decision_study as ds
from . import domain

CONFIG = "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json"
REPLAY = "docs/development/evidence/track-b-replay/motor-counted-v2.json"
REPLAY_SCHEMA = "carbon.design-search.track-b-replay.v1"
HOST_ROUTE = "operator-host-i7-12700H"
POOL_POD_ROUTE = "runpod-cpu-pod-16vcpu-flavor-unrecorded"
TRAIN_CPUS = {HOST_ROUTE: 2.0, POOL_POD_ROUTE: 1.0}
UNIT = cost.Unit("core_seconds", HOST_ROUTE)


def load_config(repository):
    return ds.load_config(Path(repository) / CONFIG, repository=repository)


def problem(config):
    contract = ds.decision_contract(config)
    designs = sorted(
        (
            track_b.Design(
                row["design_id"],
                tuple(row["values"][name] for name in cd.DESIGN_VARIABLES),
            )
            for row in config["designs"]
        ),
        key=lambda design: design.values,
    )
    conditions = tuple(
        track_b.Condition(
            row["condition_id"],
            row["group"],
            tuple(row["values"][name] for name in cd.CONDITION_VARIABLES),
        )
        for row in config["conditions"]
    )
    return (
        track_b.Problem(
            challenge=cd.CHALLENGE,
            designs=tuple(designs),
            conditions=conditions,
            passes=lambda q: bool(q["feasible"]),
            objective=lambda q: float(q["ripple_fraction"]),
            host_route=HOST_ROUTE,
            # The registered study's tie rule, reported beside Track B's.
            tie_break=lambda q: -float(q["mean_nm"]),
            tie_break_rule="registered study: higher worst-condition mean torque",
        ),
        contract,
    )


def _quantities(contract, outputs):
    try:
        return cd.quantities(contract, {"torque_nm": outputs["torque_nm"]})
    except cd.DecisionError:
        return None


def _train(config, repository):
    spec = config["models"]["learned-krr-v1"]
    path = Path(repository) / spec["training_records"]
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [record for record in records if record.get("status") == "OK"]


def _route(record):
    if str(record.get("execution", "")).startswith("runpod-cpu-pod"):
        return POOL_POD_ROUTE
    return HOST_ROUTE


def training_data_cost(train):
    by_route = {}
    for record in train:
        route = _route(record)
        by_route[route] = (
            by_route.get(route, 0.0) + record["wall_s"] * TRAIN_CPUS[route]
        )
    return tuple(
        (
            "training_data_generation",
            route,
            core_seconds,
            "ALLOCATED_CPU_X_WALL",
            f"public TRAIN pool cases on {route}",
        )
        for route, core_seconds in sorted(by_route.items())
    )


def _nearest_neighbour(train):
    import numpy as np

    from carbon import learned_baseline

    x = learned_baseline.scale(
        [record["inputs"] for record in train], domain.INPUTS, domain.INPUT_BOUNDS
    )

    def one(inputs):
        q = learned_baseline.scale([inputs], domain.INPUTS, domain.INPUT_BOUNDS)[0]
        index = int(np.argmin(((x - q) ** 2).sum(axis=1)))
        return {"torque_nm": list(train[index]["outputs"]["torque_nm"])}

    return lambda batch: {key: one(case) for key, case in batch.items()}


def _model(name, contract, batch_model, one_time=()):
    def infer(points):
        outputs = batch_model({i: cd._point_case(p) for i, p in enumerate(points)})
        return [_quantities(contract, outputs[i]) for i in range(len(points))]

    return track_b.Predictor(
        name=name,
        kind=track_b.MODEL,
        planning_core_seconds=0.0,
        planning_route=HOST_ROUTE,
        infer=infer,
        one_time=tuple(one_time),
    )


def predictors(config, *, repository, contract, reference):
    models, reconstruction = ds.reconstruct_models(config, repository=repository)
    train = _train(config, repository)
    data = training_data_cost(train)
    fitting = (
        (
            "fitting",
            HOST_ROUTE,
            float(reconstruction["learned-krr-v1"]["cpu_s"]),
            "MEASURED_CPU",
            "KRR reconstruction at the registered length and ridge",
        ),
    )
    return {
        "analytic-v1": _model("analytic-v1", contract, models["analytic-v1"]),
        "learned-krr-v1": _model(
            "learned-krr-v1", contract, models["learned-krr-v1"], data + fitting
        ),
        "nearest-neighbour-v1": _model(
            "nearest-neighbour-v1", contract, _nearest_neighbour(train), data
        ),
        "solver": track_b.Predictor(
            name="solver",
            kind=track_b.SOLVER,
            planning_core_seconds=planning_solve_core_seconds(reference),
            planning_route=HOST_ROUTE,
            reference=reference,
        ),
    }


def build_replay(config, attempt_directory, *, cpu_model):
    """A compact replay table from one counted GetDP attempt directory."""

    root = Path(attempt_directory)
    records_bytes = (root / "records.jsonl").read_bytes()
    host = json.loads((root / "host.json").read_text(encoding="utf-8"))
    by_inputs = {}
    for design in config["designs"]:
        for condition in config["conditions"]:
            key = json.dumps(
                {**design["values"], **condition["values"]}, sort_keys=True
            )
            by_inputs[key] = (design["design_id"], condition["condition_id"])
    cases = []
    for line in records_bytes.decode("utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        design_id, condition_id = by_inputs[
            json.dumps(record["inputs"], sort_keys=True)
        ]
        cases.append(
            {
                "case_id": record["case_id"],
                "design_id": design_id,
                "condition_id": condition_id,
                "status": record["status"],
                "outputs": (
                    {"torque_nm": record["outputs"]["torque_nm"]}
                    if record["status"] == "OK"
                    else None
                ),
                "wall_s": record["wall_s"],
                "cpus": host["cpus"],
            }
        )
    if len(cases) != len(config["designs"]) * len(config["conditions"]):
        raise ValueError("replay_is_not_the_full_finite_set")
    return {
        "schema": REPLAY_SCHEMA,
        "challenge": cd.CHALLENGE,
        "study_id": config["study_id"],
        "evidence_class": "COUNTED_GETDP",
        "route": HOST_ROUTE,
        "cpu_model": cpu_model,
        "parallel": host.get("parallel"),
        "solver_image": host.get("solver_image"),
        "source_records_sha256": "sha256:" + hashlib.sha256(records_bytes).hexdigest(),
        "cost_basis": "ALLOCATED_CPU_X_WALL (cpus x wall_s per case)",
        "cases": sorted(cases, key=lambda row: row["case_id"]),
    }


def replay_reference(config, table):
    tb_problem, contract = problem(config)
    designs = {d.design_id: d for d in tb_problem.designs}
    conditions = {c.condition_id: c for c in tb_problem.conditions}
    cases = {}
    for row in table["cases"]:
        point = tb_problem.point(
            designs[row["design_id"]], conditions[row["condition_id"]]
        )
        quantities = (
            None if row["outputs"] is None else _quantities(contract, row["outputs"])
        )
        cases[point] = track_b.Case(
            quantities, row["wall_s"] * row["cpus"], table["route"]
        )
    return track_b.Reference(
        cases,
        evidence_class=f"{table['evidence_class']}_REPLAY",
        source=table["source_records_sha256"],
    )


def median_solve_core_seconds(reference):
    return float(
        statistics.median(case.core_seconds for case in reference._cases.values())
    )


def planning_solve_core_seconds(reference, quantile=0.95):
    """The solver arm's planning charge: the p95 of the measured solve cost on
    its route, by linear interpolation (Test Lead, 2026-10-05). Actual cost
    always decides."""

    values = sorted(case.core_seconds for case in reference._cases.values())
    k = (len(values) - 1) * quantile
    low = int(k)
    high = min(low + 1, len(values) - 1)
    return float(values[low] + (values[high] - values[low]) * (k - low))


def proposed_budget_ladder(reference, ks=(6, 12, 24, 48)):
    """B = k x the median measured solve, in host core-seconds, proposed as
    for cooling; ``anchor_full_set`` = 48 x the planning charge, where the
    solver arm can plan the whole 8 x 6 finite set."""

    median = median_solve_core_seconds(reference)
    ladder = {f"k{k}": k * median for k in ks}
    ladder["anchor_full_set"] = 48 * planning_solve_core_seconds(reference)
    return ladder


#: Paired host/cpu5c wall-time ratio, maximum over the 12 cases of the motor
#: timing calibration (docs/development/evidence/motor-timing-2026-10-04).
MOTOR_PAIRED_HOST_PER_POD = 1.63


def bracket_conversions():
    """The two declared conversions of unrecorded-flavor pool-pod core-seconds
    into host core-seconds (Test Lead, 2026-10-05). The ratio is motor's own
    measurement, but applying it to the pool pods is an assumption: their
    flavor was not recorded."""

    return {
        "lower": (
            cost.Conversion(
                POOL_POD_ROUTE,
                HOST_ROUTE,
                1.0,
                "ASSUMPTION: one pool-pod core-second equals one host core-second",
            ),
        ),
        "upper": (
            cost.Conversion(
                POOL_POD_ROUTE,
                HOST_ROUTE,
                MOTOR_PAIRED_HOST_PER_POD,
                "ASSUMPTION: motor host/cpu5c paired wall ratio 1.63 "
                "(motor-timing-2026-10-04); the pool pods' flavor was not recorded",
            ),
        ),
    }
