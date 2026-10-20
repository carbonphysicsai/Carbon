"""F02 through the normal construction path (DEVELOPMENT, public material only).

The receiver registers `f02` 2.0 like Motor, Cooling and F08, with its own 40-row
float32 TRAIN40-v2, two-field burst schedule input and one learned output (the peak
top temperature). Claims:

1. Discovery accepts the public material (fixed TRAIN, interface, limits, physics
   contract, the eight development schedules as the practice query).
2. The served recipe contract is registered.
3. A recipe is rebuilt fresh from the fixed TRAIN in a separate process, frozen and
   run source-free on the development bank's query; the output has F02's width and
   float32 dtype.

No score, qualification or LIVE claim: fixed programs run in local processes.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

pytest.importorskip("jax")

import test_direct_clean_rebuild_acceptance as acceptance

from carbon.challenge_kit import f02_train, physical_material
from carbon.challenge_kit.interface_dtype import output_dtype
from carbon.development_session.bundle_construction_worker import (
    infer_public,
    reconstruct_public,
)
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.reconstruction import served_recipe_contract

F02 = (f02_train.CHALLENGE_ID, f02_train.CHALLENGE_VERSION)

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


def test_f02_is_registered_beside_the_others():
    assert F02 in physical_material.REGISTERED
    assert physical_material.is_registered(*F02)
    assert not physical_material.is_registered("f02", "1.0")


def test_the_material_is_f02s_own_float32_interface():
    material = physical_material.bundle_material(*F02)
    n_inputs, n_outputs = len(f02_train.FIELDS), len(f02_train.TARGETS)
    assert material["practice_inputs"].shape == (8, n_inputs)
    assert material["practice_reference"].shape == (8, n_outputs)
    assert material["practice_inputs"].dtype == np.float32
    assert material["practice_reference"].dtype == np.float32
    assert output_dtype(material["interface_document"]) == "<f4"
    assert material["disclosure"]["scope"] == "PUBLIC_F02_DEVELOPMENT_ONLY"
    assert material["disclosure"]["hidden_evaluation"] is False
    train = np.load(io.BytesIO(material["train"]))
    assert train["inputs"].shape == (40, n_inputs)
    assert len(material["train_case_ids"]) == 40
    assert material["construction_kit"]["id"] == "f02"
    assert material["construction_kit"]["train_digest"] == "sha256:" + (
        f02_train.load_public_train(F02[1])["provenance"]["train_sha256"].removeprefix(
            "sha256:"
        )
    )


def test_receiver_discovery_accepts_the_public_material():
    material = physical_material.bundle_material(*F02)
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    assert discovery.info.challenge_key.challenge_id == F02[0]
    assert discovery.info.challenge_key.version == F02[1]


def test_changed_material_is_refused_by_discovery():
    material = physical_material.bundle_material(*F02)
    material["practice_inputs"] = material["practice_inputs"] + np.float32(1.0)
    with pytest.raises(ValueError):
        DirectFixtureDiscovery(material, task_admission=True)


def test_a_float64_practice_query_is_refused_for_f02():
    material = physical_material.bundle_material(*F02)
    material["practice_inputs"] = material["practice_inputs"].astype(np.float64)
    with pytest.raises(ValueError):
        DirectFixtureDiscovery(material, task_admission=True)


def test_the_served_contract_is_registered():
    contract = served_recipe_contract.registered(*F02)
    assert contract.evidence_label == "DEVELOPMENT_PUBLIC_PHYSICAL"
    assert (
        contract.construction_kit
        == physical_material.bundle_material(*F02)["construction_kit"]
    )


def test_an_unknown_f02_version_is_refused():
    with pytest.raises(ValueError):
        physical_material.bundle_material("f02", "2.1")


def test_fresh_rebuild_then_source_free_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, "SOURCE", SOURCE)
    material = physical_material.bundle_material(*F02)
    image, installed = acceptance._source_bundle(tmp_path)
    recipe = acceptance._recipe(material, image)
    runner = acceptance.LocalProcessRunner(installed)
    ledger = CampaignLedger(tmp_path / "campaign")
    built = reconstruct_public(
        ledger,
        owner="miner",
        identity="f02-build",
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
        identity="f02-inference",
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


def test_a_measured_task_is_admitted_for_f02(tmp_path, monkeypatch):
    """F02 declares its dtype as train_dtype, not outputs.dtype or dtype."""
    import test_direct_v3_durable_tasks as durable

    material = physical_material.bundle_material(*F02)
    request, provider, _ = durable._fixture(tmp_path, monkeypatch, material=material)
    tasks = provider()
    try:
        started = tasks.start_research_task(request, measure_query=True)
        assert started.task.state.name in ("QUEUED", "RUNNING")
    finally:
        tasks.close()


def test_the_resource_policy_binds_the_f02_limits():
    from carbon.development_session.bundle_construction_worker import (
        verify_direct_resource_policy,
    )

    material = physical_material.bundle_material(*F02)
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
