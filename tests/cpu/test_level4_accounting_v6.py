"""Fitted-information accounting v6 (Validator WIRING_CHANNEL_AND_LOOKUP_P0_RULING_20261030):
the 16 KiB budget bounds the zlib-9 size of the whole canonical recipe, so operand wiring and
topology count. Replaces the strict xfail of the wiring-channel audit."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("jax")

import jax.numpy as jnp

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, validate
from carbon.level4.tooling import lower_jax

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


def test_v6_is_served_with_allowlist_v8_to_the_four_launch_versions_only():
    from carbon.challenge_kit import version_registry

    assert allowlist_module.ACCOUNTING_V6_VERSIONS == frozenset({"level4-allowlist-v8"})
    assert allowlist_module.accounting_for(V8)[0] == "level4-constant-accounting-v6"
    launch = [
        ("electric-motor-magnetics", "1.5"),
        ("chip-cold-plate", "1.6"),
        ("f08-ribbed-bracket", "1.7"),
        ("f02", "2.5"),
    ]
    for key in launch:
        version = "level4-allowlist-" + version_registry.entry(*key).allowlist
        assert (
            allowlist_module.accounting_for(version)[0]
            == "level4-constant-accounting-v6"
        )
    for old in ("level4-allowlist-v6", "level4-allowlist-v7"):
        assert (
            allowlist_module.accounting_for(old)[0] == "level4-constant-accounting-v3"
        )


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


def test_the_same_graph_written_differently_measures_the_same_on_the_real_parse_path():
    """The submission path is `graph.parse` over raw bytes: key order, whitespace and a shifted
    numbering of the value ids must not move the measured size (which is the canonical, relative form).
    """
    import json

    doc = _wired_table(_random(2_000, levels=16, seed=7), levels=16)
    base = graph.parse(graph.dumps(doc), max_bytes=10**8)
    reordered = json.dumps(base, indent=2, sort_keys=False).encode()
    swapped = json.dumps({k: base[k] for k in reversed(list(base))}).encode()
    sizes = {
        graph.recipe_info_bytes(graph.parse(raw, max_bytes=10**8))
        for raw in (reordered, swapped)
    }
    assert sizes == {graph.recipe_info_bytes(base)}

    shifted = json.loads(graph.dumps(base))
    for g in shifted["graphs"].values():
        for entry in g["inputs"] + g["constants"]:
            entry["value"] += 1000
        for node in g["nodes"]:
            node["in"] = [i + 1000 for i in node["in"]]
            for out in node["out"]:
                out["value"] += 1000
        g["outputs"] = [o + 1000 for o in g["outputs"]]
    # absolute ids change the bytes; the relative measure of the first definition differs only by that offset
    assert (
        graph.recipe_info_bytes(
            graph.parse(json.dumps(shifted).encode(), max_bytes=10**8)
        )
        <= graph.recipe_info_bytes(base) + 8
    )


def test_repeated_layers_cost_the_same_wherever_they_sit(v6):
    """Relative ids: a repeated layer has identical bytes, so a deeper model of the same shape adds little."""
    shallow = graph.recipe_info_bytes(_wired_table([0, 1] * 5_000))
    deep = graph.recipe_info_bytes(_wired_table([0, 1] * 50_000))
    assert deep < shallow * 3


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
