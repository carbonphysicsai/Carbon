"""Battery Track A (construction integrity) at Level 0: the registered harness.

`Design_Specs/Challenge_Admission.md` §3 asks, for each attack family, for
attacks, plus a known-vulnerable specimen showing the detector can fire. This
module registers them for the battery Challenge at Level 0
(CI-BATTERY-L0-01). Each family has three parts:

- **attacks**, run against the real boundary; each must be held;
- **a vulnerable specimen**: the same attacks against a deliberately weakened
  boundary. The detector must fire there, or it is vacuous and the family is
  INCONCLUSIVE, never a pass;
- **a valid control**: a legitimate input against the real boundary. It must
  pass, which measures wrongful rejection.

A breached attack is a finding (`FAILING_TRIGGER`), and so is a control the
real boundary wrongly refuses. Score-value divergence and gate anomalies on
retained EV results come from `carbon.battery.value.divergence`, unchanged.
Every finding is emitted and none is suppressed (§3.2).

What it is not. In-process checks prove the boundary they call, nothing more
(§3: "in-process fixture tests prove the fixture boundary only"). Worker
isolation is evidence from the pinned C-03 worker service lane, reused here
only through the applicability analysis in `COVERAGE`. No value is chosen
here: the owner's values (OWNER-TRACK-A-L0-02) are frozen in `STUDY_SHEET`,
and no family state is an acceptance. The family logic (run, findings,
state) is Carbon's Challenge-neutral attack engine
(`carbon.agent_campaign.attack.engine`, OWNER-GRAPHITE-ATTACKER-01); the
records and the coverage report are unchanged byte for byte. GRAPHITE-01 phase 4 (the attacker
agent) drives agent-generated attempts through these same detectors. Under
OWNER-ADMISSION-COMBINED-01 this harness is the attack side of the one
combined admission test.

    python -m carbon.battery.track_a run --out DIR
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

from carbon.agent_campaign.attack import engine

PROFILE = "level-0"
ATTEMPT_SCHEMA = "carbon.battery.track-a.attempt.v1"
REPORT_SCHEMA = "carbon.battery.track-a.coverage.v1"
CHALLENGE_ID = "battery-fastcharge-ageing-development-v1"
STUDY_SHEET = "docs/development/evidence/track-a-battery-l0-2026-10-02/study-sheet.json"
#: What every attempt record names: this harness's own schema, unchanged.
CONTEXT = engine.RunContext(
    challenge=CHALLENGE_ID, profile=PROFILE, schema=ATTEMPT_SCHEMA
)

HELD, BREACHED = engine.HELD, engine.BREACHED
FIRED, SILENT = engine.FIRED, engine.SILENT
PASSED, REFUSED = engine.PASSED, engine.REFUSED

_canonical = engine.canonical
_digest = engine.digest


def _strategy(backbone="mlp", **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE_ID,
        "backbone": backbone,
        "parameters": parameters,
    }


# --- Family 1: the recipe surface (artifact_and_dependency_attacks) --------

#: Hostile strategies a miner can submit at Level 0. Each names what it tries.
RECIPE_ATTACKS = (
    ("nonfinite_learning_rate", _strategy(learning_rate=math.nan)),
    ("infinite_learning_rate", _strategy(learning_rate=math.inf)),
    ("width_out_of_surface", _strategy(width=4096)),
    ("negative_steps", _strategy(steps=-1)),
    ("string_for_integer", _strategy(width="256")),
    ("boolean_for_integer", _strategy(width=True)),
    ("float_for_integer", _strategy(width=256.0)),
    ("nested_object_value", _strategy(width={"value": 256})),
    ("embedded_weight_table", _strategy(weights=[0.1] * 4096)),
    ("pretrained_weights_field", _strategy(pretrained_weights="https://x/w.bin")),
    ("submitted_dataset_field", _strategy(submitted_datasets=["train-extra"])),
    ("loss_expression_field", _strategy(loss_expression="mse(v)*0")),
    ("label_method_field", _strategy(label_method="reference_solver")),
    ("not_permitted_family", _strategy("transolver")),
    ("pretrained_family", _strategy("pretrained_weights")),
    ("unknown_backbone", _strategy("python_callable")),
    (
        "code_at_top_level",
        {**_strategy(), "code": "import os; os.system('id')"},
    ),
    ("other_challenge", {**_strategy(), "challenge_id": "burgers-dynamics-v1"}),
    ("unknown_schema_version", {**_strategy(), "schema_version": "9.9"}),
    ("parameters_not_an_object", {**_strategy(), "parameters": [["width", 256]]}),
    ("ignored_field_smuggled", _strategy(steps=100, warmup_steps=100)),
)
RECIPE_CONTROL = _strategy(steps=6000, width=256, depth=3)


def compile_boundary(strategy):
    """The real Level 0 boundary: Carbon's battery recipe compiler."""
    from carbon.battery.compile import compile_recipe
    from carbon.development_session.research_catalog import RecipeRejected

    try:
        _, recipe = compile_recipe(strategy)
    except RecipeRejected as refused:
        codes = sorted({(i.code, i.path) for i in refused.rejected.issues})
        return {"accepted": False, "codes": codes}
    except (TypeError, ValueError, KeyError, AttributeError) as refused:
        return {"accepted": False, "codes": [(type(refused).__name__, "")]}
    return {"accepted": True, "recipe_digest": recipe.recipe_digest}


