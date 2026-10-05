"""Bounded loss expressions: Carbon's reconstruction for construction Level 1.

`Design_Specs/Challenge_Admission.md` §3, Level 1: "Custom loss expressions
using a bounded operation set". A loss expression is declarative data, never
code: a tree of operations from a closed set over a Challenge's registered
per-case terms. Carbon validates it, puts it in canonical form, pins it by
digest and builds the loss with Carbon's own code. Nothing a participant
supplies is executed.

**Status: development only** (GRAPHITE-ADMISSION-01 slice B; built for
battery in GRAPHITE-L1-BUILD-01). No construction contract registers this
surface and no miner, validator or intake path reads it.
`objective.loss_expressions` stays excluded in every contract. Battery's
registered development-only variants (`carbon.battery.level1`) serve it to
Carbon's own Graphite campaigns only. Opening it to miners is not this
module's act.

The form (Challenge-neutral; each Challenge supplies its `OperationSet`):

    {"term": "<name>"}                      one of the Challenge's per-case terms
    {"op": "add", "args": [E, E, ...]}      2 to max_arity summands
    {"op": "mul", "args": [E, E]}
    {"op": "div", "args": [E, E]}           numerator / (denominator + epsilon)
    {"op": "scale", "by": c, "arg": E}      c within the set's scale range
    {"op": "pow", "exponent": p, "arg": E}  (E + epsilon) ** p, p within range
    {"op": "log1p", "arg": E}
    {"op": "sqrt", "arg": E}                sqrt(E + epsilon)

Version 2 (`SCHEMA_V2`) adds, where a set names them:

    {"op": "max" | "min", "args": [E, E, ...]}   elementwise, 2 to max_arity
    {"op": "cap", "at": c, "arg": E}             min(E, c)
    {"op": "excess", "over": c, "arg": E}        max(E - c, 0)
    {"op": "expm1", "cap": c, "arg": E}          expm1(min(E, c))
    {"op": "mean_t" | "max_t", "over": T, "arg": E_time}
                                                 the mean or maximum over time,
                                                 summed over trajectories T
    {"op": "sub", "args": [E, E]}, {"op": "neg" | "exp", "arg": E},
    {"const": c}                                 the signed arm only

and a second sort: a time term is one value per case and time, evaluated
per trajectory; elementwise operations take one sort, a reduction turns time
into case, and an expression is case-sorted. A set using none of this is a
version-1 set: its schemas, documents and digests are version 1's.

A Challenge registers only non-negative per-case terms, and every version-1
operation and every unsigned version-2 operation keeps a non-negative argument
non-negative, so a valid expression over an unsigned set is a non-negative
loss that is finite wherever its terms are. Depth and node count are
bounded. `add` and `mul` are commutative, so their arguments are sorted in
the canonical form, and evaluation follows the canonical order. Two
expressions that differ only in that order rebuild bit for bit the same.

Importing this module initializes no numerical runtime. Evaluation takes the
array namespace (`numpy` or `jax.numpy`) as an argument.

**Every refusal is typed** (B1 of the Level-1 review packet,
`docs/development/graphite/L1_LOSS_EXPRESSIONS_REVIEW_PACKET.md` on branch
`claude/l1-loss-expressions-packet`). Whatever a strategy supplies, `compile_expression` and
`from_bytes` either return a `CompiledLoss` or raise `ExpressionRefused` with
a code, on Carbon's host. An untyped exception could be classified as an
infrastructure failure, which is a refund path. So:
- a numeric constant must convert to a finite float; an integer too large to
  convert (`10**400`) is `<field>_outside_bounds`, not an `OverflowError`;
- `-0.0` is stored as `0.0`, so one constant has one digest;
- `from_bytes` bounds the document's size (`document_too_large`) and its
  nesting (`document_too_deep`) before parsing, so a deep document never
  reaches the recursive parser; it refuses bytes that are not UTF-8 JSON
  (`not_json`), a repeated key (`duplicate_key`) and any document that is not
  exactly the canonical bytes of what it compiles to (`not_canonical`).

Valid canonical documents compile exactly as before, to the same digests.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass

SCHEMA = "carbon.loss-expression.v1"
OPERATION_SET_SCHEMA = "carbon.loss-expression-operation-set.v1"
#: Version 2 (the Level-1 build): two sorts, more operations, constant
#: leaves for the signed arm. A set that uses none of it keeps version 1's
#: schemas and documents, byte for byte.
SCHEMA_V2 = "carbon.loss-expression.v2"
OPERATION_SET_SCHEMA_V2 = "carbon.loss-expression-operation-set.v2"
OPERATIONS = ("add", "mul", "div", "scale", "pow", "log1p", "sqrt")
#: Every operation version 2 may name. `const` is a leaf, `{"const": c}`.
#: `sub`, `neg`, `exp` and `const` can make a loss negative or non-finite on
#: ordinary inputs; they exist for the signed attack arm only.
OPERATIONS_V2 = OPERATIONS + (
    "max",
    "min",
    "cap",
    "excess",
    "expm1",
    "mean_t",
    "max_t",
    "sub",
    "neg",
    "exp",
    "const",
)
SIGNED = ("sub", "neg", "exp", "const")
_VARIADIC = ("add", "max", "min")
_BINARY = ("mul", "div", "sub")
_UNARY = ("log1p", "sqrt", "neg", "exp")
_REDUCTIONS = ("mean_t", "max_t")
_COMMUTATIVE = ("add", "mul", "max", "min")
#: Each parametrized operation's constant field and the set's range for it.
_PARAMETRIZED = {
    "scale": ("by", "scale"),
    "pow": ("exponent", "exponent"),
    "cap": ("at", "cap_at"),
    "excess": ("over", "excess_over"),
    "expm1": ("cap", "expm1_cap"),
}
#: What a reduction may reduce over: both trajectories, or one.
OVER = {"both": ("voltage", "temperature"), "voltage": ("voltage",)}
OVER["temperature"] = ("temperature",)
_TERM = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_V2_RANGES = ("cap_at", "excess_over", "expm1_cap", "const")


class ExpressionRefused(ValueError):
    """An expression outside the bounded operation set; the code names why."""

    def __init__(self, code, path="/"):
        super().__init__(f"{code} at {path}")
        self.code = code
        self.path = path


#: Bytes allowed in a pinned document: a fixed allowance for the document's
#: own fields plus a per-node allowance. A canonical node needs at most about
#: 60 bytes (a 48-character term name, or a 24-character float repr with its
#: field and operation names), so 128 bytes a node is more than twice that.
_DOCUMENT_BYTES = 1024
_NODE_BYTES = 128


class _DuplicateKey(ValueError):
    pass


def _number(value):
    """A finite number: an exact int or float that converts to a finite float.
    A bool is refused, and so is an int too large to convert."""
    if type(value) is int:
        try:
            value = float(value)
        except OverflowError:
            return False
    return type(value) is float and math.isfinite(value)


def _constant(value):
    """The canonical float of a constant `_number` admitted: `-0.0` is `0.0`,
    so one constant has one digest. Every other value is unchanged."""
    return float(value) + 0.0


def _byte_limit(opset):
    """The largest document `from_bytes` reads for `opset`."""
    return _DOCUMENT_BYTES + _NODE_BYTES * opset.max_nodes


def _depth_limit(opset):
    """The deepest JSON nesting a valid document has: the document object,
    then an object and an argument array for every tree level."""
    return 2 * opset.max_depth + 2


def _too_deep(text, limit):
    """Whether `text` nests objects or arrays deeper than `limit`, counted
    without parsing (brackets inside strings do not count)."""
    depth = 0
    in_string = escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "{[":
            depth += 1
            if depth > limit:
                return True
        elif ch in "}]":
            depth -= 1
    return False


def _unique_pairs(pairs):
    """`json.loads`' object hook: a repeated key is refused, never overwritten."""
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        raise _DuplicateKey
    return dict(pairs)


