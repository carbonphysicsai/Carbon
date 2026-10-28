"""Device placement for the registered constant-graph catalog implementation.

This transforms an admitted catalog source, not submitted miner code. Source
spans preserve all existing algebra and formatting; only missing owner-device
placement is inserted. Unknown constructor structure is not a compatibility
promise and is refused.
"""

from __future__ import annotations

import ast


class PlacementRefused(ValueError):
    """The complete registered constructor capability was not recognized."""


def _fail():
    raise PlacementRefused("constant graph device capability is partial or ambiguous")


def _attribute(node, owner, name):
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == owner
        and node.attr == name
    )


def _call(node, name):
    return isinstance(node, ast.Call) and _attribute(node.func, "torch", name)


def _nested(parent, name):
    found = [
        node
        for node in parent.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(found) != 1:
        _fail()
    return found[0]


def rewrite(source: bytes) -> bytes | None:
    """Repair the complete shared implementation, or return None if absent."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, UnicodeError) as error:
        raise PlacementRefused(
            "constant graph device capability: invalid Python source"
        ) from error
    names = (
        "_torch_scatter_standin", "_constant_graph_helpers", "_MeshGraphNetOnCurve"
    )
    roots = [
        [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name
        ]
        for name in names
    ]
    if not any(roots):
        return None
    if any(len(found) != 1 for found in roots):
        _fail()
    scatter = _nested(roots[0][0], "scatter")
    concat = _nested(roots[1][0], "concat_efeat")
    aggregate = _nested(roots[1][0], "aggregate_and_concat")
    forward = _nested(roots[2][0], "forward")
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    lines = source.splitlines(keepends=True)
    offsets, total = [], 0
    for line in lines:
        offsets.append(total)
        total += len(line)
    edits = {}

    def device(node, owner, *, transfer=False, aliases=()):
        allowed = (owner, *aliases)
        supplied = [
            keyword.value for keyword in node.keywords if keyword.arg == "device"
        ]
        if supplied:
            if len(supplied) != 1 or not any(
                _attribute(supplied[0], name, "device") for name in allowed
            ):
                _fail()
            return
        parent = parents.get(node)
        outer = parents.get(parent)
        if (
            isinstance(parent, ast.Attribute)
            and parent.value is node
            and parent.attr == "to"
        ):
            if (
                not isinstance(outer, ast.Call)
                or len(outer.args) != 1
                or outer.keywords
            ):
                _fail()
            if not any(_attribute(outer.args[0], name, "device") for name in allowed):
                _fail()
            return
        end = offsets[node.end_lineno - 1] + node.end_col_offset
        if source[end - 1:end] != b")":
            _fail()
        position = end if transfer else end - 1
        addition = (
            f".to({owner}.device)" if transfer else f", device={owner}.device"
        )
        if position in edits:
            _fail()
        edits[position] = addition.encode()

    def torch_calls(scope, allowed):
        calls = [
            node
            for node in ast.walk(scope)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "torch"
        ]
        if any(node.func.attr not in allowed for node in calls):
            _fail()
        return calls

    torch_calls(scatter, {"zeros", "ones"})
    torch_calls(concat, {"as_tensor", "cat"})
    torch_calls(aggregate, {"as_tensor", "arange", "clamp", "matmul", "cat"})
    torch_calls(forward, {"as_tensor", "cat"})
    fields = [
        node.attr
        for node in ast.walk(forward)
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.value, ast.Name)
        and node.value.id == "graph"
    ]
    if sorted(fields) != ["cases", "dst_local", "dst_np", "nodes_per_case", "src_np"]:
        _fail()

    factories = [
        node for node in ast.walk(scatter)
        if _call(node, "zeros") or _call(node, "ones")
    ]
    if (
        sum(_call(node, "zeros") for node in factories) != 2
        or sum(_call(node, "ones") for node in factories) != 1
    ):
        _fail()
    for node in factories:
        dtype = [
            keyword.value for keyword in node.keywords if keyword.arg == "dtype"
        ]
        if len(dtype) != 1 or not _attribute(dtype[0], "src", "dtype"):
            _fail()
        device(node, "src")

    gathers = [node for node in ast.walk(concat) if _call(node, "as_tensor")]
    if len(gathers) != 2:
        _fail()
    for field, alias in (("src_np", "src_feat"), ("dst_np", "dst_feat")):
        found = [
            node for node in gathers
            if len(node.args) == 1 and _attribute(node.args[0], "graph", field)
        ]
        if len(found) != 1:
            _fail()
        device(found[0], "efeat", transfer=True, aliases=(alias,))

    indices = [
        node for node in ast.walk(aggregate)
        if _call(node, "arange") or _call(node, "as_tensor")
    ]
    if len(indices) == 1:
        node = indices[0]
        dtype = [
            keyword.value for keyword in node.keywords if keyword.arg == "dtype"
        ]
        if (
            not _call(node, "as_tensor")
            or len(node.args) != 1
            or not isinstance(node.args[0], ast.Name)
            or node.args[0].id != "matrix"
            or len(dtype) != 1
            or not _attribute(dtype[0], "efeat", "dtype")
        ):
            _fail()
        device(node, "efeat")
    elif len(indices) == 2:
        for name, argument in (("arange", "nodes"), ("as_tensor", "local")):
            found = [
                node for node in indices
                if _call(node, name)
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == argument
            ]
            if len(found) != 1:
                _fail()
            device(found[0], "efeat", transfer=name == "as_tensor")
    else:
        _fail()

    edges = [node for node in ast.walk(forward) if _call(node, "as_tensor")]
    if (
        len(edges) != 1
        or len(edges[0].args) != 1
        or not isinstance(edges[0].args[0], ast.Name)
        or edges[0].args[0].id != "edges_np"
    ):
        _fail()
    device(edges[0], "x", transfer=True)
    for position in sorted(edits, reverse=True):
        source = source[:position] + edits[position] + source[position:]
    return source
