import numpy as np
import pytest

from carbon.battery.monotone_capacity import layout_type
from carbon.battery.recipes import Layout


def _data(capacity):
    data = type("Data", (), {})()
    data.v = np.array([[3.7, 3.8, 3.9]])
    data.q = np.asarray([capacity], dtype=float)
    data.t = np.array([[25.0, 26.0, 27.0]])
    data.x = np.array([[1.0, 0.5, 25.0, 0.7]])
    data.eta = np.array([0.2])
    return data


def test_monotone_layout_round_trips_capacity_targets_and_never_rises():
    candidate_type = layout_type(Layout)
    candidate = candidate_type(3, 3, bounded_v=False, predict_v0=False, fade=True)
    data = _data([2.0, 1.8, 1.5])

    target = candidate.targets(data)
    decoded = candidate.split(target)
    np.testing.assert_allclose(decoded[3], data.q, rtol=0.0, atol=1e-14)
    assert np.all(np.diff(decoded[3], axis=1) <= 0.0)

    arbitrary_logits = target.copy()
    arbitrary_logits[:, candidate.nv + candidate.nt + 2 :] = [[-3.0, 2.0]]
    predicted_capacity = candidate.split(arbitrary_logits)[3]
    assert np.all(np.diff(predicted_capacity, axis=1) < 0.0)


def test_monotone_layout_refuses_nonpositive_observed_fade():
    candidate = layout_type(Layout)(
        3, 3, bounded_v=False, predict_v0=False, fade=True
    )

    with pytest.raises(ValueError, match="requires_positive_observed_fade"):
        candidate.targets(_data([2.0, 2.0, 1.5]))


def test_candidate_builder_rejects_unsupported_construction():
    from carbon.battery.monotone_capacity import MonotoneCapacityCandidate

    model = type(
        "Model", (), {"family": "mlp", "settings": {"capacity_fade_head": False}}
    )()
    with pytest.raises(ValueError, match="requires_capacity_fade_head"):
        MonotoneCapacityCandidate(model)


def test_layout_binding_is_restored_after_failed_fit():
    from carbon.battery import recipes
    from carbon.battery.monotone_capacity import MonotoneCapacityCandidate

    original = recipes.Layout
    def fail(self):
        raise RuntimeError("stop")

    model = type(
        "Model",
        (),
        {"family": "mlp", "settings": {"capacity_fade_head": True}, "fit": fail},
    )()
    with pytest.raises(RuntimeError, match="stop"):
        MonotoneCapacityCandidate(model).fit()
    assert recipes.Layout is original