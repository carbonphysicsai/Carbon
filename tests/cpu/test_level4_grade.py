"""Level 4 G7 grading (development only): `carbon.level4.grade`.

Claims tested:

1. A trained Level 0 graph (classic MLP and DeepONet), graded through G7 on
   battery's public PRACTICE set with battery's exam code unchanged, gets
   exactly the exam verdict the declarative path gets.
2. Inference cost is measured from the compiled graph and only recorded:
   the rule stays HUMAN_INPUT.
3. A graph emitting NaN on selected cases: G7 names exactly those cases, and
   the exam's own gates fail them (mandatory failure is never compensated).
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import grade, submission, tooling, train, validate

MAX_BYTES = 1 << 26  # the tests' parser bound; not a G3 limit


@pytest.fixture(scope="module")
def allowlist():
    return allowlist_module.load()


def _trained(allowlist, label, steps=16):
    from carbon.battery import level4 as battery

    strategy = battery._steps(battery.level0_strategies()[label], steps)
    manifest, files = battery.lower_recipe(strategy, allowlist, max_bytes=MAX_BYTES)
    _, parsed = submission.verify(
        submission.canonical(manifest),
        files,
        allowlist=allowlist,
        challenge=battery.challenge_id(),
        interface=battery.interface(strategy).digest(),
        max_bytes=MAX_BYTES,
    )
    verdict = validate.validate_submission(
        parsed,
        allowlist,
        interface=battery.interface(strategy),
        batch=battery.training_batch(strategy),
    )
    prepared = train.prepare(parsed, allowlist, verdict=verdict)
    result = train.train(battery, strategy, prepared, seed=7)
    return battery, strategy, prepared, result["params"]


@pytest.mark.parametrize("label", ["scaffold_mlp", "panel_deeponet"])
def test_g7_equals_the_declarative_exam_verdict(allowlist, label):
    import numpy as np

    from carbon.battery.domain import INPUTS
    from carbon.battery.practice import PracticeSet, score_practice
    from carbon.battery.recipes import to_predictions

    battery, strategy, prepared, params = _trained(allowlist, label)
    graded = grade.grade(battery, strategy, prepared, params, seed=7)

    m = battery.material()
    _, native = battery._model(strategy, m.train)
    native.fit(m.train, battery.structure(m), 7)
    practice = PracticeSet.load(battery.REPOSITORY)
    x = np.array([[r["inputs"][k] for k in INPUTS] for r in practice.records], float)
    _, summary = score_practice(
        to_predictions(native.predict(x), practice.case_ids),
        practice,
        m,
        battery.REPOSITORY,
    )
    assert json.dumps(graded["exam"], sort_keys=True, default=str) == json.dumps(
        summary, sort_keys=True, default=str
    )
    assert graded["nonfinite_cases"] == []
    cost = graded["inference_cost"]
    assert cost["flops_per_case"] > 0 and cost["batch"] == prepared.batch
    assert cost["rule"] == allowlist_module.HUMAN_INPUT


def test_nonfinite_cases_are_named_and_gated(allowlist):
    import jax.numpy as jnp
    import numpy as np

    battery, strategy, prepared, params = _trained(allowlist, "scaffold_mlp")
    net = battery.classic_net()
    pairs = [(params[i], params[i + 1]) for i in range(0, len(params), 2)]

    def poisoned(p, f):
        # NaN wherever the first (unit-scaled) input exceeds 0.8.
        return net(p, f) + jnp.where(f[:, :1] > 0.8, jnp.nan, 0.0)

    f = jnp.zeros((prepared.batch, pairs[0][0].shape[0]), jnp.float32)
    names = [f"params/{i}" for i in range(len(params))] + ["inputs/features"]
    rebuilt, _, _ = tooling.through_bprime(
        poisoned,
        (pairs, f),
        role="forward",
        allowlist=allowlist,
        input_names=names,
        max_bytes=MAX_BYTES,
    )
    bad = train.Prepared(
        init=prepared.init,
        apply=lambda p, *xs: rebuilt(*p, *xs),
        batch=prepared.batch,
        parameters=prepared.parameters,
    )
    graded = grade.grade(battery, strategy, bad, params, seed=7)
    exam = battery.grade_graph(strategy, bad, params, seed=7)
    expected = [
        c for c, x in zip(exam["case_ids"], np.asarray(exam["inputs"][0])) if x[0] > 0.8
    ]
    assert expected and graded["nonfinite_cases"] == expected
    assert graded["exam"]["n_gate_failed"] == len(expected)
