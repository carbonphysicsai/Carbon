"""Motor's Level 4 adapter (development only; public data only).

E6 in `docs/development/graphite/level4/PHASE1_PLAN.md`: a second Challenge
through `carbon.level4`, unchanged, with only this adapter.

Motor has no gradient-trained family: its Level 0 model is the closed-form
kernel ridge fit of `carbon.learned_baseline` on public TRAIN. Here that
model's prediction is lowered to a Level 4 graph. Its parameters (the scaled
TRAIN inputs, the ridge solution and the target scaling) are what Carbon's
own fit supplies at G6 (`train_graph`); the init spec declares zeros, which
the fit replaces. G7 grades through motor's own practice exam, unchanged.
Gradient training for a second Challenge needs a trainable family there
first; that is recorded in the plan, not done here.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
#: The batch this adapter lowers at in development: smaller than PRACTICE's
#: 30 cases, so grading exercises padded inference. Not a Challenge value.
BATCH = 16


def challenge_id():
    from .challenge import CHALLENGE

    return CHALLENGE.challenge_id


def level0_strategy():
    import json

    from .research import SCAFFOLD

    return json.loads(json.dumps(SCAFFOLD))


def material():
    from .challenge import PublicMaterial

    return PublicMaterial.load(REPOSITORY)


def _recipe(strategy_):
    from .compile import compile_recipe

    return compile_recipe(strategy_)[1]


def interface(strategy_=None):
    """Scaled inputs in, the torque curve out, both float64 per case."""
    del strategy_
    from ..level4.validate import Interface
    from .domain import ANGLE_STEPS, INPUTS

    return Interface(
        inputs=(("inputs/x", "float64", (len(INPUTS),)),),
        outputs=(("float64", (ANGLE_STEPS,)),),
    )


def _scaled(records):
    from carbon import learned_baseline

    from .domain import INPUT_BOUNDS, INPUTS

    return learned_baseline.scale([r["inputs"] for r in records], INPUTS, INPUT_BOUNDS)


def _fit(recipe, m):
    """Carbon's closed-form fit: `[x_train, alpha, mean, std]`."""
    from .recipes import build

    ridge = build(recipe.family, recipe.settings, m.train)._model
    return [ridge.x, ridge.alpha, ridge.mean, ridge.std]


def forward_fn(length):
    """The kernel ridge prediction with motor's mean correction, in JAX."""
    import jax.numpy as jnp

    def forward(p, x):
        x_train, alpha, mean, std = p
        squared = (
            (x**2).sum(1)[:, None] + (x_train**2).sum(1)[None, :] - 2 * x @ x_train.T
        )
        k = jnp.exp(-jnp.maximum(squared, 0.0) / (2 * length**2))
        curve = k @ alpha * std + mean
        offset = curve.mean(1, keepdims=True)
        return curve - jnp.where(offset < 0, offset, 0.0)

    return forward


def lower_recipe(strategy_, allowlist, *, max_bytes, batch=BATCH):
    """Miner side: the recipe's prediction as a Level 4 submission."""
    import jax

    from ..level4 import graph, initializers, submission, tooling

    recipe = _recipe(strategy_)
    m = material()
    with jax.enable_x64(True):
        shapes = [jax.ShapeDtypeStruct(a.shape, "float64") for a in _fit(recipe, m)]
        x = jax.ShapeDtypeStruct((batch, shapes[0].shape[1]), "float64")
        names = [f"params/{i}" for i in range(len(shapes))] + ["inputs/x"]
        _, forward, _ = tooling.through_bprime(
            forward_fn(recipe.settings["length"]),
            (shapes, x),
            role="forward",
            allowlist=allowlist,
            input_names=names,
            max_bytes=max_bytes,
        )
    spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(forward),
        "parameters": [
            {"input": n, "initializer": "zeros", "fan_in_axes": [], "fan_out_axes": []}
            for n in names[:-1]
        ],
    }
    return submission.build(
        challenge=challenge_id(),
        interface=interface().digest(),
        allowlist=allowlist,
        forward=forward,
        init_spec=spec,
    )


