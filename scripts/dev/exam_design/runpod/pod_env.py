"""What a pod is shipped, and how big its environment may be (shared by the
A40 harness and Graphite's pods).

RunPod answers a create request whose environment is over about 118,000
characters with an opaque HTTP 500, which the operator layer can only record
as an ambiguous launch. So a pod ships the static import closure of the
modules it runs, never the whole tree, and its environment is measured
before any create (`env_chars`; `ENV_LIMIT_CHARS` is a conservative bound).
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

#: Conservative bound on a pod environment (names plus values); the
#: provider's limit lies between 100,000 and 250,000 characters, and an
#: oversized request fails as an opaque 500.
ENV_LIMIT_CHARS = 90_000


def read_blobs(ref, repository, paths):
    """{path: bytes} at `ref`, in one `git cat-file --batch`; a path that is
    not a blob at `ref` raises ValueError."""
    request = "".join(f"{ref}:{p}\n" for p in paths).encode()
    blob = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "--batch"],
        input=request,
        capture_output=True,
        check=True,
    ).stdout
    out, offset = {}, 0
    for path in paths:
        end = blob.index(b"\n", offset)
        header = blob[offset:end].split()
        if len(header) != 3 or header[1] != b"blob":
            raise ValueError(f"refused: {path} is not a blob at {ref}")
        size = int(header[2])
        out[path] = blob[end + 1 : end + 1 + size]
        offset = end + 1 + size + 1
    return out


def module_name(path):
    parts = list(Path(path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def import_closure(sources, entries):
    """Paths of `sources` ({path: bytes}) reachable from `entries` by static
    imports (module level and inside functions), with every parent package's
    `__init__`. Names that are not in `sources` (stdlib, third party) are
    ignored."""
    by_module = {module_name(p): p for p in sources if p.endswith(".py")}
    seen, queue = set(), []

    def want(name):
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            path = by_module.get(".".join(parts[:i]))
            if path is not None and path not in seen:
                seen.add(path)
                queue.append(path)

    for entry in entries:
        want(entry)
    while queue:
        path = queue.pop()
        package = module_name(path).split(".")
        if not path.endswith("__init__.py"):
            package = package[:-1]
        for node in ast.walk(ast.parse(sources[path])):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    want(alias.name)
            elif isinstance(node, ast.ImportFrom):
                base = package[: len(package) - (node.level - 1)] if node.level else []
                module = ".".join(
                    [*base, *(node.module.split(".") if node.module else [])]
                )
                want(module)
                for alias in node.names:
                    want(module + "." + alias.name)
    return sorted(seen)


def env_chars(env):
    """Total characters of a pod environment (names plus values)."""
    return sum(len(k) + len(v) for k, v in dict(env).items())


def largest_variable(env):
    return max(dict(env).items(), key=lambda kv: len(kv[1]))[0]
