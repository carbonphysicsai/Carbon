"""Bounded loss expressions: Carbon's reconstruction for construction Level 1.

`Design_Specs/Challenge_Admission.md` §3, Level 1: "Custom loss expressions
using a bounded operation set". A loss expression is declarative data, never
code: a tree of operations from a closed set over a Challenge's registered
per-case terms. Carbon validates it, puts it in canonical form, pins it by
digest and builds the loss with Carbon's own code. Nothing a participant
supplies is executed.

**Status: ENGINEERING DRAFT** (GRAPHITE-ADMISSION-01 slice B). No
construction contract registers this surface and no miner, validator or intake
path reads it. `objective.loss_expressions` stays excluded in every contract
until the construction contract owner accepts a Level-1 proposal and the climb
records the expansion (`expansion_record`). Opening it is not this module's
act.

The form (Challenge-neutral; each Challenge supplies its `OperationSet`):

    {"term": "<name>"}                      one of the Challenge's per-case terms
    {"op": "add", "args": [E, E, ...]}      2 to max_arity summands
    {"op": "mul", "args": [E, E]}
    {"op": "div", "args": [E, E]}           numerator / (denominator + epsilon)
    {"op": "scale", "by": c, "arg": E}      c within the set's scale range
    {"op": "pow", "exponent": p, "arg": E}  (E + epsilon) ** p, p within range
    {"op": "log1p", "arg": E}
    {"op": "sqrt", "arg": E}                sqrt(E + epsilon)

A Challenge registers only non-negative per-case terms, and every operation
keeps a non-negative argument non-negative, so a valid expression is a
non-negative loss that is finite wherever its terms are. Depth and node count
are bounded. `add` and `mul` are commutative, so their arguments are sorted in
the canonical form, and evaluation follows the canonical order. Two
expressions that differ only in that order rebuild bit for bit the same.

Importing this module initializes no numerical runtime. Evaluation takes the
array namespace (`numpy` or `jax.numpy`) as an argument.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass

SCHEMA = "carbon.loss-expression.v1"
OPERATION_SET_SCHEMA = "carbon.loss-expression-operation-set.v1"
OPERATIONS = ("add", "mul", "div", "scale", "pow", "log1p", "sqrt")
_VARIADIC = ("add",)
_BINARY = ("mul", "div")
_UNARY = ("log1p", "sqrt")
_COMMUTATIVE = ("add", "mul")
_TERM = re.compile(r"^[a-z][a-z0-9_]{0,47}$")


class ExpressionRefused(ValueError):
    """An expression outside the bounded operation set; the code names why."""

    def __init__(self, code, path="/"):
        super().__init__(f"{code} at {path}")
        self.code = code
        self.path = path


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def digest_of(value):
    body = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class OperationSet:
    """One Challenge's bounded operation set over its registered terms.

    The bounds are engineering admission bounds on a construction surface,
    not quality or scientific claims."""

    name: str
    terms: tuple
    max_depth: int
    max_nodes: int
    max_arity: int
    scale: tuple
    exponent: tuple
    epsilon: float
    operations: tuple = OPERATIONS

    def __post_init__(self):
        if not (
            type(self.terms) is tuple
            and self.terms
            and len(set(self.terms)) == len(self.terms)
            and all(type(t) is str and _TERM.fullmatch(t) for t in self.terms)
        ):
            raise ValueError("terms are unique lower-case names")
        if not (
            type(self.operations) is tuple and set(self.operations) <= set(OPERATIONS)
        ):
            raise ValueError("operations are drawn from the closed set")
        for name in ("max_depth", "max_nodes", "max_arity"):
            value = getattr(self, name)
            if type(value) is not int or value < (2 if name == "max_arity" else 1):
                raise ValueError(name + " is a positive integer")
        for name in ("scale", "exponent"):
            low, high = getattr(self, name)
            if not (_number(low) and _number(high) and 0 <= low <= high):
                raise ValueError(name + " is a non-negative closed range")
        if not (_number(self.epsilon) and self.epsilon > 0):
            raise ValueError("epsilon is positive")

    def document(self):
        return {
            "schema": OPERATION_SET_SCHEMA,
            "name": self.name,
            "terms": list(self.terms),
            "operations": list(self.operations),
            "max_depth": self.max_depth,
            "max_nodes": self.max_nodes,
            "max_arity": self.max_arity,
            "scale": [float(v) for v in self.scale],
            "exponent": [float(v) for v in self.exponent],
            "epsilon": float(self.epsilon),
        }

    @property
    def digest(self):
        return digest_of(self.document())


def _keys(node, expected, path):
    if set(node) != expected:
        raise ExpressionRefused("node_fields", path)


def _canonical(node, opset, path, depth, count):
    """The canonical node and the running node count, or a refusal."""
    if depth > opset.max_depth:
        raise ExpressionRefused("too_deep", path)
    count += 1
    if count > opset.max_nodes:
        raise ExpressionRefused("too_many_nodes", path)
    if type(node) is not dict:
        raise ExpressionRefused("node_is_an_object", path)
    if "term" in node:
        _keys(node, {"term"}, path)
        if node["term"] not in opset.terms:
            raise ExpressionRefused("term_not_registered", path)
        return {"term": node["term"]}, count
    op = node.get("op")
    if op not in opset.operations:
        raise ExpressionRefused("operation_not_in_the_set", path)
    if op in _VARIADIC or op in _BINARY:
        _keys(node, {"op", "args"}, path)
        args = node["args"]
        if type(args) is not list or not (
            len(args) == 2 if op in _BINARY else 2 <= len(args) <= opset.max_arity
        ):
            raise ExpressionRefused("arity", path)
        out = []
        for index, arg in enumerate(args):
            child, count = _canonical(
                arg, opset, f"{path}args/{index}/", depth + 1, count
            )
            out.append(child)
        if op in _COMMUTATIVE:
            out.sort(key=lambda child: json.dumps(child, sort_keys=True))
        return {"op": op, "args": out}, count
    if op in _UNARY:
        _keys(node, {"op", "arg"}, path)
        child, count = _canonical(node["arg"], opset, path + "arg/", depth + 1, count)
        return {"op": op, "arg": child}, count
    field, bounds = (
        ("by", opset.scale) if op == "scale" else ("exponent", opset.exponent)
    )
    _keys(node, {"op", field, "arg"}, path)
    value = node[field]
    if not _number(value) or not bounds[0] <= value <= bounds[1]:
        raise ExpressionRefused(field + "_outside_bounds", path)
    child, count = _canonical(node["arg"], opset, path + "arg/", depth + 1, count)
    return {"op": op, field: float(value), "arg": child}, count


@dataclass(frozen=True)
class CompiledLoss:
    """A validated expression in canonical form, pinned with its operation set."""

    expression: dict
    operation_set: OperationSet
    digest: str

    def document(self):
        return {
            "schema": SCHEMA,
            "operation_set": self.operation_set.digest,
            "expression": self.expression,
        }

    def canonical_bytes(self):
        return json.dumps(
            self.document(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")


def compile_expression(expression, opset):
    """Validate and canonicalize; raises `ExpressionRefused` with a code."""
    if type(opset) is not OperationSet:
        raise TypeError("exact OperationSet required")
    canonical, _count = _canonical(expression, opset, "/", 1, 0)
    document = {
        "schema": SCHEMA,
        "operation_set": opset.digest,
        "expression": canonical,
    }
    return CompiledLoss(canonical, opset, digest_of(document))


def from_bytes(body, opset):
    """Rebuild from a pinned document's bytes, refusing another operation set."""
    try:
        document = json.loads(body)
    except ValueError:
        raise ExpressionRefused("not_json") from None
    if type(document) is not dict or set(document) != {
        "schema",
        "operation_set",
        "expression",
    }:
        raise ExpressionRefused("document_fields")
    if document["schema"] != SCHEMA:
        raise ExpressionRefused("unknown_schema")
    if document["operation_set"] != opset.digest:
        raise ExpressionRefused("operation_set_mismatch")
    return compile_expression(document["expression"], opset)


def evaluate(compiled, terms, xp):
    """The per-case loss: `terms` maps each registered term to its per-case
    values; `xp` is the array namespace."""
    if type(compiled) is not CompiledLoss:
        raise TypeError("a CompiledLoss from compile_expression is required")
    missing = set(compiled.operation_set.terms) - set(terms)
    if missing:
        raise ValueError("terms missing: " + ", ".join(sorted(missing)))
    epsilon = compiled.operation_set.epsilon

    def value(node):
        if "term" in node:
            return terms[node["term"]]
        op = node["op"]
        if op == "add":
            total = value(node["args"][0])
            for arg in node["args"][1:]:
                total = total + value(arg)
            return total
        if op == "mul":
            return value(node["args"][0]) * value(node["args"][1])
        if op == "div":
            return value(node["args"][0]) / (value(node["args"][1]) + epsilon)
        if op == "scale":
            return node["by"] * value(node["arg"])
        if op == "pow":
            return (value(node["arg"]) + epsilon) ** node["exponent"]
        if op == "log1p":
            return xp.log1p(value(node["arg"]))
        return xp.sqrt(value(node["arg"]) + epsilon)  # sqrt

    return value(compiled.expression)