def train_graph(strategy_, prepared, *, seed):
    """G6 for motor: Carbon's closed-form fit, shaped as the graph declares."""
    del seed  # the fit is deterministic
    import numpy as np

    params = [
        np.asarray(a, dtype=np.float64) for a in _fit(_recipe(strategy_), material())
    ]
    declared = [(d, list(s)) for _, d, s in prepared.parameters]
    if [("float64", list(a.shape)) for a in params] != declared:
        raise ValueError("the graph's parameters are not the closed-form fit's")
    blob = b"".join(a.tobytes() for a in params)
    return {
        "path": "closed_form",
        "params": params,
        "params_sha256": hashlib.sha256(blob).hexdigest(),
    }


def grade_graph(strategy_, prepared, params, *, seed):
    """G7's exam for motor: the graph predicts public PRACTICE and motor's
    exam code, unchanged (`practice.score_practice`), scores it."""
    del strategy_, seed
    import jax
    import numpy as np

    from .practice import PracticeSet, score_practice

    m = material()
    practice = PracticeSet.load(REPOSITORY)
    x = _scaled(practice.records)
    with jax.enable_x64(True):
        curves = np.asarray(prepared.predict(list(params), x)[0])
    predictions = {
        cid: {"torque_nm": [float(v) for v in curve]}
        for cid, curve in zip(practice.case_ids, curves)
    }
    rows, summary = score_practice(predictions, practice, m)
    return {
        "summary": summary,
        "rows": rows,
        "outputs": [curves],
        "inputs": [x],
        "case_ids": practice.case_ids,
    }


def graph_equivalence(allowlist, strategy_=None, *, max_bytes):
    """E6: motor's Level 0 recipe, native against the Level 4 graph path
    (verify, G4, Carbon's fit at G6, G7 through motor's practice exam)."""
    import jax
    import numpy as np

    from ..level4 import grade, submission, train, validate
    from .compile import rebuild
    from .practice import PracticeSet, score_practice

    s = strategy_ or level0_strategy()
    recipe = _recipe(s)
    m = material()
    practice = PracticeSet.load(REPOSITORY)
    native_model = rebuild(recipe, m, root=REPOSITORY)
    native = {
        cid: native_model.predict(r["inputs"])
        for cid, r in zip(practice.case_ids, practice.records)
    }
    native_rows, native_summary = score_practice(native, practice, m)
    manifest, files = lower_recipe(s, allowlist, max_bytes=max_bytes)
    _, parsed = submission.verify(
        submission.canonical(manifest),
        files,
        allowlist=allowlist,
        challenge=challenge_id(),
        interface=interface().digest(),
        max_bytes=max_bytes,
    )
    verdict = validate.validate_submission(
        parsed, allowlist, interface=interface(), batch=BATCH
    )
    with jax.enable_x64(True):
        prepared = train.prepare(parsed, allowlist, verdict=verdict)
        trained = train.train(sys.modules[__name__], s, prepared, seed=0)
        graded = grade.grade(
            sys.modules[__name__], s, prepared, trained["params"], seed=0
        )
    exam = grade_graph(s, prepared, trained["params"], seed=0)
    native_curves = np.asarray([native[c]["torque_nm"] for c in practice.case_ids])
    return {
        "status": verdict["status"],
        "batch": verdict["batch"],
        "submission": submission.digest(manifest),
        "max_abs_prediction_difference": float(
            np.max(np.abs(exam["outputs"][0] - native_curves))
        ),
        "predictions_identical": bool(
            np.array_equal(exam["outputs"][0], native_curves)
        ),
        "exam_identical": graded["exam"] == native_summary,
        "case_states_identical": [r.get("state") for r in exam["rows"]]
        == [r.get("state") for r in native_rows],
        "score_difference": abs(graded["exam"]["score"] - native_summary["score"]),
        "graph_exam": graded["exam"],
        "native_exam": native_summary,
        "nonfinite_cases": graded["nonfinite_cases"],
        "inference_cost": graded["inference_cost"],
    }
