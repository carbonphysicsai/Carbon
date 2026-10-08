"""The Carbon graph format v0 (B'): strict JSON, one node per allowlisted op.

A document is::

    {"schema": SCHEMA, "allowlist": "<allowlist version>", "role": "forward",
     "entry": "main",
     "graphs": {"main": {"inputs": [...], "constants": [...],
                         "nodes": [...], "outputs": [...]}, ...}}

* every value has an integer id, unique in its graph, defined before use;
* `inputs`: `{"value", "name", "dtype", "shape"}` (Carbon feeds them);
* `constants`: `{"value", "dtype", "shape", "bytes", "data"}`; `data` is the
  base64 of the little-endian bytes and `bytes` its declared length, so the
  total embedded bytes are counted without decoding;
* `nodes`: `{"op", "in", "out", "params"}`; `out` declares each result's
  dtype and shape, which the interpreter checks against what the op returns;
* a parameter `{"graph": "<name>"}` names another graph of the document (a
  nested call), never a definition inline, so JSON depth stays bounded and
  call depth is measured separately.

Parsing uses Carbon's existing strict JSON rules
(`carbon.challenge_validator.strict_json`). Nothing here deserializes a
third-party format. Refusals carry a typed code and never echo content.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re

SCHEMA = "carbon.development.level4-graph.v0"
ROLES = ("forward", "init", "loss")
#: Array dtypes the format can carry, with their item sizes.
DTYPES = {
    "bool": 1,
    "uint8": 1,
    "uint32": 4,
    "uint64": 8,
    "int32": 4,
    "int64": 8,
    "bfloat16": 2,
    "float16": 2,
    "float32": 4,
    "float64": 8,
    "complex64": 8,
    "complex128": 16,
}
#: Extended dtypes: typed PRNG keys. Never constants; the allowlist limits
#: the ops (and so the roles) that can produce or consume them.
KEY_DTYPES = {"key<fry>": 8}
_GRAPH_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_INPUT_NAME = re.compile(r"[A-Za-z0-9_./\[\]-]{1,128}\Z")
_NODE_KEYS = {"op", "in", "out", "params"}
_GRAPH_KEYS = {"inputs", "constants", "nodes", "outputs"}
_TOP_KEYS = {"schema", "allowlist", "role", "entry", "graphs"}


#: Ops whose parameter of kind "graph" names a nested graph, run inline.
CALL_OPS = ("jit", "closed_call", "custom_jvp_call")


class GraphRefused(ValueError):
    """A typed refusal. `code` is stable; `where` locates it without content."""

    def __init__(self, code, where=""):
        super().__init__(code if not where else f"{code} at {where}")
        self.code, self.where = code, where


def itemsize(dtype):
    if dtype in DTYPES:
        return DTYPES[dtype]
    if dtype in KEY_DTYPES:
        return KEY_DTYPES[dtype]
    raise GraphRefused("dtype_not_allowed")


def nbytes(aval):
    return math.prod(aval["shape"]) * itemsize(aval["dtype"])


def encode_array(array):
    """A constant entry (without its value id) for a numpy array."""
    import numpy as np

    a = np.asarray(array)  # not ascontiguousarray: it makes a scalar 1-d
    dtype = str(a.dtype)
    if dtype not in DTYPES:
        raise GraphRefused("dtype_not_allowed")
    raw = a.astype(a.dtype.newbyteorder("<"), copy=False).tobytes(order="C")
    return {
        "dtype": dtype,
        "shape": list(a.shape),
        "bytes": len(raw),
        "data": base64.b64encode(raw).decode("ascii"),
    }


def decode_array(entry, where=""):
    """The numpy array a constant entry holds, after its counts are checked."""
    import numpy as np

    if entry["dtype"] not in DTYPES:
        raise GraphRefused("constant_dtype_not_allowed", where)
    expected = math.prod(entry["shape"]) * DTYPES[entry["dtype"]]
    if entry["bytes"] != expected:
        raise GraphRefused("constant_bytes_mismatch", where)
    try:
        raw = base64.b64decode(entry["data"].encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        raise GraphRefused("constant_not_base64", where) from None
    if len(raw) != expected:
        raise GraphRefused("constant_bytes_mismatch", where)
    if entry["dtype"] == "bfloat16":
        import ml_dtypes

        dtype = np.dtype(ml_dtypes.bfloat16)
    else:
        dtype = np.dtype(entry["dtype"]).newbyteorder("<")
    return np.frombuffer(raw, dtype=dtype).reshape(entry["shape"]).copy()


def dumps(doc):
    """Canonical bytes: sorted keys, no whitespace, UTF-8."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()


