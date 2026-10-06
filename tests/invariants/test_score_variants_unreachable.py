"""No miner surface, the validator or the intake can import the development
score variant module (VALIDATOR-09).

A development score variant is read only by Carbon's development runners and
the operator's tuning tools. The miner MCP server, the Launchpad, the
validator, the intake and every miner-facing registry path never reach
`carbon/scoring/development_score_variants.py`. A Challenge's scoring declares
the legs a variant may weight as data only
(`ChallengeScoring.declared_score_components`).

This reuses the development-variant invariant's surfaces and both walks (the
static import walk and a fresh interpreter importing every door), checked
against this module's own names. Nothing is patched.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
MODULE = "carbon.scoring.development_score_variants"
PATH = "carbon/scoring/development_score_variants.py"
NAMES = (MODULE, PATH, PATH.removesuffix(".py"))


def _load(name):
    path = ROOT / "tests/invariants" / name
    spec = importlib.util.spec_from_file_location("_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load("test_development_variants_unreachable.py")
WALK = BASE.WALK


def _imports_module(name):
    return name == MODULE or name.startswith(MODULE + ".")


def reach(root=ROOT, surfaces=BASE.SURFACES):
    """`(file, how)` for every way the surfaces reach the score variant
    module: the module itself, an import naming it, or a string naming it."""
    found = set()
    for path in WALK.closure(root, surfaces):
        label = path.relative_to(root).as_posix()
        if label == PATH:
            found.add((label, "is the score variant module"))
            continue
        for name in WALK.SCAN.imported_names(path, root):
            if _imports_module(name):
                found.add((label, "imports " + name))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and type(node.value) is str:
                for text in NAMES:
                    if text in node.value:
                        found.add((label, "names " + text))
    return found


def test_no_miner_surface_the_validator_or_the_intake_reaches_score_variants():
    for surface in BASE.SURFACES:
        assert (ROOT / surface).exists(), surface
    found = reach()
    assert not found, sorted(found)


def test_importing_every_door_loads_no_score_variant_module():
    modules = BASE._importable_modules()
    assert "carbon.challenge_validator.scoring" in modules
    loaded, _stubbed = WALK.import_all(modules)
    leaked = sorted(name for name in loaded if _imports_module(name))
    assert not leaked, leaked


def test_the_name_searched_for_is_the_modules_own():
    path = ROOT / PATH
    assert path.is_file()
    assert WALK.SCAN._module_name(path, ROOT) == MODULE
    assert "def load_variant(" in path.read_text(encoding="utf-8")


def test_a_planted_import_of_score_variants_fails_the_check(tmp_path):
    """Specimen: a lazy import from the validator package is found and fails
    the assertion the real check makes."""
    root = BASE._plant(
        tmp_path,
        {
            "carbon/__init__.py": "",
            "carbon/scoring/__init__.py": "",
            "carbon/scoring/development_score_variants.py": "X = 1\n",
            "carbon/challenge_validator/__init__.py": "",
            "carbon/challenge_validator/door.py": (
                "def load():\n"
                "    from carbon.scoring import development_score_variants\n"
                "    return development_score_variants.X\n"
            ),
        },
    )
    found = reach(root, ("carbon/challenge_validator",))
    assert ("carbon/challenge_validator/door.py", "imports " + MODULE) in found
    with pytest.raises(AssertionError):
        assert not found, sorted(found)
