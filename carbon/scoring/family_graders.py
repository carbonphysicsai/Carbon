"""The sealed kit and the sealed grader of a family registered by data (`family_registry`), served without a producer edit.

`sealed_batch_source` names the kit and the grader of the families the code serves, and its bytes are in every producer
identity. ``install()`` lets its three dispatch functions (``_kit``, ``_pool_graded``, ``_adapter``) also answer for a
family NO code names, and registers that family's grader in `physical_adapters` (its existing ``register``):

- a family is served only from its own kept row, which names its ``sealed_kit`` and ``sealed_grader`` modules by sha256;
  a file that does not hash to its row is never imported and the family is not served;
- its PRODUCER identity binds those files: every module its row names must be in the grader's ``FILES`` (names relative to
  ``carbon/scoring``, as `physical_dual_pack.producer_digest` reads them), so a changed grader or kit always moves the
  family's own digest, the one its pack pins. A grader that leaves one out is refused;
- those modules import nothing else of Carbon: the standard library, numpy, jax, the shared producer files and the files in
  the grader's ``FILES`` only, so no file outside the digest can change a grade (read from their text, nothing computed);
- a family the code serves is never extended or replaced: its calls reach the original function unchanged;
- modules are loaded HERE, when `lean_recipe_retention` or `copy_delivery` is imported. The three functions only read a
  table afterwards: no call a request makes can import, register or change anything.

A family that fails a check is refused whole (logged, ``refused()``) and takes no other family down: it stays unserved, as
with no row. With no row, nothing is wrapped. This module adds no scoring rule and no value of its own.

The interface a family's modules serve. ``sealed_kit``: ``sealed_bank(document, records, version=, [pool=])`` and
``private_roles(bank)``. ``sealed_grader``: ``CHALLENGE`` (the family), ``VERSION``, ``VERSIONS``, ``POOL_VERSIONS`` (the
pool-graded versions, may be empty), ``FILES`` and ``adapter_for_bank(bank, version)`` (``ValueError``: a population with
no grader), plus what `physical_dual_pack` asks of an adapter. A pool-graded family's grader sets ``POOL_GRADED = True``.
"""

from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

from carbon.challenge_kit import family_registry
from carbon.challenge_registry import pinned_module
from carbon.scoring import physical_dual_pack, sealed_batch_source

ROLES = ("sealed_kit", "sealed_grader")
_HERE = Path(__file__).resolve().parent
_LOG = logging.getLogger(__name__)

#: Family -> (kit module, grader module, the files its row names). Add-only.
_SERVED: dict = {}
_REFUSED: dict = {}
#: The wrapped functions' originals, by name: filled once, before the first family is served.
_ORIGINAL: dict = {}


class FamilyGraderRefused(ValueError):
    """A registered family's kit or grader is refused; the family is not served."""


def _bound(adapter, sources) -> bool:
    """Whether every module file the family's row names is in the adapter's producer files."""
    files = getattr(adapter, "FILES", None)
    if type(files) not in (tuple, list) or not all(type(n) is str for n in files):
        return False
    return sources <= {(_HERE / name).resolve() for name in files}


#: Outside Carbon, what a family's module may import beside the standard library.
_LIBRARIES = frozenset({"jax", "numpy"})
#: Calls that import or run code by a computed name: none is allowed.
_COMPUTED = frozenset(
    {
        "__import__",
        "eval",
        "exec",
        "exec_module",
        "import_module",
        "load_module",
        "run_module",
        "run_path",
        "spec_from_file_location",
    }
)


def _import_allowed(name, files) -> bool:
    """Whether the dotted ``name`` a module imports is an allowed library or one of ``files``."""
    top = name.partition(".")[0]
    if top != "carbon":
        return top in _LIBRARIES or top in sys.stdlib_module_names
    try:
        return pinned_module.source_file(name) in files
    except pinned_module.PinnedModuleRefused:
        return False


def _outside(source, files):
    """The first thing a module file imports, or could import, outside ``files`` and the allowed libraries, or None."""
    for node in ast.walk(ast.parse(source.read_bytes())):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _import_allowed(alias.name, files):
                    return alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                return "a relative import"
            # ``from package import module`` names each module; ``from module import name`` names the module itself
            if not _import_allowed(node.module, files):
                for alias in node.names:
                    if not _import_allowed(f"{node.module}.{alias.name}", files):
                        return f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Call):
            called = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if called in _COMPUTED:
                return f"a call of {called}"
    return None