def _require_canonical(body, compiled):
    if body != compiled.canonical_bytes():
        raise ExpressionRefused("not_canonical")


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
    #: Version 2: time-sorted terms (one value per case and time, evaluated
    #: per trajectory) and the ranges of the version-2 constants.
    time_terms: tuple = ()
    cap_at: tuple = (0.0, 0.0)
    excess_over: tuple = (0.0, 0.0)
    expm1_cap: tuple = (0.0, 0.0)
    const: tuple = (0.0, 0.0)

    def __post_init__(self):
        names = self.terms + self.time_terms if type(self.time_terms) is tuple else ()
        if not (
            type(self.terms) is tuple
            and self.terms
            and type(self.time_terms) is tuple
            and len(set(names)) == len(names)
            and all(type(t) is str and _TERM.fullmatch(t) for t in names)
        ):
            raise ValueError("terms are unique lower-case names")
        if not (
            type(self.operations) is tuple
            and len(set(self.operations)) == len(self.operations)
            and set(self.operations) <= set(OPERATIONS_V2)
        ):
            raise ValueError("operations are drawn from the closed set")
        for name in ("max_depth", "max_nodes", "max_arity"):
            value = getattr(self, name)
            if type(value) is not int or value < (2 if name == "max_arity" else 1):
                raise ValueError(name + " is a positive integer")
        for name in ("scale", "exponent", "cap_at", "excess_over", "expm1_cap"):
            low, high = getattr(self, name)
            if not (_number(low) and _number(high) and 0 <= low <= high):
                raise ValueError(name + " is a non-negative closed range")
        low, high = self.const
        if not (_number(low) and _number(high) and low <= high):
            raise ValueError("const is a closed range")
        if not (_number(self.epsilon) and self.epsilon > 0):
            raise ValueError("epsilon is positive")

    @property
    def version2(self):
        """Whether the set uses anything version 1 does not have."""
        return bool(self.time_terms) or not set(self.operations) <= set(OPERATIONS)

    @property
    def signed(self):
        """Whether the set admits operations that can make a loss negative."""
        return bool(set(self.operations) & set(SIGNED))

    @property
    def expression_schema(self):
        return SCHEMA_V2 if self.version2 else SCHEMA

    def document(self):
        document = {
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
        if self.version2:
            document["schema"] = OPERATION_SET_SCHEMA_V2
            document["time_terms"] = list(self.time_terms)
            for name in _V2_RANGES:
                document[name] = [_constant(v) for v in getattr(self, name)]
        return document

    @classmethod
    def from_document(cls, document):
        """The set a document describes; `ValueError` if it is not exactly one."""
        if type(document) is not dict or document.get("schema") not in (
            OPERATION_SET_SCHEMA,
            OPERATION_SET_SCHEMA_V2,
        ):
            raise ValueError("not an operation-set document")
        fields = {
            k: v for k, v in document.items() if k not in ("schema", "time_terms")
        }
        for name in ("terms", "operations", "scale", "exponent", *_V2_RANGES):
            if name in fields:
                if type(fields[name]) is not list:
                    raise ValueError(name + " is a list")
                fields[name] = tuple(fields[name])
        if "time_terms" in document:
            if type(document["time_terms"]) is not list:
                raise ValueError("time_terms is a list")
            fields["time_terms"] = tuple(document["time_terms"])
        try:
            found = cls(**fields)
        except TypeError:
            raise ValueError("unknown operation-set fields") from None
        if found.document() != document:
            raise ValueError("the document is not this set's canonical document")
        return found

    @property
    def digest(self):
        return digest_of(self.document())


def _keys(node, expected, path):
    if set(node) != expected:
        raise ExpressionRefused("node_fields", path)


#: The sorts: one value per case, or one per case and time. A constant leaf
#: has no sort of its own (`None`): it takes its siblings'.
CASE, TIME = "case", "time"


def _joined(sorts, path):
    found = {s for s in sorts if s is not None}
    if len(found) > 1:
        raise ExpressionRefused("mixed_sorts", path)
    return found.pop() if found else None


def _canonical(node, opset, path, depth, count):
    """The canonical node, the running node count and the node's sort, or a
    refusal. A version-1 set has one sort, so its nodes are all CASE."""
    if depth > opset.max_depth:
        raise ExpressionRefused("too_deep", path)
    count += 1
    if count > opset.max_nodes:
        raise ExpressionRefused("too_many_nodes", path)
    if type(node) is not dict:
        raise ExpressionRefused("node_is_an_object", path)
    if "term" in node:
        _keys(node, {"term"}, path)
        if node["term"] in opset.terms:
            return {"term": node["term"]}, count, CASE
        if node["term"] in opset.time_terms:
            return {"term": node["term"]}, count, TIME
        raise ExpressionRefused("term_not_registered", path)
    if "const" in node and "const" in opset.operations:
        _keys(node, {"const"}, path)
        value = node["const"]
        low, high = opset.const
        if not _number(value) or not low <= value <= high:
            raise ExpressionRefused("const_outside_bounds", path)
        return {"const": _constant(value)}, count, None
    op = node.get("op")
    if op not in opset.operations or op == "const":
        raise ExpressionRefused("operation_not_in_the_set", path)
    if op in _VARIADIC or op in _BINARY:
        _keys(node, {"op", "args"}, path)
        args = node["args"]
        if type(args) is not list or not (
            len(args) == 2 if op in _BINARY else 2 <= len(args) <= opset.max_arity
        ):
            raise ExpressionRefused("arity", path)
        out, sorts = [], []
        for index, arg in enumerate(args):
            child, count, sort = _canonical(
                arg, opset, f"{path}args/{index}/", depth + 1, count
            )
            out.append(child)
            sorts.append(sort)
        if op in _COMMUTATIVE:
            out.sort(key=lambda child: json.dumps(child, sort_keys=True))
        return {"op": op, "args": out}, count, _joined(sorts, path)
    if op in _UNARY:
        _keys(node, {"op", "arg"}, path)
        child, count, sort = _canonical(
            node["arg"], opset, path + "arg/", depth + 1, count
        )
        return {"op": op, "arg": child}, count, sort
    if op in _REDUCTIONS:
        _keys(node, {"op", "over", "arg"}, path)
        if type(node["over"]) is not str or node["over"] not in OVER:
            raise ExpressionRefused("over_not_registered", path)
        child, count, sort = _canonical(
            node["arg"], opset, path + "arg/", depth + 1, count
        )
        if sort != TIME:
            raise ExpressionRefused("reduction_needs_time", path)
        return {"op": op, "over": node["over"], "arg": child}, count, CASE
    field, bounds = _PARAMETRIZED[op]
    bounds = getattr(opset, bounds)
    _keys(node, {"op", field, "arg"}, path)
    value = node[field]
    if not _number(value) or not bounds[0] <= value <= bounds[1]:
        raise ExpressionRefused(field + "_outside_bounds", path)
    child, count, sort = _canonical(node["arg"], opset, path + "arg/", depth + 1, count)
    return {"op": op, field: _constant(value), "arg": child}, count, sort


@dataclass(frozen=True)
class CompiledLoss:
    """A validated expression in canonical form, pinned with its operation set."""

    expression: dict
    operation_set: OperationSet
    digest: str

    def document(self):
        return {
            "schema": self.operation_set.expression_schema,
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
    canonical, _count, sort = _canonical(expression, opset, "/", 1, 0)
    if sort == TIME:
        raise ExpressionRefused("loss_is_per_case")
    document = {
        "schema": opset.expression_schema,
        "operation_set": opset.digest,
        "expression": canonical,
    }
    return CompiledLoss(canonical, opset, digest_of(document))


def walk(expression):
    """Every node of a canonical expression, depth first."""
    stack = [expression]
    while stack:
        node = stack.pop()
        yield node
        if "args" in node:
            stack.extend(reversed(node["args"]))
        elif "arg" in node:
            stack.append(node["arg"])


def uses(expression):
    """The operations and terms a canonical expression names."""
    operations, terms = set(), set()
    for node in walk(expression):
        if "term" in node:
            terms.add(node["term"])
        elif "const" in node:
            operations.add("const")
        else:
            operations.add(node["op"])
    return operations, terms


def from_bytes(body, opset):
    """Rebuild from a pinned document's bytes, refusing another operation set.

    The bytes must be exactly the canonical bytes of the document they compile
    to. Size and nesting are bounded before anything is parsed, so every
    refusal is an `ExpressionRefused`."""
    if type(opset) is not OperationSet:
        raise TypeError("exact OperationSet required")
    if type(body) is str:
        body = body.encode("utf-8", "surrogatepass")
    elif type(body) is bytearray:
        body = bytes(body)
    elif type(body) is not bytes:
        raise ExpressionRefused("not_bytes")
    if len(body) > _byte_limit(opset):
        raise ExpressionRefused("document_too_large")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise ExpressionRefused("not_json") from None
    if _too_deep(text, _depth_limit(opset)):
        raise ExpressionRefused("document_too_deep")
    try:
        document = json.loads(text, object_pairs_hook=_unique_pairs)
    except _DuplicateKey:
        raise ExpressionRefused("duplicate_key") from None
    except ValueError:
        raise ExpressionRefused("not_json") from None
    if type(document) is not dict or set(document) != {
        "schema",
        "operation_set",
        "expression",
    }:
        raise ExpressionRefused("document_fields")
    if document["schema"] != opset.expression_schema:
        raise ExpressionRefused("unknown_schema")
    if document["operation_set"] != opset.digest:
        raise ExpressionRefused("operation_set_mismatch")
    compiled = compile_expression(document["expression"], opset)
    _require_canonical(body, compiled)
    return compiled


def evaluate(compiled, terms, xp, trajectories=None):
    """The per-case loss: `terms` maps each registered term to its per-case
    values; `xp` is the array namespace.

    A version-2 set's time terms come from `trajectories`, which maps each
    trajectory (`voltage`, `temperature`) to its time terms (cases x times).
    A reduction evaluates its argument once per trajectory it names, reduces
    over time and sums."""
    if type(compiled) is not CompiledLoss:
        raise TypeError("a CompiledLoss from compile_expression is required")
    opset = compiled.operation_set
    missing = set(opset.terms) - set(terms)
    if opset.time_terms:
        if type(trajectories) is not dict or set(trajectories) != set(OVER["both"]):
            raise ValueError("per-trajectory time terms are required")
        for name, found in trajectories.items():
            missing |= {f"{name}:{t}" for t in set(opset.time_terms) - set(found)}
    if missing:
        raise ValueError("terms missing: " + ", ".join(sorted(missing)))
    epsilon = opset.epsilon

    def value(node, trajectory=None):
        if "term" in node:
            if trajectory is None:
                return terms[node["term"]]
            return trajectories[trajectory][node["term"]]
        if "const" in node:
            return node["const"]
        op = node["op"]
        if op in _REDUCTIONS:
            total = None
            for name in OVER[node["over"]]:
                # Every time term of a trajectory has the same (cases x times)
                # shape; a constant broadcasts to it.
                shape = trajectories[name][opset.time_terms[0]].shape
                inner = xp.broadcast_to(value(node["arg"], name), shape)
                reduced = (
                    xp.mean(inner, axis=1) if op == "mean_t" else xp.max(inner, axis=1)
                )
                total = reduced if total is None else total + reduced
            return total
        if op in ("add", "max", "min"):
            total = value(node["args"][0], trajectory)
            for arg in node["args"][1:]:
                if op == "add":
                    total = total + value(arg, trajectory)
                elif op == "max":
                    total = xp.maximum(total, value(arg, trajectory))
                else:
                    total = xp.minimum(total, value(arg, trajectory))
            return total
        if op == "mul":
            return value(node["args"][0], trajectory) * value(
                node["args"][1], trajectory
            )
        if op == "div":
            return value(node["args"][0], trajectory) / (
                value(node["args"][1], trajectory) + epsilon
            )
        if op == "sub":
            return value(node["args"][0], trajectory) - value(
                node["args"][1], trajectory
            )
        inner = value(node["arg"], trajectory)
        if op == "scale":
            return node["by"] * inner
        if op == "pow":
            return (inner + epsilon) ** node["exponent"]
        if op == "log1p":
            return xp.log1p(inner)
        if op == "sqrt":
            return xp.sqrt(inner + epsilon)
        if op == "cap":
            return xp.minimum(inner, node["at"])
        if op == "excess":
            return xp.maximum(inner - node["over"], 0.0)
        if op == "expm1":
            return xp.expm1(xp.minimum(inner, node["cap"]))
        if op == "neg":
            return -inner
        return xp.exp(inner)  # exp

    result = value(compiled.expression)
    if _constant_only(compiled.expression):
        # A loss with no term is the same constant for every case.
        first = terms[opset.terms[0]]
        result = xp.zeros_like(first) + result
    return result


def _constant_only(expression):
    return not any("term" in node for node in walk(expression))
