"""Level 4 Phase 0 spike (development only): graph-only construction, B'.

Claims tested:

1. Allowlist v0 is versioned data: every op is classified allow, review or
   refuse; refused ops (callbacks, unbounded loops, host transfer, unkeyed
   RNG) have no role; keyed RNG is admitted only in the init role.
2. No cap is chosen: every D6 cap is HUMAN_INPUT and blocks, never passes.
3. B' round trip: a program lowered to the strict-JSON Carbon graph, parsed
   with Carbon's strict JSON rules and rebuilt by Carbon's interpreter gives
   bit-identical outputs and gradients, and Carbon's own `jax.grad` trains it
   to the same parameters as the native program.
4. Each known-vulnerable program and each tampered document is refused with
   its expected typed code.
5. Constants are counted (one table or a table split into scalars) and only
   ever compared with a HUMAN_INPUT cap.
6. Battery's Level 0 MLP (classic path) and DeepONet (general path) rebuilt
   through B' reproduce the declarative path's parameter digests (R1:
   bit-identical) on CPU.
7. PyTorch: battery's FNO and MLP lowered from `torch.export` Core ATen into
   the same format agree with torch within float32 rounding.
8. Shared modules carry no Challenge literal; battery lives in its adapter.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")
REPOSITORY = Path(__file__).resolve().parents[2]
SPIKE = REPOSITORY / "scripts" / "dev" / "level4_spike"
sys.path.insert(0, str(SPIKE.parent))

from level4_spike import allowlist as allowlist_module
from level4_spike import graph, interpret, params, specimens

MAX_BYTES = 1 << 26  # the tests' parser bound; not a G3 limit


@pytest.fixture(scope="module")
def allowlist():
    return allowlist_module.load()


def test_allowlist_is_versioned_and_classified(allowlist):
    assert allowlist.version == "level4-allowlist-v0"
    assert allowlist.digest.startswith("sha256:")
    kinds = set(re.findall(r'kind == "([a-z_]+)"', (SPIKE / "params.py").read_text()))
    kinds |= {"none", "call_metadata", "custom_rule_dropped", "dtype_or_none"}
    for name, entry in allowlist.ops.items():
        assert entry["default"] in ("allow", "review", "refuse"), name
        if entry["default"] == "refuse":
            assert entry["roles"] == [] and not entry["v0_interpreter"], name
        assert set(entry["params"].values()) <= kinds, name
    for name in (
        "pure_callback",
        "io_callback",
        "debug_callback",
        "debug_print",
        "ffi_call",
        "custom_call",
        "while",
        "infeed",
        "outfeed",
        "rng_uniform",
        "random_seed",
    ):
        assert allowlist.ops[name]["default"] == "refuse", name
    for name in ("random_bits", "random_split", "random_wrap", "random_unwrap"):
        assert allowlist.ops[name]["roles"] == ["init"], name
    for name, entry in allowlist.aten.items():
        assert entry["default"] in ("allow", "review", "refuse"), name
        assert entry["lowering"] in ("emitted", "dropped", "refused"), name


def test_every_cap_is_human_input():
    assert set(allowlist_module.CAPS.values()) == {allowlist_module.HUMAN_INPUT}
    verdicts = allowlist_module.check_caps({name: 0 for name in allowlist_module.CAPS})
    assert set(verdicts.values()) == {"blocked_human_input"}


def _mlp():
    import jax
    import jax.numpy as jnp

    def init(key):
        params = []
        for a, b in ((3, 16), (16, 16), (16, 2)):
            key, sub = jax.random.split(key)
            params.append(
                (jax.random.normal(sub, (a, b)) * jnp.sqrt(2.0 / a), jnp.zeros(b))
            )
        return params

    def apply(p, x):
        for w, b in p[:-1]:
            x = jax.nn.gelu(x @ w + b)
        w, b = p[-1]
        return x @ w + b

    return init, apply


def test_bprime_round_trip_trains_bit_identically(allowlist):
    import jax
    import jax.numpy as jnp
    import numpy as np

    init, apply = _mlp()
    key = jax.random.PRNGKey(3)
    x = jax.random.normal(jax.random.PRNGKey(1), (32, 3))
    y = jnp.sin(x[:, :2])
    p = init(key)
    names = [f"params/{i}" for i in range(6)] + ["inputs/x"]
    rebuilt, doc, raw = interpret.through_bprime(
        apply,
        (p, x),
        role="forward",
        allowlist=allowlist,
        input_names=names,
        max_bytes=MAX_BYTES,
    )
    rinit, _, _ = interpret.through_bprime(
        init,
        (key,),
        role="init",
        allowlist=allowlist,
        input_names=["carbon/key"],
        max_bytes=MAX_BYTES,
    )
    assert graph.parse(raw, max_bytes=MAX_BYTES) == doc

    def via_graph(q, xx):
        return rebuilt(*jax.tree_util.tree_leaves(q), xx)[0]

    def fit(forward, start):
        def loss(q):
            return jnp.mean((forward(q, x) - y) ** 2)

        @jax.jit
        def step(q):
            return jax.tree_util.tree_map(
                lambda a, g: a - 0.05 * g, q, jax.grad(loss)(q)
            )

        first = float(loss(start))
        for _ in range(50):
            start = step(start)
        return start, first, float(loss(start))

    leaves = rinit(key)
    p_graph = [(leaves[i], leaves[i + 1]) for i in range(0, 6, 2)]
    for a, b in zip(jax.tree_util.tree_leaves(p), jax.tree_util.tree_leaves(p_graph)):
        assert np.array_equal(np.asarray(a), np.asarray(b))
    native, first_n, last_n = fit(apply, p)
    through, first_g, last_g = fit(via_graph, p_graph)
    assert last_g < first_g
    assert (first_n, last_n) == (first_g, last_g)
    for a, b in zip(
        jax.tree_util.tree_leaves(native), jax.tree_util.tree_leaves(through)
    ):
        assert np.array_equal(np.asarray(a), np.asarray(b))


def test_program_specimens_refused_at_their_gate(allowlist):
    results = specimens.run_programs(allowlist)
    assert results and all(r["expected"] == r["observed"] for r in results), results


def test_document_specimens_refused_at_their_gate(allowlist):
    results = specimens.run_documents(allowlist, MAX_BYTES)
    assert results and all(r["expected"] == r["observed"] for r in results), results


def test_oversized_document_refused():
    with pytest.raises(graph.GraphRefused) as refused:
        graph.parse(b'{"schema": "x"}', max_bytes=4)
    assert refused.value.code == "json_oversized_submission"


def test_constants_are_counted_never_capped(allowlist):
    rows = {r["specimen"]: r for r in specimens.run_constants(allowlist)}
    assert rows["embedded table"]["constant_bytes"] == 4096 * 4
    split = rows["table split into scalars"]
    assert split["constant_count"] >= 512 and split["constant_bytes"] >= 512 * 4
    for row in rows.values():
        assert set(row["caps"].values()) == {"blocked_human_input"}


def test_parameter_codec_refuses_unknown_kind_and_extras():
    with pytest.raises(graph.GraphRefused):
        params.decode({"y": "int"}, {"y": 2, "z": 1})
    with pytest.raises(graph.GraphRefused):
        params.decode({"y": "mystery"}, {"y": 2})


def test_battery_level0_equivalence_on_cpu(allowlist):
    from level4_spike.adapters import battery

    level0 = battery.level0_strategies()
    classic = battery.equivalence_classic(
        allowlist, level0["scaffold_mlp"], steps=16, max_bytes=MAX_BYTES
    )
    assert classic["copy_matches_declarative"], classic
    assert classic["bprime_matches_native"], classic
    general = battery.equivalence_general(
        allowlist, level0["panel_deeponet"], steps=16, max_bytes=MAX_BYTES
    )
    assert (
        general["bprime_matches_native"] and general["predictions_identical"]
    ), general
    assert general["review_ops_in_graphs"] == {}


def test_battery_torch_lowering_agrees_with_torch(allowlist):
    pytest.importorskip("torch")
    pytest.importorskip("neuralop")
    import jax.numpy as jnp
    import numpy as np
    import torch
    from level4_spike import lower_torch
    from level4_spike.adapters import battery

    for strategy in (
        battery.level0_strategies()["default_fno"],
        battery.strategy("mlp", {"backend": "pytorch"}),
    ):
        (p, net, _), (rp, rnet, _), f = battery.torch_build(strategy)
        _, core = lower_torch.export(net, p, f[:8])
        doc, lowering = lower_torch.lower(core, allowlist=allowlist)
        if strategy["backbone"] == "fno":
            # The captured module's own weights reach the export only through
            # dropped metadata assertions; pruning removes them, so they are
            # neither shipped nor counted as smuggled constants.
            assert lowering["pruned"]["constant_bytes"] > 0
            assert graph.measure(doc)["constant_bytes"] < 1024
        fn = interpret.rebuild(
            graph.parse(graph.dumps(doc), max_bytes=1 << 30), allowlist
        )
        got = np.asarray(
            fn(
                *[jnp.asarray(t.detach().numpy()) for t in rp],
                jnp.asarray(f[:8].numpy()),
            )[0]
        )
        with torch.no_grad():
            want = rnet(rp, f[:8]).as_subclass(torch.Tensor).numpy()
        # Cross-framework float32 agreement for the spike, not an R1 claim.
        assert np.max(np.abs(got - want)) <= 1e-4 * max(1.0, np.max(np.abs(want)))


def test_shared_modules_carry_no_challenge_literal():
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    banned = re.compile(
        r"battery|fastcharge|PublicMaterial|carbon\.battery", re.IGNORECASE
    )
    shared = [p for p in SPIKE.glob("*.py")]
    shared.append(allowlist_module.PATH)
    assert shared
    for path in shared:
        text = path.read_text()
        assert BATTERY_CHALLENGE not in text, path
        assert not banned.search(text), path
