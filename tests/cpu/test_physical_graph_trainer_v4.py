"""The two-phase trust trainer (carbon/development_session/physical_graph_trainer_v4.py, SELF_TRUST H3d-2b): phase 1 is the pinned
trainer unchanged on a W-view of the model, phase 2 updates ONLY the trust parameters of member 0 on the held-out rows, and with no
held-out row there is no silent in-sample fit (the typed status `no_held_out_rows`).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

jnp = pytest.importorskip("jax.numpy")
pytest.importorskip("optax")

from carbon.development_session import physical_graph_trainer_v4 as trust  # noqa: E402
from carbon.level4.train import Prepared  # noqa: E402

W, K, BATCH = 3, 1, 2


def derive(native):
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
    """The trust graph: W physics columns `x * p0`, then K log-sigma columns from the trust parameter `p1` alone."""
    physics = x * params[0]
    log_sigma = jnp.zeros((x.shape[0], K)) + params[1]
    return [jnp.concatenate([physics, log_sigma], axis=-1)]


def prepared():
    return Prepared(init=None, apply=apply, batch=BATCH, parameters=())


def base_trainer(captured):
    def train(model, inputs, targets, settings, *, seed):
        captured["width"] = model.apply([np.ones(W), np.zeros(K)], jnp.ones((BATCH, W)))[0].shape[-1]
        return {
            "members": [[np.ones(W, dtype="float32"), np.zeros(K, dtype="float32")]],
            "mu": np.zeros(W, dtype="float32"),
            "sd": np.ones(W, dtype="float32"),
            "combine": np.ones((1, W), dtype="float32"),
            "member_losses": [0.0],
            "train_loss": 0.0,
        }

    def selected_rows(count, fraction, seed):
        return np.arange(count) if fraction >= 1.0 else np.arange(int(count * fraction))

    return SimpleNamespace(train=train, selected_rows=selected_rows)


def data(rows=7):
    inputs = np.zeros((rows, W), dtype="float32")  # physics prediction 0 on every row
    targets = np.full((rows, W), 2.0, dtype="float32")  # truth 2: a constant residual of -2
    return inputs, targets


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
    captured = {}
    inputs, targets = data()
    result = trust.train(
        prepared(),
        inputs,
        targets,
        {"train_fraction": 1.0},
        seed=0,
        base_trainer=base_trainer(captured),
        spec=spec(),
    )
    assert result["trust"] == {"status": "no_held_out_rows", "held_out_rows": 0}
    np.testing.assert_array_equal(result["members"][0][1], np.zeros(K))  # the trust parameters keep their initial values


def test_phase_one_sees_a_w_wide_model():
    captured = {}
    inputs, targets = data()
    trust.train(
        prepared(), inputs, targets, {"train_fraction": 0.5}, seed=0, base_trainer=base_trainer(captured), spec=spec()
    )
    assert captured["width"] == W  # the pinned trainer was run on the W-view, never on W + k


def test_phase_two_updates_only_the_trust_parameters_of_member_zero_on_the_held_out_rows():
    captured = {}
    inputs, targets = data(rows=7)
    result = trust.train(
        prepared(), inputs, targets, {"train_fraction": 0.5}, seed=0, base_trainer=base_trainer(captured), spec=spec()
    )
    assert result["trust"] == {"status": "trained", "held_out_rows": 4}  # 7 rows, 3 selected
    physics, log_sigma = result["members"][0]
    np.testing.assert_array_equal(physics, np.ones(W, dtype="float32"))  # the physics parameters are bit for bit
    assert physics.dtype == np.float32 and log_sigma.dtype == np.float32
    assert np.isfinite(log_sigma).all()
    # a constant residual of -2 under floor 0.1: the optimal sigma is about 2, so log_sigma moves up from 0
    assert float(log_sigma[0]) > 0.3


def test_the_other_results_of_the_base_trainer_are_returned_untouched():
    captured = {}
    inputs, targets = data()
    result = trust.train(
        prepared(), inputs, targets, {"train_fraction": 0.5}, seed=0, base_trainer=base_trainer(captured), spec=spec()
    )
    assert set(result) == {"members", "mu", "sd", "combine", "member_losses", "train_loss", "trust"}
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
