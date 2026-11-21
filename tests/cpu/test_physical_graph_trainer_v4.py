"""The two-phase trust trainer (carbon/development_session/physical_graph_trainer_v4.py, SELF_TRUST H3d-2b): phase 1 is the pinned
trainer unchanged on a W-view of the model, phase 2 restarts and updates ONLY the trust parameters of member 0 on the held-out rows
against the ENSEMBLE's residual, and with no held-out row there is no silent in-sample fit (the typed status `no_held_out_rows`).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

jnp = pytest.importorskip("jax.numpy")
pytest.importorskip("optax")

from carbon.development_session import physical_graph_trainer_v4 as trust
from carbon.level4.train import Prepared

W, K, BATCH = 3, 1, 2
INIT_LOG_SIGMA = 0.7  # the trust parameter's INITIAL value (what `prepared.init` draws)
PHASE_ONE_LOG_SIGMA = 0.123  # what phase 1 leaves behind (weight decay drift): phase 2 must NOT start from it


def derive(native, inputs):
    """One trust output: the first physics column (jax-traceable)."""
    return native[:, :1]


def spec(**override):
    values = {
        "width": W,
        "outputs": K,
        "derive": derive,
        "trust_parameters": (1,),
        "sigma_floor": (0.1,),
        "epochs": 200,
        "learning_rate": 0.05,
    }
    values.update(override)
    return trust.TrustSpec(**values)


def apply(params, x):
    """The trust graph: W physics columns `x * p0 + p2`, then K log-sigma columns from the trust parameter `p1` alone."""
    physics = x * params[0] + params[2]
    log_sigma = jnp.zeros((x.shape[0], K)) + params[1]
    return [jnp.concatenate([physics, log_sigma], axis=-1)]


def init(_key):
    return [jnp.ones(W), jnp.full((K,), INIT_LOG_SIGMA), jnp.zeros(W)]


def prepared(**override):
    return Prepared(init=init, apply=apply, batch=BATCH, parameters=(), **override)


def base_trainer(captured, biases=(0.0,)):
    """A stand-in for the pinned trainer: one member per bias (its physics offset), combined with equal weights."""

    def train(model, inputs, targets, settings, *, seed):
        probe = model.apply(
            [np.ones(W), np.zeros(K), np.zeros(W)], jnp.ones((BATCH, W))
        )[0]
        captured["width"] = probe.shape[-1]
        return {
            "members": [
                [
                    np.ones(W, dtype="float32"),
                    np.full(K, PHASE_ONE_LOG_SIGMA, dtype="float32"),
                    np.full(W, bias, dtype="float32"),
                ]
                for bias in biases
            ],
            "mu": np.zeros(W, dtype="float32"),
            "sd": np.ones(W, dtype="float32"),
            "combine": np.full((len(biases), W), 1.0 / len(biases), dtype="float32"),
            "member_losses": [0.0] * len(biases),
            "train_loss": 0.0,
        }

    def selected_rows(count, fraction, seed):
        return np.arange(count) if fraction >= 1.0 else np.arange(int(count * fraction))

    return SimpleNamespace(train=train, selected_rows=selected_rows)


def data(rows=7):
    inputs = np.zeros(
        (rows, W), dtype="float32"
    )  # the physics scale term is 0 on every row
    targets = np.zeros((rows, W), dtype="float32")  # truth 0
    return inputs, targets


def run(biases=(0.0,), targets=None, fraction=0.5, **spec_override):
    captured = {}
    inputs, default_targets = data()
    result = trust.train(
        prepared(),
        inputs,
        default_targets if targets is None else targets,
        {"train_fraction": fraction},
        seed=0,
        base_trainer=base_trainer(captured, biases),
        spec=spec(**spec_override),
    )
    return result, captured


# -- the registration: every value of the owner's has no default -------------------------------------------------------------


def test_a_complete_spec_passes():
    assert trust.check(spec()) is None


@pytest.mark.parametrize("field", ["sigma_floor", "epochs", "learning_rate"])
def test_a_missing_owner_value_refuses_as_human_input(field):
    with pytest.raises(trust.TrustRefused) as refused:
        trust.check(spec(**{field: None}))
    assert refused.value.code == "trust_value_is_human_input"


@pytest.mark.parametrize(
    "override",
    [
        {"sigma_floor": (0.0,)},
        {"sigma_floor": (0.1, 0.1)},
        {"sigma_floor": [0.1]},
        {"epochs": 0},
        {"epochs": True},
        {"learning_rate": -1.0},
        {"learning_rate": float("nan")},
    ],
)
def test_an_out_of_domain_owner_value_refuses(override):
    with pytest.raises(trust.TrustRefused) as refused:
        trust.check(spec(**override))
    assert refused.value.code == "trust_value_out_of_domain"


@pytest.mark.parametrize(
    "override",
    [
        {"width": 0},
        {"outputs": 0},
        {"derive": None},
        {"trust_parameters": ()},
        {"trust_parameters": (1, 1)},
        {"trust_parameters": [1]},
        {"trust_parameters": (-1,)},
    ],
)
def test_a_malformed_structure_refuses(override):
    with pytest.raises(trust.TrustRefused) as refused:
        trust.check(spec(**override))
    assert refused.value.code == "trust_spec_malformed"


# -- the pieces ------------------------------------------------------------------------------------------------------------------


def test_the_held_out_rows_are_the_unselected_train_rows():
    assert list(trust.held_out_rows(6, np.array([0, 2, 3]))) == [1, 4, 5]
    assert len(trust.held_out_rows(6, np.arange(6))) == 0


def test_the_chunks_cover_every_held_out_row_once_and_pad_the_last_with_a_mask():
    chunks = list(trust._chunks(np.array([4, 5, 9]), 2))
    assert [list(rows) for rows, _ in chunks] == [[4, 5], [9, 9]]
    assert [used for _, used in chunks] == [2, 1]


def test_the_w_view_cuts_the_first_output_to_its_physics_columns_and_keeps_the_rest():
    def wide(params, x):
        return [jnp.ones((x.shape[0], W + K)), "aux"]

    view = trust.w_view(Prepared(init=None, apply=wide, batch=BATCH, parameters=()), W)
    outputs = view.apply([], jnp.ones((BATCH, W)))
    assert outputs[0].shape == (BATCH, W) and outputs[1] == "aux"
    assert view.isolated_apply is None


def test_the_nll_is_the_gaussian_one_with_the_registered_floor():
    residual, log_sigma = jnp.asarray([[2.0]]), jnp.asarray([[0.0]])
    value = float(trust.trust_nll(residual, log_sigma, (1.0,))[0])
    sigma = 1.0 + 1.0  # floor + exp(0)
    assert value == pytest.approx(0.5 * (2.0 / sigma) ** 2 + np.log(sigma), rel=1e-6)


# -- the two phases ---------------------------------------------------------------------------------------------------------------


def test_with_no_held_out_row_phase_two_does_not_run_and_the_status_is_typed():
    result, _ = run(fraction=1.0)
    assert result["trust"] == {"status": "no_held_out_rows", "held_out_rows": 0}
    # the trust parameters are whatever phase 1 returned: no in-sample fit is made
    np.testing.assert_allclose(result["members"][0][1], PHASE_ONE_LOG_SIGMA)


def test_phase_one_sees_a_w_wide_model():
    _, captured = run()
    assert (
        captured["width"] == W
    )  # the pinned trainer was run on the W-view, never on W + k


def test_phase_two_updates_only_the_trust_parameters_of_member_zero_on_the_held_out_rows():
    result, _ = run(
        targets=np.full((7, W), 2.0, dtype="float32")
    )  # a constant residual of -2
    assert result["trust"] == {
        "status": "trained",
        "held_out_rows": 4,
    }  # 7 rows, 3 selected
    physics, log_sigma, bias = result["members"][0]
    np.testing.assert_array_equal(
        physics, np.ones(W, dtype="float32")
    )  # the physics parameters are bit for bit
    np.testing.assert_array_equal(bias, np.zeros(W, dtype="float32"))
    assert physics.dtype == np.float32 and log_sigma.dtype == np.float32
    assert np.isfinite(log_sigma).all()
    # a constant residual of -2 under floor 0.1: the optimal sigma is about 2, so log_sigma settles near ln(1.9) = 0.64
    assert float(log_sigma[0]) == pytest.approx(np.log(1.9), abs=0.15)


def test_phase_two_restarts_from_the_initial_trust_parameters_not_from_phase_ones_drifted_values():
    # one epoch at a vanishing learning rate: the result is where phase 2 STARTED
    result, _ = run(
        epochs=1, learning_rate=1e-12, targets=np.full((7, W), 2.0, dtype="float32")
    )
    np.testing.assert_allclose(result["members"][0][1], INIT_LOG_SIGMA, atol=1e-5)
    assert abs(float(result["members"][0][1][0]) - PHASE_ONE_LOG_SIGMA) > 0.5


def test_sigma_follows_the_ensembles_residual_not_member_zeros():
    # two members whose physics errs in opposite directions (offsets +1 and -1) combine, with equal weights, to the truth 0:
    # the reported (ensemble) residual is 0, so sigma shrinks to the floor. Judged on member 0 alone (residual +1) it would settle
    # near ln(0.9) = -0.1.
    ensemble, _ = run(biases=(1.0, -1.0))
    alone, _ = run(biases=(1.0,))
    assert float(ensemble["members"][0][1][0]) < -1.0
    assert float(alone["members"][0][1][0]) == pytest.approx(np.log(0.9), abs=0.2)
    # the physics offsets of BOTH members are returned bit for bit
    np.testing.assert_array_equal(
        ensemble["members"][1][2], np.full(W, -1.0, dtype="float32")
    )


def test_the_other_results_of_the_base_trainer_are_returned_untouched():
    result, _ = run()
    assert set(result) == {
        "members",
        "mu",
        "sd",
        "combine",
        "member_losses",
        "train_loss",
        "trust",
    }
    np.testing.assert_array_equal(result["mu"], np.zeros(W, dtype="float32"))


def test_an_incomplete_spec_refuses_before_any_training():
    captured = {}
    inputs, targets = data()
    with pytest.raises(trust.TrustRefused):
        trust.train(
            prepared(),
            inputs,
            targets,
            {"train_fraction": 0.5},
            seed=0,
            base_trainer=base_trainer(captured),
            spec=spec(epochs=None),
        )
    assert captured == {}  # the base trainer never ran


def test_a_batch_loss_graph_on_a_trust_model_is_refused_before_any_training():
    # V2 09:10:14Z: the trainer feeds W columns, a loss graph on the trust interface would take W + k
    captured = {}
    inputs, targets = data()
    with pytest.raises(trust.TrustRefused) as refused:
        trust.train(
            prepared(loss=object()),
            inputs,
            targets,
            {"train_fraction": 0.5},
            seed=0,
            base_trainer=base_trainer(captured),
            spec=spec(),
        )
    assert refused.value.code == "trust_loss_graph_not_offered"
    assert captured == {}


def test_the_residual_is_computed_the_way_carbon_grades_one_case_per_call():
    # door-code 10:10:41Z: a graph whose output depends on its batch-mates is allowed to build, which is why grading is isolated;
    # the residual must be the reported (isolated) prediction's, not a batched one's.
    def batch_dependent(params, x):
        physics = (
            x * params[0] + params[2] + 10.0 * jnp.roll(x, 1, axis=0)
        )  # row 0 reads the LAST row of the batch
        log_sigma = jnp.zeros((x.shape[0], K)) + params[1]
        return [jnp.concatenate([physics, log_sigma], axis=-1)]

    model = Prepared(init=init, apply=batch_dependent, batch=BATCH, parameters=())
    members = [
        [
            np.ones(W, dtype="float32"),
            np.zeros(K, dtype="float32"),
            np.zeros(W, dtype="float32"),
        ]
    ]
    inputs = np.ones((4, W), dtype="float32")
    targets = np.ones(
        (4, W), dtype="float32"
    )  # isolated prediction is x * 1 = 1: no error
    residual = trust.combined_residual(
        model,
        members,
        np.ones((1, W), dtype="float32"),
        inputs,
        targets,
        np.zeros(W, dtype="float32"),
        np.ones(W, dtype="float32"),
        np.arange(4),
        spec(),
    )
    np.testing.assert_allclose(
        residual, 0.0, atol=1e-6
    )  # a batched forward would give +10
