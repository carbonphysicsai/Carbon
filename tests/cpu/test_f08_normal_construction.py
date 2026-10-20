"""F08 through the normal construction path (DEVELOPMENT, public material only).

The receiver registers `f08-ribbed-bracket` like Motor and Cooling, with its own
255-row float32 TRAIN, six-field geometry input and seven learned outputs. Claims:

1. Discovery accepts the public material (fixed TRAIN, interface, limits, physics
   contract, the eight accepted development geometries as the practice query).
2. The served recipe contract is registered.
3. A recipe is rebuilt fresh from the fixed TRAIN in a separate process, frozen and
   run source-free on the development bank's query; the output has F08's width and
   float32 dtype.

No score, qualification or LIVE claim: fixed programs run in local processes.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

pytest.importorskip("jax")

import test_direct_clean_rebuild_acceptance as acceptance

from carbon.challenge_kit import physical_material
from carbon.challenge_kit.interface_dtype import output_dtype
from carbon.development_session.bundle_construction_worker import (
    infer_public,
    reconstruct_public,
)
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.reconstruction import served_recipe_contract

F08 = ("f08-ribbed-bracket", "1.0")

SOURCE = (
    "import numpy as np\n"
    "import jax.numpy as jnp\n"
    "def build(train_inputs, train_targets, *, seed, configuration, train_use):\n"
    "    x = np.asarray(train_inputs, np.float64)\n"
    "    y = np.asarray(train_targets, np.float64)\n"
    "    mu, sd = x.mean(axis=0), x.std(axis=0) + 1e-9\n"
    "    z = np.concatenate([(x - mu) / sd, np.ones((len(x), 1))], axis=1)\n"
    "    w = np.linalg.lstsq(z, y, rcond=None)[0]\n"
    "    wj, mj, sj = (jnp.asarray(a, jnp.float32) for a in (w, mu, sd))\n"
    "    def apply(x):\n"
    "        z = (x - mj) / sj\n"
    "        one = jnp.ones((z.shape[0], 1), z.dtype)\n"
    "        return jnp.concatenate([z, one], axis=1) @ wj\n"
    "    return {'framework': 'jax', 'apply': apply, 'parameters': []}\n"
)


def test_the_material_is_f08s_own_float32_interface():
    material = physical_material.bundle_material(*F08)
    assert material["practice_inputs"].shape == (8, 6)
    assert material["practice_reference"].shape == (8, 7)
    assert material["practice_inputs"].dtype == np.float32
    assert material["practice_reference"].dtype == np.float32
    assert output_dtype(material["interface_document"]) == "<f4"
    assert material["disclosure"]["scope"] == "PUBLIC_F08_DEVELOPMENT_ONLY"
    assert material["disclosure"]["hidden_evaluation"] is False


def test_receiver_discovery_accepts_the_public_material():
    material = physical_material.bundle_material(*F08)
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    assert discovery.info.challenge_key.challenge_id == F08[0]


def test_changed_material_is_refused_by_discovery():
    material = physical_material.bundle_material(*F08)
    material["practice_inputs"] = material["practice_inputs"] + np.float32(1.0)
    with pytest.raises(ValueError):
        DirectFixtureDiscovery(material, task_admission=True)


def test_a_float64_practice_query_is_refused_for_f08():
    material = physical_material.bundle_material(*F08)
    material["practice_inputs"] = material["practice_inputs"].astype(np.float64)
    with pytest.raises(ValueError):
        DirectFixtureDiscovery(material, task_admission=True)


def test_the_served_contract_is_registered():
    contract = served_recipe_contract.registered(*F08)
    assert contract.evidence_label == "DEVELOPMENT_PUBLIC_PHYSICAL"
    assert (
        contract.construction_kit
        == physical_material.bundle_material(*F08)["construction_kit"]
    )


def test_fresh_rebuild_then_source_free_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, "SOURCE", SOURCE)
    material = physical_material.bundle_material(*F08)
    image, installed = acceptance._source_bundle(tmp_path)
    recipe = acceptance._recipe(material, image)
    runner = acceptance.LocalProcessRunner(installed)
    ledger = CampaignLedger(tmp_path / "campaign")
    built = reconstruct_public(
        ledger,
        owner="miner",
        identity="f08-build",
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
        identity="f08-inference",
        image=image,
        inference_image=image.parent,
        recipe=recipe,
        challenge_binding=acceptance._binding(material),
        build=built,
        inputs=material["practice_inputs"],
        expected_output_shape=material["expected_output_shape"],
        allowlist_bytes=material["allowlist_bytes"],
        expected_output_dtype=output_dtype(material["interface_document"]),
        runner=runner,
    )
    predictions = np.asarray(inferred.predictions, dtype=np.float32)
    assert predictions.shape == material["practice_reference"].shape
    assert np.isfinite(predictions).all()
    train = np.load(io.BytesIO(material["train"]))
    assert train["inputs"].shape == (255, 6)


def test_a_measured_task_is_admitted_for_f08(tmp_path, monkeypatch):
    """F08 declares its dtype as train_dtype, not outputs.dtype or dtype."""
    import test_direct_v3_durable_tasks as durable

    material = physical_material.bundle_material(*F08)
    request, provider, _ = durable._fixture(tmp_path, monkeypatch, material=material)
    tasks = provider()
    try:
        started = tasks.start_research_task(request, measure_query=True)
        assert started.task.state.name in ("QUEUED", "RUNNING")
    finally:
        tasks.close()


def test_the_resource_policy_binds_the_f08_limits():
    from carbon.development_session.bundle_construction_worker import (
        verify_direct_resource_policy,
    )

    material = physical_material.bundle_material(*F08)
    kit = material["construction_kit"]
    binding = {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        "train_digest": kit["train_digest"],
        "interface_digest": kit["interface_digest"],
        "construction_limits_digest": kit["construction_limits_digest"],
    }
    assert (
        verify_direct_resource_policy(binding, material["construction_limits_document"])
        == kit["construction_limits_digest"]
    )