def _load(challenge, blocks):
    """``(kit, grader, sources)`` of a family, every check passed, or `FamilyGraderRefused`."""
    if (
        _original("_kit")(challenge) is not None
        or _original("_pool_graded")(challenge, None)
        or _original("_adapter")(challenge, None, None, None) is not None
    ):
        raise FamilyGraderRefused("the code serves this family")
    kit, grader = (family_registry.module(challenge, role) for role in ROLES)
    sources = frozenset(pinned_module.source_file(b["module"]) for b in blocks.values())
    if getattr(grader, "CHALLENGE", None) != challenge:
        raise FamilyGraderRefused("the grader serves another Challenge")
    if not _bound(grader, sources):
        raise FamilyGraderRefused("the grader's FILES do not bind every module")
    files = {
        (_HERE / name).resolve()
        for name in (*physical_dual_pack._SHARED_FILES, *grader.FILES)
    }
    for source in sorted(sources):
        outside = _outside(source, files)
        if outside is not None:
            raise FamilyGraderRefused(f"{source.name} reaches {outside}")
    if not all(
        callable(getattr(kit, n, None)) for n in ("sealed_bank", "private_roles")
    ):
        raise FamilyGraderRefused("the kit has no sealed bank")
    versions, pools = (getattr(grader, n, None) for n in ("VERSIONS", "POOL_VERSIONS"))
    if (
        type(versions) is not dict
        or type(pools) is not dict
        or not set(pools) <= set(versions)
        or not callable(getattr(grader, "adapter_for_bank", None))
    ):
        raise FamilyGraderRefused("the grader has no version tables or bank dispatch")
    return kit, grader, sources


def install() -> tuple:
    """Serve every kept family with both modules (idempotent, add-only); the families served, sorted."""
    for challenge in family_registry.families():
        if challenge in _SERVED:
            continue
        blocks = family_registry.modules(challenge)
        if not set(ROLES) <= set(blocks):
            continue
        try:
            served = _load(challenge, blocks)
            from carbon.scoring import physical_adapters

            # (refuses a statically named Challenge, or another adapter registered for it)
            physical_adapters.register(served[1])
        # one bad family never takes a door or another family down
        except Exception as error:  # noqa: BLE001
            _REFUSED[challenge] = f"{type(error).__name__}: {error}"
            _LOG.warning("family %r is not served: %s", challenge, error)
            continue
        _REFUSED.pop(challenge, None)
        _wrap()
        _SERVED[challenge] = served
    return tuple(sorted(_SERVED))


def refused() -> dict:
    """{family: reason} of every family `install` did not serve."""
    return dict(_REFUSED)


def _original(name):
    return _ORIGINAL.get(name) or getattr(sealed_batch_source, name)


def _wrap() -> None:
    """Put the three functions in place (once); every call for a family not in `_SERVED` reaches the original."""
    if _ORIGINAL:
        return
    names = ("_kit", "_pool_graded", "_adapter")
    _ORIGINAL.update({name: getattr(sealed_batch_source, name) for name in names})
    for name, mine in zip(names, (_kit, _pool_graded, _adapter), strict=True):
        setattr(sealed_batch_source, name, mine)


def _served(challenge):
    return _SERVED.get(challenge) if type(challenge) is str else None


def _kit(challenge):
    served = _served(challenge)
    return _ORIGINAL["_kit"](challenge) if served is None else served[0]


def _pool_graded(challenge, version):
    served = _served(challenge)
    if served is None:
        return _ORIGINAL["_pool_graded"](challenge, version)
    return version in served[1].POOL_VERSIONS


def _adapter(challenge, bank, version, development_adapter):
    served = _served(challenge)
    if served is None:
        return _ORIGINAL["_adapter"](challenge, bank, version, development_adapter)
    _kit_module, grader, sources = served
    if version not in grader.VERSIONS:
        return None
    try:
        adapter = grader.adapter_for_bank(bank, version)
    except ValueError:  # a population with no sealed grader
        return None
    if adapter is not None and (
        getattr(adapter, "CHALLENGE", None) != challenge or not _bound(adapter, sources)
    ):
        raise sealed_batch_source.SealedBankRefused("sealed_adapter_unbound")
    return adapter
