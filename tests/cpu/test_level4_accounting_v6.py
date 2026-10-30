"""Fitted-information accounting v6 (Validator WIRING_CHANNEL_AND_LOOKUP_P0_RULING_20261030):
the 16 KiB budget bounds the zlib-9 size of the whole canonical recipe, so operand wiring and
topology count. Replaces the strict xfail of the wiring-channel audit."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("jax")

import jax.numpy as jnp  # noqa: E402

from carbon.level4 import allowlist as allowlist_module  # noqa: E402
from carbon.level4 import graph, validate  # noqa: E402
from carbon.level4.tooling import lower_jax  # noqa: E402

HERE = Path(allowlist_module.__file__).parent
V8 = allowlist_module.load(HERE / "allowlist_v8.json")
CAP = allowlist_module.CAPS["constant_bytes"]


@pytest.fixture
def v6(monkeypatch):
    monkeypatch.setattr(
        allowlist_module,
        "ACCOUNTING_V6_VERSIONS",
        frozenset({V8.version}),
    )


def _wired_table(symbols, levels=2):
    values = [jnp.full((1,), 0.125 * (i + 1), jnp.float32) for i in range(levels)]

    def table(x):
        return jnp.concatenate([values[int(s)] for s in symbols])

    closed = lower_jax.trace(table, jnp.zeros(2, jnp.float32))
    return lower_jax.lower(
        closed, role="forward", allowlist=V8, input_names=["inputs/x"]
    )


def _random(n, levels=2, seed=1):
    return np.random.default_rng(seed).integers(0, levels, n)


def test_v6_is_not_served_until_registered():
    assert allowlist_module.ACCOUNTING_V6_VERSIONS == frozenset()
    assert allowlist_module.accounting_for(V8)[0] == "level4-constant-accounting-v5"


def test_the_200k_operand_concatenate_is_refused(v6):
    doc = _wired_table(_random(200_000))
    assert allowlist_module.accounting_for(V8)[0] == "level4-constant-accounting-v6"
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(doc, V8, role="forward")
    assert refused.value.code == "fitted_info_over_budget"


def test_wiring_that_encodes_random_bytes_is_refused_once_over_the_budget(v6):
    # 8 bits per operand: 256 levels. Random bytes do not compress.
    under = _wired_table(_random(CAP // 2, levels=256, seed=2), levels=256)
    assert graph.recipe_info_bytes(under) < CAP
    validate.validate(under, V8, role="forward")
    over = _wired_table(_random(CAP * 2, levels=256, seed=3), levels=256)
    assert graph.recipe_info_bytes(over) > CAP
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(over, V8, role="forward")
    assert refused.value.code == "fitted_info_over_budget"


def test_a_regular_graph_compresses_far_below_its_size(v6):
    doc = _wired_table([0, 1] * 50_000)
    assert len(graph.dumps(doc)) > 150_000
    assert graph.recipe_info_bytes(doc) < 2_000
    validate.validate(doc, V8, role="forward")


def test_canonicalisation_is_byte_identical():
    doc = _wired_table(_random(500))
    shuffled = {k: doc[k] for k in reversed(list(doc))}
    assert graph.recipe_info_bytes(doc) == graph.recipe_info_bytes(shuffled)


def test_the_budget_is_the_submissions_not_each_documents(v6):
    half = _wired_table(_random(CAP * 3 // 8, levels=256, seed=4), levels=256)
    assert graph.recipe_info_bytes(half) < CAP
    other = _wired_table(_random(CAP * 3 // 8, levels=256, seed=5), levels=256)
    assert graph.recipe_info_bytes(half, other) > CAP
    verdict = validate.validate(half, V8, role="forward")
    with pytest.raises(graph.GraphRefused) as refused:
        validate.check_submission_budget(
            {"forward": verdict},
            V8,
            parsed={"forward": half, "loss": other},
        )
    assert refused.value.code == "fitted_info_over_budget"