def unchecked_compiler(strategy):
    """Vulnerable specimen: accepts any object-shaped strategy unchecked."""
    if type(strategy) is not dict:
        return {"accepted": False, "codes": [("not_an_object", "")]}
    return {"accepted": True, "recipe_digest": _digest(strategy)}


def recipe_breached(result):
    return result["accepted"]


# --- Family 2: forging a compiled recipe (artifact_and_dependency_attacks) --


def _forged_recipe_inputs():
    return (
        (
            "raw_recipe_without_token",
            {
                "family": "mlp",
                "values": (("width", 256),),
                "supplied": frozenset({"width"}),
                "strategy_hash": "0" * 64,
                "plan_digest": "sha256:" + "0" * 64,
            },
        ),
        (
            "raw_recipe_with_a_lookalike_token",
            {
                "family": "mlp",
                "values": (("width", 256),),
                "supplied": frozenset({"width"}),
                "strategy_hash": "0" * 64,
                "plan_digest": "sha256:" + "0" * 64,
                "token": object(),
            },
        ),
    )


def forge_boundary(fields):
    """The real boundary: `BatteryRecipe` refuses construction without the
    compiler's private token."""
    from carbon.battery.compile import BatteryRecipe

    try:
        BatteryRecipe(**fields)
    except TypeError:
        return {"accepted": False}
    return {"accepted": True}


def unsealed_recipe(fields):
    """Vulnerable specimen: a recipe type with no construction check."""
    return {"accepted": True, "fields": sorted(fields)}


def forge_control():
    """A recipe that came from the compiler is a recipe."""
    from carbon.battery.compile import BatteryRecipe, compile_recipe

    _, recipe = compile_recipe(RECIPE_CONTROL)
    return {"accepted": type(recipe) is BatteryRecipe}


# --- Family 3: mandatory failure is never compensated -----------------------
#     (score_exploitation_and_tail_failures)


def _set(outputs, key, index, value):
    values = list(outputs[key])
    values[index] = value
    outputs[key] = values


