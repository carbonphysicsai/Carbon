"""Battery's Level-2 development variant: `optimizer.muon_spectral`
(`specmuon-carbon-v1`, Carbon's interpretation of SpecMuon).

The Test Lead's conditions: determinism (R1 on CPU), a loss decrease, the
default byte for byte, and RSAV off reducing to base Muon byte for byte. No
test claims a paper's reported improvement.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("jax")

from carbon.battery import level2, level2_specmuon, level2_training, level2_worker
from carbon.battery import training as level0_training
from carbon.battery.worker import DirectBackend, WorkerFailure
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    compile_submission,
)

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = cr.BATTERY_CHALLENGE
MUON = {"width": 16, "depth": 1, "steps": 48, "optimizer_family": "muon"}


def strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {**MUON, **parameters},
    }


def compiled(**parameters):
    return dv.compile_development(strategy(**parameters), dv.variant(BATTERY, 2))


@pytest.fixture(scope="module")
def backend():
    return DirectBackend(REPOSITORY)


def rebuild(backend, **parameters):
    found = compiled(**parameters)
    record = level2_worker.spectral_record(found.reconstruction)
    return backend.reconstruct(None, found.construction, 7, record)


def test_the_variant_is_registered_recorded_and_built_from_the_code():
    found = dv.variant(BATTERY, 2)
    assert found.version == level2.VERSION
    assert found.document() == level2.variant_document(
        base={
            "digest": found.base_contract_digest,
            "record_sequence": found.base_record_sequence,
        }
    )
    assert dv.newest_record(found, None, None) is not None
    (widened,) = found.widened
    assert widened.surface.kind == "bool" and widened.surface.default is False
    bounds = level2.variant_document()["widened"][0]["bounds"]
    assert bounds["interpretation"] == "specmuon-carbon-v1"


def test_miner_surfaces_never_resolve_level_2():
    with pytest.raises(SubmissionRefused):
        compile_submission(strategy(muon_spectral=True))


SIGNATURE = (
    "def train(*, init, apply, f, z, sw, gw, trajectory, settings, seed, order):\n"
)
DOC_END = "    cases for the curriculum. All arrays are in the requested precision.\n"
OPTIMIZER = "    tx = optimizer(jax, optax, s, steps)\n"
UPDATE = (
    "        if plateau:\n"
    "            updates, state = tx.update(g, state, p, value=value)\n"
    "        else:\n"
    "            updates, state = tx.update(g, state, p)\n"
)


def level2_train_source(source):
    """`training.train`'s source with the Level-2 edits applied."""
    for part in (SIGNATURE, OPTIMIZER, UPDATE):
        assert source.count(part) == 1, part
    source = source.replace(
        SIGNATURE,
        "def train(*, init, apply, f, z, sw, gw, trajectory, settings, seed, order, spectral):\n",
    )
    source = source.replace(
        DOC_END,
        DOC_END + "\n"
        "    Level 2: with `spectral`, battery's Muon is wrapped by\n"
        "    `level2_specmuon.spectral`, which takes the step's loss and its\n"
        "    minibatch objective. Everything else is `training.train`, line for line.\n",
    )
    source = source.replace(
        OPTIMIZER,
        OPTIMIZER
        + "    if spectral:\n        tx = level2_specmuon.spectral(jax, optax, tx)\n",
    )
    return source.replace(
        UPDATE,
        "        if spectral:\n"
        "            updates, state = tx.update(\n"
        "                g, state, p, value=value, value_fn=lambda q: loss(q, idx, i)\n"
        "            )\n"
        "        elif plateau:\n"
        "            updates, state = tx.update(g, state, p, value=value)\n"
        "        else:\n"
        "            updates, state = tx.update(g, state, p)\n",
    )


def test_the_level2_trainer_is_the_general_trainer_with_its_edits():
    expected = level2_train_source(inspect.getsource(level0_training.train))
    assert inspect.getsource(level2_training.train) == expected


def _muon(jax, optax):
    from optax import contrib

    def mask(params):
        return jax.tree_util.tree_map(lambda x: x.ndim >= 2, params)

    return contrib.muon(
        1e-2, beta=0.9, eps=1e-8, weight_decay=0.0, weight_decay_mask=mask
    )


def _run(jax, optax, tx, extra, steps=20):
    import jax.numpy as jnp

    key = jax.random.PRNGKey(0)
    x = jax.random.normal(key, (32, 5))
    y = jnp.sin(x.sum(1, keepdims=True))
    p = {
        "w": jax.random.normal(key, (5, 8)) * 0.3,
        "b": jnp.zeros(8),
        "v": jnp.ones((8, 1)) * 0.1,
    }

    def loss(p):
        return jnp.mean((jnp.tanh(x @ p["w"] + p["b"]) @ p["v"] - y) ** 2)

    state = tx.init(p)
    for _ in range(steps):
        value, g = jax.value_and_grad(loss)(p)
        kw = {"value": value, "value_fn": loss} if extra else {}
        u, state = tx.update(g, state, p, **kw)
        p = optax.apply_updates(p, u)
    return p, loss(p)


