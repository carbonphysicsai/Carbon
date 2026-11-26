"""The data kit's LOCAL SCORER: a thin caller of the official grade's own code.

`python -m carbon.challenge_kit.local_scorer score --recipe R --submission-dir D
--verify V --verify-sha256 S --out OUT.json`

It imports and calls the functions the official grade path runs, in the same
order, and holds no scoring, training or admission logic of its own
(KIT_LOCAL_SCORER_DESIGN_TE_20261103, Validator conditions A5 and A6):

1. admission and build: the version's graph adapter (`graph_adapters.module_for`;
   graph route v2, `physical_graph_adapter_v2`): the recipe's identity binding
   (`construction_recipe.bind_recipe`, the construction kit), the public TRAIN by
   exact digest (`checked_train`), then `build_validated_graph(recipe,
   raw_manifest, files, allowlist_bytes=served_allowlist_bytes(cid, ver),
   train_cases=spec.rows)`, as the build child runs them. A refusal carries the
   adapter's own closed code and its class (`build_refusal_v2.outcome`), as the
   build child declines. The information budget is reported from the same
   `intake` and `validate.validate_submission` calls: the counted measurement and
   the cap the version's allowlist accounting reads;
2. train: `model.fit(inputs, targets, seed=0)` on the version's PUBLIC TRAIN
   (seed 0 is the official build's);
3. predict: `model.predict(rows, isolated=True)` on the verify designs' inputs, in
   the interface's input order (the public TRAIN's numeric interface);
4. score what the verify designs can show: per design the official per-case gates
   (`carbon.motor.exam.evaluate_case` / `gates`) and the kit verify's
   accuracy-vs-U check (`carbon.motor.exam.feasibility`: |model - truth| <= U on
   mean torque and ripple fraction, U from the verify set). The design value D,
   picks, regret, the pool score and the sealed minimums need Carbon's hidden
   pools: they are reported as "not evaluated locally" (A5), never a pass. The
   speed gate is a local timing of isolated single-case predict calls, labelled a
   local estimate, never the official gate.

The output names the code it ran (A6): the checkout's git HEAD and the sha256 of
every module it calls. It opens no evaluation pack, seed, sealed material or
private state, and writes no path into its output. A practice result, never a
grade; nothing here is LIVE authority.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, NamedTuple

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "carbon.kit-local-score.v1"
LABEL = "local practice score: never a grade"
NOT_EVALUATED = "not evaluated locally"
TIMING_LABEL = "local estimate, not the official gate"
#: The seed the official build trains at.
OFFICIAL_SEED = 0
MOTOR = "electric-motor-magnetics"
#: The graded quantities the kit's verify compares within U.
U_KEYS = ("mean_torque_nm", "ripple_fraction")
#: What needs Carbon's hidden material and is never computed or defaulted here (A5).
HIDDEN = {
    "D": "the design value on Carbon's hidden pool",
    "picks": "the designs a model picks from the hidden pool",
    "regret": "the picks' regret against the hidden pool's truths",
    "pool_score": "the pool grade over the hidden pool",
    "sealed_minimums": "the sealed per-version minimums",
    "paired_repeat_gate": "the hidden duplicate cases the paired-repeat gate reads",
    "official_speed_gate": "the timed query on the validator's machine",
}
#: Path parts the scorer never reads or writes: Carbon's packs, custody and
#: private material never pass through a kit command.
PROTECTED_PARTS = (
    "custody",
    "sealed",
    "case_bank",
    "evaluation_pack",
    "validator_host_classes",
    ".carbon-local",
    "secrets",
)
#: The modules whose code the score ran (A6), by repository path.
CODE_MODULES = (
    "carbon/challenge_kit/local_scorer.py",
    "carbon/development_session/construction_recipe.py",
    "carbon/development_session/build_refusal_v2.py",
    "carbon/development_session/physical_graph_adapter_v2.py",
    "carbon/development_session/physical_graph_trainer_v2.py",
    "carbon/development_session/physical_graph_trainer_v3.py",
    "carbon/development_session/physical_graph_state_v2.py",
    "carbon/level4/allowlist.py",
    "carbon/level4/graph.py",
    "carbon/level4/intake.py",
    "carbon/level4/train.py",
    "carbon/level4/validate.py",
    "carbon/motor/exam.py",
    "carbon/motor/row18.py",
    "carbon/motor/row19.py",
    "carbon/scoring/pool_adapters.py",
    "carbon/scoring/pool_plugin.py",
    "carbon/scoring/pool_version.py",
)


class ScorerRefused(ValueError):
    """A refused kit-scorer input (never a candidate refusal), with a plain reason."""


# --- inputs ---------------------------------------------------------------------


def refuse_protected(path) -> Path:
    resolved = Path(path).expanduser().resolve()
    for part in resolved.parts:
        if any(mark in part.lower() for mark in PROTECTED_PARTS):
            raise ScorerRefused(
                "that looks like a Carbon pack, custody or private path; "
                "the local scorer never reads or writes those"
            )
    return resolved


def _hex(value: str) -> str:
    value = value.strip().lower()
    return value.removeprefix("sha256:")


def _finite(value) -> bool:
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def load_verify_set(
    raw: bytes, expected_sha256: str, input_names, *, truth_error=None
) -> dict:
    """The verify set, only at the digest the caller pins. ``truth_error(design)``
    names what is wrong with a design's truth, or None; None (the default) is the
    Motor check (a finite ``truth.torque_nm`` curve), as before."""
    if type(raw) is not bytes or type(expected_sha256) is not str:
        raise ScorerRefused("a verify set and its sha256 are required")
    if hashlib.sha256(raw).hexdigest() != _hex(expected_sha256):
        raise ScorerRefused("the verify set's bytes differ from the given sha256")
    try:
        document = json.loads(raw)
    except ValueError:
        raise ScorerRefused("the verify set is not JSON") from None
    designs = document.get("designs") if type(document) is dict else None
    if type(designs) is not list or not designs:
        raise ScorerRefused("the verify set holds no designs")
    seen = set()
    for design in designs:
        if type(design) is not dict:
            raise ScorerRefused("a verify design must be an object")
        case_id = design.get("case_id")
        inputs = design.get("inputs")
        if type(case_id) is not str or not case_id or case_id in seen:
            raise ScorerRefused("each verify design needs its own case_id")
        seen.add(case_id)
        if (
            type(inputs) is not dict
            or set(inputs) != set(input_names)
            or not all(_finite(inputs[name]) for name in input_names)
        ):
            raise ScorerRefused(f"{case_id}: the inputs are not the interface's")
        wrong = (truth_error or _motor_truth_error)(design)
        if wrong is not None:
            raise ScorerRefused(f"{case_id}: {wrong}")
    return document


def _motor_truth_error(design):
    curve = (design.get("truth") or {}).get("torque_nm")
    if type(curve) is not list or not all(_finite(v) for v in curve):
        return "the truth curve is malformed"
    return None


def _u(document):
    """The verify set's U per graded quantity, or None while unregistered."""
    u = document.get("u")
    if type(u) is not dict or not all(_finite(u.get(k)) and u[k] >= 0 for k in U_KEYS):
        return None
    return {k: float(u[k]) for k in U_KEYS}


