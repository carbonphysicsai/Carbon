"""Static source boundary for registered score kernels, not an execution audit.

The audit follows repository-local Python imports from explicit entry modules.
It fails closed when a chain or reward module becomes reachable. Dynamic
imports, caller-provided objects and runtime injection are separately reported
as unproved; this tool never accesses a chain or protected exam material.
"""

from __future__ import annotations

import ast
import importlib.util
from collections import deque
from pathlib import Path

SCORE_ROOTS = (
    "carbon.scoring.engine",
    "carbon.scoring.development",
    "carbon.battery.value.scoring",
    "carbon.battery.value.score_tuning",
    "carbon.design_search.score_bridge",
    "carbon.challenge_validator.battery_scoring",
    "carbon.challenge_validator.motor_scoring",
    "carbon.challenge_validator.cooling_scoring",
)
FORBIDDEN = ("carbon.chain", "carbon.rewards", "bittensor")
PROVEN_SCORE_ROOTS = (
    "carbon.scoring.engine",
    "carbon.battery.value.scoring",
    "carbon.design_search.score_bridge",
)


def _path(root: Path, module: str) -> Path | None:
    stem = root.joinpath(*module.split("."))
    for candidate in (stem.with_suffix(".py"), stem / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _imports(
    root: Path, module: str, source: str, *, package: bool
) -> tuple[set[str], list[str]]:
    tree = ast.parse(source, filename=module)
    dependencies: set[str] = set()
    dynamic: list[str] = []
    context = module if package else module.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            dependencies.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = importlib.util.resolve_name(
                    "." * node.level + (node.module or ""), context
                )
            else:
                base = node.module or ""
            dependencies.add(base)
            dependencies.update(
                candidate
                for alias in node.names
                if alias.name != "*"
                for candidate in (base + "." + alias.name,)
                if _path(root, candidate) is not None
            )
        elif isinstance(node, ast.Call) and (
            isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
        ):
            dynamic.append(f"{module}:{node.lineno}")
    return dependencies, dynamic


def audit(root: Path, roots=SCORE_ROOTS, *, overrides=None) -> dict:
    """Return complete static reachability and explicit unknowns for these roots."""
    overrides = overrides or {}
    seen: set[str] = set()
    missing: set[str] = set()
    dynamic: list[str] = []
    pending = deque(roots)
    parent = {name: None for name in roots}
    while pending:
        module = pending.popleft()
        if module in seen:
            continue
        seen.add(module)
        if not module.startswith("carbon."):
            continue
        path = _path(root, module)
        if path is None:
            missing.add(module)
            continue
        source = overrides.get(module, path.read_text(encoding="utf-8"))
        imports, calls = _imports(
            root, module, source, package=path.name == "__init__.py"
        )
        dynamic.extend(calls)
        for dependency in sorted(imports - seen):
            parent.setdefault(dependency, module)
            pending.append(dependency)
    forbidden = sorted(
        module
        for module in seen
        if any(module == name or module.startswith(name + ".") for name in FORBIDDEN)
    )

    def path_to(name):
        path = []
        while name is not None:
            path.append(name)
            name = parent[name]
        return list(reversed(path))

    return {
        "roots": list(roots),
        "forbidden_reachable": forbidden,
        "first_forbidden_paths": {
            family: path_to(
                next(
                    name
                    for name in forbidden
                    if name == family or name.startswith(family + ".")
                )
            )
            for family in FORBIDDEN
            if any(
                name == family or name.startswith(family + ".") for name in forbidden
            )
        },
        "score_root_paths": {
            name: path_to(name) for name in PROVEN_SCORE_ROOTS if name in seen
        },
        "missing_local_modules": sorted(missing),
        "dynamic_import_calls": sorted(dynamic),
        "local_modules": sorted(name for name in seen if name.startswith("carbon.")),
        "local_modules_seen": len(
            [name for name in seen if name.startswith("carbon.")]
        ),
    }