def _mandatory_attacks():
    """Each attack is the exact public PRACTICE references (a perfect score
    everywhere else) with one case made inadmissible in one way."""

    def nan_voltage(o, _):
        _set(o, "voltage_v", 60, math.nan)

    def short_voltage(o, _):
        o["voltage_v"] = list(o["voltage_v"])[:-1]

    def initial_voltage_off(o, _):
        _set(o, "voltage_v", 0, o["voltage_v"][0] + 0.5)

    def above_ceiling(o, _):
        _set(o, "voltage_v", 30, 9.0)

    def below_floor(o, _):
        _set(o, "voltage_v", 30, 0.5)

    def initial_temperature_off(o, inputs):
        _set(o, "temperature_c", 0, inputs["t_amb_c"] + 25.0)

    def negative_capacity(o, _):
        _set(o, "capacity_ah", 0, -1.0)

    def missing_output(o, _):
        del o["plating_margin_v"]

    def string_output(o, _):
        o["capacity_ah"] = "4.9,4.9,4.9,4.9"

    return (
        ("nan_voltage", nan_voltage),
        ("truncated_trajectory", short_voltage),
        ("initial_voltage_off", initial_voltage_off),
        ("voltage_above_ceiling", above_ceiling),
        ("voltage_below_floor", below_floor),
        ("initial_temperature_off", initial_temperature_off),
        ("negative_capacity", negative_capacity),
        ("missing_output", missing_output),
        ("string_output", string_output),
    )


class _Practice:
    """The public PRACTICE references and the exam's own scoring, loaded once."""

    _cached = None

    @classmethod
    def get(cls, root="."):
        if cls._cached is None:
            from carbon.battery.challenge import PublicMaterial
            from carbon.battery.practice import PracticeSet

            cls._cached = (PracticeSet.load(root), PublicMaterial.load(root))
        return cls._cached


def _oracle(practice):
    return {r["case_id"]: copy.deepcopy(r["outputs"]) for r in practice.records}


def mandatory_inputs(root="."):
    practice, _ = _Practice.get(root)
    victim = practice.records[17]
    out = []
    for name, damage in _mandatory_attacks():
        predictions = _oracle(practice)
        damage(predictions[victim["case_id"]], victim["inputs"])
        out.append((name, predictions))
    return tuple(out)


def scoring_boundary(predictions, root="."):
    """The real boundary: the exam's gates and aggregate on public PRACTICE."""
    from carbon.battery.practice import score_practice

    practice, material = _Practice.get(root)
    _, summary = score_practice(predictions, practice, material, root)
    return {
        "eligible": summary["eligible"],
        "score": summary["score"],
        "n_gate_failed": summary["n_gate_failed"],
        "gate_failures": summary["gate_failures"],
    }


def averaging_scorer(predictions, root="."):
    """Vulnerable specimen: scores the cases that passed and drops the rest,
    so one inadmissible case is averaged away instead of disqualifying."""
    import numpy as np

    from carbon.battery import exam
    from carbon.battery.calibration import SHAPES, frozen_calibration

    practice, material = _Practice.get(root)
    tol, scales = frozen_calibration(root)
    refs = {r["case_id"]: r for r in practice.records}
    ocv = {
        c: float(np.interp(r["inputs"]["soc0"], material.ocv_soc, material.ocv_v))
        for c, r in refs.items()
    }
    rows, _ = exam.evaluate(
        predictions, practice.case_ids, exam.CaseStore(refs, ocv, tol, scales, SHAPES)
    )
    scored = [r for r in rows if r["state"] == "SCORABLE"]
    return {
        "eligible": bool(scored),
        "score": float(np.mean([r["error"] for r in scored])) if scored else None,
        "n_gate_failed": 0,
        "gate_failures": {},
    }


def mandatory_breached(result):
    return result["eligible"]


def mandatory_control(root="."):
    practice, _ = _Practice.get(root)
    return _oracle(practice)


# --- Family 4: every supplied field changes what Carbon rebuilds ------------
#     (reconstruction_and_recipient_rebuild)

