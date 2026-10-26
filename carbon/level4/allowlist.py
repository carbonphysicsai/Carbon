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
#: Containment bounds (Validator, VALIDATOR_NO_MODEL_SIZE_CAP_SPEC_20261021):
#: what the host parses before any isolation, never a model rule and never
#: miner-tunable. Proposals under containment, not a security acceptance
#: (the owner's security review).
CONTAINMENT = {"document_bytes": 64 * 1024**2, "call_depth": graph.MAX_CALL_DEPTH}
#: Allowlist versions served with no model-size caps (owner, 2026-10-21: "No
#: cap. Only cap should be if it fits the training resource limit"): only the
#: constants cap, which enforces from-scratch (owner: kept), and containment.
#: The training resource limits bind instead. Every earlier version keeps CAPS.
UNCAPPED_VERSIONS = frozenset({"level4-allowlist-v7", "level4-allowlist-v8"})
UNCAPPED_CAPS = {"constant_bytes": CAPS["constant_bytes"], **CONTAINMENT}
#: Versions whose init graphs may build structured tables from `iota` arithmetic
#: (identity, DFT, orthogonal bases): the keyed-or-uniform-fill rule is removed
#: (Validator VALIDATOR_GRAPH_OPS_V8_RULINGS_20261025, row 2). Under accounting v5 the
#: constants cap already bounds the information an init can carry; the from-scratch
#: rule (no pretrained `initial_state`) and "an init never returns a key" stay.
OPEN_INIT_VERSIONS = frozenset({"level4-allowlist-v8"})


def caps_for(allowlist):
    """The caps a document validated under ``allowlist`` (an `Allowlist` or
    its version string) is measured against: `UNCAPPED_CAPS` for an uncapped
    version, else the owner's `CAPS`. An unknown version gets `CAPS`."""
    version = (
        allowlist if type(allowlist) is str else getattr(allowlist, "version", None)
    )
    return dict(UNCAPPED_CAPS if version in UNCAPPED_VERSIONS else CAPS)


def _refusal(code, where, op):
    """The typed refusal, naming the primitive too (`op`, a public op name)."""
    refusal = graph.GraphRefused(code, where)
    refusal.op = op
    return refusal


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
        if name not in named.NAMES:
            raise graph.GraphRefused("named_function_not_allowlisted", where)
        if role not in entry["roles"]:
            raise graph.GraphRefused("op_not_allowed_in_role", where)
        return entry

    def admit(self, op, role, where=""):
        """The parameter spec of `op` in `role`, or `GraphRefused`."""
        entry = self.ops.get(op)
        if entry is None:
            raise _refusal("op_not_allowlisted", where, op)
        if entry["default"] in ("refuse", "strip"):
            # "strip": lowering drops the op on the miner's machine; a document that
            # carries it is refused.
            raise _refusal("op_refused", where, op)
        if role not in entry["roles"]:
            raise _refusal("op_not_allowed_in_role", where, op)
        if not entry["v0_interpreter"]:
            raise _refusal("op_not_supported_v0", where, op)
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


#: The allowlist every Challenge serves (Validator, 2026-10-20: v6 for every
#: Challenge, one evaluation version before the recalibration). Frozen by its
#: sha; v1-v5 stay loadable by path for historical evidence.
SERVED_PATH = Path(__file__).with_name("allowlist_v6.json")
SERVED_SHA256 = "c21dd41476ab7cd83badc62a2f3d17fc4de8ada721b03c8d456ca9c64af99bf2"


def served_bytes():
    """The served allowlist's exact frozen bytes, or ValueError."""
    import hashlib

    raw = SERVED_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SERVED_SHA256:
        raise ValueError("served allowlist bytes differ")
    return raw


def load_served():
    return Allowlist(served_bytes())


