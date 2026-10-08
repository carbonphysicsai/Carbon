"""Carbon-built initialization for graphs that carry no init graph (Q3).

A `torch.export` program has no init function. Carbon builds one itself: the
shape and dtype of every parameter come from the forward graph's declared
inputs, the values come from Carbon's key and Carbon's initializer menu, and
the module's own initialization never reaches Carbon (its weights are not in
the document; lowering prunes them).

The miner declares only, per parameter, a menu name and which axes count as
fan-in and fan-out. That declaration is a strict-JSON document:

    {"schema": SCHEMA, "graph": "<sha256 of the forward document>",
     "parameters": [{"input": "params/0", "initializer": "he_normal",
                     "fan_in_axes": [0], "fan_out_axes": [1]}, ...]}

Every `params/*` input needs exactly one entry; anything else refuses. The
menu's scale rules are the standard named initializers; which names a
Challenge admits is the Challenge's (its adapter may narrow the menu).
"""

from __future__ import annotations

import math

from . import graph

SCHEMA = "carbon.development.level4-init-spec.v0"
MENU = ("he_normal", "glorot_normal", "lecun_normal", "zeros")
_ENTRY_KEYS = {"input", "initializer", "fan_in_axes", "fan_out_axes"}


def parse(raw, *, max_bytes):
    from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy

    try:
        spec = parse_strategy(raw, max_bytes=max_bytes)
    except MalformedStrategy as refused:
        raise graph.GraphRefused("json_" + refused.code) from None
    if set(spec) != {"schema", "graph", "parameters"} or spec["schema"] != SCHEMA:
        raise graph.GraphRefused("init_spec_malformed")
    return spec


def _axes(value, rank, where):
    if type(value) is not list or not all(type(a) is int for a in value):
        raise graph.GraphRefused("init_spec_axes", where)
    if len(set(value)) != len(value) or any(not 0 <= a < rank for a in value):
        raise graph.GraphRefused("init_spec_axes", where)
    return value


def _scale(name, shape, fan_in_axes, fan_out_axes):
    fan_in = math.prod(shape[a] for a in fan_in_axes) if fan_in_axes else 1
    fan_out = math.prod(shape[a] for a in fan_out_axes) if fan_out_axes else 1
    if name == "he_normal":
        return math.sqrt(2.0 / fan_in)
    if name == "glorot_normal":
        return math.sqrt(2.0 / (fan_in + fan_out))
    return math.sqrt(1.0 / fan_in)  # lecun_normal


def build(spec, doc, *, menu=MENU):
    """`init(key) -> [arrays]` in the forward graph's parameter order."""
    if spec["graph"] != graph.digest(doc):
        raise graph.GraphRefused("init_spec_graph_mismatch")
    params = [
        i
        for i in doc["graphs"][doc["entry"]]["inputs"]
        if i["name"].startswith("params/")
    ]
    entries = spec["parameters"]
    if type(entries) is not list or [e.get("input") for e in entries] != [
        p["name"] for p in params
    ]:
        raise graph.GraphRefused("init_spec_parameters_mismatch")
    plan = []
    for entry, param in zip(entries, params):
        where = param["name"]
        if type(entry) is not dict or set(entry) != _ENTRY_KEYS:
            raise graph.GraphRefused("init_spec_malformed", where)
        if entry["initializer"] not in menu:
            raise graph.GraphRefused("initializer_not_in_menu", where)
        if not param["dtype"].startswith("float"):
            raise graph.GraphRefused("init_spec_dtype", where)
        rank = len(param["shape"])
        fan_in = _axes(entry["fan_in_axes"], rank, where)
        fan_out = _axes(entry["fan_out_axes"], rank, where)
        scale = (
            None
            if entry["initializer"] == "zeros"
            else _scale(entry["initializer"], param["shape"], fan_in, fan_out)
        )
        plan.append((tuple(param["shape"]), param["dtype"], scale))

    def init(key):
        import jax
        import jax.numpy as jnp

        keys = jax.random.split(key, len(plan))
        out = []
        for k, (shape, dtype, scale) in zip(keys, plan):
            if scale is None:
                out.append(jnp.zeros(shape, dtype))
            else:
                out.append(
                    jax.random.normal(k, shape, dtype) * jnp.asarray(scale, dtype)
                )
        return out

    return init
