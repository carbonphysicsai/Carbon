"""Battery's Level 1 attack adapter: loss expressions under a development variant.

GRAPHITE-L1-BUILD-01. The Level-1 surface is two registered development-only
variants (`carbon.battery.level1`): the valid surface
`battery-l1-loss-expressions-v1` (the level's own variant, which this
adapter attacks: its `contract_digest` is that variant's digest) and the
signed arm `battery-l1-loss-expressions-signed-v1` (arm `signed`), used in the
attack panel only. Nothing here is served to a miner, and nothing runs
participant code: an expression is data, compiled and evaluated by Carbon.

What it adds over Level 0 (`adapters.battery`, whose oracle and session
surface it reuses):
- **the Level-1 gate**: `development_variants.compile_development` under a
  variant, optionally without one permission (a climb ablation);
- **a CPU practice trial** (`trial`): Carbon's pod phase run locally on CPU
  with a short step budget, scored by the frozen rule. It proves R1
  (non-finite training is GATE_FAILED, never FAILED_INFRA) and Q3 (a
  degenerate loss runs and is scored as the candidate's own result). It is
  no pod, no GPU and no spend;
- **families** for the eight Track A checks: six run here, two are seams;
- **matched panels**: the packet's valid constructions and attack
  constructions, each with its declared violation, and the combined attacks
  pairing the expression with a Level-0 permission;
- **the climb** (`climb_report`): valid against attack panels under Level 0
  and Level 1, one ablation per Level-1 permission, the combined attacks, and
  a clean rebuild of the promising valid runs. It runs on the variant gate
  and continues past a finding with the conditional tag.

Every Level-1 result carries `rebuild: CPU-verified only` until GPU identity
is measured (Test Lead Q6). Nothing here keys anything on an expression
digest (OWNER-GRAPHITE-TEST-WAVE-04 §1). U1 (metric-aimed training) and U2
(tail sacrifice) are alignment findings for the live climb, measured as
τ/ρ, regret, false-feasible and tail metrics; the frozen rule's tail
coverage is their instrument for testing only, not a scientific
qualification (§2).
"""

from __future__ import annotations

import copy
import functools
import json
import tempfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from carbon.agent_campaign.attack.adapters import battery as b

CHALLENGE_ID = b.CHALLENGE_ID
LEVEL = 1
PROFILE = "level-1"
ADAPTER_VERSION = "carbon.attack.adapter.battery-l1.v1"
CONTROLS_VERSION = "carbon.attack.controls.battery-l1.v1"
SIGNED_ARM = "signed"
#: The step budget of a CPU practice trial: the contract's smallest.
TRIAL_STEPS = 32
REBUILD_LABEL = "rebuild: CPU-verified only"
FIELD = "loss_expressions"
SPLITS = b.SPLITS

FamilySpec, ControlSpec, SeamSpec = b.FamilySpec, b.ControlSpec, b.SeamSpec


def _level1():
    from carbon.battery import level1

    return level1


def _dv():
    from carbon.reconstruction import development_variants

    return development_variants


def variant(arm=None):
    """The registered Level-1 variant (or its named arm), with a fresh base."""
    return _dv().variant(CHALLENGE_ID, LEVEL, arm)


def _pinned_digest():
    """The valid variant's pinned digest, read from the registry as data so
    a registry problem never breaks the adapters package at import."""
    from carbon.reconstruction import capability_registry as cr

    try:
        return cr.development_variant_registry()["versions"][_level1().VERSION]
    except (RuntimeError, KeyError):
        return "sha256:" + "0" * 64


# -- constructions -----------------------------------------------------------------
def strategy(expression=None, *, backbone="mlp", steps=None, **parameters):
    """The pinned scaffold with a loss expression and any other fields."""
    from carbon.battery.research import SCAFFOLD

    made = copy.deepcopy(SCAFFOLD)
    made["backbone"] = backbone
    if backbone != "mlp":
        # The scaffold's `depth` is the MLP's; other families name their own.
        made["parameters"].pop("depth", None)
    made["parameters"].update(parameters)
    if expression is not None:
        made["parameters"][FIELD] = expression
    if steps is not None:
        made["parameters"]["steps"] = steps
    return made


def _term(name):
    return {"term": name}


def _add(*args):
    return {"op": "add", "args": list(args)}


def _scale(by, arg):
    return {"op": "scale", "by": by, "arg": arg}


def _pow(exponent, arg):
    return {"op": "pow", "exponent": exponent, "arg": arg}


GROUPS = ("voltage", "temperature", "plating", "capacity")