#: Allowlist v7 (prospective, not yet served): frozen by its sha. A Challenge
#: serves it only on a new version registered for it, never in place of v6.
V7_PATH = Path(__file__).with_name("allowlist_v7.json")
V7_SHA256 = "7cc0152989d797a71f64b3faf03bb76a0a15d89adf873722d28cb3d134441c5c"


def v7_bytes():
    """Allowlist v7's exact frozen bytes, or ValueError."""
    raw = V7_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != V7_SHA256:
        raise ValueError("allowlist v7 bytes differ")
    return raw


#: Allowlist v8 (prospective, not yet served): v7 plus every pure, deterministic
#: array op the graph route can run (OWNER-GRAPH-OPS-OPEN-01; Validator
#: VALIDATOR_GRAPH_OPS_V8_RULINGS_20261025). A new file, served only by new
#: versions: v7's bytes and digests stay. Frozen by its sha once the head is done.
V8_PATH = Path(__file__).with_name("allowlist_v8.json")
V8_SHA256 = "a873632fe0c6d7f5dbbfde1e2b62535847b48b07194a11418eea6fdcc2a6fe64"


def v8_bytes():
    """Allowlist v8's exact frozen bytes, or ValueError."""
    raw = V8_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != V8_SHA256:
        raise ValueError("allowlist v8 bytes differ")
    return raw


#: How the `constant_bytes` cap is measured, versioned prospectively:
#: v1 summed every embedded constant's bytes; v2 (OWNER-L4-CONSTANT-
#: ACCOUNTING-02) counted identical constants once; v3 (OWNER-L4-CONSTANT-
#: ACCOUNTING-03, "count in numbers") counts values, identical copies once,
#: at `graph.VALUE_BYTES` each, so float64 is not charged double. The 16 KiB
#: cap itself is unchanged; verdicts recorded under v1 or v2 keep their
#: meaning and are never re-measured.
CONSTANT_ACCOUNTING = "level4-constant-accounting-v3"
#: The measurement each cap reads under the current accounting.
MEASURED_AS = {"constant_bytes": "constant_value_bytes"}
#: Accounting v5 (Validator VALIDATOR_GRAPH_OPS_V8_RULINGS_20261025 sections 3
#: and 7): the 16 KiB cap bounds every channel that carries a fitted value into the
#: rebuilt model, counted by what it really stores: the constants (an integer by the
#: bits its range and offset need, floats at their real size, float64 eight bytes) and
#: the static integer, bool and float parameters of every node (`graph.measure`:
#: `fitted_info_bytes`). Served with allowlist v8 only (not yet published); every
#: earlier version keeps v3 and no recorded verdict is re-measured.
CONSTANT_ACCOUNTING_V5 = "level4-constant-accounting-v5"
ACCOUNTING_V5_VERSIONS = frozenset({"level4-allowlist-v8"})
MEASURED_AS_V5 = {"constant_bytes": "fitted_info_bytes"}


def accounting_for(allowlist):
    """(accounting name, cap -> measurement map) for ``allowlist`` (an
    `Allowlist` or its version string): v5 for v8, else v3."""
    version = (
        allowlist if type(allowlist) is str else getattr(allowlist, "version", None)
    )
    if version in ACCOUNTING_V5_VERSIONS:
        return CONSTANT_ACCOUNTING_V5, MEASURED_AS_V5
    return CONSTANT_ACCOUNTING, MEASURED_AS


def check_caps(measurements, caps=None, measured_as=None):
    """Each cap's verdict: `blocked_human_input` while unset, else pass/refuse.
    ``measured_as`` is the accounting's cap -> measurement map (`accounting_for`);
    the default is v3."""
    caps = CAPS if caps is None else caps
    measured_as = MEASURED_AS if measured_as is None else measured_as
    out = {}
    for name, cap in caps.items():
        if cap == HUMAN_INPUT or cap is None:
            out[name] = "blocked_human_input"
        else:
            measured = measurements[measured_as.get(name, name)]
            out[name] = "pass" if measured <= cap else "refuse"
    return out
