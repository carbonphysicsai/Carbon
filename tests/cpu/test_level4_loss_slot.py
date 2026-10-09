"""The G6 loss slot v1 working contract (PHASE1_PLAN.md section 4.5): fixtures.

Claims tested:

1. The Level 1 gate: a loss document is refused (`loss_not_permitted`) unless
   the Challenge declares `loss_override: graph`; `none`, `terms`, unset and
   unknown declarations permit nothing. At G0 and at G4, never ignored.
2. The slot: a valid per-case loss takes exactly `loss/pred/*`,
   `loss/target/*`, `loss/x/*` (per case, leading dimension 1) and returns
   one float `[1]`. Each fixture violation has its typed code: a parameter
   input, a missing or reordered input, a batch-declared input, a scalar or
   second output.
3. `aux`: a forward graph's extra outputs are refused while the limit is
   HUMAN_INPUT, and read per case when a limit admits them.
4. Carbon's reduction: `per_case_mean` maps the per-case graph over the
   batch and takes the mean, equal to the mean of each case alone.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret, submission, validate
from carbon.level4 import loss as loss_slot
from carbon.level4.tooling import through_bprime

MAX_BYTES = 1 << 24
INTERFACE = validate.Interface(
    inputs=(("inputs/x", "float32", (3,)),), outputs=(("float32", (2,)),)
)
NAMES = ["loss/pred/0", "loss/target/0", "loss/x/x"]


@pytest.fixture(scope="module")
def allowlist():
    return allowlist_module.load()


def _lower(fn, shapes, names, allowlist, role="loss"):
    import jax
    import jax.numpy as jnp

    args = [jax.ShapeDtypeStruct(s, jnp.float32) for s in shapes]
    _, doc, _ = through_bprime(
        fn, tuple(args), role=role, allowlist=allowlist, input_names=names,
        max_bytes=MAX_BYTES,
    )  # fmt: skip
    return doc


def _mse(pred, target, x):
    import jax.numpy as jnp

    del x
    return jnp.sum((pred - target) ** 2, axis=1)


PER_CASE = [(1, 2), (1, 2), (1, 3)]


@pytest.fixture(scope="module")
def valid(allowlist):
    return _lower(_mse, PER_CASE, NAMES, allowlist)


def test_the_gate_admits_a_loss_only_under_graph(valid):
    loss_slot.gate({"forward": {}}, None)  # no loss document: nothing to gate
    for declared in (None, "none", "terms", "HUMAN_INPUT", "everything"):
        with pytest.raises(graph.GraphRefused) as refused:
            loss_slot.gate({"loss": valid}, declared)
        assert refused.value.code == "loss_not_permitted"
    loss_slot.gate({"loss": valid}, "graph")


def test_a_valid_per_case_loss_fits_the_slot(valid):
    loss_slot.check(valid, INTERFACE)
    assert [n for n, _, _ in loss_slot.expected_inputs(INTERFACE)] == NAMES


@pytest.mark.parametrize(
    ("label", "fn", "shapes", "names", "code"),
    [
        (
            "a parameter input",
            lambda p, t, x, w: _mse(p, t, x) * w[0, 0],
            [*PER_CASE, (1, 1)],
            [*NAMES, "params/0"],
            "loss_input_unexpected",
        ),
        (
            "an input missing",
            lambda p, t: _mse(p, t, None),
            PER_CASE[:2],
            NAMES[:2],
            "loss_input_missing",
        ),
        (
            "inputs reordered",
            lambda t, p, x: _mse(p, t, x),
            PER_CASE,
            [NAMES[1], NAMES[0], NAMES[2]],
            "loss_input_missing",
        ),
        (
            "declared at a batch, not per case",
            _mse,
            [(4, 2), (4, 2), (4, 3)],
            NAMES,
            "loss_input_shape",
        ),
        (
            "a scalar, not the case's loss",
            lambda p, t, x: _mse(p, t, x).sum(),
            PER_CASE,
            NAMES,
            "loss_output",
        ),
        (
            "two outputs",
            lambda p, t, x: (_mse(p, t, x), _mse(p, t, x)),
            PER_CASE,
            NAMES,
            "loss_output",
        ),
    ],
)
def test_each_fixture_violation_is_refused_by_code(
    allowlist, label, fn, shapes, names, code
):
    doc = _lower(fn, shapes, names, allowlist)
    with pytest.raises(graph.GraphRefused) as refused:
        loss_slot.check(doc, INTERFACE)
    assert refused.value.code == code, label


def _forward(allowlist, extra_output=False):
    import jax.numpy as jnp

    def forward(w, x):
        out = jnp.tanh(x @ w)
        return (out, out.sum(axis=1, keepdims=True)) if extra_output else out

    return _lower(
        forward, [(3, 2), (4, 3)], ["params/0", "inputs/x"], allowlist, "forward"
    )


def test_aux_outputs_wait_for_their_limit(allowlist):
    plain = _forward(allowlist)
    assert loss_slot.aux_outputs(plain, INTERFACE) == []
    widened = _forward(allowlist, extra_output=True)
    with pytest.raises(graph.GraphRefused) as refused:
        loss_slot.aux_outputs(widened, INTERFACE)
    assert refused.value.code == "loss_aux_not_admitted"
    assert loss_slot.aux_outputs(widened, INTERFACE, aux_limit=1) == [("float32", (1,))]


def test_carbon_owns_the_mean_over_cases(allowlist, valid):
    import jax
    import numpy as np

    rebuilt = interpret.rebuild(valid, allowlist)
    loss = loss_slot.per_case_mean(rebuilt)
    pred, target, x = (
        jax.random.normal(jax.random.PRNGKey(k), s, "float32")
        for k, s in enumerate([(5, 2), (5, 2), (5, 3)])
    )
    each = [
        float(rebuilt(pred[i : i + 1], target[i : i + 1], x[i : i + 1])[0][0])
        for i in range(5)
    ]
    assert np.isclose(float(loss([pred], [target], [x])), np.mean(each), rtol=1e-6)
    grads = jax.grad(lambda p: loss([p], [target], [x]))(pred)
    assert grads.shape == pred.shape


def test_the_gate_holds_at_g0_and_g4(allowlist, valid):
    import jax

    def init(key):
        return [jax.random.normal(key, (3, 2))]

    _, ini, _ = through_bprime(
        init, (jax.random.PRNGKey(0),), role="init", allowlist=allowlist,
        input_names=["carbon/key"], max_bytes=MAX_BYTES,
    )  # fmt: skip
    manifest, files = submission.build(
        challenge="example",
        interface=INTERFACE.digest(),
        allowlist=allowlist,
        forward=_forward(allowlist),
        init=ini,
        loss=valid,
    )
    _, parsed = submission.verify(
        submission.canonical(manifest),
        files,
        allowlist=allowlist,
        challenge="example",
        interface=INTERFACE.digest(),
        max_bytes=MAX_BYTES,
    )
    for declared in (None, "terms"):
        with pytest.raises(graph.GraphRefused) as refused:
            validate.validate_submission(
                parsed, allowlist, interface=INTERFACE, loss_override=declared
            )
        assert refused.value.code == "loss_not_permitted"
    verdict = validate.validate_submission(
        parsed, allowlist, interface=INTERFACE, loss_override="graph"
    )
    assert set(verdict["documents"]) == {"forward", "init", "loss"}
    from carbon.level4 import intake

    with pytest.raises(graph.GraphRefused) as refused:
        intake.intake(
            submission.canonical(manifest),
            files,
            allowlist=allowlist,
            challenge="example",
            interface=INTERFACE.digest(),
            isolate=False,
        )
    assert refused.value.code == "loss_not_permitted"
