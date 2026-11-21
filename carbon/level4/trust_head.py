"""The trust-head SHAPE RULE of a self-trust graph (SELF_TRUST DESIGN_v2, section 7; door-code 04:34:35Z and 06:56:24Z).

A miner graph bound to a version's TRUST interface returns `physics_width + trust_width` columns. The physics columns are
trained exactly as today; the trust columns must not move them. Which columns of one output tensor depend on which
parameters is not decidable in general (slice, gather, reshape and concatenate can mix columns), so the rule is a SHAPE a
checker can verify exactly:

* the entry graph has ONE output, produced by ONE ``concatenate`` node along the last axis of EXACTLY two operands: the
  PHYSICS operand first (`physics_width` wide) and the TRUST operand second (`trust_width` wide), equal leading shape;
* parameters are the entry graph's inputs but the last (Carbon feeds them from the built state); the last input is the data
  input, which both operands may read;
* the two operands' PARAMETER sets (every parameter input reachable from the operand, through every node: a node, a nested
  call and a scan body included, depends on ALL its operands) must be DISJOINT, and the trust operand must own at least one
  parameter (a trust head with none cannot be trained).

Feeding the physics operand's own VALUE into the trust head stays allowed (it reads as data): phase 2 of training updates
only the trust parameters, so the physics columns are byte-identical with and without the trust head. A physics value
EARLIER than the operand (a feature the physics operand is computed from) carries physics parameters and does not.

Pure structure: no op membership, dtype or interpretation (the allowlist and the interpreter own those). Refusals are typed
`GraphRefused` codes and never echo content.
"""

from __future__ import annotations

from carbon.level4.graph import GraphRefused

CONCATENATE = "concatenate"


def _is_int(value):
    return type(value) is int


def check(doc, *, physics_width, trust_width):
    """The trust-head shape rule (see the module text). A document that names a value it does not define, or lacks a key the
    format requires, is refused typed (``trust_output_shape``), never with a KeyError: the checker is meant to run on an
    intake-validated document, and this keeps it safe if it is ever called before."""
    try:
        return _check(doc, physics_width=physics_width, trust_width=trust_width)
    except (KeyError, IndexError, TypeError, AttributeError):
        raise GraphRefused("trust_output_shape", "graph") from None


def _check(doc, *, physics_width, trust_width):
    """Verify the trust-head shape rule on a parsed forward graph document.

    Returns ``{"physics_parameters": [...], "trust_parameters": [...]}``, the indices (in input order) of the parameters
    each operand reaches. Raises `GraphRefused` ``trust_output_shape``, ``trust_head_shares_parameters`` or
    ``trust_head_has_no_parameters``.
    """
    if not (
        _is_int(physics_width)
        and _is_int(trust_width)
        and physics_width >= 1
        and trust_width >= 1
    ):
        raise GraphRefused("trust_output_shape", "widths")
    graph = doc["graphs"][doc["entry"]]
    inputs, nodes, outputs = graph["inputs"], graph["nodes"], graph["outputs"]
    if len(inputs) < 2 or len(outputs) != 1:
        raise GraphRefused("trust_output_shape", "outputs")
    # value id -> aval shape, and value id -> the node that produces it
    shapes, producer = {}, {}
    n_params = len(inputs) - 1
    for entry in inputs:
        shapes[entry["value"]] = entry["shape"]
    for entry in graph["constants"]:
        shapes[entry["value"]] = entry["shape"]
    for node in nodes:
        for out in node["out"]:
            shapes[out["value"]] = out["shape"]
            producer[out["value"]] = node

    def reach(exempt=None):
        """value id -> bitmask of the parameter inputs it depends on; the ``exempt`` value reads as data (mask 0)."""
        mask = {}
        for i, entry in enumerate(inputs):
            mask[entry["value"]] = (1 << i) if i < n_params else 0
        for entry in graph["constants"]:
            mask[entry["value"]] = 0
        for node in nodes:
            depends = 0
            for value_id in node["in"]:
                depends |= mask[value_id]
            for out in node["out"]:
                mask[out["value"]] = 0 if out["value"] == exempt else depends
        return mask

    node = producer.get(outputs[0])
    if node is None or node["op"] != CONCATENATE or len(node["in"]) != 2:
        raise GraphRefused("trust_output_shape", "concatenate")
    physics, trust = node["in"]
    out_shape = shapes[outputs[0]]
    rank = len(out_shape)
    dimension = node["params"].get("dimension")
    if rank < 1 or not _is_int(dimension) or dimension not in (rank - 1, -1):
        raise GraphRefused("trust_output_shape", "axis")
    p_shape, t_shape = shapes[physics], shapes[trust]
    if (
        len(p_shape) != rank
        or len(t_shape) != rank
        or p_shape[-1] != physics_width
        or t_shape[-1] != trust_width
        or p_shape[:-1] != t_shape[:-1]
        or out_shape[-1] != physics_width + trust_width
    ):
        raise GraphRefused("trust_output_shape", "widths")
    # The physics operand's own VALUE may feed the trust head (phase 2 never updates the physics parameters), so it reads as
    # data when the trust operand's parameters are collected; any EARLIER physics value (a feature before the operand) does not.
    physics_bits, trust_bits = reach()[physics], reach(exempt=physics)[trust]
    if physics_bits & trust_bits:
        raise GraphRefused("trust_head_shares_parameters")
    if trust_bits == 0:
        raise GraphRefused("trust_head_has_no_parameters")

    def indices(bits):
        return [i for i in range(n_params) if bits >> i & 1]

    return {
        "physics_parameters": indices(physics_bits),
        "trust_parameters": indices(trust_bits),
    }