#: The packet's valid constructions (section 4.1), one or more per family, so
#: every single-permission ablation refuses something.
VALID = {
    "valid_menu_restated": _term("sq_error"),
    "valid_robust_l2": {"op": "sqrt", "arg": _term("sq_error")},
    "valid_component_relative": _add(
        *(
            {"op": "div", "args": [_term("sq_error_" + g), _term("target_energy_" + g)]}
            for g in GROUPS
        )
    ),
    "valid_plating_emphasis": _add(
        _term("sq_error"), _scale(4, _term("sq_error_plating"))
    ),
    "valid_late_voltage": _add(
        _term("sq_error"),
        {
            "op": "mean_t",
            "over": "voltage",
            "arg": {
                "op": "mul",
                "args": [_pow(2, _term("time_t")), _term("err_sq_t")],
            },
        },
    ),
    "valid_worst_time": _add(
        _term("sq_error"),
        _scale(0.1, {"op": "max_t", "over": "both", "arg": _term("err_sq_t")}),
    ),
    "valid_huber_like": _add(
        {"op": "cap", "at": 1.0, "arg": _term("sq_error")},
        {"op": "excess", "over": 1.0, "arg": {"op": "sqrt", "arg": _term("sq_error")}},
    ),
    "valid_expm1_emphasis": {
        "op": "expm1",
        "cap": 4.0,
        "arg": _scale(0.5, _term("sq_error")),
    },
    "valid_wide_smoothness": _add(_term("sq_error"), _scale(50, _term("traj_d1"))),
}

#: Attack constructions on the valid variant (section 4.2): (expression or
#: whole strategy, declared violation, how the climb judges it). `gate`:
#: reproduced when the variant admits it; `refused`: reproduced when it is
#: refused (Level 1 must run it); `trial`: reproduced when a CPU trial types
#: its result as infrastructure failure or the worker fails.
ADMITTED = "admitted although the variant refuses it"
ATTACKS = {
    "attack_unregistered_term": (_term("label"), ADMITTED, "gate"),
    "attack_unregistered_operation": (
        {"op": "exp", "arg": _term("sq_error")},
        ADMITTED,
        "gate",
    ),
    "attack_code_node": ({"op": "python", "code": "import os"}, ADMITTED, "gate"),
    "attack_text_expression": ("sq_error*0", ADMITTED, "gate"),
    "attack_constant_out_of_range": (_scale(1000, _term("sq_error")), ADMITTED, "gate"),
    "attack_huge_integer": (_scale(10**400, _term("sq_error")), ADMITTED, "gate"),
    "attack_too_deep": ("too_deep", ADMITTED, "gate"),
    "attack_time_root": (_term("err_sq_t"), ADMITTED, "gate"),
    "attack_menu_and_expression": ("menu", ADMITTED, "gate"),
    "attack_wrong_backend": ("pytorch", ADMITTED, "gate"),
    "attack_wrong_family": ("knn", ADMITTED, "gate"),
    "attack_permission_field": ("permission_field", ADMITTED, "gate"),
    "attack_adversarial_denominator": (
        {"op": "div", "args": [_term("sq_error"), _term("traj_d1")]},
        "refused although div stays general (Q4)",
        "refused",
    ),
    "attack_constant_loss": (
        {"op": "mean_t", "over": "both", "arg": _term("time_t")},
        "a degenerate loss is refused, refunded or typed FAILED_INFRA (Q3)",
        "trial",
    ),
    "attack_overflow_chain": (
        _pow(4, _pow(4, _pow(4, _scale(100, _term("sq_error"))))),
        "non-finite training typed FAILED_INFRA or the worker fails (R1)",
        "trial",
    ),
}

#: The signed arm's attacks (attack panel only): each must be the
#: candidate's own failure when its training goes non-finite (R1).
SIGNED_ATTACKS = {
    "signed_exp_overflow": {"op": "exp", "arg": _scale(10, _term("sq_error"))},
    "signed_unbounded_below": {"op": "neg", "arg": _term("sq_error")},
    "signed_negative_difference": {
        "op": "sub",
        "args": [_term("target_energy"), _scale(10, _term("sq_error"))],
    },
    "signed_constant_leaf": _add(
        {"const": -5.0}, {"op": "log1p", "arg": _term("sq_error")}
    ),
}
SIGNED_VIOLATION = (
    "non-finite or negative training typed FAILED_INFRA or the worker fails (R1)"
)

#: Combined attacks: the expression with a Level-0 permission that changes how
#: the loss is consumed (packet section 5, step 4).
COMBINED = {
    "combined_hard_example_weight": {"hard_example_weight": 1.0},
    "combined_polish": {"polish_steps": 8},
    "combined_plateau": {"learning_rate_curve": "train_loss_plateau"},
    "combined_float64": {"precision": "float64"},
    "combined_microbatches": {"microbatches": 2},
    "combined_trajectory_components": {"trajectory_components": 8},
    "combined_bounded_voltage": {"bounded_voltage_head": False},
    "combined_width": {"width": 128},
    "combined_ensemble": {"ensemble_members": 2},
    "combined_curriculum_weights": {
        "curriculum": "low_rate_first",
        "important_region_weight": 3.0,
    },
}
#: One expression that uses every valid-surface family, so each combined
#: attack covers every Level-1 permission (an uncovered one is NOT_RUN).
COMBINED_EXPRESSION = _add(
    _scale(4, _term("sq_error_plating")),
    VALID["valid_late_voltage"]["args"][1],
    {"op": "cap", "at": 1.0, "arg": _term("sq_error")},
    {"op": "expm1", "cap": 4.0, "arg": _scale(0.5, _term("sq_error"))},
    _scale(50, _term("traj_d1")),
)
COMBINED_VIOLATION = (
    "the combination fails the CPU trial or types a result as infrastructure failure"
)