REBUILD_PAIRS = (
    ("width", _strategy(width=256), _strategy(width=128)),
    ("steps", _strategy(steps=6000), _strategy(steps=3000)),
    ("train_fraction", _strategy(train_fraction=1.0), _strategy(train_fraction=0.5)),
    (
        "optimizer",
        _strategy(optimizer_family="adam"),
        _strategy(optimizer_family="lion"),
    ),
    ("backbone", _strategy("mlp"), _strategy("deeponet")),
)


def rebuild_boundary(pair):
    """The real boundary: two strategies that differ in a supplied field must
    compile to different recipes (a field is never silently dropped)."""
    left, right = compile_boundary(pair[0]), compile_boundary(pair[1])
    if not (left["accepted"] and right["accepted"]):
        return {"collapsed": False, "refused": True}
    return {"collapsed": left["recipe_digest"] == right["recipe_digest"]}


def field_dropping_digest(pair):
    """Vulnerable specimen: a recipe identity that keeps only the Challenge,
    so every field a miner supplies is silently dropped."""
    return {"collapsed": pair[0]["challenge_id"] == pair[1]["challenge_id"]}


def rebuild_breached(result):
    return result["collapsed"]


def rebuild_control():
    """The same strategy, its keys reordered, is the same recipe."""
    reordered = json.loads(json.dumps(RECIPE_CONTROL))
    reordered["parameters"] = dict(reversed(list(reordered["parameters"].items())))
    a, b = compile_boundary(RECIPE_CONTROL), compile_boundary(reordered)
    return {"accepted": a["accepted"] and a == b}


# --- Family 5: what crosses into the worker (construction_evaluation_isolation)

#: Validator-private material the worker must never receive, as distinctive
#: bytes. They sit beside the staging calls as a validator's state does.
CANARY_ROOT = b"CANARY-PRIVATE-ROOT-0123456789AB"  # 32 bytes, like a root
CANARY_LABEL = "CANARY-HIDDEN-LABEL-7f3c"
CANARY_VALUE = 0.123456789123


def _hidden_batch():
    """A hidden batch as the validator holds it: opaque ids, inputs, and the
    private references and labels the worker must never see."""
    cases = {}
    for i in range(3):
        case_id = f"screen-{i:04x}"
        cases[case_id] = {
            "inputs": {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2},
            "reference": {
                "plating_margin_v": CANARY_VALUE,
                "label": CANARY_LABEL,
            },
        }
    return cases


def _staging_inputs():
    from carbon.battery.compile import compile_recipe

    _, recipe = compile_recipe(RECIPE_CONTROL)
    batch = _hidden_batch()
    return recipe, batch


def _stage_all(stager):
    recipe, batch = _staging_inputs()
    inputs = {c: row["inputs"] for c, row in batch.items()}
    return stager(recipe, inputs, batch)


def real_stager(recipe, inputs, batch):
    """The real boundary: the three staging calls the daemon and practice make.
    They are given what the daemon gives them, while the private state exists."""
    from carbon.battery import practice, worker

    practice_set, _ = _Practice.get()
    return {
        "reconstruct": worker.reconstruct_files(".", recipe, 7),
        "infer": worker.infer_files(b"model-state", inputs),
        "practice": practice.staged_files(".", practice_set, recipe, 7),
    }


def leaky_stager(recipe, inputs, batch):
    """Vulnerable specimen: inference also stages the hidden batch's
    references and the private root, as a careless refactor might."""
    staged = real_stager(recipe, inputs, batch)
    staged["infer"] = {
        **staged["infer"],
        "batch.json": json.dumps(batch).encode(),
        "root.bin": CANARY_ROOT,
    }
    return staged


def staged_canaries(staged):
    """Every canary found in any staged byte: the detector."""
    needles = (
        CANARY_ROOT,
        CANARY_LABEL.encode(),
        repr(CANARY_VALUE).encode(),
    )
    found = []
    for stage, files in staged.items():
        for name, body in files.items():
            for needle in needles:
                if needle in body:
                    found.append((stage, name, needle.decode(errors="replace")))
    return {"found": found}


