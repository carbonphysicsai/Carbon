"""AST helpers for resolving imported Python module namespaces."""

from __future__ import annotations

import ast
from pathlib import Path


def _module_name(repository_root: Path, path: Path) -> str:
    relative = path.relative_to(repository_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _from_module(repository_root: Path, path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    current = _module_name(repository_root, path).split(".")
    package = current if path.name == "__init__.py" else current[:-1]
    trim = node.level - 1
    if trim > len(package):
        return ""
    base = package[: len(package) - trim]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _module_exists(repository_root: Path, module_name: str) -> bool:
    target = repository_root.joinpath(*module_name.split("."))
    return target.with_suffix(".py").is_file() or (target / "__init__.py").is_file()


def direct_import_modules(
    repository_root: Path,
    path: Path,
    *,
    tree: ast.AST | None = None,
) -> tuple[tuple[str, int], ...]:
    """Return directly imported modules, including ImportFrom module aliases."""
    parsed = (
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if tree is None
        else tree
    )
    imports: list[tuple[str, int]] = []
    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _from_module(repository_root, path, node)
            if base:
                imports.append((base, node.lineno))
            for alias in node.names:
                if alias.name == "*":
                    continue
                candidate = f"{base}.{alias.name}" if base else alias.name
                if _module_exists(repository_root, candidate):
                    imports.append((candidate, node.lineno))
    return tuple(imports)