def _too_deep():
    node = _term("sq_error")
    for _ in range(40):
        node = {"op": "sqrt", "arg": node}
    return node


def attack_strategy(name):
    """The strategy an attack in `ATTACKS` submits."""
    value = ATTACKS[name][0]
    if value == "too_deep":
        return strategy(_too_deep())
    if value == "menu":
        return strategy(_term("sq_error"), relative_loss=True)
    if value == "pytorch":
        return strategy(_term("sq_error"), backend="pytorch")
    if value == "knn":
        return strategy(_term("sq_error"), backbone="knn")
    if value == "permission_field":
        return strategy(_term("sq_error"), loss_time_reductions=True)
    return strategy(value)


# -- the Level-1 gate and the CPU trial ---------------------------------------------
def l1_gate(construction, without=(), arm=None):
    """The Level-1 admission: `compile_development` under the variant (or its
    arm), less the permissions `without`. Only typed refusals read as
    REFUSED; anything else propagates (a crash is never a hold)."""
    from carbon.development_session.research_catalog import RecipeRejected
    from carbon.reconstruction.challenge_contracts import SubmissionRefused

    dv = _dv()
    try:
        compiled = dv.compile_development(construction, variant(arm), without=without)
    except dv.VariantRefused as refused:
        return {
            "status": "REFUSED",
            "codes": sorted({refused.code, *(str(i[0]) for i in refused.issues)}),
        }
    except SubmissionRefused as refused:
        return {"status": "REFUSED", "codes": sorted({i.code for i in refused.issues})}
    except RecipeRejected as refused:
        return {
            "status": "REFUSED",
            "codes": sorted({i.code for i in refused.rejected.issues}),
        }
    loss = compiled.reconstruction.get(_level1().CORE, {})
    return {
        "status": "OK",
        "development": compiled.development,
        "families": loss.get("families", []),
        "diagnostics": loss.get("diagnostics", []),
        "rebuild": REBUILD_LABEL,
    }


def _short(construction):
    made = copy.deepcopy(construction)
    if isinstance(made.get("parameters"), dict):
        made["parameters"]["steps"] = TRIAL_STEPS
    return made


@functools.lru_cache(maxsize=64)
def _trial(body, arm):
    from carbon.agent_campaign.graphite import experiment, pod_phase

    construction = json.loads(body)
    found = variant(arm)
    try:
        record, _files, _program = pod_phase.development_built_record(
            construction,
            found.base_contract_digest,
            found.digest,
            7,
            experiment.REPOSITORY,
        )
    except Exception as error:
        refusal = b._challenge_scoring().refusal(error)
        if isinstance(error, _dv().VariantRefused):
            refusal = (error.code, error.issues)
        if refusal is None:
            raise
        return {
            "stage": "host_compile",
            "refused": refusal[0],
            "rebuild": REBUILD_LABEL,
        }
    config = {
        "strategy": construction,
        "contract_digest": found.base_contract_digest,
        "development_variant": found.digest,
        "seed": 7,
        "expected": {"files": record["staged"], "program": record["program"]},
        "seconds": 600,
    }
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory) / "out"
        code = pod_phase.run(config, out, root=experiment.REPOSITORY)
        result = {
            "stage": "trained",
            "exit": code,
            "rebuild": REBUILD_LABEL,
            "record_rebuild": record.get("rebuild"),
        }
        if (out / "failure.json").is_file():
            result["failure"] = json.loads((out / "failure.json").read_text())
        if not (out / "predictions.json").is_file():
            return result
        predictions = json.loads((out / "predictions.json").read_text())
        fit = json.loads((out / "fit.json").read_text())
    rows, summary = b._frozen_rule().score(predictions)
    states = Counter(r["state"] for r in rows)
    result.update(
        {
            "states": dict(sorted(states.items())),
            "failed_infra": states.get("FAILED_INFRA", 0),
            "eligible": bool(summary["eligible"]),
            "nonfinite_predictions": any(
                not _finite(v) for p in predictions.values() for v in _values(p)
            ),
            "final_loss_finite": _finite(fit.get("final_loss")),
            "negative_loss": any(
                _finite(v) and v < 0
                for _i, v in (fit.get("loss_history") or {}).get("points", [])
            ),
            "loss_history_nonfinite": len(
                (fit.get("loss_history") or {}).get("points", [])
            )
            < min(TRIAL_STEPS, 64),
        }
    )
    return result


def _values(prediction):
    if isinstance(prediction, Mapping):
        for value in prediction.values():
            yield from _values(value)
    elif isinstance(prediction, list):
        for value in prediction:
            yield from _values(value)
    else:
        yield prediction


def _finite(value):
    import math

    return isinstance(value, int | float) and math.isfinite(value)


def trial(construction, arm=None):
    """A CPU practice trial of a Level-1 construction: Carbon's pod phase
    (compile on the host, pinned files, the Level-1 program) run locally with
    `TRIAL_STEPS` updates, its predictions scored by the frozen rule. No pod,
    no GPU, no spend."""
    return _trial(json.dumps(_short(construction), sort_keys=True), arm)


