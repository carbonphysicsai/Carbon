"""Motor and Cooling through the normal construction path (DEVELOPMENT, public material only).

Claims tested:

1. The receiver's discovery accepts each Challenge's public material (fixed TRAIN, interface,
   limits, physics contract, development-bank practice query) with task admission.
2. The served recipe contract is registered and labelled physical.
3. A recipe is rebuilt fresh from the fixed TRAIN in a separate process, frozen, and
   run source-free one case at a time on the development bank's queries; the
   output has the Challenge's width.

No model score, evaluation, qualification or LIVE claim: the harness runs the fixed
programs in local processes, like the synthetic acceptance test.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

pytest.importorskip("jax")

import test_direct_clean_rebuild_acceptance as acceptance

from carbon.challenge_kit import physical_material
from carbon.development_session.bundle_construction_worker import (
    infer_public,
    reconstruct_public,
)
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.reconstruction import served_recipe_contract

CHALLENGES = pytest.mark.parametrize(
    ("challenge_id", "version"), physical_material.REGISTERED
)

SOURCE = (
    "import numpy as np\n"
    "import jax.numpy as jnp\n"
    "def build(train_inputs, train_targets, *, seed, configuration, train_use):\n"
    "    x = np.asarray(train_inputs, float)\n"
    "    y = np.asarray(train_targets, float)\n"
    "    mu, sd = x.mean(axis=0), x.std(axis=0) + 1e-9\n"
    "    z = np.concatenate([(x - mu) / sd, np.ones((len(x), 1))], axis=1)\n"
    "    w = np.linalg.lstsq(z, y, rcond=None)[0]\n"
    "    wj, mj, sj = jnp.asarray(w), jnp.asarray(mu), jnp.asarray(sd)\n"
    "    def apply(x):\n"
    "        z = (x - mj) / sj\n"
    "        one = jnp.ones((z.shape[0], 1), z.dtype)\n"
    "        return jnp.concatenate([z, one], axis=1) @ wj\n"
    "    return {'framework': 'jax', 'apply': apply, 'parameters': []}\n"
)


def _expected(material):
    train = np.load(io.BytesIO(material["train"]))
    x, y = np.asarray(train["inputs"], float), np.asarray(train["targets"], float)
    mu, sd = x.mean(axis=0), x.std(axis=0) + 1e-9
    z = np.concatenate([(x - mu) / sd, np.ones((len(x), 1))], axis=1)
    w = np.linalg.lstsq(z, y, rcond=None)[0]
    q = np.asarray(material["practice_inputs"], float)
    return np.concatenate([(q - mu) / sd, np.ones((len(q), 1))], axis=1) @ w


@CHALLENGES
def test_receiver_discovery_accepts_the_public_material(challenge_id, version):
    material = physical_material.bundle_material(challenge_id, version)
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    assert discovery.info.challenge_key.challenge_id == challenge_id
    rows = len(material["practice_case_ids"])
    assert material["practice_inputs"].shape[0] == rows
    assert material["practice_reference"].shape[0] == rows
    assert material["disclosure"]["hidden_evaluation"] is False


@CHALLENGES
def test_changed_material_is_refused_by_discovery(challenge_id, version):
    material = physical_material.bundle_material(challenge_id, version)
    material["practice_inputs"] = material["practice_inputs"] + 1.0
    with pytest.raises(ValueError):
        DirectFixtureDiscovery(material, task_admission=True)


@CHALLENGES
def test_the_served_contract_is_registered(challenge_id, version):
    contract = served_recipe_contract.registered(challenge_id, version)
    assert contract.evidence_label == "DEVELOPMENT_PUBLIC_PHYSICAL"
    assert (
        contract.construction_kit
        == physical_material.bundle_material(challenge_id, version)["construction_kit"]
    )


@CHALLENGES
def test_fresh_rebuild_then_per_case_source_free_inference(
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
        identity="motor-build",
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
        identity="motor-inference",
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
    np.testing.assert_allclose(predictions, _expected(material), rtol=1e-6, atol=1e-6)
