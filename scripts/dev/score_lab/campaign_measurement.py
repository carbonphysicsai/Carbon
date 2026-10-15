"""Finite synthetic measurement study; existing scorers and crossed bootstrap.

Additional rows are sampling draws, never new models or physical support.
This module neither selects a score rule nor estimates real Challenge power.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import random
import statistics
from pathlib import Path

from . import (
    campaign_blocks,
    campaign_goodhart,
    campaign_reference,
    core,
    physics,
    synthetic,
)

SCHEMA = "carbon.dev.score-lab-measurement-study.v1"
SCOPE = "SYNTHETIC_DEVELOPMENT"


def finite_law(panel, proposal):
    """Separate P, Q and buyer w on the complete, fixed finite support."""
    _population(panel)
    questions = sorted(panel["value_questions"])
    if proposal not in ("uniform", "half_extrapolated"):
        raise core.LabRefused("measurement_proposal")
    extrapolated = {q for q in questions if panel["value_strata"][q] == "extrapolated"}
    if proposal == "half_extrapolated" and not 0 < len(extrapolated) < len(questions):
        raise core.LabRefused("measurement_proposal_support")
    return {
        q: {
            "P": 1 / len(questions),
            "Q": (
                1 / len(questions)
                if proposal == "uniform"
                else 0.5
                / (
                    len(extrapolated)
                    if q in extrapolated
                    else len(questions) - len(extrapolated)
                )
            ),
            "w": 1.0,
        }
        for q in questions
    }


def _population(panel):
    if panel.get("scope") != SCOPE:
        raise core.LabRefused("measurement_requires_synthetic")
    core.validate_panel(panel)
    questions = panel["value_questions"]
    if not questions or set(panel.get("value_strata", {})) != set(questions):
        raise core.LabRefused("measurement_population_support")
    if set(panel.get("exact_oracle_losses", {})) != set(questions):
        raise core.LabRefused("measurement_population_oracle")
    for values in [panel["exact_oracle_losses"]] + [
        m["value_losses"] for m in panel["members"]
    ]:
        if any(
            type(v) not in (int, float) or not math.isfinite(v) for v in values.values()
        ):
            raise core.LabRefused("measurement_population_incomplete")


def validate_law(panel, law):
    _population(panel)
    if type(law) is not dict or set(law) != set(panel["value_questions"]):
        raise core.LabRefused("measurement_law_support")
    for row in law.values():
        if (
            type(row) is not dict
            or set(row) != {"P", "Q", "w"}
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                for v in row.values()
            )
        ):
            raise core.LabRefused("measurement_law_quantity")
    if any(
        not math.isclose(sum(r[k] for r in law.values()), 1.0, abs_tol=1e-12)
        for k in ("P", "Q")
    ):
        raise core.LabRefused("measurement_law_normalization")


def cells():
    """Prospective Cartesian product, not a result-selected subset."""
    rows = []
    for n, b, dependence, seed in itertools.product(
        (30, 300, 3000), (3, 10, 30), ("iid", "replicated"), (11, 22, 33)
    ):
        rows.append(
            {
                "study": "sample_blocks",
                "N": n,
                "B": b,
                "dependence": dependence,
                "seed": seed,
                "proposal": "uniform",
                "estimand": "P",
                "outage": 0.0,
                "policy": "REQUIRE_COMPLETE",
            }
        )
    for dependence, seed, outage, policy, estimand in itertools.product(
        ("iid", "replicated"),
        (11, 22, 33),
        (0.0, 0.01, 0.05),
        ("REQUIRE_COMPLETE", "EXCLUDE_COMPLETE_BLOCKS"),
        ("Q", "P"),
    ):
        rows.append(
            {
                "study": "proposal_outages",
                "N": 300,
                "B": 10,
                "dependence": dependence,
                "seed": seed,
                "proposal": "half_extrapolated",
                "estimand": estimand,
                "outage": outage,
                "policy": policy,
            }
        )
    return rows


def sample(panel, law, *, n, blocks, dependence, seed, estimand):
    """Draw independent block streams; P uses unnormalised HT, Q raw w-loss."""
    validate_law(panel, law)
    if (
        type(n) is not int
        or type(blocks) is not int
        or not 3 <= blocks <= 30
        or not blocks <= n <= 3000
        or n % blocks
        or dependence not in ("iid", "replicated")
        or type(seed) is not int
        or seed < 0
        or estimand not in ("P", "Q")
    ):
        raise core.LabRefused("measurement_draw_spec")
    sources = sorted(law)
    weights = [law[q]["Q"] for q in sources]
    draws, groups = {}, {}
    for b in range(blocks):
        rng = random.Random(core.canonical_sha(["measurement-block-v1", seed, b]))
        chosen = rng.choices(
            sources, weights=weights, k=1 if dependence == "replicated" else n // blocks
        )
        if dependence == "replicated":
            chosen *= n // blocks
        group = []
        for index, source in enumerate(chosen):
            qid = f"MEAS-V-{b:03d}-{index:05d}"
            row = law[source]
            draws[qid] = {
                "source": source,
                "block": b,
                **row,
                "correction": row["P"] / row["Q"] if estimand == "P" else 1.0,
            }
            group.append(qid)
        groups[f"b-{b:03d}"] = group
    view = copy.deepcopy(panel)
    view["value_questions"] = draws
    view["value_strata"] = {
        q: panel["value_strata"][r["source"]] for q, r in draws.items()
    }
    for member in view["members"]:
        original = member["value_losses"]
        member["value_losses"] = {
            q: original[r["source"]] * r["w"] * r["correction"]
            for q, r in draws.items()
        }
    view["exact_oracle_losses"] = {
        q: panel["exact_oracle_losses"][r["source"]] * r["w"] * r["correction"]
        for q, r in draws.items()
    }
    return view, groups


def build_population(config):
    """Existing analytic physics members and existing cached-map/abstain probes."""
    panel = physics.build(config)
    neighbours = panel["members"][0]["score_metadata"]["neighbours"]
    cheap = campaign_goodhart._legacy_cheap_score_control(
        config, panel, {"neighbours": neighbours}
    )
    if cheap is None:
        raise core.LabRefused("measurement_cheap_control_grammar")

    def predict(name, questions, score_side):
        return {
            q: {
                a: synthetic._predict(
                    name,
                    q,
                    float(a[2:]),
                    ref["context"],
                    config["problem"],
                    score_side=score_side,
                )
                for a in ref["actions"]
            }
            for q, ref in questions.items()
        }

    for name in ("control-bilinear", "control-always-abstain"):
        member = (
            copy.deepcopy(cheap)
            if name == "control-bilinear"
            else {
                "id": name,
                "score_predictions": predict(name, panel["score_questions"], True),
                "score_metadata": {
                    "neighbours": [
                        {
                            "id": r["id"],
                            "references": r["references"],
                            "predictions": predict(name, r["references"], True),
                        }
                        for r in neighbours
                    ]
                },
            }
        )
        vp = predict(name, panel["value_questions"], False)
        member.update(
            recipe=name,
            kind="PROBE",
            score_row=synthetic._row(
                panel["score_questions"], member["score_predictions"], config["problem"]
            ),
            value_losses={
                q: physics._loss(
                    ref,
                    vp[q],
                    config["decision"],
                    config["problem"]["verification_cost_ASSUMPTION"],
                )
                for q, ref in panel["value_questions"].items()
            },
        )
        panel["members"].append(member)
    panel["score_metadata"] = {
        "knobs": {
            "physics": {"mode": "OFF", "limit": {}, "weight": {}},
            "neighbourhood_weight": config["neighbourhood"]["score_weight"],
        }
    }
    _population(panel)
    return panel


def frozen_rule(panel, rule):
    """Compute only score-side calls once; refuse any later score-input drift."""
    table = {}
    for member in panel["members"]:
        args = (
            member["score_predictions"],
            panel["score_questions"],
            {
                "score_row": member.get("score_row"),
                **panel.get("score_metadata", {}),
                **member.get("score_metadata", {}),
            },
        )
        table[core.canonical_sha(args)] = rule(*copy.deepcopy(args))

    def frozen(*args):
        key = core.canonical_sha(args)
        if key not in table:
            raise core.LabRefused("measurement_score_input_changed")
        return copy.deepcopy(table[key])

    frozen.rule_identity = copy.deepcopy(getattr(rule, "rule_identity", {}))
    frozen.scorer_calls = len(panel["members"])
    return frozen


def population_values(panel, law, estimand):
    validate_law(panel, law)
    if estimand not in ("P", "Q"):
        raise core.LabRefused("measurement_estimand")
    return {
        m["id"]: -sum(
            law[q][estimand] * law[q]["w"] * loss
            for q, loss in m["value_losses"].items()
        )
        for m in panel["members"]
    }


def compare(panel, law, cell, rules, *, bootstrap):
    """Case/block CIs on the identical common-complete-block mask."""
    if type(bootstrap) is not int or bootstrap < 1:
        raise core.LabRefused("bootstrap_count")
    drawn, groups = sample(
        panel,
        law,
        n=cell["N"],
        blocks=cell["B"],
        dependence=cell["dependence"],
        seed=cell["seed"],
        estimand=cell["estimand"],
    )
    masked, outage = campaign_reference.prepare(
        drawn,
        {
            "schema": campaign_reference.SCHEMA,
            "label": "ASSUMPTION: draw-level reference outages",
            "fraction": cell["outage"],
            "seed": cell["seed"],
            "policy": "EXCLUDE_COMMON",
        },
    )
    blockview, receipt = campaign_blocks.prepare(
        masked,
        {
            "schema": campaign_blocks.SCHEMA,
            "label": "ASSUMPTION: independent simulated blocks",
            "groups": groups,
            "missing_policy": cell["policy"],
        },
    )
    # Stable block order across N, including identical repeated-row experiments.
    rename = {
        q: f"MEAS-B-{masked['value_questions'][r['source_questions'][0]]['block']:03d}"
        for q, r in blockview["value_questions"].items()
    }
    blockview["value_questions"] = {
        rename[q]: r for q, r in blockview["value_questions"].items()
    }
    for m in blockview["members"]:
        m["value_losses"] = {rename[q]: v for q, v in m["value_losses"].items()}
    blockview["exact_oracle_losses"] = {
        rename[q]: v for q, v in blockview["exact_oracle_losses"].items()
    }
    keep = {
        q for r in blockview["value_questions"].values() for q in r["source_questions"]
    }
    caseview = copy.deepcopy(masked)
    caseview["value_questions"] = {
        q: r for q, r in masked["value_questions"].items() if q in keep
    }
    caseview["exact_oracle_losses"] = {
        q: v for q, v in masked["exact_oracle_losses"].items() if q in keep
    }
    for m in caseview["members"]:
        m["value_losses"] = {q: v for q, v in m["value_losses"].items() if q in keep}
    insufficient = receipt["complete_blocks_available"] < 3 or (
        cell["policy"] == "REQUIRE_COMPLETE" and receipt["incomplete_blocks"]
    )
    rows = {}
    truth = population_values(panel, law, cell["estimand"])
    primary = [m["id"] for m in panel["members"] if m["kind"] == "MODEL"]
    for name, rule in rules.items():
        if insufficient:
            rows[name] = {
                "status": "INSUFFICIENT_EVIDENCE",
                "reason": "incomplete_or_fewer_than_three_blocks",
            }
            continue
        case = core.analyze(caseview, rule, bootstrap=bootstrap, seed=cell["seed"])
        block = core.analyze(blockview, rule, bootstrap=bootstrap, seed=cell["seed"])
        if (
            case["status"] != "MEASURED_DEVELOPMENT"
            or block["status"] != "MEASURED_DEVELOPMENT"
        ):
            rows[name] = {
                "status": "INSUFFICIENT_EVIDENCE",
                "case": case,
                "block": block,
            }
            continue
        target_tau = core.score_proof._tau(
            block["ranked_scores"], {m: -v for m, v in truth.items()}, primary
        )
        # Explicit population target is unconditional; exclusion changes estimand.
        selected = block["top1_member"]
        for result in (case, block):
            ci = result["tau_ci95"]
            result["interval_width"] = None if ci is None else ci[1] - ci[0]
            result["covers_population_tau"] = (
                None
                if ci is None or target_tau is None or receipt["incomplete_blocks"]
                else ci[0] <= target_tau <= ci[1]
            )
            result["selected_value"] = (
                None
                if selected is None
                else -statistics.fmean(
                    next(m for m in caseview["members"] if m["id"] == selected)[
                        "value_losses"
                    ].values()
                )
            )
        rows[name] = {
            "status": "MEASURED_DEVELOPMENT",
            "case": case,
            "block": block,
            "population_tau": target_tau,
            "population_selected_value": None if selected is None else truth[selected],
        }
    return {
        "schema": SCHEMA,
        "scope": SCOPE,
        "cell": cell,
        "law": law,
        "draws_sha256": core.canonical_sha(drawn["value_questions"]),
        "population_sha256": core.canonical_sha(panel),
        "reference_outage": outage,
        "block_mask": receipt,
        "stable_block_panel_sha256": core.canonical_sha(blockview),
        "estimand": f"{'conditional_retained_draw_' if receipt['incomplete_blocks'] else ''}{cell['estimand']}_mean_buyer_weighted_loss",
        "rows": rows,
    }


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    Path(path).write_text(
        json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
