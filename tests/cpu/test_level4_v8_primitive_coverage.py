"""Allowlist v8 names every primitive the pinned JAX can bind (OWNER-GRAPH-OPS-OPEN-01;
Validator VALIDATOR_GRAPH_OPS_V8_RULINGS_20261025, GRAPH_OPS_FREEDOM_AUDIT section 7.3 #1).

The audit found the graph route short of inverse trigonometry and 76 other ops by
reading names. This guard makes the gap impossible to reopen silently: every primitive
JAX defines is either an entry in v8's `carbon_ops` or listed below with the reason it is
not admitted, and a new JAX primitive fails here until someone decides.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path

import pytest

jax = pytest.importorskip("jax")

from carbon.level4 import allowlist as allowlist_module

V8 = Path(allowlist_module.__file__).with_name("allowlist_v8.json")

#: Containment: device meshes, placement and cross-device traffic belong to Carbon.
COLLECTIVES = [
    "all_gather_done",
    "all_gather_invariant",
    "all_gather_reduced",
    "all_gather_reduced_start",
    "all_gather_start",
    "all_to_all_done",
    "all_to_all_start",
    "pbroadcast",
    "pbroadcast_done",
    "pbroadcast_start",
    "pmax",
    "pmin",
    "ppermute_done",
    "ppermute_start",
    "precv",
    "preduced",
    "psend",
    "psum_done",
    "psum_invariant",
    "psum_invariant_start",
    "psum_start",
    "pvary",
    "ragged_all_to_all",
    "reduce_scatter",
    "reduce_scatter_done",
    "reduce_scatter_start",
    "reduced_vary_cast_p",
    "unreduced_psum",
    "unreduced_psum_start",
    "unreduced_reduce_scatter",
    "unreduced_reduce_scatter_start",
    "vary_unreduced_cast_p",
    "shard_map",
    "reshard",
]
#: Side effects: mutable references are state, and the format is pure.
MUTABLE_STATE = [
    "get",
    "swap",
    "addupdate",
    "new_ref",
    "empty_ref",
    "free_ref",
    "freeze",
    "accum_grad_in_ref",
    "pin",
    "unpin",
    "broadcast_to",
    "create_linear",
]
#: Not reproducible: uninitialised memory. (`platform_index` is admitted: JAX's platform
#: dispatch, whose branches compute the same values.)
NOT_REPRODUCIBLE = ["empty", "empty2"]
#: Typed PRNG keys convert only through Carbon's keyed `random_*` ops, in init graphs.
KEY_CONVERSIONS = ["to_edtype", "from_edtype", "random_gamma", "random_clone"]
#: Autodiff and compiler plumbing: never part of a traced forward a miner writes.
INTERNAL = [
    "call",
    "call_hi_primitive",
    "composite",
    "custom_lin",
    "custom_jvp_call_jaxpr",
    "linear_call",
    "remat_opt",
    "eval_jaxpr",
    "unreachable",
    "dce_sink",
    "stage",
    "tie",
    "name",
    "inspect_sharding",
    "zeros_like",
]
#: Pure ops still to admit: each needs a parameter codec (a nested body, a recall target)
#: that this head does not carry. Not a policy refusal.
PENDING = [
    "ragged_dot_general",
    "reduce",
    "reduce_window",
    "select_and_scatter",
    "symmetric_product",
    "scaled_dot",
]

NOT_ADMITTED = {
    **{n: "collective or placement: containment" for n in COLLECTIVES},
    **{n: "mutable reference: a side effect" for n in MUTABLE_STATE},
    **{n: "not reproducible" for n in NOT_REPRODUCIBLE},
    **{
        n: "typed key conversion: Carbon's keyed random ops only"
        for n in KEY_CONVERSIONS
    },
    **{n: "internal plumbing" for n in INTERNAL},
    **{n: "pending: pure, needs a parameter codec" for n in PENDING},
}


def _primitives():
    from jax.extend.core import Primitive

    found = {}

    def scan(module):
        for name in dir(module):
            value = getattr(module, name, None)
            if name.endswith("_p") and isinstance(value, Primitive):
                found.setdefault(value.name.replace("-", "_"), module.__name__)

    import jax._src.lax as lax_package
    import jax.extend.core.primitives as public

    scan(public)
    for info in pkgutil.walk_packages(lax_package.__path__, "jax._src.lax."):
        try:
            scan(importlib.import_module(info.name))
        except ImportError:
            continue
    for extra in (
        "jax._src.random",
        "jax._src.custom_derivatives",
        "jax._src.ad_checkpoint",
        "jax._src.pjit",
        "jax._src.debugging",
        "jax._src.state.primitives",
        "jax._src.ad_util",
        "jax._src.core",
        "jax._src.shard_map",
    ):
        try:
            scan(importlib.import_module(extra))
        except ImportError:
            continue
    return found


def test_every_jax_primitive_is_admitted_or_listed_with_its_reason():
    ops = json.loads(V8.read_text(encoding="utf-8"))["carbon_ops"]
    unknown = sorted(
        name for name in _primitives() if name not in ops and name not in NOT_ADMITTED
    )
    assert not unknown, (
        "JAX defines primitives allowlist v8 neither admits nor lists as not admitted "
        f"(decide each one): {unknown}"
    )


def test_the_not_admitted_list_does_not_rot():
    ops = json.loads(V8.read_text(encoding="utf-8"))["carbon_ops"]
    for name in NOT_ADMITTED:
        entry = ops.get(name)
        usable = (
            entry is not None
            and entry["default"] not in ("refuse", "strip")
            and entry["v0_interpreter"]
        )
        assert not usable, f"{name} is admitted by v8 but still listed as not admitted"


def test_the_refused_ops_name_their_reason():
    ops = json.loads(V8.read_text(encoding="utf-8"))["carbon_ops"]
    for name, entry in ops.items():
        if entry["default"] in ("refuse", "strip"):
            assert entry.get("note") or entry["category"], name
