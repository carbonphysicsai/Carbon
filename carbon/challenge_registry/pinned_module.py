"""A ``{module, sha256}`` block: a ``carbon.*`` module named by host data and imported only after its file is hashed.

The same integrity shape as a ``version_overlay`` dispatch (v2 ruling row 4033): the file is found by path, importing
nothing, its bytes (CRLF read as LF) must hash to the named sha256, and only then is it imported. Used by the host
registries (`family_registry`, `exam_build`).
"""

from __future__ import annotations

import hashlib
import importlib
import re
from pathlib import Path

import carbon

_MODULE = re.compile(r"carbon(\.[a-z_][a-z0-9_]*)+")
_SHA = re.compile(r"[0-9a-f]{64}")


class PinnedModuleRefused(ValueError):
    """The block is malformed, its module has no source file, or the file's sha256 differs."""


def source_file(name: str) -> Path:
    """The source file a ``carbon.*`` module is imported from, found by path over ``carbon.__path__`` in import order:
    nothing is imported and no package's ``__init__`` runs."""
    if type(name) is not str or not _MODULE.fullmatch(name):
        raise PinnedModuleRefused(f"{name!r} must be a carbon.* module")
    parts = name.split(".")[1:]
    for base in carbon.__path__:
        found = Path(base).joinpath(*parts).with_suffix(".py")
        if found.is_file():
            return found.resolve()
    raise PinnedModuleRefused(f"module {name} is not found")


def file_sha256(name: str) -> str:
    """The sha256 of a ``carbon.*`` module's source file (CRLF read as LF), found without importing anything."""
    path = source_file(name)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise PinnedModuleRefused(f"module {name} is unreadable") from error
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def check(block) -> None:
    """The block is exactly ``{module, sha256}`` and names a module file that hashes to it (not imported)."""
    if (
        type(block) is not dict
        or set(block) != {"module", "sha256"}
        or type(block["sha256"]) is not str
        or not _SHA.fullmatch(block["sha256"])
    ):
        raise PinnedModuleRefused("a module block is exactly {module, sha256}")
    if file_sha256(block["module"]) != block["sha256"]:
        raise PinnedModuleRefused(f"module {block['module']}: its sha256 differs")


def load(block):
    """Import a block's module, checked first, every time; the module handed back is the hashed file's own."""
    check(block)
    name = block["module"]
    try:
        loaded = importlib.import_module(name)
    except Exception as error:
        raise PinnedModuleRefused(f"module {name} does not import") from error
    origin = getattr(getattr(loaded, "__spec__", None), "origin", None)
    if not origin or Path(origin).resolve() != source_file(name):
        raise PinnedModuleRefused(f"module {name} is loaded from another file")
    return loaded