# --- the code it ran (A6) ---------------------------------------------------------


def _git(*args):
    try:
        done = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def code_identity() -> dict:
    """The checkout's git HEAD and the sha256 (CRLF read as LF) of every module
    the score calls."""
    head = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain", "--untracked-files=no", "--", *CODE_MODULES)
    return {
        "commit": head,
        "code_modules_modified": None if status is None else bool(status),
        "modules_sha256": {
            rel: hashlib.sha256(
                (ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            for rel in CODE_MODULES
        },
    }


# --- per-Challenge local verify checks ---------------------------------------------


def _motor_quantities(curve):
    """Mean torque and ripple fraction from the exam's own feasibility reading,
    as the kit's verify reads them; None where the mean is not positive."""
    from carbon.motor import exam

    values = exam.feasibility(
        {"torque_nm": curve}, min_torque_nm=0.0, max_ripple_fraction=0.0
    )
    mean = values["mean_nm"]
    return {
        "mean_torque_nm": mean,
        "ripple_fraction": values["ripple_pk_pk_nm"] / mean if mean > 0 else None,
    }


def motor_torque(row):
    """The torque curve a Motor check reads from a model's row: the torque slice of a whole 240-wide Motor 1.8 row or a
    whole 241-wide Motor 1.9 row (their public splits, `carbon.motor.row18.split` / `row19.split`, which the grades also
    use), any other row as it is, which the native gates then judge."""
    from carbon.motor import row18, row19

    parts = row18.split(row) or row19.split(row)
    return list(row) if parts is None else parts["torque_nm"]


def _motor_design(design, prediction, u):
    from carbon.motor import exam

    curve = [float(v) for v in motor_torque(prediction)]
    verdict = exam.evaluate_case({"torque_nm": curve}, {"status": "OK"})
    row = {
        "case_id": design["case_id"],
        "prediction": {"torque_nm": curve},
        "state": verdict["state"],
        "gates": verdict["gates"],
    }
    if u is None:
        row["accuracy_vs_u"] = {
            "status": NOT_EVALUATED,
            "reason": "the verify set carries no registered U",
        }
        return row
    got = _motor_quantities(curve)
    want = _motor_quantities(design["truth"]["torque_nm"])
    within = True
    check = {}
    for name in U_KEYS:
        delta = (
            abs(got[name] - want[name])
            if got[name] is not None and want[name] is not None
            else None
        )
        ok = delta is not None and delta <= u[name]
        check[name] = {
            "model": got[name],
            "truth": want[name],
            "delta": delta,
            "u": u[name],
            "within_u": ok,
        }
        within = within and ok
    check["within_u"] = within
    row["accuracy_vs_u"] = check
    return row


def _motor_aggregate(rows, u):
    from carbon.motor import exam

    fails = {}
    for row in rows:
        for gate, verdict in row["gates"].items():
            if verdict == exam.FAIL:
                fails[gate] = fails.get(gate, 0) + 1
    out = {
        "n_designs": len(rows),
        "n_scorable": sum(r["state"] == exam.SCORABLE for r in rows),
        "n_gate_failed": sum(r["state"] == exam.GATE_FAILED for r in rows),
        "gate_failures": fails,
    }
    if u is None:
        out["accuracy_vs_u"] = {"status": NOT_EVALUATED}
    else:
        out["accuracy_vs_u"] = {
            **{
                name: sum(r["accuracy_vs_u"][name]["within_u"] for r in rows)
                for name in U_KEYS
            },
            "n_within_u": sum(r["accuracy_vs_u"]["within_u"] for r in rows),
        }
    return out


#: Challenges with a check written in code: (per-design, aggregate). Every other
#: Challenge is checked from its registered pool binding (`local_check`), so a new
#: family needs no row here (miner-ux 8683).
LOCAL_CHECKS = {MOTOR: (_motor_design, _motor_aggregate)}

#: A verify design of a binding-checked Challenge carries its truth as the raw
#: output row in the model's output space: ``{"truth": {"raw": [numbers]}}``.
RAW_TRUTH = "raw"
PASS, FAIL = "PASS", "FAIL"
SCORABLE, GATE_FAILED = "SCORABLE", "GATE_FAILED"


class LocalCheck(NamedTuple):
    """One Challenge version's local verify check."""

    truth_error: Callable  # (design) -> str | None
    u: Callable  # (verify document) -> {quantity: U} | None
    per_design: Callable  # (design, prediction, u) -> row
    aggregate: Callable  # (rows, u) -> summary


def _raw_truth_error(design):
    raw = (design.get("truth") or {}).get(RAW_TRUTH)
    if type(raw) is not list or not raw or not all(_finite(v) for v in raw):
        return "the truth is not a finite raw output row"
    return None


def _named_u(document):
    """The verify set's U per derived output it names, or None while unregistered."""
    u = document.get("u")
    if type(u) is not dict or not u:
        return None
    if not all(type(k) is str and _finite(v) and v >= 0 for k, v in u.items()):
        return None
    return {k: float(u[k]) for k in sorted(u)}


def _registered_binding(challenge_id, version):
    """The OFFICIAL pool binding the grade reads for this version: its own
    registered one, or the static adapter's for a version no overlay serves. An
    overlay version whose dispatch has not registered its binding in this process
    refuses: the static adapter would be another version's (miner-ux 8683 R1)."""
    from carbon.challenge_kit import version_overlay
    from carbon.scoring import pool_adapters, pool_exam, pool_version

    kind = pool_version.KINDS.get(challenge_id)
    if kind is None:
        raise ScorerRefused("no local verify check is registered for this Challenge")
    registered = (kind, version) in pool_version._BINDINGS
    if not registered and version_overlay.is_overlay(challenge_id, version):
        raise ScorerRefused(
            "this version's pool binding is not registered in this process"
        )
    try:
        binding = pool_version.official_binding(kind, version)
    except (pool_adapters.PoolAdapterRefused, pool_exam.ExamRefused):
        raise ScorerRefused("no pool binding is registered for this version") from None
    if binding.physics_gates is None:
        raise ScorerRefused("the version's pool binding registers no gates")
    return binding


def _derived(binding, inputs, raw):
    try:
        values = binding.derive(inputs, raw)
    except Exception:  # a candidate's row the derive cannot read: no value, not a pass
        return {}
    return values if type(values) is dict else {}


def _binding_check(binding):
    names = tuple(binding.physics_gates.gate_names)

    def per_design(design, prediction, u):
        try:
            inputs = {n: float(design["inputs"][n]) for n in binding.input_names}
        except KeyError:
            raise ScorerRefused(
                "the registered binding's inputs are not the interface's"
            ) from None
        raw = [float(v) for v in prediction]
        failed = set(binding.physics_gates.failed(inputs, raw))
        row = {
            "case_id": design["case_id"],
            "state": GATE_FAILED if failed else SCORABLE,
            "gates": {
                g: FAIL if g in failed else PASS for g in sorted({*names, *failed})
            },
        }
        if u is None:
            row["accuracy_vs_u"] = {
                "status": NOT_EVALUATED,
                "reason": "the verify set carries no registered U",
            }
            return row
        got = _derived(binding, inputs, raw)
        want = _derived(binding, inputs, design["truth"][RAW_TRUTH])
        check = {}
        for name in u:
            model, truth = got.get(name), want.get(name)
            delta = (
                abs(float(model) - float(truth))
                if _finite(model) and _finite(truth)
                else None
            )
            check[name] = {
                "model": model,
                "truth": truth,
                "delta": delta,
                "u": u[name],
                "within_u": delta is not None and delta <= u[name],
            }
        check["within_u"] = all(check[name]["within_u"] for name in u)
        row["accuracy_vs_u"] = check
        return row

    def aggregate(rows, u):
        fails = {}
        for row in rows:
            for gate, verdict in row["gates"].items():
                if verdict == FAIL:
                    fails[gate] = fails.get(gate, 0) + 1
        out = {
            "n_designs": len(rows),
            "n_scorable": sum(r["state"] == SCORABLE for r in rows),
            "n_gate_failed": sum(r["state"] == GATE_FAILED for r in rows),
            "gate_failures": fails,
        }
        if u is None:
            out["accuracy_vs_u"] = {"status": NOT_EVALUATED}
        else:
            out["accuracy_vs_u"] = {
                **{
                    name: sum(r["accuracy_vs_u"][name]["within_u"] for r in rows)
                    for name in u
                },
                "n_within_u": sum(r["accuracy_vs_u"]["within_u"] for r in rows),
            }
        return out

    return LocalCheck(_raw_truth_error, _named_u, per_design, aggregate)


def local_check(challenge_id: str, version: str) -> LocalCheck:
    """The local verify check of one Challenge version: its code row in
    `LOCAL_CHECKS`, else the gates and derive of its registered pool binding (the
    ones the official grade reads), else `ScorerRefused`."""
    if challenge_id in LOCAL_CHECKS:
        per_design, aggregate = LOCAL_CHECKS[challenge_id]
        return LocalCheck(_motor_truth_error, _u, per_design, aggregate)
    return _binding_check(_registered_binding(challenge_id, version))


# --- the official functions, in the official order ------------------------------------


def _adapter(challenge_id: str, version: str):
    from carbon.development_session import graph_adapters, physical_graph_adapter_v2

    module = graph_adapters.module_for(challenge_id, version)
    if module is not physical_graph_adapter_v2:
        raise ScorerRefused("the local scorer serves graph route v2 versions only")
    local_check(challenge_id, version)
    return module


def public_train(challenge_id: str, version: str) -> dict:
    """The version's public TRAIN bytes and numeric interface (Motor's loader,
    the one the official material serves)."""
    from carbon.challenge_kit import physical_public_train

    source = physical_public_train.load_public_train(challenge_id, version)
    return {
        "train": source["train"],
        "input_names": list(source["provenance"]["numeric_interface"]["input_names"]),
    }


def _x64(enabled: bool):
    if not enabled:
        return contextlib.nullcontext()
    import jax

    return jax.enable_x64(True)


def _wide(raw_manifest: bytes, files: dict) -> bool:
    """The build child's 64-bit switch: the interface is float64, or the graph
    names a 64-bit dtype (`direct_graph_construction_worker`)."""
    from carbon.development_session.direct_graph_construction_worker import (
        _envelope_has_wide_values,
    )
    from carbon.development_session.profile import canonical
    from carbon.level4 import staging

    return _envelope_has_wide_values(canonical(staging.envelope(raw_manifest, files)))


def _refusal(code: str) -> dict:
    """The build child's decline record for a closed code."""
    from carbon.development_session import build_refusal_v2

    state = (
        "REFUSED"
        if build_refusal_v2.outcome(code) == build_refusal_v2.REFUSED
        else "UNRESOLVED"
    )
    return {
        "state": state,
        "reason_code": (
            "graph_submission_invalid"
            if state == "REFUSED"
            else "carbon_graph_adapter_unavailable"
        ),
        "detail_code": code,
    }


def information_budget(module, spec, recipe, raw_manifest, files, allowlist_bytes):
    """The counted fitted-information measurement and its cap, from the same
    `intake` and `validate_submission` calls `build_validated_graph` makes."""
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import graph, intake, validate

    allowed = allowlist_module.Allowlist(allowlist_bytes)
    interface = module.graph_interface(spec)
    _, parsed = intake.intake(
        raw_manifest,
        files,
        allowlist=allowed,
        challenge=spec.challenge_id,
        interface=interface.digest(),
        loss_override=module.LOSS_OVERRIDE,
    )
    verdict = validate.validate_submission(
        parsed,
        allowed,
        interface=interface,
        batch=module.training_settings(recipe)["batch_size"],
        loss_override=module.LOSS_OVERRIDE,
    )
    accounting, measured_as = allowlist_module.accounting_for(allowed)
    cap = allowlist_module.caps_for(allowed).get("constant_bytes")
    measurement = measured_as.get("constant_bytes", "constant_bytes")
    documents = verdict["documents"]
    if accounting == allowlist_module.CONSTANT_ACCOUNTING_V6:
        docs = [parsed[k] for k in ("forward", "init", "loss") if k in parsed]
        counted, scope = graph.recipe_info_bytes(*docs), "whole_submission"
    elif accounting == allowlist_module.CONSTANT_ACCOUNTING_V5:
        counted = sum(v["measurements"][measurement] for v in documents.values())
        scope = "whole_submission"
    else:
        counted = max(v["measurements"][measurement] for v in documents.values())
        scope = "largest_document"
    return {
        "accounting": accounting,
        "allowlist": {"version": allowed.version, "digest": allowed.digest},
        "measurement": measurement,
        "scope": scope,
        "counted_bytes": counted,
        "cap_bytes": cap,
        "documents": {
            slot: {"measured": v["measurements"].get(measurement), "caps": v["caps"]}
            for slot, v in sorted(documents.items())
        },
    }


def build_and_predict(recipe_bytes, raw_manifest, files, rows, *, train_bytes=None):
    """Steps 1-3. Returns {"admission", "budget", "fit", "predictions", "model",
    "spec", "input_names"}; a refused recipe returns its decline record in
    "admission" and nothing else."""
    import numpy as np

    from carbon.challenge_kit import physical_material
    from carbon.development_session.construction_recipe import (
        ConstructionRecipe,
        RecipeRefused,
        bind_recipe,
    )
    from carbon.level4 import intake
    from carbon.level4.graph import GraphRefused

    try:
        recipe = ConstructionRecipe.from_bytes(recipe_bytes)
    except RecipeRefused as error:
        return {"admission": _refusal(error.code)}
    named = recipe.to_dict()["challenge"]
    cid, version = named["id"], named["version"]
    module = _adapter(cid, version)
    material = public_train(cid, version)
    train = material["train"] if train_bytes is None else train_bytes
    allowlist_bytes = module.served_allowlist_bytes(cid, version)
    try:
        kit = physical_material.construction_kit(cid, version)
        bind_recipe(
            recipe.to_dict(),
            challenge_id=cid,
            challenge_version=version,
            train_digest=kit["train_digest"],
            interface_digest=kit["interface_digest"],
            construction_limits_digest=kit["construction_limits_digest"],
        )
        spec = module.spec_for(cid, version)
        inputs, targets = module.checked_train(spec, train, kit["train_digest"])
    except RecipeRefused as error:
        return {"admission": _refusal(error.code)}
    query = np.ascontiguousarray(np.asarray(rows, dtype=spec.dtype))
    wide = spec.dtype == "float64" or _wide(raw_manifest, files)
    with _x64(wide):
        try:
            model = module.build_validated_graph(
                recipe,
                raw_manifest,
                files,
                allowlist_bytes=allowlist_bytes,
                train_cases=len(inputs),
            )
        except (GraphRefused, RecipeRefused) as error:
            return {"admission": _refusal(error.code)}
        except intake.IntakeBlocked:
            return {"admission": _refusal("graph_validation_not_ready")}
        try:
            fit = model.fit(inputs, targets, seed=OFFICIAL_SEED)
        except RecipeRefused as error:
            if error.code != module.CODE + "nonfinite_state":
                raise
            return {"admission": _refusal(error.code)}
        budget = information_budget(
            module, spec, recipe, raw_manifest, files, allowlist_bytes
        )
        predictions = model.predict(query, isolated=True)
    return {
        "admission": {"state": "ADMITTED", "recipe_digest": recipe.digest},
        "budget": budget,
        "fit": fit,
        "predictions": predictions,
        "model": model,
        "spec": spec,
        "wide": wide,
        "input_names": material["input_names"],
    }


def local_timing(model, query, *, wide: bool, calls: int) -> dict:
    """Isolated single-case predict calls, timed on this machine."""
    import jax

    seconds = []
    with _x64(wide):
        for index in range(max(1, calls)):
            row = query[index % len(query)][None, :]
            start = time.perf_counter()
            model.predict(row, isolated=True)
            seconds.append(time.perf_counter() - start)
    warm = sorted(seconds[1:]) or seconds
    return {
        "label": TIMING_LABEL,
        "backend": jax.default_backend(),
        "calls": len(seconds),
        "first_call_seconds": seconds[0],
        "median_seconds": warm[len(warm) // 2],
        "max_seconds": max(warm),
    }


def _recipe_challenge(recipe_bytes):
    """The Challenge a recipe names, {"id", "version"}; None for a refused recipe."""
    from carbon.development_session.construction_recipe import (
        ConstructionRecipe,
        RecipeRefused,
    )

    try:
        return ConstructionRecipe.from_bytes(recipe_bytes).to_dict()["challenge"]
    except RecipeRefused:
        return None


def _input_names(recipe_bytes):
    named = _recipe_challenge(recipe_bytes)
    if named is None:
        return None
    _adapter(named["id"], named["version"])
    return public_train(named["id"], named["version"])["input_names"]


def score(
    recipe_bytes: bytes,
    raw_manifest: bytes,
    files: dict,
    verify_bytes: bytes,
    verify_sha256: str,
    *,
    train_bytes: bytes | None = None,
    timing_calls: int = 8,
) -> dict:
    """The local score report (see the module doc)."""
    import numpy as np

    names = _input_names(recipe_bytes)
    report = {
        "schema": SCHEMA,
        "label": LABEL,
        "code": code_identity(),
        "seed": OFFICIAL_SEED,
        "not_evaluated_locally": {
            key: {"status": NOT_EVALUATED, "needs": why}
            for key, why in sorted(HIDDEN.items())
        },
    }
    if names is None:
        built = build_and_predict(recipe_bytes, raw_manifest, files, [])
        report.update(admission=built["admission"])
        return report
    named = _recipe_challenge(recipe_bytes)
    check = local_check(named["id"], named["version"])
    document = load_verify_set(
        verify_bytes, verify_sha256, names, truth_error=check.truth_error
    )
    designs = document["designs"]
    rows = [[float(d["inputs"][n]) for n in names] for d in designs]
    built = build_and_predict(
        recipe_bytes, raw_manifest, files, rows, train_bytes=train_bytes
    )
    report["admission"] = built["admission"]
    if built["admission"]["state"] != "ADMITTED":
        return report
    spec, predictions = built["spec"], built["predictions"]
    u = check.u(document)
    results = [
        check.per_design(design, predictions[index], u)
        for index, design in enumerate(designs)
    ]
    query = np.ascontiguousarray(np.asarray(rows, dtype=spec.dtype))
    report.update(
        challenge={"id": spec.challenge_id, "version": spec.version},
        adapter=spec.adapter_id,
        information_budget=built["budget"],
        fit=built["fit"],
        verify_set={
            "sha256": hashlib.sha256(verify_bytes).hexdigest(),
            "designs": len(designs),
            "u": u,
        },
        input_order=names,
        predictions_sha256=hashlib.sha256(
            np.ascontiguousarray(predictions, dtype=spec.dtype).tobytes()
        ).hexdigest(),
        designs=results,
        aggregate=check.aggregate(results, u),
        local_timing=local_timing(
            built["model"], query, wide=built["wide"], calls=timing_calls
        ),
    )
    return report


# --- CLI --------------------------------------------------------------------------


def _read_submission(path):
    from carbon.level4 import staging

    _digest, raw_manifest, files = staging.read_directory(refuse_protected(path))
    return raw_manifest, files


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m carbon.challenge_kit.local_scorer")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("score", help="score a graph recipe on a verify set")
    run.add_argument("--recipe", required=True, help="the construction recipe JSON")
    run.add_argument(
        "--submission-dir",
        required=True,
        help="the lowered graph directory (manifest.json and <hex>.json documents)",
    )
    run.add_argument("--verify", required=True, help="the verify set JSON")
    run.add_argument(
        "--verify-sha256", required=True, help="the verify set's pinned sha256"
    )
    run.add_argument("--out", required=True, help="where to write the report JSON")
    run.add_argument(
        "--train",
        default=None,
        help="the kit's TRAIN file (default: the version's public TRAIN); "
        "refused unless byte-identical to it",
    )
    run.add_argument("--timing-calls", type=int, default=8)
    args = parser.parse_args(argv)
    try:
        out = refuse_protected(args.out)
        raw_manifest, files = _read_submission(args.submission_dir)
        report = score(
            refuse_protected(args.recipe).read_bytes(),
            raw_manifest,
            files,
            refuse_protected(args.verify).read_bytes(),
            args.verify_sha256,
            train_bytes=(
                None
                if args.train is None
                else refuse_protected(args.train).read_bytes()
            ),
            timing_calls=args.timing_calls,
        )
    except (ScorerRefused, OSError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    out.write_text(
        json.dumps(report, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    state = report["admission"]["state"]
    print(f"{state}: report written ({LABEL})")
    return 0 if state == "ADMITTED" else 3


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "HIDDEN",
    "NOT_EVALUATED",
    "ScorerRefused",
    "build_and_predict",
    "code_identity",
    "load_verify_set",
    "main",
    "score",
]
