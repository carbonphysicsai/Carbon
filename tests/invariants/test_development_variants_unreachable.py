"""No miner surface, the validator or the intake can import the variant module.

OWNER-GRAPHITE-TEST-WAVE-03 §1 (owner, 2026-10-04): a development-only
contract variant is read only by Carbon's development runners; the miner MCP
server, the Launchpad, the validator, the intake and any miner-facing registry
path never do. GRAPHITE-DEV-VARIANTS-01 keeps every variant in
`carbon/reconstruction/development_variants.py` (the registry `DEV_VARIANTS`
and the development compile path `compile_development`). The miner-facing
doors refuse a variant by reading only the registry's data
(`capability_registry.is_development_variant`), never that module.

Checked on the code, with the attack-store invariant's own walk
(`test_attack_store_unreachable.py`): every import statement the surfaces
contain, however deep and however lazily, and every parent package on the way.
An import statement naming the module, or a string constant naming it by
module or path, counts as reaching it. A fresh interpreter that imports every
importable module of the surfaces then holds no variant module. As there, it
runs without numpy (an inert stand-in only where numpy is not installed), so
the contract-authority lane runs it too; the daemon, which computes with numpy
when it loads, is walked statically only (`STATIC_ONLY`).

Specimens: a planted lazy import of the variant module from a miner surface,
one two imports deep behind the intake, a string import from the validator,
and an import by a name built at run time are each found and fail the same
assertion the real check makes.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
VARIANT_PATH = "carbon/reconstruction/development_variants.py"
VARIANT_MODULE = "carbon.reconstruction.development_variants"
#: Text that names the variant module. Kept literal, so a rename of the module
#: fails `test_the_names_searched_for_are_the_modules_own` first.
VARIANT_NAMES = (VARIANT_MODULE, VARIANT_PATH, VARIANT_PATH.removesuffix(".py"))


def _walk_module():
    """The attack-store invariant's import walk, loaded from its own file."""
    path = ROOT / "tests/invariants/test_attack_store_unreachable.py"
    spec = importlib.util.spec_from_file_location("_development_variants_walk", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WALK = _walk_module()
#: Every miner surface (the attack-store invariant's), the validator, the
#: intake and its daemon, and the miner-facing Challenge registry.
SURFACES = (
    *WALK.MINER_SURFACES,
    "carbon/challenge_validator",
    "carbon/battery/intake.py",
    "carbon/battery/intake_client.py",
    "carbon/battery/daemon.py",
    "carbon/challenge_registry",
)


def _variant_import(module):
    return module == VARIANT_MODULE or module.startswith(VARIANT_MODULE + ".")


def reach(root=ROOT, surfaces=SURFACES):
    """`(file, how)` for every way the surfaces reach the variant module."""
    found = set()
    for path in WALK.closure(root, surfaces):
        label = path.relative_to(root).as_posix()
        if label == VARIANT_PATH:
            found.add((label, "is the variant module"))
            continue
        for module in WALK.SCAN.imported_names(path, root):
            if _variant_import(module):
                found.add((label, "imports " + module))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and type(node.value) is str:
                for name in VARIANT_NAMES:
                    if name in node.value:
                        found.add((label, "names " + name))
    return found


def test_no_miner_surface_the_validator_or_the_intake_reaches_the_variant_module():
    for surface in SURFACES:
        assert (ROOT / surface).exists(), surface
    found = reach()
    assert not found, sorted(found)


def test_the_walk_covers_every_door_that_refuses_a_variant():
    """The doors that refuse a variant are walked, and the walk sees the data
    reader they use, so the check is not vacuous."""
    names = {path.relative_to(ROOT).as_posix() for path in WALK.closure(ROOT, SURFACES)}
    assert {
        "carbon/reconstruction/capability_registry.py",
        "carbon/reconstruction/challenge_contracts.py",
        "carbon/challenge_validator/dispatch.py",
        "carbon/battery/daemon.py",
        "carbon/battery/intake.py",
        "carbon/battery/campaign.py",
        "carbon/challenge_registry/registry.py",
        "carbon/miner_mcp/mcp_challenges.py",
        "scripts/dev/miner_launchpad/runner.py",
    } <= names


def test_the_names_searched_for_are_the_modules_own():
    path = ROOT / VARIANT_PATH
    assert path.is_file()
    assert WALK.SCAN._module_name(path, ROOT) == VARIANT_MODULE
    text = path.read_text(encoding="utf-8")
    assert "DEV_VARIANTS = _DevVariants()" in text
    assert "def compile_development(" in text


#: Walked statically only: importing it computes with numpy at module load
#: (its exam rule's float32 epsilon), which the inert stand-in cannot do in a
#: lane without numpy. The intake, which carries submissions to it, is
#: imported at run time.
STATIC_ONLY = frozenset({"carbon.battery.daemon"})


def _importable_modules():
    names = set(WALK._importable_modules())
    for surface in SURFACES[len(WALK.MINER_SURFACES) :]:
        path = ROOT / surface
        files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        names.update(WALK.SCAN._module_name(p, ROOT) for p in files)
    return sorted(names - STATIC_ONLY)


def test_importing_every_door_loads_no_variant_module():
    """A fresh interpreter imports every importable module of the surfaces;
    afterwards it holds no variant module (numpy is an inert stand-in only
    where it is not installed)."""
    modules = _importable_modules()
    assert {
        "carbon.battery.intake",
        "carbon.challenge_validator.dispatch",
        "carbon.challenge_registry.registry",
        "carbon.miner_mcp.service",
    } <= set(modules)
    loaded, _stubbed = WALK.import_all(modules)
    assert set(modules) <= loaded
    leaked = sorted(name for name in loaded if _variant_import(name))
    assert not leaked, leaked


def _plant(tmp_path, files):
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


_PACKAGES = {
    "carbon/__init__.py": "",
    "carbon/reconstruction/__init__.py": "",
    "carbon/reconstruction/development_variants.py": "DEV_VARIANTS = {}\n",
    "carbon/battery/__init__.py": "",
    "carbon/challenge_validator/__init__.py": "",
    "carbon/miner_mcp/__init__.py": "",
}


def test_a_planted_import_of_the_variant_module_fails_the_check(tmp_path):
    """Specimen for the static check: a lazy import from the miner MCP door,
    a chain two imports deep behind the intake and a string import in the
    validator are each found and fail the assertion the real check makes."""
    root = _plant(
        tmp_path,
        {
            **_PACKAGES,
            "carbon/miner_mcp/door.py": (
                "def serve():\n"
                "    from carbon.reconstruction import development_variants\n"
                "    return development_variants.DEV_VARIANTS\n"
            ),
            "carbon/battery/intake.py": "from . import helper\n",
            "carbon/battery/helper.py": (
                "def deeper():\n    from .deep import hint\n    return hint()\n"
            ),
            "carbon/battery/deep.py": (
                "def hint():\n"
                "    import carbon.reconstruction.development_variants as v\n"
                "    return v\n"
            ),
            "carbon/challenge_validator/dispatch.py": (
                "import importlib\n"
                "def load():\n"
                "    return importlib.import_module(\n"
                "        'carbon.reconstruction.development_variants'\n"
                "    )\n"
            ),
        },
    )
    found = reach(root, ("carbon/miner_mcp", "carbon/battery/intake.py"))
    assert (VARIANT_PATH, "is the variant module") in found
    assert ("carbon/battery/deep.py", "imports " + VARIANT_MODULE) in found
    with pytest.raises(AssertionError):
        assert not found, sorted(found)
    found = reach(root, ("carbon/challenge_validator",))
    assert ("carbon/challenge_validator/dispatch.py", "names " + VARIANT_MODULE) in (
        found
    )
    with pytest.raises(AssertionError):
        assert not found, sorted(found)


def test_a_runtime_import_of_the_variant_module_fails_the_import_check(tmp_path):
    """Specimen for the runtime check: a miner module that reaches the variant
    module by a name built at run time, which no import statement or string
    shows, is not seen by the static walk but leaves the module loaded."""
    root = _plant(
        tmp_path,
        {
            **_PACKAGES,
            "carbon/miner_mcp/planted.py": (
                "import importlib\n"
                "_PARTS = ('carbon', 'reconstruction', 'development' + '_variants')\n"
                "importlib.import_module('.'.join(_PARTS))\n"
            ),
        },
    )
    planted = "carbon.miner_mcp.planted"
    assert not reach(root, ("carbon/miner_mcp",))
    loaded, _stubbed = WALK.import_all([planted], root)
    leaked = sorted(name for name in loaded if _variant_import(name))
    assert leaked == [VARIANT_MODULE]
    with pytest.raises(AssertionError):
        assert not leaked, leaked
