"""Motor 1.9's trust registration (owner MOTOR19-TRUST-REGISTRATION + MOTOR19-TRUST-FLOOR-0, 23 Nov 2026; model-eval 5619 /
5667): k = 5 in pool order, derive with emf_scalar 'rms', sigma floor 0, epochs / learning rate BY REFERENCE to the main
trainer's registered surface defaults; the derive equals the grader's numpy formulas."""

from __future__ import annotations

import math

import numpy as np
import pytest

from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session import motor19_trust_derive as m19
from carbon.development_session import physical_graph_adapter_v2 as v2
from carbon.development_session import physical_graph_trust_registry as registry
from carbon.motor import back_emf, domain
from carbon.scoring import motor19_dual_pack

KEY = ("electric-motor-magnetics", "1.9")


def test_the_entry_takes_the_owner_values_and_the_trainer_defaults_by_reference():
    entry = registry.REGISTRATIONS[KEY]
    assert entry["sigma_floor"] == (0.0,) * 5
    assert entry["epochs"] == v2.TRAIN_SURFACES_V3["steps"][2]
    assert entry["learning_rate"] == v2.TRAIN_SURFACES_V3["learning_rate"][2]
    spec = registry.trust_spec(*KEY, width=241, outputs=5, trust_parameters=(0,))
    assert spec.sigma_floor == (0.0,) * 5 and spec.epochs == entry["epochs"]


def test_the_layout_and_outputs_are_the_1_9_grader_s():
    assert m19.WIDTH == 241 and m19.ANGLE_STEPS == domain.ANGLE_STEPS
    assert m19.PERIOD_DEG == domain.PERIOD_DEG and m19.STEP_RAD == back_emf.STEP_RAD
    assert back_emf.GRADED_PAIR == ("a", "b")
    assert m19.OUTPUTS == (
        "mean_torque_nm",
        "ripple_pk_pk_nm",
        *motor19_dual_pack.EMF_OUTPUTS,
        *motor19_dual_pack.SCALAR_OUTPUTS,
    )


def test_the_derive_is_staged_into_the_trust_build_container_only():
    name = "carbon.development_session.motor19_trust_derive"
    assert name in worker.PHYSICAL_V2_TRUST_STAGED_MODULES
    assert name not in worker.PHYSICAL_V2_STAGED_MODULES


def test_make_derive_has_no_default():
    for bad in (None, "amplitude", "RMS"):
        with pytest.raises(ValueError):
            m19.make_derive(bad)


def test_the_derive_equals_the_grader_formulas():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    rng = np.random.default_rng(19)
    rows = rng.normal(size=(6, 241))
    out = np.asarray(registry.REGISTRATIONS[KEY]["derive"](rows, np.zeros((6, 8))))
    assert out.shape == (6, 5)
    for row, got in zip(rows, out):
        # the grader's own helpers take plain Python floats (a numpy scalar is refused as derivative_input_invalid)
        curve = [float(v) for v in row[0:60]]
        ke = back_emf.derivative([float(v) for v in row[60:120] - row[120:180]])
        rms = math.sqrt(sum(v * v for v in ke) / len(ke))
        want = [sum(curve) / len(curve), max(curve) - min(curve), rms, rms, row[240]]
        assert got[1] == want[1] and got[4] == want[4]
        assert np.allclose(got, want, rtol=1e-12, atol=0)
