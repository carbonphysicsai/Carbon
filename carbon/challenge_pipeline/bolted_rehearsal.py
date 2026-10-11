"""Pure REPRESENTATIVE joint preparation. No files written or solvers called."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import time
from pathlib import Path

FAMILY = "bolted-joint"
SCOPE = "REPRESENTATIVE"
IMAGE = "sha256:d9ef68d016226a945c7eefcb6b2261c60a11249ee0f93458ae6c3aca956fd6f8"
PINS = {
    "image": IMAGE,
    "ccx_source": "sha256:9c88385c10fb04f5dc6c4e98027a51bebdd8aee3920e05190d6c1dd08357d6e7",
    "deck": "bolted-contact-draft.v1",
    "observer": "bolted-representative-history.v1",
}
FIELDS = (
    "bolt_diameter_mm",
    "bolt_spacing_mm",
    "support_thickness_mm",
    "preload_max_n",
)
BOUNDS = ((8, 12), (40, 70), (8, 16), (8000, 16000))
STEPS = ("assembly", "lock", "service")
OUTPUTS = (
    "opening_mm",
    "slip_mm",
    "clamp_n",
    "bolt_force_n",
    "stress_mean_mpa",
    "displacement_mm",
)


def digest(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )


def number(value, *, positive=False):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or (positive and value <= 0)
    ):
        raise ValueError("finite numeric value required")
    return float(value)


def geometry(action):
    if type(action) is not dict or set(action) != set(FIELDS):
        raise ValueError("closed representative action required")
    out = {k: number(action[k]) for k in FIELDS}
    if any(not lo <= out[k] <= hi for k, (lo, hi) in zip(FIELDS, BOUNDS)):
        raise ValueError("outside representative support, not a customer law")
    return out


def actions():
    return [
        dict(zip(FIELDS, row))
        for row in itertools.product(
            (8, 10, 12), (40, 55, 70), (8, 12, 16), (8000, 12000, 16000)
        )
    ]


def conditions():
    return [
        {
            "id": "nominal",
            "mu": 0.2,
            "alpha_A": 1.6,
            "clamp_state": "mid",
            "opening_n": 2000,
            "shear_n": 1000,
            "eccentricity_mm": 50,
        },
        {
            "id": "low-clamp-friction",
            "mu": 0.1,
            "alpha_A": 2.0,
            "clamp_state": "low",
            "opening_n": 4000,
            "shear_n": 2000,
            "eccentricity_mm": 50,
        },
        {
            "id": "high-preload-load",
            "mu": 0.3,
            "alpha_A": 1.4,
            "clamp_state": "high",
            "opening_n": 4000,
            "shear_n": 2000,
            "eccentricity_mm": 50,
        },
        {
            "id": "reverse-eccentric",
            "mu": 0.1,
            "alpha_A": 1.6,
            "clamp_state": "low",
            "opening_n": 4000,
            "shear_n": 2000,
            "eccentricity_mm": -50,
        },
    ]


def case(action, condition, rung):
    if condition not in conditions() or type(rung) is not int or rung not in (1, 2):
        raise ValueError("registered representative condition/rung required")
    return {
        "scope": SCOPE,
        "action": geometry(action),
        "condition": dict(condition),
        "rung": rung,
        "pins": dict(PINS),
    }


def validate_case(row):
    if type(row) is not dict or set(row) != {
        "scope",
        "action",
        "condition",
        "rung",
        "pins",
    }:
        raise ValueError("exact representative case required")
    if row != case(row["action"], row["condition"], row["rung"]):
        raise ValueError("representative case/pins mismatch")
    return row


def physical_key(row):
    validate_case(row)
    return digest({"action": row["action"], "condition": row["condition"]})


def panel(designs, *, rungs, completed, scheduled):
    if not designs or not rungs or len(designs) * len(rungs) > 1000:
        raise ValueError("bounded nonempty proposal required")
    known = {}
    for state, inventory in (("COMPLETED", completed), ("SCHEDULED", scheduled)):
        for row in inventory:
            key = digest(validate_case(row))
            if key in known:
                raise ValueError("conflicting reuse identity")
            known[key] = state
    rows = {}
    for a, c, rung in itertools.product(designs, conditions(), rungs):
        row = case(a, c, rung)
        key = digest(row)
        rows[key] = {"case": row, "reuse": known.get(key, "NEW")}
    body = {
        "scope": SCOPE,
        "family": FAMILY,
        "cases": list(rows.values()),
        "status": "PROPOSED_NOT_REGISTERED",
        "dispatchable": False,
        "customer_result": False,
    }
    return {**body, "panel_digest": digest(body)}


def train_plan(designs, test_cases):
    if not test_cases:
        raise ValueError("explicit nonempty test inventory required")
    # Hold whole geometry out across all service siblings and mesh/pin changes.
    excluded = {digest(validate_case(r)["action"]) for r in test_cases}
    rows = {
        physical_key(case(a, c, 1)): case(a, c, 1)
        for a, c in itertools.product(designs, conditions())
        if digest(geometry(a)) not in excluded
    }
    return {
        "scope": SCOPE,
        "cases": list(rows.values()),
        "status": "PROPOSED_NOT_REGISTERED",
        "dispatchable": False,
    }


def preload(row):
    validate_case(row)
    hi = row["action"]["preload_max_n"]
    c = row["condition"]
    lo = hi / c["alpha_A"]
    return {"low": lo, "high": hi, "mid": (lo + hi) / 2}[c["clamp_state"]]


def deck(row, *, normal_penalty_mpa_per_mm, stick_slope_mpa_per_mm):
    """Draft fragments only. DC owns the solid mesh and solved lock transition."""
    validate_case(row)
    normal = number(normal_penalty_mpa_per_mm, positive=True)
    stick = number(stick_slope_mpa_per_mm, positive=True)
    f, mu = preload(row), row["condition"]["mu"]
    model = "** REPRESENTATIVE / UNVERIFIED, mm N MPa\n*INCLUDE,INPUT=registered-mesh.inp\n*MATERIAL,NAME=REP_STEEL\n*ELASTIC\n197000.,0.29\n"
    for part in ("TOP", "BASE", "BOLTS"):
        model += f"*SOLID SECTION,ELSET={part},MATERIAL=REP_STEEL\n"
    model += f"*SURFACE INTERACTION,NAME=FAYING\n*SURFACE BEHAVIOR,PRESSURE-OVERCLOSURE=LINEAR\n{normal}\n*FRICTION\n{mu},{stick}\n*CONTACT PAIR,INTERACTION=FAYING,TYPE=SURFACE TO SURFACE\nFAYING_SLAVE,FAYING_MASTER\n"
    model += "** HEAD/NUT/SHANK contact pairs and smooth solid bolt cuts supplied by registered mesh\n*INCLUDE,INPUT=registered-bearing-contact.inp\n"
    for i in (1, 2):
        model += f"*PRE-TENSION SECTION,SURFACE=BOLT_CUT_{i},NODE={9900+i}\n0.,0.,1.\n"
    model += "*BOUNDARY\nFIX,1,3\n"
    outputs = "*NODE FILE\nU,RF\n*NODE PRINT,NSET=PRETENSION\nU,RF\n*CONTACT FILE\nCDIS,CSTR\n*EL PRINT,ELSET=REGULAR_STRESS\nS,COORD\n"
    assembly = f"*STEP,NLGEOM,INC=200\n*STATIC\n0.1,1.,1.e-6,0.1\n*CLOAD\n9901,1,{f}\n9902,1,{f}\n{outputs}*END STEP\n"
    service = "** RETAIN state; remove assembly force commands and hold the solved pretension-section extensions.\n** HUMAN_INPUT: accepted same-case displacement/restart transition, not a new force-maintained preload.\n** Apply distributed service pad traction with force and eccentric moment preserved.\n** HUMAN_INPUT: verified contact/mesh/step and observer mapping before service deck rendering.\n"
    return {
        "scope": SCOPE,
        "pins": dict(PINS),
        "status": "UNVERIFIED_DECK_DRAFT",
        "files": {
            "model.inp": model,
            "assembly-step.inc": assembly,
            "service-step.template": service,
        },
        "mesh_contract": {
            "solids": ["TOP", "BASE", "BOLTS"],
            "surfaces": ["FAYING_SLAVE", "FAYING_MASTER", "BOLT_CUT_1", "BOLT_CUT_2"],
            "node_sets": ["FIX", "PRETENSION", "LOAD_PAD", "DISPLACEMENT_PROBE"],
            "reserved_pretension_nodes": [9901, 9902],
            "state": "HUMAN_INPUT mesh/bearing-contact and full-history bindings",
        },
        "dispatchable": False,
        "customer_result": False,
    }


def observe(row, history):
    """All mapped increments, not three endpoints; extractor verification pending."""
    validate_case(row)
    if type(history) is not list or len(history) != len(STEPS):
        raise ValueError("complete assembly-lock-service history required")
    out = []
    finding = False
    records = []
    for stage, section in zip(STEPS, history):
        if type(section) is not dict or set(section) != {
            "stage",
            "source_sha256",
            "declared_increments",
            "increments",
        }:
            raise ValueError("closed stage and raw-source identity required")
        if (
            section["stage"] != stage
            or type(section["declared_increments"]) is not int
            or not 1 <= section["declared_increments"] <= 10000
        ):
            raise ValueError("ordered bounded nonempty stages required")
        source = section["source_sha256"]
        if (
            type(source) is not str
            or len(source) != 64
            or any(c not in "0123456789abcdef" for c in source)
        ):
            raise ValueError("raw-source SHA256 required")
        if (
            type(section["increments"]) is not list
            or len(section["increments"]) != section["declared_increments"]
        ):
            raise ValueError("every declared increment required")
        for i, data in enumerate(section["increments"], 1):
            if type(data) is not dict or set(data) != {
                "increment",
                "converged",
                "step_complete",
                "signed_gaps_mm",
                "relative_slips_mm",
                "normal_contact_n",
                "bolt_forces_n",
                "stress_mpa",
                "stress_volumes_mm3",
                "displacement_mm",
                "external_force_n",
                "support_force_n",
                "external_moment_nmm",
                "support_moment_nmm",
            }:
                raise ValueError("closed mapped increment required")
            if (
                type(data["increment"]) is not int
                or data["increment"] != i
                or type(data["converged"]) is not bool
                or type(data["step_complete"]) is not bool
                or data["step_complete"] != (i == section["declared_increments"])
            ):
                raise ValueError("missing/reordered increment or incomplete step")
            records.append((stage, data))
    for stage, data in records:
        finding |= not data["converged"]
        arrays = {
            k: [number(x) for x in data[k]]
            for k in (
                "signed_gaps_mm",
                "relative_slips_mm",
                "normal_contact_n",
                "bolt_forces_n",
                "stress_mpa",
                "stress_volumes_mm3",
            )
        }
        if (
            any(not a for a in arrays.values())
            or len(arrays["bolt_forces_n"]) != 2
            or len(arrays["stress_mpa"]) != len(arrays["stress_volumes_mm3"])
            or any(x <= 0 for x in arrays["stress_volumes_mm3"])
        ):
            raise ValueError("nonempty aligned contact/bolt/stress evidence required")
        if len(
            {
                len(arrays[k])
                for k in ("signed_gaps_mm", "relative_slips_mm", "normal_contact_n")
            }
        ) != 1 or any(x < 0 for x in arrays["stress_mpa"]):
            raise ValueError(
                "aligned contact samples and nonnegative stress scalar required"
            )
        finding |= any(x < 0 for x in arrays["normal_contact_n"])
        vectors = {
            k: [number(x) for x in data[k]]
            for k in (
                "external_force_n",
                "support_force_n",
                "external_moment_nmm",
                "support_moment_nmm",
            )
        }
        if any(len(x) != 3 for x in vectors.values()):
            raise ValueError("global resultant vectors required")
        force = [
            a + b
            for a, b in zip(vectors["external_force_n"], vectors["support_force_n"])
        ]
        moment = [
            a + b
            for a, b in zip(
                vectors["external_moment_nmm"], vectors["support_moment_nmm"]
            )
        ]
        out.append(
            {
                "stage": stage,
                "increment": data["increment"],
                "opening_mm": max(0, max(arrays["signed_gaps_mm"])),
                "slip_mm": max(abs(x) for x in arrays["relative_slips_mm"]),
                "clamp_n": sum(arrays["normal_contact_n"]),
                "bolt_force_n": max(arrays["bolt_forces_n"]),
                "stress_mean_mpa": sum(
                    s * v
                    for s, v in zip(arrays["stress_mpa"], arrays["stress_volumes_mm3"])
                )
                / sum(arrays["stress_volumes_mm3"]),
                "displacement_mm": abs(number(data["displacement_mm"])),
                "force_balance_n": math.sqrt(sum(x * x for x in force)),
                "moment_balance_nmm": math.sqrt(sum(x * x for x in moment)),
            }
        )
    return {
        "scope": SCOPE,
        "observer": PINS["observer"],
        "case_digest": digest(row),
        "raw_source_sha256": [s["source_sha256"] for s in history],
        "rows": out,
        "status": "REFERENCE_FINDING" if finding else "OBSERVED_NOT_ADEQUATE",
        "balance_acceptance": "HUMAN_INPUT",
        "stress_definition_acceptance": "HUMAN_INPUT",
        "extractor_verification": "HUMAN_INPUT",
        "buyer_verdict": "UNRESOLVED",
        "qualified": False,
        "customer_result": False,
    }


def hand_calculation(row, *, bolt_stiffness_n_per_mm, member_stiffness_n_per_mm):
    """VDI-style closed-contact elastic group, not VDI2230 certification."""
    validate_case(row)
    kb, km = (
        number(v, positive=True)
        for v in (bolt_stiffness_n_per_mm, member_stiffness_n_per_mm)
    )
    phi = kb / (kb + km)
    c, a = row["condition"], row["action"]
    fv = preload(row)
    ys = [-a["bolt_spacing_mm"] / 2, a["bolt_spacing_mm"] / 2]
    moment = c["opening_n"] * c["eccentricity_mm"]
    loads = [c["opening_n"] / 2 + moment * y / sum(z * z for z in ys) for y in ys]
    clamps = [fv - (1 - phi) * load for load in loads]
    bolts = [fv + phi * load for load in loads]
    residual = c["mu"] * sum(clamps) - abs(c["shear_n"])
    return {
        "scope": SCOPE,
        "phi": phi,
        "clamp_per_bolt_n": clamps,
        "bolt_force_per_bolt_n": bolts,
        "friction_reserve_n": residual,
        "outside_closed_contact": min(clamps) <= 0,
        "values": {
            "clamp_n": sum(clamps),
            "bolt_force_n": max(bolts),
            "friction_reserve_n": residual,
        },
        "missing_quantities": [
            "opening_mm",
            "slip_mm",
            "stress_mean_mpa",
            "displacement_mm",
        ],
        "buyer_verdict": "UNRESOLVED",
        "fit": "NONE physical stiffness inputs only; no held-out truth fit",
        "customer_result": False,
    }


def compare(export):
    """Representative neutral-task report; missing nonlinear outputs abstain."""
    from carbon.design_search import tasks
    from carbon.development_comparison import cheap_baselines as cb
    from carbon.development_comparison import portfolio_baselines as pb

    if (
        type(export) is not dict
        or set(export)
        != {"scope", "family", "questions", "rows", "costs", "export_digest"}
        or export["scope"] != SCOPE
        or export["family"] != FAMILY
    ):
        raise ValueError("closed representative comparison export required")
    if export["export_digest"] != digest(
        {k: v for k, v in export.items() if k != "export_digest"}
    ):
        raise ValueError("export identity mismatch")
    if not export["questions"] or not export["rows"] or len(export["rows"]) > 10000:
        raise ValueError("bounded nonempty comparison required")
    if type(export["costs"]) is not dict or set(export["costs"]) != set(pb.COST_FIELDS):
        raise ValueError("full retained cost inventory required")
    for value in export["costs"].values():
        if value is not None and number(value) < 0:
            raise ValueError(
                "nonnegative retained cost or explicit unmeasured null required"
            )
    required = {
        (r["candidate"], r["condition"])
        for e in export["questions"]
        for r in e["reference"]
    }
    physical = {}
    predictions, screening = {}, []
    for raw in export["rows"]:
        if set(raw) != {
            "candidate",
            "condition",
            "case",
            "bolt_stiffness_n_per_mm",
            "member_stiffness_n_per_mm",
        }:
            raise ValueError("closed hand-calculation input required")
        row = validate_case(raw["case"])
        key = (raw["candidate"], raw["condition"])
        if key in physical:
            raise ValueError("duplicate physical comparison row")
        physical[key] = row
        start, cpu = time.perf_counter(), time.process_time()
        hand = hand_calculation(
            row,
            bolt_stiffness_n_per_mm=raw["bolt_stiffness_n_per_mm"],
            member_stiffness_n_per_mm=raw["member_stiffness_n_per_mm"],
        )
        cost = {
            "wall_s": time.perf_counter() - start,
            "cpu_s": time.process_time() - cpu,
        }
        if not hand["outside_closed_contact"]:
            predictions[(None, *key)] = hand["values"]
        screening.append(
            {
                "candidate": key[0],
                "condition": key[1],
                "fit_cost": {"wall_s": 0, "cpu_s": 0},
                "query_cost": cost,
                "status": "PARTIAL_HAND_PREDICTION",
            }
        )
    if set(physical) != required:
        raise ValueError("physical inputs must cover exact reference menu")
    needed_by_row = {}
    for entry in export["questions"]:
        task = entry["task"]
        if (
            task["schema"] != tasks.RUNNABLE_SCHEMA
            or task["identity"]["observer_version"] != PINS["observer"]
        ):
            raise ValueError("matched representative runnable observer required")
        tasks._verify_task_digest(task)
        tasks._validate_runnable(task["identity"], task["candidates"], task["actions"])
        grammar = task["identity"]["action_grammar"]
        if any(
            tasks.digest(tasks.snap_action(grammar, a)) != tasks.digest(a)
            for a in task["actions"].values()
        ):
            raise ValueError("task action numeric types must match canonical digest")
        needed = {task["objective"]["quantity"]} | {
            lim["quantity"] for lim in task["limits"]
        }
        if task["secondary"] is not None:
            needed.add(task["secondary"]["quantity"])
        for reference in entry["reference"]:
            key = reference["candidate"], reference["condition"]
            if (
                task["actions"][key[0]] != physical[key]["action"]
                or key[1] != physical[key]["condition"]["id"]
            ):
                raise ValueError("task and physical action/context differ")
            needed_by_row.setdefault((None, *key), set()).update(needed)
    complete_predictions = {
        key: v for key, v in predictions.items() if needed_by_row[key] <= set(v)
    }
    screen = pb.screening_export(export, complete_predictions, screening)
    screen["query_unit"] = "candidate_condition_supported_hand_quantities_only"
    return {
        "scope": SCOPE,
        "customer_result": False,
        "V4": "NOT_DEMONSTRATED",
        "physical_rows": len(physical),
        "pointwise": cb.pointwise_errors(export, predictions),
        "decision": cb.decision_report(export, complete_predictions),
        "equal_budget_screening": screen,
        "retained_costs": export["costs"],
        "retained_cost_status": (
            "UNMEASURED"
            if any(v is None for v in export["costs"].values())
            else "SUPPLIED_NOT_AUDITED"
        ),
        "strongest_contact_aware_FE": "HOLD_NOT_SUPPLIED",
        "warning": "Missing opening/slip/stress is an abstention, never a zero or full feasible claim. No fitted model: fit cost is exactly zero; stiffness must be independently calibrated, never from held-out truth.",
    }


def kit_domain(domain, cases):
    if (
        not cases
        or set(domain)
        != {
            "scope",
            "action_bounds",
            "condition_ids",
            "observables",
            "observer",
            "history",
        }
        or domain["scope"] != SCOPE
    ):
        raise ValueError("explicit representative kit coverage required")
    if set(domain["action_bounds"]) != set(FIELDS):
        return False
    for row in cases:
        validate_case(row)
        if row["condition"]["id"] not in domain["condition_ids"]:
            return False
        for key, value in row["action"].items():
            lo, hi = map(number, domain["action_bounds"][key])
            if not lo <= value <= hi:
                return False
    return (
        domain["observer"] == PINS["observer"]
        and list(domain["history"]) == list(STEPS)
        and set(OUTPUTS) <= set(domain["observables"])
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "actions",
            "conditions",
            "panel",
            "train",
            "deck",
            "observe",
            "compare",
        ),
    )
    parser.add_argument("--input", type=Path)
    args = parser.parse_args(argv)
    if args.command in ("actions", "conditions"):
        output = {
            "scope": SCOPE,
            "customer_result": False,
            "rows": (actions if args.command == "actions" else conditions)(),
        }
    else:
        if args.input is None or args.input.stat().st_size > 4 * 1024 * 1024:
            parser.error("explicit bounded representative JSON required")
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        if raw.get("scope") != SCOPE:
            parser.error("only REPRESENTATIVE inputs allowed")
        if args.command == "panel":
            output = panel(
                raw["designs"],
                rungs=raw["rungs"],
                completed=raw["completed"],
                scheduled=raw["scheduled"],
            )
        elif args.command == "train":
            output = train_plan(raw["designs"], raw["test_cases"])
        elif args.command == "deck":
            output = deck(
                raw["case"],
                normal_penalty_mpa_per_mm=raw["normal_penalty_mpa_per_mm"],
                stick_slope_mpa_per_mm=raw["stick_slope_mpa_per_mm"],
            )
        elif args.command == "observe":
            output = observe(raw["case"], raw["history"])
        else:
            output = compare(raw)
    print(json.dumps(output, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
