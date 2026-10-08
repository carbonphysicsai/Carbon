"""Gate G4: validate a parsed graph document (development only).

In order:

1. the allowlist (`allowlist.check`): every op admitted in the document's
   role, parameters within their kinds, named functions registered, typed
   keys only where RNG is admitted;
   then the declared shapes (`check_declared_shapes`): every node's declared
   dtype and shape against abstract evaluation of the rebuilt graph;
2. the expected role, when the caller names one;
3. the Challenge's interface (forward graphs, when the adapter supplies one):
   inputs other than `params/*` are exactly the interface's named inputs,
   with their dtypes and per-case shapes, and the outputs match; every input
   and output shares one leading batch dimension;
4. the caps (`allowlist.CAPS`): each measured count against the Challenge's
   value. An unset cap (`HUMAN_INPUT`) blocks; it never admits.

A refusal raises `graph.GraphRefused` with a typed code: a construction
refusal, never a physics failure and never `FAILED_INFRA`. A document that
passes every check is `admitted` only when every cap is set and met;
otherwise the verdict is `blocked_human_input`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from . import allowlist as allowlist_module
from . import graph

PARAMETER_PREFIX = "params/"
INPUT_PREFIX = "inputs/"


@dataclass(frozen=True)
class Interface:
    """A Challenge's Level 4 boundary: named inputs and outputs, each a dtype
    and a per-case shape (the batch dimension is not part of it)."""

    inputs: tuple[tuple[str, str, tuple[int, ...]], ...]
    outputs: tuple[tuple[str, tuple[int, ...]], ...]

    def document(self):
        return {
            "inputs": [[n, d, list(s)] for n, d, s in self.inputs],
            "outputs": [[d, list(s)] for d, s in self.outputs],
        }

    def digest(self):
        body = json.dumps(self.document(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def _batch(shape, case, code, where, batches):
    if len(shape) != len(case) + 1 or list(shape[1:]) != list(case):
        raise graph.GraphRefused(code, where)
    if shape[0] < 1:
        raise graph.GraphRefused("interface_batch", where)
    batches.add(shape[0])


def check_interface(doc, interface):
    """The batch size a forward graph declares, or `GraphRefused`."""
    entry = doc["graphs"][doc["entry"]]
    named = {
        i["name"]: i
        for i in entry["inputs"]
        if not i["name"].startswith(PARAMETER_PREFIX)
    }
    expected = {name for name, _, _ in interface.inputs}
    for name in named:
        if not name.startswith(INPUT_PREFIX) or name not in expected:
            raise graph.GraphRefused("interface_input_unexpected")
    batches = set()
    for name, dtype, case in interface.inputs:
        if name not in named:
            raise graph.GraphRefused("interface_input_missing")
        if named[name]["dtype"] != dtype:
            raise graph.GraphRefused("interface_dtype", name)
        _batch(named[name]["shape"], case, "interface_shape", name, batches)
    values = {}
    for i in entry["inputs"]:
        values[i["value"]] = i
    for c in entry["constants"]:
        values[c["value"]] = c
    for node in entry["nodes"]:
        for out in node["out"]:
            values[out["value"]] = out
    outputs = entry["outputs"]
    if len(outputs) != len(interface.outputs):
        raise graph.GraphRefused("interface_output_count")
    for k, (value_id, (dtype, case)) in enumerate(zip(outputs, interface.outputs)):
        aval = values[value_id]
        if aval["dtype"] != dtype:
            raise graph.GraphRefused("interface_dtype", f"output {k}")
        _batch(aval["shape"], case, "interface_shape", f"output {k}", batches)
    if len(batches) != 1:
        raise graph.GraphRefused("interface_batch")
    return batches.pop()


KEY_INPUT = "carbon/key"
#: Ops that keep a uniform fill uniform (a fill is a value every element of
#: which equals one scalar constant): shape-preserving rearrangements, plus
#: every op the allowlist classifies as elementwise.
_FILL_SHAPE_OPS = frozenset({"broadcast_in_dim", "reshape", "squeeze", "transpose"})


def _entry_values(g):
    values = {}
    for i in g["inputs"]:
        values[i["value"]] = i
    for c in g["constants"]:
        values[c["value"]] = c
    for node in g["nodes"]:
        for out in node["out"]:
            values[out["value"]] = out
    return values


def _init_flow(doc, allowlist, name, inputs):
    """Per output of graph `name`: (keyed, uniform fill), given the inputs'."""
    g = doc["graphs"][name]
    props = {i["value"]: p for i, p in zip(g["inputs"], inputs)}
    for c in g["constants"]:
        props[c["value"]] = (False, c["shape"] == [])
    for node in g["nodes"]:
        ins = [props[v] for v in node["in"]]
        if node["op"] in graph.CALL_OPS:
            ref = graph.graph_refs(node["params"])[0]
            outs = _init_flow(doc, allowlist, ref, ins)
        else:
            keyed = any(k for k, _ in ins)
            category = allowlist.ops.get(node["op"], {}).get("category")
            preserves = node["op"] in _FILL_SHAPE_OPS or category == "elementwise"
            fill = (not keyed) and bool(ins) and preserves and all(f for _, f in ins)
            outs = [(keyed, fill)] * len(node["out"])
        for out, p in zip(node["out"], outs):
            props[out["value"]] = p
    return [props[v] for v in g["outputs"]]


