"""Offline paired construction receipts; no training, adoption or qualification."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path

from carbon.design_search.budget_registration import BudgetCap, BudgetLedger
from carbon.design_search.cost import VERIFICATION, Charge, Ledger, Unit, price
from carbon.design_search.equal_budget import _quantile

PLAN_SCHEMA = "carbon.dev.l5-comparison-plan.v1"
RECEIPT_SCHEMA = "carbon.dev.l5-arm-receipt.v1"
REPORT_SCHEMA = "carbon.dev.l5-comparison-report.v1"
CAVEAT = (
    "These three candidates are what one partly-broken hunt recovered: the wish "
    "line was counted only at the start of a line and the first two runs had no "
    "physics theme. A measurement of three is not a measurement of Level 5."
)
COUNTERS = ("updates", "objective_evaluations", "gradient_evaluations", "tokens")
ARMS = ("baseline", "candidate")
PHASES = ("setup", "construction", "line_search", "prediction", "verification")


class ComparisonRefused(ValueError):
    pass


def _shape(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ComparisonRefused(f"{label}: closed schema required")


def _number(value, label, *, integer=False, positive=False):
    if (
        type(value) not in ((int,) if integer else (int, float))
        or not math.isfinite(value)
        or value < 0
        or (positive and value == 0)
    ):
        raise ComparisonRefused(
            f"{label}: finite {'positive' if positive else 'nonnegative'} number required"
        )
    return value


def _text(value, label):
    if type(value) is not str or not value.strip():
        raise ComparisonRefused(f"{label}: identity required")


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(value, label):
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(c not in "0123456789abcdef" for c in value[7:])
    ):
        raise ComparisonRefused(f"{label}: sha256 identity required")


def _json(data):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ComparisonRefused("duplicate JSON key")
            out[key] = value
        return out

    return json.loads(
        data,
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(
            ComparisonRefused("nonfinite JSON")
        ),
    )


def seal(body, field):
    if field not in ("plan_digest", "receipt_digest") or field in body:
        raise ComparisonRefused("unsealed plan/receipt body required")
    return {**copy.deepcopy(body), field: digest(body)}


def _bound(document, field):
    if document[field] != digest({k: v for k, v in document.items() if k != field}):
        raise ComparisonRefused(f"{field}: digest mismatch")


@dataclass(frozen=True)
class PairPlan:
    """Immutable validated plan. Raw mappings cannot enter comparison directly."""

    encoded: bytes

    def __post_init__(self):
        if type(self.encoded) is not bytes:
            raise ComparisonRefused("PairPlan requires encoded closed input")
        plan = _json(self.encoded)
        _shape(
            plan,
            (
                "schema",
                "evidence_basis",
                "candidate_id",
                "common",
                "arms",
                "scenarios",
                "metrics",
                "bootstrap",
                "plan_digest",
            ),
            "plan",
        )
        _bound(plan, "plan_digest")
        if plan["schema"] != PLAN_SCHEMA or plan["evidence_basis"] not in (
            "SYNTHETIC_FIXTURE",
            "PUBLIC_DEVELOPMENT",
        ):
            raise ComparisonRefused("public development or synthetic plan required")
        if plan["candidate_id"] not in (
            "MONOTONE_CAPACITY",
            "PHYSICS_LOSS",
            "QUASI_NEWTON",
        ):
            raise ComparisonRefused("registered L5 hypothesis identifier required")
        common = plan["common"]
        _shape(
            common,
            (
                "steps",
                "width",
                "depth",
                "recipe",
                "data_digest",
                "seeds",
                "route",
                "budget",
            ),
            "common",
        )
        for key in ("steps", "width", "depth"):
            _number(common[key], key, integer=True, positive=True)
        _shape(common["recipe"], ("family", "settings"), "full base recipe")
        _text(common["recipe"]["family"], "base recipe family")
        settings = common["recipe"]["settings"]
        if type(settings) is not dict or any(
            settings.get(key) != common[key] for key in ("steps", "width", "depth")
        ):
            raise ComparisonRefused(
                "base recipe must bind the declared architecture and steps"
            )
        _sha(common["data_digest"], "training data")
        _text(common["route"], "hardware route")
        seeds = common["seeds"]
        if (
            type(seeds) is not list
            or not seeds
            or any(type(s) is not int or s < 0 for s in seeds)
            or len(set(seeds)) != len(seeds)
        ):
            raise ComparisonRefused("unique paired reconstruction seeds required")
        budget = common["budget"]
        _shape(budget, (*COUNTERS, "wall_s", "core_s"), "shared budget")
        for key in COUNTERS:
            _number(budget[key], key, integer=True)
        for key in ("wall_s", "core_s"):
            _number(budget[key], key, positive=True)
        if budget["updates"] != common["steps"]:
            raise ComparisonRefused(
                "update budget must include all main/polish updates"
            )
        _shape(plan["arms"], ARMS, "arms")
        for name, arm in plan["arms"].items():
            _shape(
                arm,
                (
                    "implementation_ref",
                    "construction_digest",
                    "construction",
                    "configuration",
                ),
                name,
            )
            _text(arm["implementation_ref"], name)
            _sha(arm["construction_digest"], name)
            construction = arm["construction"]
            _shape(construction, ("base_recipe", "feature"), "construction descriptor")
            if construction["base_recipe"] != common["recipe"]:
                raise ComparisonRefused(f"{name}: full base recipe differs")
            feature = construction["feature"]
            if name == "baseline":
                if feature is not None:
                    raise ComparisonRefused("baseline must exclude candidate feature")
            else:
                _shape(feature, ("candidate_id", "definition"), "candidate feature")
                if (
                    feature["candidate_id"] != plan["candidate_id"]
                    or type(feature["definition"]) is not dict
                    or not feature["definition"]
                ):
                    raise ComparisonRefused(
                        "exact candidate feature definition required"
                    )
            if arm["construction_digest"] != digest(
                {
                    "implementation_ref": arm["implementation_ref"],
                    "construction": construction,
                }
            ):
                raise ComparisonRefused("construction descriptor digest mismatch")
            if arm["configuration"] != common:
                raise ComparisonRefused(
                    f"{name}: unequal architecture/data/seeds/steps/route/budget"
                )
        if (
            plan["arms"]["candidate"]["construction_digest"]
            == plan["arms"]["baseline"]["construction_digest"]
        ):
            raise ComparisonRefused(
                "distinct with/without construction identities required"
            )
        scenarios = plan["scenarios"]
        if type(scenarios) is not dict or not scenarios:
            raise ComparisonRefused("declared task/near-variant scenarios required")
        kinds = set()
        for name, scenario in scenarios.items():
            _text(name, "scenario")
            _shape(scenario, ("kind", "variant", "reference_digest"), name)
            if scenario["kind"] not in ("target", "near_variant"):
                raise ComparisonRefused("target/near_variant partition required")
            _text(scenario["variant"], "variant")
            _sha(scenario["reference_digest"], "public reference")
            kinds.add(scenario["kind"])
        if kinds != {"target", "near_variant"}:
            raise ComparisonRefused("target AND near variants required")
        if type(plan["metrics"]) is not dict or "decision_loss" not in plan["metrics"]:
            raise ComparisonRefused("decision_loss measurement required")
        for name, metric in plan["metrics"].items():
            _text(name, "metric")
            _shape(metric, ("direction", "unit"), name)
            if metric["direction"] not in ("lower", "higher"):
                raise ComparisonRefused("metric direction required")
            _text(metric["unit"], "measurement unit")
        boot = plan["bootstrap"]
        _shape(boot, ("replicates", "confidence", "seed"), "bootstrap")
        _number(boot["replicates"], "replicates", integer=True, positive=True)
        if boot["replicates"] < 100:
            raise ComparisonRefused(
                "at least 100 bootstrap replicates required, as in equal-budget replay"
            )
        if (
            type(boot["confidence"]) not in (int, float)
            or not 0 < boot["confidence"] < 1
            or type(boot["seed"]) is not int
        ):
            raise ComparisonRefused("explicit bootstrap confidence/seed required")

    @classmethod
    def from_document(cls, document):
        return cls(_canonical(document))

    def document(self):
        return _json(self.encoded)


def _receipt(plan, raw):
    _shape(
        raw,
        (
            "schema",
            "evidence_basis",
            "plan_digest",
            "arm",
            "seed",
            "construction_digest",
            "model_digest",
            "configuration",
            "completion",
            "events",
            "totals",
            "measurements",
            "receipt_digest",
        ),
        "arm receipt",
    )
    _bound(raw, "receipt_digest")
    arm, seed = raw["arm"], raw["seed"]
    _sha(raw["model_digest"], "measured model artifact")
    if (
        raw["schema"] != RECEIPT_SCHEMA
        or raw["evidence_basis"] != plan["evidence_basis"]
        or raw["plan_digest"] != plan["plan_digest"]
    ):
        raise ComparisonRefused("receipt scope/plan binding mismatch")
    if arm not in ARMS or type(seed) is not int or seed not in plan["common"]["seeds"]:
        raise ComparisonRefused("receipt arm/paired seed mismatch")
    if (
        raw["construction_digest"] != plan["arms"][arm]["construction_digest"]
        or raw["configuration"] != plan["common"]
    ):
        raise ComparisonRefused("receipt construction or equal configuration mismatch")
    if raw["completion"] not in ("COMPLETE", "FAILED_INFRA"):
        raise ComparisonRefused("typed complete/infrastructure outcome required")
    budget = plan["common"]["budget"]
    ledger = BudgetLedger(BudgetCap(1, budget["wall_s"], budget["core_s"]))
    costs = Ledger()
    counters = dict.fromkeys(COUNTERS, 0)
    ids = set()
    phases = set()
    if type(raw["events"]) is not list or not raw["events"]:
        raise ComparisonRefused("complete metering event list required")
    for event in raw["events"]:
        _shape(
            event,
            ("id", "phase", *COUNTERS, "line_search_trials", "wall_s", "core_s"),
            "work event",
        )
        _text(event["id"], "metering event")
        if event["id"] in ids or event["phase"] not in PHASES:
            raise ComparisonRefused("duplicate event or unregistered phase")
        ids.add(event["id"])
        phases.add(event["phase"])
        for key in (*COUNTERS, "line_search_trials"):
            _number(event[key], key, integer=True)
        if event["phase"] != "construction" and event["updates"] != 0:
            raise ComparisonRefused("training updates require the construction phase")
        if event["phase"] == "line_search":
            if (
                event["line_search_trials"] < 1
                or min(event["objective_evaluations"], event["gradient_evaluations"])
                < event["line_search_trials"]
            ):
                raise ComparisonRefused(
                    "line-search trials require actual objective AND gradient counters"
                )
        elif event["line_search_trials"] != 0:
            raise ComparisonRefused(
                "line-search trials must be a separate metered phase"
            )
        cost = {key: _number(event[key], key) for key in ("wall_s", "core_s")}
        if not ledger.charge_overhead(cost):
            raise ComparisonRefused(f"{arm}: actual wall/core budget exceeded")
        category = (
            "verification"
            if event["phase"] == "verification"
            else "inference" if event["phase"] == "prediction" else "fitting"
        )
        if plan["evidence_basis"] == "PUBLIC_DEVELOPMENT":
            costs.add(
                Charge(
                    VERIFICATION if category == "verification" else arm,
                    category,
                    plan["common"]["route"],
                    cost["core_s"],
                    "MEASURED_CPU",
                    f"{arm}:{event['phase']}",
                )
            )
        for key in COUNTERS:
            counters[key] += event[key]
            if counters[key] > budget[key]:
                raise ComparisonRefused(f"{arm}: actual {key} budget exceeded")
    actual = {**counters, "wall_s": ledger.wall_s, "core_s": ledger.core_s}
    _shape(raw["totals"], actual, "metered totals")
    for key, value in actual.items():
        _number(raw["totals"][key], key, integer=key in COUNTERS)
        if raw["totals"][key] != value:
            raise ComparisonRefused(f"{arm}: event totals do not reconcile: {key}")
    if raw["completion"] == "COMPLETE":
        if (
            actual["updates"] != plan["common"]["steps"]
            or not {"construction", "prediction", "verification"} <= phases
            or min(actual["objective_evaluations"], actual["gradient_evaluations"])
            < actual["updates"]
        ):
            raise ComparisonRefused("complete construction work cannot be omitted")
        if plan["candidate_id"] == "QUASI_NEWTON" and "line_search" not in phases:
            raise ComparisonRefused("quasi-Newton needs explicit line-search metering")
        if (
            plan["evidence_basis"] == "PUBLIC_DEVELOPMENT"
            and min(actual["wall_s"], actual["core_s"]) <= 0
        ):
            raise ComparisonRefused(
                "zero-cost fixture cannot claim measured public execution"
            )
    _shape(raw["measurements"], plan["scenarios"], "measurement coverage")
    for scenario, item in raw["measurements"].items():
        _shape(item, ("reference_digest", "status", "values"), scenario)
        if item["reference_digest"] != plan["scenarios"][scenario]["reference_digest"]:
            raise ComparisonRefused(f"{scenario}: reference mismatch")
        if item["status"] not in ("MEASURED", "UNRESOLVED", "FAILED_INFRA"):
            raise ComparisonRefused("typed measurement status required")
        if raw["completion"] == "FAILED_INFRA" and item["status"] != "FAILED_INFRA":
            raise ComparisonRefused(
                "infrastructure failure cannot produce measured value"
            )
        _shape(item["values"], plan["metrics"], "metric coverage")
        for value in item["values"].values():
            if item["status"] == "MEASURED":
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ComparisonRefused("finite measured value required")
            elif value is not None:
                raise ComparisonRefused("unresolved/infra value must stay null")
    priced = (
        price(costs.charges(), Unit("core_seconds", plan["common"]["route"]))
        if plan["evidence_basis"] == "PUBLIC_DEVELOPMENT"
        else {
            "status": "SYNTHETIC_ASSUMPTION",
            "value": actual["core_s"],
            "unit": {"kind": "core_seconds", "route": plan["common"]["route"]},
        }
    )
    return copy.deepcopy(raw), {
        "actual": actual,
        "shared_cap": budget,
        "core_cost_ledger": costs.as_list(),
        "core_cost": priced,
        "metering_authority": (
            "SYNTHETIC_ASSUMPTION"
            if plan["evidence_basis"] == "SYNTHETIC_FIXTURE"
            else "HOST_DECLARED_NOT_AUTHENTICATED"
        ),
    }


def _effect(plan, pairs, scenarios, metric):
    seeds = plan["common"]["seeds"]
    matrix, missing = [], []
    for seed in seeds:
        row = []
        for scenario in scenarios:
            a, b = (pairs[(arm, seed)]["measurements"][scenario] for arm in ARMS)
            if a["status"] != "MEASURED" or b["status"] != "MEASURED":
                missing.append(
                    {
                        "seed": seed,
                        "scenario": scenario,
                        "baseline": a["status"],
                        "candidate": b["status"],
                    }
                )
                row.append(None)
            else:
                sign = 1 if plan["metrics"][metric]["direction"] == "lower" else -1
                delta = sign * (a["values"][metric] - b["values"][metric])
                if not math.isfinite(delta):
                    raise ComparisonRefused("paired difference overflow")
                row.append(delta)
        matrix.append(row)
    count = len(seeds) * len(scenarios)
    common = {
        "seeds": len(seeds),
        "scenarios": len(scenarios),
        "expected_pairs": count,
        "measured_pairs": count - len(missing),
        "missing": missing,
        "unit": plan["metrics"][metric]["unit"],
        "confidence": plan["bootstrap"]["confidence"],
        "equivalence": None,
        "accepted_improvement": None,
    }
    if missing:
        return {
            **common,
            "point_improvement": None,
            "interval": None,
            "result": "UNRESOLVED_INCOMPLETE_PAIRS",
        }
    point = statistics.fmean(value for row in matrix for value in row)
    if len(seeds) < 2 or len(scenarios) < 2:
        return {
            **common,
            "point_improvement": point,
            "interval": None,
            "result": "UNRESOLVED_INSUFFICIENT_REPLICATION",
        }
    rng = random.Random(plan["bootstrap"]["seed"])
    draws = []
    for _ in range(plan["bootstrap"]["replicates"]):
        rs = [rng.randrange(len(seeds)) for _ in seeds]
        cs = [rng.randrange(len(scenarios)) for _ in scenarios]
        draws.append(statistics.fmean(matrix[r][c] for r in rs for c in cs))
    tail = (1 - plan["bootstrap"]["confidence"]) / 2
    interval = [_quantile(draws, tail), _quantile(draws, 1 - tail)]
    result = (
        "NO_OBSERVED_DIFFERENCE"
        if all(value == 0 for row in matrix for value in row)
        else (
            "POSITIVE_DIRECTION"
            if interval[0] > 0
            else "NEGATIVE_DIRECTION" if interval[1] < 0 else "UNRESOLVED"
        )
    )
    return {
        **common,
        "point_improvement": point,
        "interval": interval,
        "result": result,
    }


def compare(plan: PairPlan, receipts):
    """Bind every paired seed and task before computing descriptive effects."""
    if not isinstance(plan, PairPlan):
        raise ComparisonRefused("validated PairPlan required")
    body = plan.document()
    if type(receipts) is not list:
        raise ComparisonRefused("explicit arm receipt list required")
    pairs, budgets = {}, {}
    for raw in receipts:
        record, budget = _receipt(body, raw)
        key = (record["arm"], record["seed"])
        if key in pairs:
            raise ComparisonRefused("duplicate paired arm/seed receipt")
        pairs[key], budgets[f"{key[0]}:{key[1]}"] = record, budget
    if set(pairs) != {(arm, seed) for arm in ARMS for seed in body["common"]["seeds"]}:
        raise ComparisonRefused("all baseline/candidate paired seeds required")
    groups = {}
    for name, scenario in body["scenarios"].items():
        groups.setdefault((scenario["kind"], scenario["variant"]), []).append(name)
    effects = {
        f"{kind}:{variant}": {
            metric: _effect(body, pairs, scenarios, metric)
            for metric in body["metrics"]
        }
        for (kind, variant), scenarios in groups.items()
    }
    return {
        "schema": REPORT_SCHEMA,
        "status": (
            "SYNTHETIC_FIXTURE_RESULT"
            if body["evidence_basis"] == "SYNTHETIC_FIXTURE"
            else "PUBLIC_DEVELOPMENT_DESCRIPTIVE"
        ),
        "plan_digest": body["plan_digest"],
        "candidate_id": body["candidate_id"],
        "receipt_digests": [pairs[key]["receipt_digest"] for key in sorted(pairs)],
        "budget_records": budgets,
        "effects": effects,
        "thresholds": "HUMAN_INPUT",
        "adoption": "HUMAN_INPUT",
        "accepted_improvement": None,
        "equivalence": None,
        "target_only_is_a_win": False,
        "eligibility": {
            "official": False,
            "score": False,
            "qualification": False,
            "settlement": False,
        },
        "hunt_recovery_caveat": CAVEAT,
        "limitations": [
            "Receipts are structurally checked, not executor-authenticated.",
            "Paired seed/condition bootstrap intervals are descriptive, not equivalence or qualification.",
            "Matched resource ceilings and actual consumption are both disclosed; equal steps alone do not establish equal work.",
            "No missing pair is imputed or removed to create a positive estimate.",
        ],
    }


def standin():
    """Identical analytic arms on OPT-15b target and every declared neighbour."""
    from scripts.dev.score_lab import physics

    root = Path(__file__).resolve().parents[2]
    config = _json((root / "scripts/dev/score_lab/physics-example.json").read_bytes())
    config["problem"][
        "constraint"
    ] = "loose"  # Explicit stand-in knob; no fitted physical population.
    panel = physics.build(config)
    scenarios = {}
    for qid, question in panel["value_questions"].items():
        kind = panel["value_strata"][qid]
        if kind == "extrapolated":
            continue
        variant = "target" if kind == "in_range" else qid.split("-")[2]
        scenarios[qid] = {
            "kind": "target" if kind == "in_range" else "near_variant",
            "variant": variant,
            "reference_digest": digest(question),
        }
    common = {
        "steps": 4,
        "width": 8,
        "depth": 1,
        "recipe": {
            "family": "ANALYTIC_NO_TRAINING",
            "settings": {
                "steps": 4,
                "width": 8,
                "depth": 1,
                "note": "synthetic placeholders",
            },
        },
        "data_digest": digest({"fixture": "analytic-no-training"}),
        "seeds": [0, 1, 2, 3, 4],
        "route": "synthetic-zero-cost-no-worker",
        "budget": {
            "updates": 4,
            "objective_evaluations": 8,
            "gradient_evaluations": 8,
            "tokens": 0,
            "wall_s": 1,
            "core_s": 1,
        },
    }
    document = seal(
        {
            "schema": PLAN_SCHEMA,
            "evidence_basis": "SYNTHETIC_FIXTURE",
            "candidate_id": "MONOTONE_CAPACITY",
            "common": common,
            "arms": {
                arm: {
                    "implementation_ref": "ANALYTIC_STANDIN_WITHOUT_L5_TRAINING:" + arm,
                    "construction": {
                        "base_recipe": common["recipe"],
                        "feature": (
                            None
                            if arm == "baseline"
                            else {
                                "candidate_id": "MONOTONE_CAPACITY",
                                "definition": {
                                    "standin": "identical analytic predictions; no capacity head"
                                },
                            }
                        ),
                    },
                    "configuration": common,
                }
                for arm in ARMS
            },
            "scenarios": scenarios,
            "metrics": {"decision_loss": {"direction": "lower", "unit": "toy_loss"}},
            "bootstrap": {"replicates": 200, "confidence": 0.95, "seed": 20261013},
        },
        "plan_digest",
    )
    for arm in ARMS:
        descriptor = document["arms"][arm]
        descriptor["construction_digest"] = digest(
            {
                "implementation_ref": descriptor["implementation_ref"],
                "construction": descriptor["construction"],
            }
        )
    document = seal(
        {key: value for key, value in document.items() if key != "plan_digest"},
        "plan_digest",
    )
    member = panel["members"][0]
    receipts = []
    for arm in ARMS:
        for seed in common["seeds"]:
            event = {
                "id": "analytic-construction-placeholder",
                "phase": "construction",
                "updates": 4,
                "objective_evaluations": 4,
                "gradient_evaluations": 4,
                "line_search_trials": 0,
                "tokens": 0,
                "wall_s": 0,
                "core_s": 0,
            }
            phases = [event] + [
                {
                    **event,
                    "id": phase,
                    "phase": phase,
                    "updates": 0,
                    "objective_evaluations": 0,
                    "gradient_evaluations": 0,
                }
                for phase in ("prediction", "verification")
            ]
            receipts.append(
                seal(
                    {
                        "schema": RECEIPT_SCHEMA,
                        "evidence_basis": "SYNTHETIC_FIXTURE",
                        "plan_digest": document["plan_digest"],
                        "arm": arm,
                        "seed": seed,
                        "construction_digest": document["arms"][arm][
                            "construction_digest"
                        ],
                        "model_digest": digest({"synthetic_model": arm, "seed": seed}),
                        "configuration": common,
                        "completion": "COMPLETE",
                        "events": phases,
                        "totals": {
                            key: event[key] for key in (*COUNTERS, "wall_s", "core_s")
                        },
                        "measurements": {
                            qid: {
                                "reference_digest": scenario["reference_digest"],
                                "status": (
                                    "MEASURED"
                                    if member["value_losses"][qid] is not None
                                    else "UNRESOLVED"
                                ),
                                "values": {
                                    "decision_loss": member["value_losses"][qid]
                                },
                            }
                            for qid, scenario in scenarios.items()
                        },
                    },
                    "receipt_digest",
                )
            )
    return document, receipts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standin", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--receipts", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.standin:
            if args.plan or args.receipts:
                raise ComparisonRefused("stand-in cannot mix with external receipts")
            document, receipts = standin()
        else:
            if args.plan is None or args.receipts is None:
                raise ComparisonRefused("explicit public plan and receipts required")
            for path in (args.plan, args.receipts):
                if str(path).startswith(("\\\\", "//")) or any(
                    p.is_symlink() for p in (path, *path.parents)
                ):
                    raise ComparisonRefused("local non-symlink input required")
            document, receipts = (
                _json(path.read_bytes()) for path in (args.plan, args.receipts)
            )
        report = compare(PairPlan.from_document(document), receipts)
        pack = {
            "plan": document,
            "receipts": receipts,
            "report": report,
            "report_digest": digest(report),
        }
        text = json.dumps(pack, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.out:
            args.out.write_text(text, encoding="utf-8", newline="\n")
        else:
            print(text, end="")
        return 0
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError) as error:
        parser.exit(2, f"L5 comparison refused: {error}; {CAVEAT}\n")


if __name__ == "__main__":
    main()
