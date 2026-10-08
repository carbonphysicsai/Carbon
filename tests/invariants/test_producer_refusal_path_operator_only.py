"""A producer refusal's `path` reaches the operator's console only.

`ProducerRefused.record()` carries the operator's own local path when that is
the fix (`producer_dir_not_owner_only`). A server path in a response body would
disclose the host's layout, so wherever Carbon catches a `ProducerRefused`,
`.record()` may appear only as `print(json.dumps(refused.record()))` (a
command's console output), and `.path` is never read at all.
"""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]


def _catches_producer_refused(handler):
    kinds = handler.type
    names = kinds.elts if isinstance(kinds, ast.Tuple) else [kinds]
    return any(
        (isinstance(k, ast.Name) and k.id == "ProducerRefused")
        or (isinstance(k, ast.Attribute) and k.attr == "ProducerRefused")
        for k in names
        if k is not None
    )


def _is_console_print(call, parents):
    """`call` is the sole argument of `json.dumps(...)`, itself the sole
    argument of `print(...)`."""
    dumps = parents.get(call)
    if not (
        isinstance(dumps, ast.Call)
        and isinstance(dumps.func, ast.Attribute)
        and dumps.func.attr == "dumps"
        and dumps.args == [call]
    ):
        return False
    printed = parents.get(dumps)
    return (
        isinstance(printed, ast.Call)
        and isinstance(printed.func, ast.Name)
        and printed.func.id == "print"
        and printed.args == [dumps]
    )


def violations(source, where="<source>"):
    tree = ast.parse(source)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    found = []
    for handler in ast.walk(tree):
        if not (
            isinstance(handler, ast.ExceptHandler)
            and handler.name
            and handler.type is not None
            and _catches_producer_refused(handler)
        ):
            continue
        for statement in handler.body:
            for node in ast.walk(statement):
                if not (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == handler.name
                ):
                    continue
                if node.attr == "path":
                    found.append(f"{where}:{node.lineno} reads .path")
                elif node.attr == "record":
                    call = parents.get(node)
                    if not (
                        isinstance(call, ast.Call) and _is_console_print(call, parents)
                    ):
                        found.append(f"{where}:{node.lineno} .record() off the console")
    return found


def test_the_rule_catches_a_path_in_a_response():
    leaking = """
try:
    pass
except ProducerRefused as refused:
    return 404, refused.record()
"""
    reading = """
try:
    pass
except (ProducerRefused, OSError) as e:
    body = {"where": e.path}
"""
    console = """
try:
    pass
except ProducerRefused as refused:
    print(json.dumps(refused.record()))
"""
    assert len(violations(leaking)) == 1
    assert len(violations(reading)) == 1
    assert violations(console) == []


def test_a_producer_refusal_path_reaches_only_the_console():
    found = []
    for path in sorted((ROOT / "carbon").rglob("*.py")):
        source = path.read_text()
        if "ProducerRefused" in source:
            found += violations(source, str(path.relative_to(ROOT)))
    assert found == []
