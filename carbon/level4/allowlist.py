"""The allowlist: which ops a graph may hold, in which roles, with which
parameters. Data lives in `docs/development/graphite/level4/allowlist_v*.json`
and is bound by digest; this module only reads it. v1 (the default) adds
named functions (`named.py`) and refuses unregistered custom derivative
rules; v0 stays loadable for the Phase 0 record.

`check` is the spike's G4 subset: op membership and role, parameter kinds,
and typed-key dtypes only where RNG is admitted. Caps (constant bytes, graph
size, depth) are compared only through `check_caps`. The owner set them,
for development and testnet, in OWNER-L4-VALUES-01; a cap a caller leaves
`HUMAN_INPUT` still blocks, it never passes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import graph, params

#: The current allowlist, shipped with the package. v0 is the Phase 0 record
#: (`docs/development/graphite/level4/allowlist_v0.json`).
PATH = Path(__file__).with_name("allowlist_v1.json")
HUMAN_INPUT = "HUMAN_INPUT"
#: The owner's decision that set the values below (development and testnet).
VALUES_DECISION = "OWNER-L4-VALUES-01"
#: D6's caps, approved as proposed in
#: `docs/development/graphite/level4/LEVEL4_VALUES_PROPOSAL.md` §3.
CAPS = {
    "constant_bytes": 16 * 1024,
    "nodes_executed": 4096,
    "call_depth": 16,
    "document_bytes": 1024**2,
    "largest_intermediate_bytes": 256 * 1024**2,
}


class Allowlist:
    def __init__(self, raw):
        self.raw = raw
        self.document = json.loads(raw)
        self.version = self.document["version"]
        self.digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        self.ops = self.document["carbon_ops"]
        self.aten = self.document.get("aten_core", {})
        self.named = self.document.get("named_functions", {})

    def admit_named(self, name, role, where=""):
        """A named function's entry in `role`, or `GraphRefused`."""
        from . import named

        entry = self.named.get(name)
        if entry is None:
            raise graph.GraphRefused("named_function_not_allowlisted", where)
        if entry["default"] == "refuse":
            raise graph.GraphRefused("named_function_refused", where)
        if name not in named.kernels():
            raise graph.GraphRefused("named_function_not_allowlisted", where)
        if role not in entry["roles"]:
            raise graph.GraphRefused("op_not_allowed_in_role", where)
        return entry

    def admit(self, op, role, where=""):
        """The parameter spec of `op` in `role`, or `GraphRefused`."""
        entry = self.ops.get(op)
        if entry is None:
            raise graph.GraphRefused("op_not_allowlisted", where)
        if entry["default"] == "refuse":
            raise graph.GraphRefused("op_refused", where)
        if role not in entry["roles"]:
            raise graph.GraphRefused("op_not_allowed_in_role", where)
        if not entry["v0_interpreter"]:
            raise graph.GraphRefused("op_not_supported_v0", where)
        return entry["params"]

    def check(self, doc):
        """G4 over a parsed document. Returns the review flags it raised."""
        graph.check_structure(doc)
        if doc["allowlist"] != self.version:
            raise graph.GraphRefused("allowlist_version_mismatch")
        flags = {}
        rng_role = doc["role"] == "init"
        for name, g in doc["graphs"].items():
            for i, entry in enumerate(g["inputs"]):
                if entry["dtype"] in graph.KEY_DTYPES and not rng_role:
                    raise graph.GraphRefused(
                        "key_dtype_outside_init", f"{name}.inputs[{i}]"
                    )
            for i, node in enumerate(g["nodes"]):
                where = f"{name}.nodes[{i}]"
                spec = self.admit(node["op"], doc["role"], where)
                decoded = params.decode(spec, node["params"])
                if node["op"] == "named_function":
                    entry = self.admit_named(decoded["name"], doc["role"], where)
                    if len(node["in"]) != entry["arity"]:
                        raise graph.GraphRefused("named_function_arity", where)
                    if entry["default"] == "review":
                        key = "named_function:" + decoded["name"]
                        flags[key] = flags.get(key, 0) + 1
                for out in node["out"]:
                    if out["dtype"] in graph.KEY_DTYPES and not rng_role:
                        raise graph.GraphRefused("key_dtype_outside_init", where)
                if self.ops[node["op"]]["default"] == "review":
                    flags[node["op"]] = flags.get(node["op"], 0) + 1
        return flags


def load(path=PATH):
    return Allowlist(Path(path).read_bytes())


def check_caps(measurements, caps=None):
    """Each cap's verdict: `blocked_human_input` while unset, else pass/refuse."""
    caps = CAPS if caps is None else caps
    out = {}
    for name, cap in caps.items():
        if cap == HUMAN_INPUT or cap is None:
            out[name] = "blocked_human_input"
        else:
            out[name] = "pass" if measurements[name] <= cap else "refuse"
    return out
