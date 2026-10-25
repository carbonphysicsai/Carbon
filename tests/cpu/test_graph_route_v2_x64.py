"""A graph may compute in float64 whatever the Challenge's interface dtype
(OWNER-GRAPH-OPS-OPEN-01, Validator row 7): the build runs with JAX's 64-bit mode on
whenever the submitted graph holds a 64-bit value, and TRAIN, the decoder, the
parameters and the outputs stay in the interface dtype (float32 on F08 1.5 and F02 2.4,
float64 on Motor 1.4 and Cooling 1.4). Before this, a float64 cast inside an F08/F02
graph came out float32 and the declared dtype disagreed.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from test_graph_route_v2 import F08, _recipe

jax = pytest.importorskip("jax")

import jax.numpy as jnp

from carbon.development_session import (
    direct_graph_construction_worker,
    physical_graph_adapter_v2 as adapter,
    physical_graph_state_v2,
)
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, initializers, intake, staging, submission
from carbon.level4.tooling import through_bprime
from carbon.challenge_kit import physical_material
from carbon.development_session.profile import canonical

KEY = (F08, "1.5")  # a float32 interface


def _wide_graph(batch=8):
    """A tanh MLP that computes in float64 inside and returns float32."""
    spec = adapter.SPECS[KEY]
    allowed = allowlist_module.Allowlist(adapter.served_allowlist_bytes(*KEY))
    width = 16
    f32 = jnp.float32

    def forward(w1, b1, w2, b2, x):
        wide = lambda a: a.astype(jnp.float64)  # noqa: E731
        hidden = jnp.tanh(wide(x) @ wide(w1) + wide(b1))
        return (hidden @ wide(w2) + wide(b2)).astype(f32)

    with jax.enable_x64(True):
        _, document, _ = through_bprime(
            forward,
            (
                jnp.zeros((spec.inputs, width), f32),
                jnp.zeros((width,), f32),
                jnp.zeros((width, spec.outputs), f32),
                jnp.zeros((spec.outputs,), f32),
                jnp.ones((batch, spec.inputs), f32),
            ),
            role="forward",
            allowlist=allowed,
            input_names=["params/0", "params/1", "params/2", "params/3", adapter.INPUT_NAME],
            max_bytes=intake.BOUNDS["document_bytes"],
        )

    def parameter(index, initializer, axes):
        return {
            "input": f"params/{index}",
            "initializer": initializer,
            "fan_in_axes": axes[0],
            "fan_out_axes": axes[1],
        }

    init_spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(document),
        "parameters": [
            parameter(0, "glorot_normal", ([0], [1])),
            parameter(1, "zeros", ([], [])),
            parameter(2, "glorot_normal", ([0], [1])),
            parameter(3, "zeros", ([], [])),
        ],
    }
    manifest, files = submission.build(
        challenge=spec.challenge_id,
        interface=adapter.graph_interface(spec).digest(),
        allowlist=allowed,
        forward=document,
        init_spec=init_spec,
    )
    return document, submission.canonical(manifest), files, submission.digest(manifest)


def test_the_wide_graph_really_holds_a_64_bit_value():
    document, *_ = _wide_graph()
    dtypes = {
        out["dtype"]
        for g in document["graphs"].values()
        for node in g["nodes"]
        for out in node["out"]
    }
    assert "float64" in dtypes and "float32" in dtypes


def test_the_envelope_scan_finds_a_64_bit_value_and_only_then():
    _, raw_manifest, files, _ = _wide_graph()
    envelope = canonical(
        staging.envelope(raw_manifest, files)
    )
    assert direct_graph_construction_worker._envelope_has_wide_values(envelope)

    spec = adapter.SPECS[KEY]
    allowed = allowlist_module.Allowlist(adapter.served_allowlist_bytes(*KEY))
    f32 = jnp.float32
    _, narrow, _ = through_bprime(
        lambda w, x: x @ w,
        (jnp.zeros((spec.inputs, spec.outputs), f32), jnp.ones((4, spec.inputs), f32)),
        role="forward",
        allowlist=allowed,
        input_names=["params/0", adapter.INPUT_NAME],
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    manifest, plain = submission.build(
        challenge=spec.challenge_id,
        interface=adapter.graph_interface(spec).digest(),
        allowlist=allowed,
        forward=narrow,
        init_spec={
            "schema": initializers.SCHEMA,
            "graph": graph.digest(narrow),
            "parameters": [
                {
                    "input": "params/0",
                    "initializer": "glorot_normal",
                    "fan_in_axes": [0],
                    "fan_out_axes": [1],
                }
            ],
        },
    )
    assert not direct_graph_construction_worker._envelope_has_wide_values(
        canonical(
            staging.envelope(submission.canonical(manifest), plain)
        )
    )


def test_a_float64_graph_trains_on_a_float32_interface_and_keeps_the_interface_dtype():
    """The pin: with 64-bit mode on, TRAIN, the standardisation, the decoder and every
    parameter the build freezes are still float32, and so is the prediction."""
    _, raw_manifest, files, submission_digest = _wide_graph()
    recipe = _recipe(KEY, {"training": {"steps": 6}}, digest=submission_digest)
    raw = physical_material.bundle_material(*KEY)["train"]
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        inputs, targets = archive["inputs"].copy(), archive["targets"].copy()
    assert inputs.dtype == np.float32 and targets.dtype == np.float32
    allowed_bytes = adapter.served_allowlist_bytes(*KEY)
    with jax.enable_x64(True):
        model = adapter.build_validated_graph(
            recipe,
            raw_manifest,
            files,
            allowlist_bytes=allowed_bytes,
            train_cases=adapter.SPECS[KEY].rows,
        )
        fit = model.fit(inputs, targets, seed=0)
        state = model.frozen_state()
        _doc, members, mu, sd, combine = physical_graph_state_v2.load(
            state, recipe, allowlist_module.Allowlist(allowed_bytes)
        )
    assert np.isfinite(fit["train_loss"])
    assert mu.dtype == np.float32 and sd.dtype == np.float32
    assert all(np.asarray(p).dtype == np.float32 for m in members for p in m)
    assert combine.dtype == np.float32