def staging_control():
    """The staged names are exactly the published allow-list."""
    from carbon.battery.practice import STAGED_MODULES

    staged = _stage_all(real_stager)
    code = set(STAGED_MODULES)
    expected = {
        "reconstruct": code | {"train-v1.jsonl.gz", "ocv-table.json", "recipe.json"},
        "infer": code | {"state.npz", "query.json"},
        "practice": code
        | {
            "train-v1.jsonl.gz",
            "ocv-table.json",
            "practice-inputs.json",
            "recipe.json",
        },
    }
    return all(set(staged[k]) == expected[k] for k in expected)


# --- The families ------------------------------------------------------------
#     Run by Carbon's attack engine (`carbon.agent_campaign.attack.engine`,
#     OWNER-GRAPHITE-ATTACKER-01); this harness's records and report are
#     unchanged byte for byte.

Family = engine.Family
_control_passes = engine.control_from


FAMILIES = (
    Family(
        name="recipe_surface",
        check="artifact_and_dependency_attacks",
        description="hidden assets, embedded weights/tables, undeclared dependencies, "
        "model loaders, malformed values, parser abuse",
        attacks=lambda: RECIPE_ATTACKS,
        boundary=compile_boundary,
        specimen=unchecked_compiler,
        breached=recipe_breached,
        control=_control_passes(
            compile_boundary, lambda: RECIPE_CONTROL, recipe_breached
        ),
    ),
    Family(
        name="recipe_forgery",
        check="artifact_and_dependency_attacks",
        description="invalid artifacts",
        attacks=_forged_recipe_inputs,
        boundary=forge_boundary,
        specimen=unsealed_recipe,
        breached=lambda result: result["accepted"],
        control=lambda: forge_control()["accepted"],
    ),
    Family(
        name="mandatory_failure",
        check="score_exploitation_and_tail_failures",
        description="score averaging/denominator exploitation, malformed outputs, "
        "nonfinite values, rare catastrophic errors",
        attacks=mandatory_inputs,
        boundary=scoring_boundary,
        specimen=averaging_scorer,
        breached=mandatory_breached,
        control=lambda: scoring_boundary(mandatory_control())["eligible"],
    ),
    Family(
        name="rebuild_identity",
        check="reconstruction_and_recipient_rebuild",
        description="a field Carbon does not rebuild, accepted silently",
        attacks=lambda: tuple((name, (a, b)) for name, a, b in REBUILD_PAIRS),
        boundary=rebuild_boundary,
        specimen=field_dropping_digest,
        breached=rebuild_breached,
        control=lambda: rebuild_control()["accepted"],
    ),
    Family(
        name="staged_bytes",
        check="construction_evaluation_isolation",
        description="answer-key/log/artifact exfiltration, "
        "construction-to-evaluator access",
        attacks=lambda: (("stage_with_private_state_present", None),),
        boundary=lambda _: staged_canaries(_stage_all(real_stager)),
        specimen=lambda _: staged_canaries(_stage_all(leaky_stager)),
        breached=lambda result: bool(result["found"]),
        control=staging_control,
    ),
)


def run_family(family, *, budget=None):
    """Attempt records for one family: attacks, specimen and control."""
    return list(engine.run_family(family, budget=budget, context=CONTEXT).records)


def findings(records):
    """Every condition the records raise. None is suppressed."""
    return [finding.as_dict() for finding in engine.findings(records)]


def family_state(records, family_id):
    """IN_PROGRESS when every attack held, the specimen fired on every attack
    and the control passed; otherwise the blocking reason. Never ACCEPTED:
    acceptance is a reviewed LOCK (§3.3), not a test result."""
    return engine.family_state(records, family_id)