def candidate_owned(result):
    """R1 and Q3: the trial's result is the candidate's own. The worker
    finished; no case is FAILED_INFRA; non-finite predictions are never
    eligible. A refusal on Carbon's host before any pod is typed too (R3)."""
    if result.get("stage") == "host_compile":
        return bool(result.get("refused"))
    if result.get("exit") != 0 or result.get("failed_infra"):
        return False
    return not (result.get("nonfinite_predictions") and result.get("eligible"))


# -- the families ---------------------------------------------------------------------
def _ablation_attacks():
    level1 = _level1()
    items = []
    for name, expression in VALID.items():
        used = level1.families_used(_compiled_full(expression))
        for permission in sorted(used):
            items.append(
                (
                    f"without_{permission}_{name}",
                    {"strategy": strategy(expression), "without": [permission]},
                )
            )
    return tuple(items)


def _compiled_full(expression):
    level1 = _level1()
    return level1.compile_for(expression, {level1.CORE, *level1.FAMILIES}).expression


def ablation_boundary(item):
    """The variant gate without one permission. The full climb over every
    ablation is `climb_report` (its report is the climb's own evidence)."""
    return l1_gate(item["strategy"], without=item["without"])


def ablation_specimen(item):
    """A gate that ignores the ablation: it must fire."""
    return l1_gate(item["strategy"])


def ablation_breached(result):
    return result["status"] == "OK"


def _surface_attacks():
    return tuple(
        (name, attack_strategy(name))
        for name, (_value, _violation, judge) in ATTACKS.items()
        if judge == "gate"
    )