def check_rsav_off_is_base_muon():
    import jax
    import optax

    plain, _ = _run(jax, optax, _muon(jax, optax), False)
    off, _ = _run(
        jax,
        optax,
        level2_specmuon.spectral(jax, optax, _muon(jax, optax), rsav=False),
        True,
    )
    for a, b in zip(jax.tree_util.tree_leaves(plain), jax.tree_util.tree_leaves(off)):
        assert np.array_equal(np.asarray(a), np.asarray(b))


def test_rsav_off_reduces_to_base_muon_byte_for_byte():
    check_rsav_off_is_base_muon()


def test_specmuon_is_deterministic_and_lowers_the_loss():
    import jax
    import optax

    start = _run(jax, optax, _muon(jax, optax), False, steps=0)[1]
    first = _run(
        jax, optax, level2_specmuon.spectral(jax, optax, _muon(jax, optax)), True
    )
    second = _run(
        jax, optax, level2_specmuon.spectral(jax, optax, _muon(jax, optax)), True
    )
    assert float(first[1]) == float(second[1]) and float(first[1]) < float(start)


@pytest.mark.parametrize("parameters", [{}, {"muon_spectral": False}])
def test_off_is_level_0_byte_for_byte(parameters):
    from carbon.challenge_validator import scoring as challenge_scoring

    scoring = challenge_scoring.scoring_for(BATTERY)
    found = compiled(**parameters)
    assert level2_worker.spectral_record(found.reconstruction) is None
    level0, _f0, program0 = scoring.built_from(
        compile_submission(strategy()), 7, REPOSITORY
    )
    built, _f, program = scoring.built_from(found, 7, REPOSITORY)
    assert program == program0 and built["staged"] == level0["staged"]


@pytest.mark.parametrize(
    ("parameters", "code"),
    [
        ({"optimizer_family": "adam"}, "development.needs_muon"),
        (
            {"learning_rate_curve": "train_loss_plateau"},
            "development.not_with_plateau_curve",
        ),
        ({"backend": "pytorch"}, "development.backend_not_served"),
    ],
)
def test_the_switch_is_refused_where_it_does_not_apply(parameters, code):
    with pytest.raises(dv.VariantRefused) as refused:
        compiled(muon_spectral=True, **parameters)
    assert code in [i[0] for i in refused.value.issues]


def test_two_rebuilds_give_the_same_parameters(backend):
    first = rebuild(backend, muon_spectral=True)
    second = rebuild(backend, muon_spectral=True)
    assert first[0] == second[0] and first[1]["trainer"] == "level2"


def check_a_non_cpu_device_is_carbons_environment(monkeypatch, backend):
    import jax

    monkeypatch.setattr(jax, "default_backend", lambda: "gpu")
    with pytest.raises(WorkerFailure) as failed:
        rebuild(backend, muon_spectral=True)
    assert (
        failed.value.candidate is False and "level2_cpu_only_dev" in failed.value.code
    )


def test_a_non_cpu_device_is_carbons_environment(monkeypatch, backend):
    check_a_non_cpu_device_is_carbons_environment(monkeypatch, backend)


def test_the_built_record_says_cpu_verified_only():
    from carbon.challenge_validator import scoring as challenge_scoring

    built, _f, program = challenge_scoring.scoring_for(BATTERY).built_from(
        compiled(muon_spectral=True), 7, REPOSITORY
    )
    assert built["rebuild"] == level2_worker.REBUILD_LABEL
    assert 'raise ImportError("level2_cpu_only_dev")' in program


MUTATIONS = {
    "cpu_lane": (
        lambda m: m.setattr(
            level2_worker,
            "build_in_process",
            lambda recipe, record: level2_training.build(
                recipe.family, recipe.settings
            ),
        ),
        check_a_non_cpu_device_is_carbons_environment,
    ),
    "rsav_off_reduction": (
        lambda m: m.setattr(level2_specmuon, "spectral", _ignores_the_switch()),
        lambda m, b: check_rsav_off_is_base_muon(),
    ),
}


def _ignores_the_switch():
    """A mutant whose RSAV cannot be switched off."""
    original = level2_specmuon.spectral

    def spectral(jax, optax, base, *, rsav=True):
        return original(jax, optax, base, rsav=True)

    return spectral


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_switching_a_guard_off_fails_its_test(name, monkeypatch, backend):
    disable, guard = MUTATIONS[name]
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(monkeypatch, backend)
