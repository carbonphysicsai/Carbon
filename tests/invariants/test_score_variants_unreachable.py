"""No miner surface, the validator or the intake can import the development
score variant module (VALIDATOR-09).

A development score variant is read only by Carbon's development runners and
the operator's tuning re-scorer. The miner MCP server, the Launchpad, the
validator, the intake and every miner-facing registry path never reach
`carbon/scoring/development_score_variants.py`. A Challenge's scoring declares
the components a variant may weight as data only
(`ChallengeScoring.declared_score_components`).

This reuses the development-variant invariant's surfaces and both its walks:
the static import walk, and a fresh interpreter importing every door.
"""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
MODULE = "carbon.scoring.development_score_variants"
PATH = "carbon/scoring/development_score_variants.py"


def _load(name):
    path = ROOT / "tests/invariants" / name
    spec = importlib.util.spec_from_file_location("_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load("test_development_variants_unreachable.py")


@pytest.fixture
def score_variant_names(monkeypatch):
    """Point the development-variant walk at the score variant module."""
    monkeypatch.setattr(BASE, "VARIANT_MODULE", MODULE)
    monkeypatch.setattr(BASE, "VARIANT_PATH", PATH)
    monkeypatch.setattr(BASE, "VARIANT_NAMES", (MODULE, PATH, PATH.removesuffix(".py")))


def test_no_miner_surface_the_validator_or_the_intake_reaches_score_variants(
    score_variant_names,
):
    for surface in BASE.SURFACES:
        assert (ROOT / surface).exists(), surface
    found = BASE.reach()
    assert not found, sorted(found)


def test_importing_every_door_loads_no_score_variant_module(score_variant_names):
    modules = BASE._importable_modules()
    loaded, _stubbed = BASE.WALK.import_all(modules)
    leaked = sorted(name for name in loaded if BASE._variant_import(name))
    assert not leaked, leaked


def test_the_name_searched_for_is_the_modules_own():
    path = ROOT / PATH
    assert path.is_file()
    assert BASE.WALK.SCAN._module_name(path, ROOT) == MODULE
    assert "def load_variant(" in path.read_text(encoding="utf-8")


def test_a_planted_import_of_score_variants_fails_the_check(
    tmp_path, score_variant_names
):
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
    found = BASE.reach(root, ("carbon/challenge_validator",))
    assert ("carbon/challenge_validator/door.py", "imports " + MODULE) in found
    with pytest.raises(AssertionError):
        assert not found, sorted(found)