def _unchecked_gate(construction):
    """A weakened Level-1 gate: anything JSON under the expression field is
    accepted as it is, and no other field is checked."""
    try:
        json.dumps(construction, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return {"status": "REFUSED", "codes": ["not_json"]}
    return {"status": "OK"}


def _declarative_attacks():
    return (
        ("code_node", strategy({"op": "python", "code": "import os"})),
        (
            "lambda_field",
            strategy({"op": "add", "args": [_term("sq_error")] * 2, "lambda": "x"}),
        ),
        ("text_expression", strategy("sq_error*0")),
        ("dunder_term", strategy(_term("__import__"))),
    )


def _degenerate_attacks():
    return (
        (
            "constant_loss",
            strategy({"op": "mean_t", "over": "both", "arg": _term("time_t")}),
        ),
        ("cap_at_zero", strategy({"op": "cap", "at": 0.0, "arg": _term("sq_error")})),
        (
            "expm1_cap_zero",
            strategy({"op": "expm1", "cap": 0.0, "arg": _term("sq_error")}),
        ),
        ("scale_by_zero", strategy(_scale(0, _term("sq_error")))),
        ("target_only", strategy(_term("target_energy"))),
    )


def degenerate_boundary(construction):
    """Q3: a degenerate loss is admitted, flagged when statically detectable,
    trained and scored as the candidate's own result."""
    gate = l1_gate(construction)
    if gate["status"] != "OK":
        return {"admitted": False, "gate": gate}
    return {
        "admitted": True,
        "diagnostics": gate["diagnostics"],
        "trial": trial(construction),
    }


def degenerate_specimen(construction):
    """The rejected alternative: a gate that refuses statically detectable
    no-ops. It must fire."""
    gate = l1_gate(construction)
    if gate["status"] == "OK" and gate["diagnostics"]:
        return {
            "admitted": False,
            "gate": {"status": "REFUSED", "codes": gate["diagnostics"]},
        }
    return degenerate_boundary(construction)


def degenerate_breached(result):
    """Refused, not flagged, or not scored as the candidate's own result."""
    return (
        not result["admitted"]
        or not result["diagnostics"]
        or not candidate_owned(result["trial"])
    )


def _nonfinite_attacks():
    items = [
        (name, {"strategy": strategy(expression), "arm": SIGNED_ARM})
        for name, expression in SIGNED_ATTACKS.items()
    ]
    items.append(
        (
            "valid_overflow_chain",
            {"strategy": attack_strategy("attack_overflow_chain"), "arm": None},
        )
    )
    return tuple(items)


def nonfinite_boundary(value):
    return trial(value["strategy"], value.get("arm"))


def nonfinite_specimen(value):
    """A weakened typing: a trial whose training went non-finite or negative
    is typed as infrastructure failure (a refund). It must fire on every
    attack of this family."""
    result = dict(trial(value["strategy"], value.get("arm")))
    if (
        result.get("nonfinite_predictions")
        or not result.get("final_loss_finite", True)
        or result.get("negative_loss")
    ):
        result["failed_infra"] = sum(result.get("states", {}).values()) or 1
    return result


def _rebuild_attacks():
    return (
        ("numpy_rebuild", {"kind": "numpy"}),
        (
            "tampered_expression_bytes",
            {"kind": "tamper", "strategy": strategy(VALID["valid_late_voltage"])},
        ),
        (
            "ablated_operation_set",
            {"kind": "ablated", "strategy": strategy(VALID["valid_robust_l2"])},
        ),
    )


def rebuild_boundary(value, *, strict=True):
    """R2 and the rebuild check. `numpy`: the trainer's loss factory must
    refuse numpy (the rebuild is JAX against JAX). `tamper`: a built record
    whose staged expression differs from Carbon's own is detected
    (`experiment.rebuild_differences`). `ablated`: a build without a
    permission has another binding, so it never stands in for the full one."""
    from carbon.agent_campaign.graphite import experiment

    if value["kind"] == "numpy":
        import numpy as np

        from carbon.battery import loss_terms
        from carbon.reconstruction import loss_expressions as le

        level1 = _level1()
        compiled = level1.compile_for(_term("sq_error"), {level1.CORE})
        if not strict:
            # The weakened rebuild: the loss evaluated with numpy directly.
            z = np.zeros((2, 4))
            terms = loss_terms.case_terms(
                np, z, z, np.ones(4), lambda a: (a[:, :2], a[:, 2:]), ()
            )
            le.evaluate(compiled, terms, np)
            return {"kind": "numpy", "refused": False}
        try:
            loss_terms.factory(le, compiled)(np, None, ())
        except TypeError:
            return {"kind": "numpy", "refused": True}
        return {"kind": "numpy", "refused": False}
    expected = experiment.admit(
        value["strategy"], 7, scoring=b._challenge_scoring(), variant=variant()
    )
    if value["kind"] == "tamper":
        built = copy.deepcopy(expected)
        built["staged"]["loss-expression.json"] = "sha256:" + "0" * 64
    else:
        without = [_level1().FAMILIES[0]]
        built = _dv().admit(
            b._challenge_scoring(),
            value["strategy"],
            7,
            experiment.REPOSITORY,
            variant(),
            without=without,
        )
    differences = experiment.rebuild_differences(expected, built) if strict else []
    return {"kind": value["kind"], "differences": sorted(differences)}


def rebuild_specimen(value):
    return rebuild_boundary(value, strict=False)


def rebuild_breached(result):
    if result["kind"] == "numpy":
        return not result["refused"]
    return not result["differences"]


def _rebuild_control(construction):
    from carbon.agent_campaign.graphite import experiment

    a = experiment.admit(
        construction, 7, scoring=b._challenge_scoring(), variant=variant()
    )
    c = experiment.admit(
        construction, 7, scoring=b._challenge_scoring(), variant=variant()
    )
    return a == c and a.get("rebuild") == REBUILD_LABEL


def _gate_admits(construction):
    return l1_gate(construction)["status"] == "OK"


def _gate_runs(construction):
    return _gate_admits(construction) and (
        construction.get("parameters", {}).get("backend", "jax") == "jax"
    )


@functools.cache
def _families():
    return (
        FamilySpec(
            name="l1_permission_ablation",
            check="baseline_and_permission_ablation",
            protocol_family="each Level-1 permission ablated on its own: every valid "
            "construction that uses the removed family comes back REFUSED from the "
            "variant gate, and the climb over the variant records no finding",
            attacks=_ablation_attacks,
            boundary=ablation_boundary,
            specimen=ablation_specimen,
            breached=ablation_breached,
            control_check=_gate_admits,
            admissible=None,
            attack_example="without_objective.loss_time_reductions_valid_late_voltage",
            reads="the registered Level-1 variants and the pinned scaffold",
        ),
        FamilySpec(
            name="l1_expression_surface",
            check="artifact_and_dependency_attacks",
            protocol_family="loss expressions outside the variant (unregistered terms "
            "and operations, constants out of range, oversized integers, nesting past "
            "the depth bound, a time-sorted root, a menu field beside an expression, a "
            "non-JAX backend, a family without a trainer loss, a permission named as "
            "a field) are refused by code on Carbon's host",
            attacks=_surface_attacks,
            boundary=l1_gate,
            specimen=_unchecked_gate,
            breached=lambda r: r["status"] == "OK",
            control_check=_gate_admits,
            admissible=_gate_admits,
            attack_example="attack_unregistered_term",
            reads="the registered Level-1 variants and the pinned scaffold",
            runnable=_gate_runs,
        ),
        FamilySpec(
            name="l1_degenerate_losses",
            check="score_exploitation_and_tail_failures",
            protocol_family="degenerate losses run (Test Lead Q3): a statically "
            "detectable no-op is admitted with a diagnostic, trained, and scored as "
            "the candidate's own result, never refused and never refunded",
            attacks=_degenerate_attacks,
            boundary=degenerate_boundary,
            specimen=degenerate_specimen,
            breached=degenerate_breached,
            control_check=lambda s: _gate_admits(s) and not l1_gate(s)["diagnostics"],
            admissible=None,
            attack_example="constant_loss",
            reads="public TRAIN v1 and PRACTICE inputs, on CPU",
        ),
        FamilySpec(
            name="l1_nonfinite_typing",
            check="resource_and_failure_accounting",
            protocol_family="R1: training that goes non-finite or negative (the "
            "signed arm, and an overflowing valid chain) finishes, its predictions "
            "fail the frozen rule's schema_finite gate (GATE_FAILED), and no case is "
            "FAILED_INFRA, so nothing is refunded",
            attacks=_nonfinite_attacks,
            boundary=nonfinite_boundary,
            specimen=nonfinite_specimen,
            breached=lambda r: not candidate_owned(r),
            control_check=lambda s: candidate_owned(trial(s)),
            admissible=None,
            attack_example="signed_exp_overflow",
            reads="public TRAIN v1 and PRACTICE inputs, on CPU",
        ),
        FamilySpec(
            name="l1_rebuild_identity",
            check="reconstruction_and_recipient_rebuild",
            protocol_family="R2: the loss is rebuilt with JAX against JAX, never "
            "numpy; a built record whose staged expression or permission set differs "
            "from Carbon's own is detected; the same construction rebuilds to the same "
            "record, labelled 'rebuild: CPU-verified only'",
            attacks=_rebuild_attacks,
            boundary=rebuild_boundary,
            specimen=rebuild_specimen,
            breached=rebuild_breached,
            control_check=_rebuild_control,
            admissible=None,
            attack_example="numpy_rebuild",
            reads="recipes and public material",
        ),
        FamilySpec(
            name="l1_declarative_only",
            check="construction_evaluation_isolation",
            protocol_family="an expression is data over a closed set: a node that "
            "carries code, an extra field or text, or names an unregistered term, is "
            "refused by code; the variants declare participant_code false",
            attacks=_declarative_attacks,
            boundary=l1_gate,
            specimen=_unchecked_gate,
            breached=lambda r: r["status"] == "OK",
            control_check=_gate_admits,
            admissible=_gate_admits,
            attack_example="code_node",
            reads="the registered Level-1 variants",
            runnable=_gate_runs,
        ),
    )


@functools.cache
def _controls():
    out = []

    def add(family, split, label, make):
        out.append(ControlSpec(family, split, label, make, version=CONTROLS_VERSION))

    trained = {
        "l1_permission_ablation": "valid_component_relative",
        "l1_expression_surface": "valid_late_voltage",
        "l1_degenerate_losses": "valid_plating_emphasis",
        "l1_nonfinite_typing": "valid_robust_l2",
        "l1_rebuild_identity": "valid_worst_time",
        "l1_declarative_only": "valid_huber_like",
    }
    held_out = {
        "l1_permission_ablation": ("valid_wide_smoothness", "valid_expm1_emphasis"),
        "l1_expression_surface": ("valid_menu_restated", "valid_huber_like"),
        "l1_degenerate_losses": ("valid_worst_time",),
        "l1_nonfinite_typing": ("valid_plating_emphasis",),
        "l1_rebuild_identity": ("valid_component_relative",),
        "l1_declarative_only": ("valid_robust_l2",),
    }
    for family, label in trained.items():
        add(family, "trained", label, lambda x=label: strategy(VALID[x]))
    for family, labels in held_out.items():
        for label in labels:
            # Held-out controls train a DeepONet: canonically distinct from
            # every trained control (all MLPs).
            add(
                family,
                "held_out",
                "deeponet_" + label,
                lambda x=label: strategy(VALID[x], backbone="deeponet"),
            )
    return tuple(out)


SEAMS = (
    SeamSpec(
        "l1_feedback_paths",
        "adaptive_feedback_and_state_attacks",
        1,
        "Level 1 changes no practice feedback, disclosure or result path (the "
        "Level-0 adapter's practice_disclosure covers them); repeated-query "
        "search over the larger construction space (packet U5) needs a live "
        "session and an attack budget",
    ),
    SeamSpec(
        "l1_fresh_cases_rerun",
        "fresh_attack_confirmation",
        1,
        "needs a frozen study sheet and fresh cases",
    ),
    SeamSpec(
        "l1_alignment_u1_u2",
        "score_exploitation_and_tail_failures",
        1,
        "U1 (metric-aimed training) and U2 (tail sacrifice) are alignment "
        "findings, measured in a live climb as tau/rho, regret, false-feasible "
        "and tail metrics; the frozen rule's tail coverage is their instrument "
        "for testing only (OWNER-GRAPHITE-TEST-WAVE-04 section 2), not a "
        "scientific qualification of the rule",
    ),
)


# -- the climb ------------------------------------------------------------------------
def _uses(construction):
    """The capability ids a construction uses: Level 0's reading plus the
    Level-1 families its expression names (read without compiling)."""
    used = set(b.uses(construction))
    parameters = (
        construction.get("parameters") if isinstance(construction, Mapping) else None
    )
    if isinstance(parameters, Mapping) and FIELD in parameters:
        used |= _level1().raw_families(parameters[FIELD])
    return frozenset(used)


def _items(arm=None):
    from carbon.agent_campaign import climb

    if arm == SIGNED_ARM:
        panel = {"panel_baseline": strategy()}
        attacks = {
            name: (strategy(expression), SIGNED_VIOLATION, "trial")
            for name, expression in SIGNED_ATTACKS.items()
        }
        # A negative per-case loss under hard-example weighting: the packet's
        # measured NaN path ((loss / mean) ** w of a negative loss).
        combined = {
            "combined_signed_hard_example_weight": (
                strategy(
                    SIGNED_ATTACKS["signed_negative_difference"],
                    hard_example_weight=1.0,
                ),
                SIGNED_VIOLATION,
                "trial",
            )
        }
    else:
        panel = {name: strategy(expression) for name, expression in VALID.items()}
        attacks = {
            name: (attack_strategy(name), violation, judge)
            for name, (_value, violation, judge) in ATTACKS.items()
        }
        combined = {
            name: (strategy(COMBINED_EXPRESSION, **fields), COMBINED_VIOLATION, "trial")
            for name, fields in COMBINED.items()
        }
    items = {
        "panel": [climb.Item(n, _uses(s)) for n, s in panel.items()],
        "attacks": [
            climb.Item(n, _uses(s), declared_violation=v)
            for n, (s, v, _j) in attacks.items()
        ],
        "combined": [
            climb.Item(n, _uses(s), declared_violation=v)
            for n, (s, v, _j) in combined.items()
        ],
    }
    constructions = {
        **panel,
        **{n: s for n, (s, _v, _j) in attacks.items()},
        **{n: s for n, (s, _v, _j) in combined.items()},
    }
    judges = {
        **{n: j for n, (_s, _v, j) in attacks.items()},
        **{n: j for n, (_s, _v, j) in combined.items()},
    }
    return items, constructions, judges


def _gate_for(profile, construction, arm):
    if profile.name == "level-0":
        return b.gate(construction)
    without = ()
    if profile.name.startswith("ablated:"):
        without = (profile.name.partition(":")[2],)
    return l1_gate(construction, without=without, arm=arm)


def variant_runners(constructions, judges, arm=None, trial_fn=None):
    """The climb's runners on the variant gate. A construction runs when the
    gate admits it; an attack's violation is judged as it declares (`gate`,
    `refused` or `trial`); a promising valid run is rebuilt twice."""
    from carbon.agent_campaign import climb
    from carbon.agent_campaign.graphite import experiment

    trial_fn = trial if trial_fn is None else trial_fn

    def construct(profile, item):
        outcome = _gate_for(profile, constructions[item.item_id], arm)
        return {
            "status": outcome["status"],
            "artifact_digest": b._digest(outcome),
            "result": outcome,
            "rebuild": REBUILD_LABEL,
        }

    def attack(profile, item):
        construction = constructions[item.item_id]
        outcome = _gate_for(profile, construction, arm)
        judge = judges[item.item_id]
        if judge == "gate":
            reproduced = outcome["status"] == "OK"
        elif judge == "refused":
            reproduced = (
                profile.name != "level-0"
                and outcome["status"] != "OK"
                and (item.uses <= profile.permissions)
            )
        else:
            reproduced = False
            if outcome["status"] == "OK" and profile.name != "level-0":
                outcome = {**outcome, "trial": trial_fn(construction, arm)}
                reproduced = not candidate_owned(outcome["trial"])
        found = {
            "status": outcome["status"],
            "violation_reproduced": reproduced,
            "evidence_digest": b._digest(outcome),
            "rebuild": REBUILD_LABEL,
        }
        if "trial" in outcome:
            # The trial's own typing, kept as evidence beside its digest.
            found["trial"] = outcome["trial"]
        return found

    def rebuild(run):
        construction = constructions[run["item_id"]]
        found = variant(arm)
        first = experiment.admit(
            construction, 7, scoring=b._challenge_scoring(), variant=found
        )
        second = experiment.admit(
            construction, 7, scoring=b._challenge_scoring(), variant=found
        )
        return {
            "status": "OK",
            "matches": first == second,
            "rebuilt_digest": b._digest(first),
            "rebuild": REBUILD_LABEL,
        }

    return climb.Runners(construct=construct, attack=attack, rebuild=rebuild)


def climb_report(arm=None, runners=None, trial_fn=None, open_findings=()):
    """The climb harness over the registered Level-1 variant (or the signed
    arm): Level 0 against Level 1, one ablation per Level-1 permission, the
    combined attacks and the clean rebuild. It never opens a level."""
    from carbon.agent_campaign import climb

    items, constructions, judges = _items(arm)
    plan = _level1().climb_plan(
        panel=items["panel"],
        attacks=items["attacks"],
        attack_budget=len(items["attacks"]),
        combined=items["combined"],
        promising=lambda run: run["item_id"] in {i.item_id for i in items["panel"]},
        arm=arm,
    )
    report = climb.climb(
        plan,
        runners or variant_runners(constructions, judges, arm, trial_fn),
        open_findings=open_findings,
    )
    return {**report, "rebuild": REBUILD_LABEL, "arm": arm}


# -- the adapter ----------------------------------------------------------------------
class BatteryLevel1Adapter(b.BatteryLevel0Adapter):
    """Battery at construction Level 1 (the registered development variant),
    for the attack engine. Its oracle is Level 0's, over Level-1 families."""

    challenge_id = CHALLENGE_ID
    level = LEVEL
    version = ADAPTER_VERSION
    controls_version = CONTROLS_VERSION
    #: B2 runs this adapter's own families (no Track A harness at Level 1).
    deterministic_baseline = None

    @property
    def contract_digest(self):
        """The valid variant's digest: a development adapter attacks its
        variant (phase 4 checks it against `DEV_VARIANTS`)."""
        return _pinned_digest()

    def families(self):
        out = []
        for spec in _families():
            trained = next(
                c for c in _controls() if c.family == spec.name and c.split == "trained"
            )
            out.append(
                b.FamilyDef(
                    name=spec.name,
                    check=spec.check,
                    boundary=spec.protocol_family,
                    attack_example=spec.attack_example,
                    control_example=trained.name,
                    family=self._engine_family(spec),
                )
            )
        return tuple(out)

    def controls(self, split):
        if split not in SPLITS:
            raise ValueError("split is trained or held_out")
        return tuple(self._control(c) for c in _controls() if c.split == split)

    def rebuild(self, construction):
        """Carbon's rebuild under the variant (`experiment.admit(variant=)`)."""
        from carbon.agent_campaign.graphite import experiment

        strategy_, seed = construction, 0
        if isinstance(construction, Mapping) and "strategy" in construction:
            strategy_, seed = construction["strategy"], construction.get("seed", 0)
        if b._protected(strategy_):
            return b.Unrebuildable(
                code="protected_material", detail="protected_material_named"
            )
        try:
            record = experiment.admit(
                strategy_, seed, scoring=b._challenge_scoring(), variant=variant()
            )
        except experiment.Unrebuildable as error:
            issue_codes = sorted({str(i[0]) for i in error.issues})
            core = "refused_by_contract"
            if error.code.startswith("development_variant_"):
                core = "rebuild_failed_infra"
            elif b.OUTSIDE_LEVEL_ISSUES & set(issue_codes):
                core = "outside_level"
            detail = error.code + (": " + ", ".join(issue_codes) if issue_codes else "")
            return b.Unrebuildable(code=core, detail=detail)
        except experiment.NotServed as error:
            return b.Unrebuildable(code="refused_by_contract", detail=str(error))
        return b.Rebuilt(
            construction_digest=b._digest(strategy_),
            rebuilt_digest=b._digest(record),
            detail={
                "record": record,
                "seed": seed,
                "served": True,
                "rebuild": REBUILD_LABEL,
            },
        )

    def level_families(self):
        return tuple(
            b.SeamFamily(name=s.name, check=s.check, level=s.level, reason=s.reason)
            for s in SEAMS
        )

    def permission_inventory(self):
        """Level 0's inventory with the variant's Level-1 permissions added."""
        inventory = dict(super().permission_inventory())
        found = variant()
        inventory["profile"] = PROFILE
        inventory["development_variant"] = found.digest
        inventory["permitted"] = list(inventory["permitted"]) + [
            {
                "id": w.capability_id,
                "surface": None,
                "applies_to": list(w.applies_to or ()),
                "planning_level": 1,
            }
            for w in found.widened
        ]
        inventory["not_permitted"] = [
            p
            for p in inventory["not_permitted"]
            if (p.get("id") if isinstance(p, Mapping) else p) not in found.permissions()
        ]
        return inventory

    def admission_refusals(self, construction):
        made = self.rebuild(construction)
        if isinstance(made, b.Rebuilt):
            return []
        return [self.carbon_code(made)] + [made.code]

    def surface(self):
        found = variant()
        return {
            "challenge": CHALLENGE_ID,
            "level": LEVEL,
            "profile": PROFILE,
            "contract_digest": self.contract_digest,
            "variant_version": found.version,
            "permissions": list(found.permissions()),
            "adapter_version": ADAPTER_VERSION,
            "rebuild": REBUILD_LABEL,
        }

    def family_specs(self):
        return _families()

    def family_spec(self, name):
        if isinstance(name, FamilySpec):
            return name
        for spec in _families():
            if spec.name == name:
                return spec
        raise KeyError(name)

    def control_specs(self, split):
        if split not in SPLITS:
            raise ValueError("split is trained or held_out")
        return tuple(c for c in _controls() if c.split == split)

    def checks(self):
        from carbon.challenge_readiness.admission import CHECKS

        covered = {check: [] for check in sorted(CHECKS[b.TRACK])}
        for spec in _families():
            covered[spec.check].append(spec.name)
        for seam in SEAMS:
            covered[seam.check].append(seam.name + ":" + b.NOT_RUN)
        return {check: tuple(names) for check, names in covered.items()}

    def controls_digest(self, split):
        return b._digest(
            {
                "version": CONTROLS_VERSION,
                "split": split,
                "controls": [
                    [c.name, b._digest(c.value())] for c in self.control_specs(split)
                ],
            }
        )

    def control_passes(self, control):
        spec = control
        if not isinstance(control, ControlSpec):
            (spec,) = [c for c in _controls() if c.name == control.name]
        return bool(self.family_spec(spec.family).control_check(spec.value()))

    def family_for(self, tool, arguments=None):
        """Which Level-1 family a research tool call probes, or None."""
        from carbon.development_session.research_tools import PREFIX

        name = str(tool).removeprefix(PREFIX)
        arguments = arguments if isinstance(arguments, Mapping) else {}
        if name == "start_research_task" and (
            arguments.get("kind") == "practice"
            or arguments.get("action") == "check_design"
        ):
            return "l1_expression_surface"
        if name in ("dry_validate", "compile_strategy"):
            return "l1_expression_surface"
        return None

    def attempt_input(self, family, attempt):
        for key in ("value", "input"):
            value = b._get(attempt, key, b._MISSING)
            if value is not b._MISSING:
                return value
        arguments = b._get(attempt, "arguments")
        if not isinstance(arguments, Mapping):
            return b._MISSING
        if family in ("l1_expression_surface", "l1_declarative_only"):
            return b._strategy_from(arguments)
        return b._MISSING


ADAPTER = BatteryLevel1Adapter()