def divergence_findings(root="."):
    """Conditions on retained EV results, emitted by the existing detector."""
    from carbon.battery.value import divergence

    out = {}
    for name in ("ev2-2026-10-01", "ev4-2026-10-01"):
        path = Path(root) / "docs/development/evidence" / name / "results.json"
        results = json.loads(path.read_text())
        out[name] = {
            "results_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "conditions": divergence.conditions(results),
        }
    return out


#: Applicability analysis: evidence this harness reuses rather than reruns,
#: with the pin it depends on, and what remains untested. Reuse is valid only
#: while those pins match (§3, "shared infrastructure evidence").
COVERAGE = {
    "baseline_and_permission_ablation": {
        "here": [],
        "reused": [],
        "untested": [
            (
                "the legitimate Level 0 panel under the same attack budget: the "
                "EV4 panel is the candidate baseline; the budget is HUMAN_INPUT"
            ),
        ],
    },
    "artifact_and_dependency_attacks": {
        "here": ["recipe_surface", "recipe_forgery"],
        "reused": [
            (
                "tests/cpu/test_battery_construction_contract.py (per-field refusals, "
                "cross-Challenge refusal, every surface changes the rebuild)"
            ),
            (
                "tests/cpu/test_battery_validator_daemon.py::"
                "test_contract_artifact_and_cross_challenge_mismatches_are_refused"
            ),
        ],
        "untested": [
            (
                "intake transport limits (body size, JSON depth) through the live "
                "intake listener"
            ),
        ],
    },
    "score_exploitation_and_tail_failures": {
        "here": ["mandatory_failure", "divergence on EV2 and EV4 results"],
        "reused": [],
        "untested": [
            (
                "always-abstain and subgroup sacrifice on the hidden pool (needs "
                "the frozen study population, HUMAN_INPUT)"
            ),
        ],
    },
    "adaptive_feedback_and_state_attacks": {
        "here": [],
        "reused": [
            (
                "tests/cpu/test_battery_validator_daemon.py::"
                "test_outcomes_disclose_no_private_case_label_or_seed"
            ),
            (
                "tests/cpu/test_battery_rule_v2.py::"
                "test_a_scored_v2_outcome_shows_a_miner_nothing_from_the_hidden_batch"
            ),
            (
                "tests/cpu/test_battery_feedback_modes.py::"
                "test_the_withheld_view_is_an_allow_list_so_new_fields_stay_hidden"
            ),
            (
                "tests/cpu/test_battery_validator_daemon.py::"
                "test_published_campaign_cases_cannot_be_hidden_cases"
            ),
            (
                "tests/cpu/test_battery_validator_daemon.py::"
                "test_duplicate_admission_and_replay_count_once"
            ),
        ],
        "untested": [
            (
                "repeated-query learning and colluding hotkeys over many practice "
                "rounds (an attack budget, HUMAN_INPUT; GRAPHITE phase 4)"
            ),
            "timing side channels on refusal codes",
        ],
    },
    "resource_and_failure_accounting": {
        "here": [],
        "reused": [
            (
                "tests/cpu/test_battery_validator_daemon.py::"
                "test_infrastructure_failure_is_retried_never_scored"
            ),
            (
                "tests/service/test_battery_validator_containers.py::"
                "test_a_run_killed_at_its_wall_clock_bound_is_infrastructure"
            ),
            (
                "tests/service/test_battery_validator_containers.py::"
                "test_partial_output_is_infrastructure_never_a_candidate_failure"
            ),
        ],
        "untested": [
            (
                "surface-edge recipes (widest, longest, largest ensemble) against "
                "the pinned worker envelope (CPU 2, 4 GiB, 600 s), in the C-03 "
                "service lane"
            ),
        ],
    },
    "construction_evaluation_isolation": {
        "here": ["staged_bytes"],
        "reused": [
            (
                "tests/service/test_c03_worker_service.py::"
                "test_network_filesystem_pid_memory_and_scratch_enforcement"
            ),
            (
                "tests/service/test_c03_worker_service.py::"
                "test_network_none_denies_controlled_canary_and_negative_control_detects_it"
            ),
            (
                "tests/service/test_c03_worker_service.py::"
                "test_descendant_cannot_survive_exact_container_termination"
            ),
            (
                "tests/service/test_battery_practice_carrier.py::"
                "test_battery_practice_runs_in_the_isolated_carrier"
            ),
        ],
        "pin": "the C-03 worker image manifest built by scripts/dev/c03_worker_image.sh "
        "in CI; reuse holds only for the same manifest",
        "untested": [
            (
                "the same canary scan over every byte a real practice run "
                "leaves in the isolated carrier, against the pinned image "
                "(tests/service/test_battery_track_a_service.py, CI only)"
            ),
        ],
    },
    "reconstruction_and_recipient_rebuild": {
        "here": ["rebuild_identity"],
        "reused": [
            (
                "tests/service/test_battery_validator_containers.py::"
                "test_isolated_programs_match_the_in_process_backend"
            ),
        ],
        "untested": [
            (
                "a second operator rebuilding from the delivery package; "
                "tolerances are HUMAN_INPUT"
            ),
        ],
    },
    "fresh_attack_confirmation": {
        "here": [],
        "reused": [],
        "untested": ["NOT_RUN: needs a frozen study sheet and fresh cases"],
    },
}
NOT_RUN_AT_LEVEL_0 = (
    "hidden preprocessing/compilation, child processes, device/host memory, "
    "inference/solver hybrids and custom inference need participant code, "
    "which Level 0 does not permit: NOT_RUN for this profile, never a pass"
)