def check_init(doc, allowlist):
    """An init graph takes only Carbon's key, and every output it returns is
    derived from that key or is a uniform fill (zeros, ones, a constant).

    A parameter built from neither, a table from `iota` arithmetic or one
    assembled from pieces, is refused (§8.3 initializer abuse). Arithmetic
    can still hide a fixed table behind the key; the constant cap and D4
    (procedural tables) own what data flow cannot see. An init graph never
    returns a key: Carbon's training key is Carbon's (`train.keys`)."""
    if doc["role"] != "init":
        raise graph.GraphRefused("role_mismatch")
    entry = doc["graphs"][doc["entry"]]
    inputs = entry["inputs"]
    if [i["name"] for i in inputs] != [KEY_INPUT] or (
        inputs[0]["dtype"],
        inputs[0]["shape"],
    ) != ("uint32", [2]):
        raise graph.GraphRefused("init_input_malformed")
    values = _entry_values(entry)
    for k, value_id in enumerate(entry["outputs"]):
        if values[value_id]["dtype"] in graph.KEY_DTYPES or (
            values[value_id]["dtype"],
            values[value_id]["shape"],
        ) == ("uint32", [2]):
            raise graph.GraphRefused("init_returns_key", f"output {k}")
    for k, (keyed, fill) in enumerate(
        _init_flow(doc, allowlist, doc["entry"], [(True, False)])
    ):
        if not (keyed or fill):
            raise graph.GraphRefused("init_output_not_keyed", f"output {k}")


_WIDE = frozenset({"float64", "int64", "uint64", "complex128"})


def check_declared_shapes(doc, allowlist):
    """Every node's declared dtype and shape, checked by evaluating the
    rebuilt graph abstractly (`jax.eval_shape`: shapes only, no data, no
    compile). A document whose declarations lie is refused here, at G4,
    with `declared_aval_mismatch`, before anything is compiled or trained.
    (Found by the Level 4 attack adapter: a lie caught only on execution
    would surface inside G6 training, untyped.)"""
    import jax

    from . import interpret

    entry = doc["graphs"][doc["entry"]]
    if any(i["dtype"] in graph.KEY_DTYPES for i in entry["inputs"]):
        return  # typed-key inputs exist only in init graphs, checked by data flow
    rebuilt = interpret.rebuild(doc, allowlist)
    wide = any(
        o["dtype"] in _WIDE
        for g in doc["graphs"].values()
        for o in g["inputs"] + [out for n in g["nodes"] for out in n["out"]]
    )
    structs = [
        jax.ShapeDtypeStruct(tuple(i["shape"]), i["dtype"]) for i in entry["inputs"]
    ]
    with jax.enable_x64(wide):
        jax.eval_shape(lambda *args: rebuilt(*args), *structs)


