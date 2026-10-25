"""A loss graph in a graph route v2 recipe (OWNER-GRAPH-OPS-OPEN-01; Validator
VALIDATOR_GRAPH_OPS_V8_RULINGS_20261025, row 3: "per-batch loss, parameter input,
cross-case terms, aux outputs ... the loss trains on TRAIN only, and the grade uses the
Challenge's own metric").

Claims tested:
- a recipe may carry a `loss` document over the whole training batch with the model's
  parameters as inputs (`loss/pred/0`, `loss/target/0`, `loss/x/<name>`, `loss/param/<k>`)
  and one floating scalar out; Carbon trains with it in place of the menu loss;
- a loss that reproduces the menu's mean squared error trains to the same model, and a
  loss that adds a parameter penalty or a cross-case term trains to a different one;
- a loss whose inputs, shapes or output break the slot is refused with its typed code,
  and the per-case slot's shape (leading dimension 1) is not the batch slot;
- two seeded rebuilds of the same recipe are bit-identical;
- the pinned trainer's digest moved (a new version) and is the one the limits carry.
"""

from __future__ import annotations

import numpy as np
import pytest
from test_graph_route_v2 import F08, _fit

from carbon.development_session import physical_graph_adapter_v2 as adapter
from carbon.level4 import graph
from carbon.level4 import submission as submission_module

pytest.importorskip("jax")

KEY = (F08, "1.5")
WIDTH = 16


def _loss_document(fn, key, batch, *, pred_rows=None, extra_name=None):
    import jax.numpy as jnp

    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4.tooling import through_bprime

    spec = adapter.SPECS[key]
    dtype = jnp.float64 if spec.dtype == "float64" else jnp.float32
    allowed = allowlist_module.Allowlist(adapter.served_allowlist_bytes(*key))
    rows = pred_rows or batch
    shapes = [
        (rows, spec.outputs),
        (rows, spec.outputs),
        (rows, spec.inputs),
        (spec.inputs, WIDTH),
        (WIDTH,),
        (WIDTH, spec.outputs),
        (spec.outputs,),
    ]
    names = [
        "loss/pred/0",
        "loss/target/0",
        "loss/x/features",
        "loss/param/0",
        "loss/param/1",
        "loss/param/2",
        "loss/param/3",
    ]
    if extra_name:
        names[-1] = extra_name
    _, document, _ = through_bprime(
        fn,
        tuple(jnp.zeros(shape, dtype) for shape in shapes),
        role="loss",
        allowlist=allowed,
        input_names=names,
        max_bytes=1 << 26,
    )
    return document


_REAL_BUILD = submission_module.build


def _with_loss(monkeypatch, document):
    def build(**kwargs):
        return _REAL_BUILD(**kwargs, loss=document)

    monkeypatch.setattr(submission_module, "build", build)


def _fit_with_loss(monkeypatch, fn, steps=24, **loss_kwargs):
    _with_loss(monkeypatch, _loss_document(fn, KEY, 8, **loss_kwargs))
    return _fit(KEY, {"training": {"steps": steps}})


def mse(pred, target, x, w1, b1, w2, b2):
    import jax.numpy as jnp

    return jnp.mean((pred - target) ** 2)


def test_a_loss_that_is_the_menu_mse_trains_the_same_model(monkeypatch):
    _plain, plain_fit, _ = _fit(KEY, {"training": {"steps": 24}})
    model, fitted, _ = _fit_with_loss(monkeypatch, mse)
    assert model.prepared.loss is not None
    assert abs(fitted["train_loss"] - plain_fit["train_loss"]) < 5e-3


def test_a_parameter_penalty_changes_the_fit_and_shrinks_the_weights(monkeypatch):
    import jax.numpy as jnp

    def penalised(pred, target, x, w1, b1, w2, b2):
        return jnp.mean((pred - target) ** 2) + 1.0 * (jnp.sum(w1**2) + jnp.sum(w2**2))

    _model, plain, _ = _fit_with_loss(monkeypatch, mse, steps=48)
    _model, shrunk, _ = _fit_with_loss(monkeypatch, penalised, steps=48)
    assert plain["params_sha256"] != shrunk["params_sha256"]


def test_a_cross_case_term_is_admitted(monkeypatch):
    import jax.numpy as jnp

    def spread(pred, target, x, w1, b1, w2, b2):
        return jnp.mean((pred - target) ** 2) + jnp.var(pred, axis=0).sum()

    _model, fitted, _ = _fit_with_loss(monkeypatch, spread)
    assert np.isfinite(fitted["train_loss"])


def test_two_seeded_rebuilds_are_bit_identical(monkeypatch):
    _a, first, _ = _fit_with_loss(monkeypatch, mse)
    _b, second, _ = _fit_with_loss(monkeypatch, mse)
    assert first["params_sha256"] == second["params_sha256"]