def digest(doc):
    return "sha256:" + hashlib.sha256(dumps(doc)).hexdigest()


def parse(raw, *, max_bytes):
    """The document in `raw`, through strict JSON and the structure check.

    `max_bytes` is the caller's; this module chooses no limit (G0's source
    size and G3's graph size limits are `HUMAN_INPUT`)."""
    from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy

    try:
        doc = parse_strategy(raw, max_bytes=max_bytes)
    except MalformedStrategy as refused:
        raise GraphRefused("json_" + refused.code) from None
    check_structure(doc)
    return doc


def _is_int(value):
    return type(value) is int


def _aval(value, where):
    if type(value) is not dict or set(value) - {"value", "name", "dtype", "shape"}:
        raise GraphRefused("aval_malformed", where)
    shape = value.get("shape")
    if type(shape) is not list or not all(_is_int(d) and d >= 0 for d in shape):
        raise GraphRefused("shape_malformed", where)
    if value.get("dtype") not in DTYPES and value.get("dtype") not in KEY_DTYPES:
        raise GraphRefused("dtype_not_allowed", where)


def graph_refs(params):
    """Names of the graphs a node's parameters call."""
    return [
        v["graph"]
        for v in params.values()
        if type(v) is dict and set(v) == {"graph"} and type(v["graph"]) is str
    ]


def check_structure(doc):
    """Shape of the document only: ids, avals, references, no cycles.

    Op membership, parameters and roles are the allowlist's (G4), checked by
    `allowlist.check`; declared shapes are checked again when interpreted."""
    if type(doc) is not dict or set(doc) != _TOP_KEYS:
        raise GraphRefused("document_keys")
    if doc["schema"] != SCHEMA:
        raise GraphRefused("schema_unknown")
    if doc["role"] not in ROLES:
        raise GraphRefused("role_unknown")
    graphs = doc["graphs"]
    if type(graphs) is not dict or doc["entry"] not in graphs:
        raise GraphRefused("entry_missing")
    for name, g in graphs.items():
        if not _GRAPH_NAME.match(name):
            raise GraphRefused("graph_name_malformed")
        if type(g) is not dict or set(g) != _GRAPH_KEYS:
            raise GraphRefused("graph_keys", name)
        defined = set()

        def define(value_id, where, _defined=defined, _name=name):
            if not _is_int(value_id) or value_id < 0 or value_id in _defined:
                raise GraphRefused("value_id_invalid", where)
            _defined.add(value_id)

        for i, entry in enumerate(g["inputs"]):
            where = f"{name}.inputs[{i}]"
            _aval(entry, where)
            if not _INPUT_NAME.match(str(entry.get("name", ""))):
                raise GraphRefused("input_name_malformed", where)
            define(entry.get("value"), where)
        for i, entry in enumerate(g["constants"]):
            where = f"{name}.constants[{i}]"
            if type(entry) is not dict or set(entry) != {
                "value",
                "dtype",
                "shape",
                "bytes",
                "data",
            }:
                raise GraphRefused("constant_malformed", where)
            _aval({"dtype": entry["dtype"], "shape": entry["shape"]}, where)
            if entry["dtype"] in KEY_DTYPES:
                raise GraphRefused("constant_dtype_not_allowed", where)
            if not _is_int(entry["bytes"]) or type(entry["data"]) is not str:
                raise GraphRefused("constant_malformed", where)
            if entry["bytes"] != nbytes(entry):
                raise GraphRefused("constant_bytes_mismatch", where)
            define(entry["value"], where)
        for i, node in enumerate(g["nodes"]):
            where = f"{name}.nodes[{i}]"
            if type(node) is not dict or set(node) != _NODE_KEYS:
                raise GraphRefused("node_keys", where)
            if type(node["op"]) is not str or type(node["params"]) is not dict:
                raise GraphRefused("node_malformed", where)
            if type(node["in"]) is not list or type(node["out"]) is not list:
                raise GraphRefused("node_malformed", where)
            for value_id in node["in"]:
                if value_id not in defined:
                    raise GraphRefused("value_undefined", where)
            for out in node["out"]:
                _aval(out, where)
                define(out.get("value"), where)
            for ref in graph_refs(node["params"]):
                if ref not in graphs:
                    raise GraphRefused("graph_reference_unknown", where)
        if type(g["outputs"]) is not list or not all(
            o in defined for o in g["outputs"]
        ):
            raise GraphRefused("output_undefined", name)
    call_depth(doc)  # refuses cycles


