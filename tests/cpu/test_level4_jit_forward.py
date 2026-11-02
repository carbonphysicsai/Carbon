"""The versioned jitted graph forward (carbon/level4/forward_mode.py, train.prepare(forward=...)).

Claims: no version is opted in until the Validator rules (every version stays eager); prepare refuses an unknown mode; a jitted
forward is bit-equal run to run; the jit-vs-eager difference is reported (it is not required to be 0: XLA may fuse); one predict wall
each way on a scan graph is reported; and the physical graph adapters pass the registry's mode for the recipe's own version.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import forward_mode, submission, tooling, train, validate

MAX_BYTES = 1 << 26
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def allowlist():
    # v8: the served allowlist that admits `scan`
    return allowlist_module.load(
        Path(allowlist_module.__file__).with_name("allowlist_v8.json")
    )


def _scan_submission(allowlist, n=4):
    import jax
    import jax.numpy as jnp
    from jax import lax

    def forward(w, b, x):
        def step(c, xi):
            return jnp.tanh(c * w[0] + xi[:, None] * b), None

        return lax.scan(step, jnp.zeros((x.shape[0], 2), x.dtype), x.T)[0]

    _, fwd, _ = tooling.through_bprime(
        forward, (jnp.ones((3, 2)), jnp.zeros(2), jnp.ones((n, 3))), role="forward", allowlist=allowlist,
        input_names=["params/0", "params/1", "inputs/x"], max_bytes=MAX_BYTES,
    )  # fmt: skip
    _, ini, _ = tooling.through_bprime(
        lambda key: [jax.random.normal(key, (3, 2)), jnp.zeros(2)], (jax.random.PRNGKey(0),), role="init",
        allowlist=allowlist, input_names=["carbon/key"], max_bytes=MAX_BYTES,
    )  # fmt: skip
    interface = validate.Interface(
        inputs=(("inputs/x", "float32", (3,)),), outputs=(("float32", (2,)),)
    )
    manifest, files = submission.build(
        challenge="example",
        interface=interface.digest(),
        allowlist=allowlist,
        forward=fwd,
        init=ini,
    )
    _, parsed = submission.verify(
        submission.canonical(manifest), files, allowlist=allowlist, challenge="example",
        interface=interface.digest(), max_bytes=MAX_BYTES,
    )  # fmt: skip
    verdict = validate.validate_submission(
        parsed, allowlist, interface=interface, batch=n
    )
    return parsed, verdict


def test_no_version_is_opted_in_until_the_validator_rules():
    assert forward_mode.JIT_FORWARD_VERSIONS == frozenset()
    for key in (
        ("f08-ribbed-bracket", "1.7"),
        ("electric-motor-magnetics", "1.6"),
        ("f02", "3.0"),
    ):
        assert forward_mode.mode(*key) == forward_mode.EAGER


def test_the_mode_follows_the_registry(monkeypatch):
    monkeypatch.setattr(
        forward_mode, "JIT_FORWARD_VERSIONS", frozenset({("f02", "3.0")})
    )
    assert forward_mode.mode("f02", "3.0") == forward_mode.JIT
    assert forward_mode.mode("f02", "2.5") == forward_mode.EAGER


def test_prepare_refuses_an_unknown_mode(allowlist):
    parsed, verdict = _scan_submission(allowlist)
    with pytest.raises(ValueError, match="forward must be"):
        train.prepare(parsed, allowlist, verdict=verdict, forward="compiled")


def test_the_jitted_forward_is_bit_equal_run_to_run_and_its_difference_from_eager_is_reported(
    allowlist, record_property
):
    import jax
    import numpy as np

    parsed, verdict = _scan_submission(allowlist)
    eager = train.prepare(parsed, allowlist, verdict=verdict)
    jitted = train.prepare(parsed, allowlist, verdict=verdict, forward=forward_mode.JIT)
    params = eager.init(train.keys(3)[0])
    x = jax.random.normal(jax.random.PRNGKey(1), (40, 3))
    walls = {}
    outs = {}
    for name, prepared in (("eager", eager), ("jit", jitted)):
        prepared.predict(params, x)  # the first call compiles (jit) / warms up (eager)
        started = time.perf_counter()
        first = np.asarray(prepared.predict(params, x, isolated=True)[0])
        walls[name] = time.perf_counter() - started
        again = np.asarray(prepared.predict(params, x, isolated=True)[0])
        assert first.tobytes() == again.tobytes()  # run to run, bit for bit
        outs[name] = first
    diff = float(np.max(np.abs(outs["jit"] - outs["eager"])))
    record_property("jit_vs_eager_max_abs_diff", diff)
    record_property("isolated_predict_wall_s", walls)
    print(
        f"jit vs eager max abs diff {diff:.3e}; isolated predict wall eager {walls['eager']:.3f} s, jit {walls['jit']:.3f} s"
    )
    np.testing.assert_allclose(
        outs["jit"], outs["eager"], rtol=1e-5, atol=1e-6
    )  # same graph; fusion may move the last bit


def test_the_physical_graph_adapters_pass_the_registry_mode_for_the_recipes_version():
    for rel in (
        "carbon/development_session/physical_graph_adapter.py",
        "carbon/development_session/physical_graph_adapter_v2.py",
    ):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "forward=forward_mode.mode(" in source, rel
        assert source.count("prepare(") >= 1