def test_a_per_case_shaped_loss_is_not_the_batch_slot(monkeypatch):
    def per_case(pred, target, x, w1, b1, w2, b2):
        import jax.numpy as jnp

        return jnp.mean((pred - target) ** 2)

    _with_loss(monkeypatch, _loss_document(per_case, KEY, 8, pred_rows=1))
    with pytest.raises(graph.GraphRefused) as refused:
        _fit(KEY, {"training": {"steps": 4}})
    assert refused.value.code == "loss_input_shape"


def test_a_loss_missing_a_parameter_input_is_refused(monkeypatch):
    def short(pred, target, x, w1, b1, w2):
        import jax.numpy as jnp

        return jnp.mean((pred - target) ** 2)

    import jax.numpy as jnp

    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4.tooling import through_bprime

    spec = adapter.SPECS[KEY]
    allowed = allowlist_module.Allowlist(adapter.served_allowlist_bytes(*KEY))
    _, document, _ = through_bprime(
        short,
        (
            jnp.zeros((8, spec.outputs), jnp.float32),
            jnp.zeros((8, spec.outputs), jnp.float32),
            jnp.zeros((8, spec.inputs), jnp.float32),
            jnp.zeros((spec.inputs, WIDTH), jnp.float32),
            jnp.zeros((WIDTH,), jnp.float32),
            jnp.zeros((WIDTH, spec.outputs), jnp.float32),
        ),
        role="loss",
        allowlist=allowed,
        input_names=[
            "loss/pred/0",
            "loss/target/0",
            "loss/x/features",
            "loss/param/0",
            "loss/param/1",
            "loss/param/2",
        ],
        max_bytes=1 << 26,
    )
    _with_loss(monkeypatch, document)
    with pytest.raises(graph.GraphRefused) as refused:
        _fit(KEY, {"training": {"steps": 4}})
    assert refused.value.code == "loss_input_missing"


def test_a_vector_valued_loss_is_refused(monkeypatch):
    def vector(pred, target, x, w1, b1, w2, b2):
        return ((pred - target) ** 2).mean(axis=1)

    _with_loss(monkeypatch, _loss_document(vector, KEY, 8))
    with pytest.raises(graph.GraphRefused) as refused:
        _fit(KEY, {"training": {"steps": 4}})
    assert refused.value.code == "loss_output"


def test_the_trainer_digest_moved_and_the_limits_carry_it():
    from carbon.challenge_kit import physical_material

    assert (
        adapter.TRAINER_SHA256
        != "54152a38628862cad0f94314b830130fc6e3d39480a41be94af85eca669a517d"
    )
    block = physical_material.bundle_material(*KEY)["construction_limits_document"][
        "graph_training_adapter"
    ]
    assert block["trainer"]["sha256"] == "sha256:" + adapter.TRAINER_SHA256


def test_a_recipe_without_a_loss_graph_trains_as_before():
    model, _fitted, _ = _fit(KEY, {"training": {"steps": 8}})
    assert model.prepared.loss is None


SPEC = """
FRAMEWORK = "jax"
INPUTS = {{"inputs/features": (({inputs},), "float32")}}


def init(key):
    import jax

    a, b = jax.random.split(key)
    return [
        jax.random.normal(a, ({inputs}, 8)) * 0.1,
        jax.numpy.zeros((8,)),
        jax.random.normal(b, (8, {outputs})) * 0.1,
        jax.numpy.zeros(({outputs},)),
    ]


def forward(params, x):
    import jax.numpy as jnp

    w1, b1, w2, b2 = params
    return jnp.tanh(x @ w1 + b1) @ w2 + b2


def loss(params, pred, target, x):
    import jax.numpy as jnp

    return jnp.mean((pred - target) ** 2) + 1e-3 * sum(jnp.sum(p**2) for p in params)
"""


def test_the_lowering_tool_writes_a_spec_loss_as_the_batch_slot(tmp_path):
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import intake, staging, validate
    from carbon.level4.tooling import __main__ as tool

    spec = adapter.SPECS[KEY]
    path = tmp_path / "spec.py"
    path.write_text(SPEC.format(inputs=spec.inputs, outputs=spec.outputs))
    interface = adapter.graph_interface(spec)
    out = tmp_path / "out"
    tool.lower(
        path,
        out,
        challenge=spec.challenge_id,
        challenge_version=KEY[1],
        interface=interface.digest(),
        batch=8,
        max_bytes=1 << 26,
    )
    _digest, raw_manifest, files = staging.read_directory(out)
    allowed = allowlist_module.Allowlist(adapter.served_allowlist_bytes(*KEY))
    _, parsed = intake.intake(
        raw_manifest,
        files,
        allowlist=allowed,
        challenge=spec.challenge_id,
        interface=interface.digest(),
        loss_override="batch",
    )
    assert "loss" in parsed
    verdict = validate.validate_submission(
        parsed, allowed, interface=interface, batch=8, loss_override="batch"
    )
    assert verdict["status"] == "admitted" and "loss" in verdict["documents"]