def run(root="."):
    records = [r for family in FAMILIES for r in run_family(family)]
    emitted = findings(records)
    divergence = divergence_findings(root)
    report = {
        "schema": REPORT_SCHEMA,
        "challenge": CHALLENGE_ID,
        "profile": PROFILE,
        "evidence": "DEVELOPMENT",
        "families": {f.family_id: family_state(records, f.family_id) for f in FAMILIES},
        "attempts": {
            role: sum(r["role"] == role for r in records)
            for role in ("attack", "specimen", "control")
        },
        "findings": emitted,
        "divergence": {
            name: {
                "results_sha256": d["results_sha256"],
                "conditions": len(d["conditions"]),
                "by_condition": {
                    c: sum(x["condition"] == c for x in d["conditions"])
                    for c in sorted({x["condition"] for x in d["conditions"]})
                },
            }
            for name, d in divergence.items()
        },
        "coverage": COVERAGE,
        "not_run_at_level_0": NOT_RUN_AT_LEVEL_0,
        "values": {
            "authority": "OWNER-TRACK-A-L0-02",
            "study_sheet": STUDY_SHEET,
            "state": "INCONCLUSIVE",
            "lock_precondition": (
                "the deciding rule must stop scoring the boundary-optimist "
                "control at or above eligible real models (route a)"
            ),
        },
        "claims": {"security_acceptance": False, "qualification": False},
    }
    return records, report, divergence


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.track_a")
    sub = parser.add_subparsers(dest="command", required=True)
    go = sub.add_parser("run", help="Run every family; write ledger and report")
    go.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    records, report, divergence = run(".")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "attempts.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)
    )
    (args.out / "conditions.json").write_text(
        json.dumps(
            {k: v["conditions"] for k, v in divergence.items()},
            sort_keys=True,
            indent=1,
            default=repr,
        )
    )
    (args.out / "coverage.json").write_text(
        json.dumps(report, sort_keys=True, indent=1)
    )
    print(json.dumps({k: report[k] for k in ("families", "attempts")}, sort_keys=True))
    fired = report["findings"] or any(
        d["conditions"] for d in report["divergence"].values()
    )
    # Like the divergence command: exit 1 when any condition fires.
    return 1 if fired else 0


if __name__ == "__main__":
    sys.exit(main())