def prune(doc):
    """Drop nodes, constants and graphs no output depends on (all ops are
    pure). Lowering tools run this on the miner's side; the validator still
    counts every constant byte a document declares. Returns what was pruned."""
    graphs = doc["graphs"]
    pruned = {"nodes": 0, "constants": 0, "constant_bytes": 0, "graphs": 0}
    for g in graphs.values():
        live = set(g["outputs"])
        keep = []
        for node in reversed(g["nodes"]):
            if any(out["value"] in live for out in node["out"]):
                keep.append(node)
                live.update(node["in"])
        pruned["nodes"] += len(g["nodes"]) - len(keep)
        g["nodes"] = keep[::-1]
        dead = [c for c in g["constants"] if c["value"] not in live]
        pruned["constants"] += len(dead)
        pruned["constant_bytes"] += sum(c["bytes"] for c in dead)
        g["constants"] = [c for c in g["constants"] if c["value"] in live]
    reachable, stack = set(), [doc["entry"]]
    while stack:
        name = stack.pop()
        if name not in reachable:
            reachable.add(name)
            stack.extend(
                r for n in graphs[name]["nodes"] for r in graph_refs(n["params"])
            )
    for name in [n for n in graphs if n not in reachable]:
        del graphs[name]
        pruned["graphs"] += 1
    return pruned


def call_depth(doc):
    """The deepest chain of nested calls from the entry (entry alone = 1)."""
    graphs, memo = doc["graphs"], {}

    def depth(name, stack):
        if name in stack:
            raise GraphRefused("graph_call_cycle", name)
        if name not in memo:
            refs = [
                r for node in graphs[name]["nodes"] for r in graph_refs(node["params"])
            ]
            memo[name] = 1 + max((depth(r, stack | {name}) for r in refs), default=0)
        return memo[name]

    return depth(doc["entry"], frozenset())


def measure(doc):
    """D6 inputs: counts only. Nothing here compares against a cap."""
    graphs = doc["graphs"]
    op_counts, executed = {}, 0
    # Executed node count: a call node expands to its graph each time it runs.
    sizes = {}

    def expanded(name):
        if name not in sizes:
            total = 0
            for node in graphs[name]["nodes"]:
                refs = graph_refs(node["params"])
                total += 1 + sum(expanded(r) for r in refs)
            sizes[name] = total
        return sizes[name]

    for g in graphs.values():
        for node in g["nodes"]:
            op_counts[node["op"]] = op_counts.get(node["op"], 0) + 1
    executed = expanded(doc["entry"])
    constants = [c for g in graphs.values() for c in g["constants"]]
    entry = graphs[doc["entry"]]
    largest = max(
        (nbytes(o) for g in graphs.values() for n in g["nodes"] for o in n["out"]),
        default=0,
    )
    return {
        "graphs": len(graphs),
        "nodes_stored": sum(len(g["nodes"]) for g in graphs.values()),
        "nodes_executed": executed,
        "call_depth": call_depth(doc),
        "op_counts": dict(sorted(op_counts.items())),
        "distinct_ops": len(op_counts),
        "constant_count": len(constants),
        "constant_bytes": sum(c["bytes"] for c in constants),
        "largest_constant_bytes": max((c["bytes"] for c in constants), default=0),
        "input_bytes": sum(nbytes(i) for i in entry["inputs"]),
        "largest_intermediate_bytes": largest,
        "document_bytes": len(dumps(doc)),
    }
