"""A JAX product may carry its trained arrays as parameters, like the Torch path.

The closed form stays capped (graph constants); a realistic model passes as state.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("jax")

import test_direct_clean_rebuild_acceptance as acceptance
import test_motor_normal_construction as motor

from carbon.challenge_kit import physical_material
from carbon.development_session.bundle_construction_worker import (
    infer_public,
    native_build_predictions,
    reconstruct_public,
)
from carbon.development_session.research_ledger import CampaignLedger

SOURCE = (
    "import numpy as np\n"
    "import jax.numpy as jnp\n"
    "def build(train_inputs, train_targets, *, seed, configuration, train_use):\n"
    "    x = np.asarray(train_inputs, float)\n"
    "    y = np.asarray(train_targets, float)\n"
    "    mu, sd = x.mean(axis=0), x.std(axis=0) + 1e-9\n"
    "    z = (x - mu) / sd\n"
    "    rng = np.random.default_rng(seed)\n"
    "    w1 = rng.normal(size=(z.shape[1], 128))\n"
    "    b1 = rng.normal(size=(128,))\n"
    "    h = np.tanh(z @ w1 + b1)\n"
    "    h1 = np.concatenate([h, np.ones((len(h), 1))], axis=1)\n"
    "    w2 = np.linalg.lstsq(h1, y, rcond=None)[0]\n"
    "    parameters = [jnp.asarray(w1), jnp.asarray(b1), jnp.asarray(w2),\n"
    "                  jnp.asarray(mu), jnp.asarray(sd)]\n"
    "    def apply(params, x):\n"
    "        w1, b1, w2, mu, sd = params\n"
    "        h = jnp.tanh(((x - mu) / sd) @ w1 + b1)\n"
    "        h1 = jnp.concatenate([h, jnp.ones((h.shape[0], 1), h.dtype)], axis=1)\n"
    "        return h1 @ w2\n"
    "    return {'framework': 'jax', 'apply': apply, 'parameters': parameters}\n"
)


@motor.CHALLENGES
def test_a_realistic_jax_model_freezes_as_state_and_infers(
    tmp_path, monkeypatch, challenge_id, version
):
    monkeypatch.setattr(acceptance, "SOURCE", SOURCE)
    material = physical_material.bundle_material(challenge_id, version)
    image, installed = acceptance._source_bundle(tmp_path)
    recipe = acceptance._recipe(material, image)
    runner = acceptance.LocalProcessRunner(installed)
    ledger = CampaignLedger(tmp_path / "campaign")
    built = reconstruct_public(
        ledger,
        owner="miner",
        identity="jax-parameters-build",
        image=image,
        recipe=recipe,
        challenge_binding=acceptance._binding(material),
        train=material["train"],
        example=material["example"],
        seed=11,
        allowlist_bytes=material["allowlist_bytes"],
        runner=runner,
    )
    inferred = infer_public(
        ledger,
        owner="miner",
        identity="jax-parameters-inference",
        image=image,
        inference_image=image.parent,
        recipe=recipe,
        challenge_binding=acceptance._binding(material),
        build=built,
        inputs=material["practice_inputs"],
        expected_output_shape=material["expected_output_shape"],
        allowlist_bytes=material["allowlist_bytes"],
        expected_output_dtype="float64",
        runner=runner,
    )
    predictions = np.asarray(inferred.predictions, dtype=np.float64)
    assert predictions.shape == material["practice_reference"].shape
    assert np.isfinite(predictions).all()
    # The frozen graph and the native build agree on the public probe.
    native = native_build_predictions(built)
    np.testing.assert_allclose(predictions, native, rtol=1e-6, atol=1e-6)
