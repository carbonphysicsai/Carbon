"""Gate G4: validate a parsed graph document (development only).

In order:

1. the allowlist (`allowlist.check`): every op admitted in the document's
   role, parameters within their kinds, named functions registered, typed
   keys only where RNG is admitted;
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


def validate(doc, allowlist, *, role=None, interface=None, caps=None):
    """G4's verdict for a parsed document, or `GraphRefused`."""
    flags = allowlist.check(doc)
    if role is not None and doc["role"] != role:
        raise graph.GraphRefused("role_mismatch")
    batch = None
    if interface is not None:
        if doc["role"] != "forward":
            raise graph.GraphRefused("interface_needs_forward_graph")
        batch = check_interface(doc, interface)
    measurements = graph.measure(doc)
    # A cap the caller does not name stays HUMAN_INPUT: it blocks, never passes.
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