def validate(doc, allowlist, *, role=None, interface=None, batch=None, caps=None):
    """G4's verdict for a parsed document, or `GraphRefused`.

    `batch`, when given, is the batch the forward graph must be lowered at
    (the recipe's training batch; Phase 1 finding: per-case graphs batched by
    `vmap` do not train bit-identically for every family)."""
    flags = allowlist.check(doc)
    check_declared_shapes(doc, allowlist)
    if role is not None and doc["role"] != role:
        raise graph.GraphRefused("role_mismatch")
    if doc["role"] == "init":
        check_init(doc, allowlist)
    declared = None
    if interface is not None:
        if doc["role"] != "forward":
            raise graph.GraphRefused("interface_needs_forward_graph")
        declared = check_interface(doc, interface)
        if batch is not None and declared != batch:
            raise graph.GraphRefused("interface_batch")
    batch = declared
    measurements = graph.measure(doc)
    # A cap the caller does not name is the owner's (`allowlist.CAPS`); one a
    # caller sets to HUMAN_INPUT blocks, it never passes.
    verdicts = allowlist_module.check_caps(
        measurements, {**allowlist_module.CAPS, **(caps or {})}
    )
    exceeded = sorted(name for name, v in verdicts.items() if v == "refuse")
    if exceeded:
        raise graph.GraphRefused("cap_exceeded", ",".join(exceeded))
    status = (
        "admitted"
        if all(v == "pass" for v in verdicts.values())
        else "blocked_human_input"
    )
    return {
        "status": status,
        "role": doc["role"],
        "document": graph.digest(doc),
        "allowlist": {"version": allowlist.version, "digest": allowlist.digest},
        "interface": None if interface is None else interface.digest(),
        "batch": batch,
        "review_flags": flags,
        "measurements": measurements,
        "caps": verdicts,
    }


def parameters(doc):
    """A forward graph's parameter inputs, in order: `[(name, dtype, shape)]`."""
    entry = doc["graphs"][doc["entry"]]
    return [
        (i["name"], i["dtype"], i["shape"])
        for i in entry["inputs"]
        if i["name"].startswith(PARAMETER_PREFIX)
    ]


def validate_submission(parsed, allowlist, *, interface, batch=None, caps=None):
    """G4 over a verified submission (`submission.verify`): every document,
    then the init graph's outputs against the forward graph's parameters.
    The submission's status is the strictest of its documents'."""
    from . import initializers

    verdicts = {
        "forward": validate(
            parsed["forward"],
            allowlist,
            role="forward",
            interface=interface,
            batch=batch,
            caps=caps,
        )
    }
    if "loss" in parsed:
        verdicts["loss"] = validate(parsed["loss"], allowlist, role="loss", caps=caps)
    wanted = [(d, s) for _, d, s in parameters(parsed["forward"])]
    if "init" in parsed:
        verdicts["init"] = validate(parsed["init"], allowlist, role="init", caps=caps)
        entry = parsed["init"]["graphs"][parsed["init"]["entry"]]
        values = _entry_values(entry)
        got = [(values[v]["dtype"], values[v]["shape"]) for v in entry["outputs"]]
        if got != wanted:
            raise graph.GraphRefused("init_outputs_mismatch")
    else:
        initializers.build(parsed["init_spec"], parsed["forward"])
    statuses = {v["status"] for v in verdicts.values()}
    return {
        "status": "admitted" if statuses == {"admitted"} else "blocked_human_input",
        "batch": verdicts["forward"]["batch"],
        "documents": verdicts,
    }
