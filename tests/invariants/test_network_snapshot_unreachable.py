"""Scoring and weights code never reaches the network snapshot (DASHBOARD-02 S3).

The Carbon Validator's condition 4: the signed network snapshot is display
data only. It never feeds scoring or weights. Its builder
(`carbon/challenge_validator/network_snapshot.py`), the dashboard's reader
(`carbon/dashboard/snapshot.py`) and its fixture
(`carbon/dashboard/snapshot_fixtures.py`) are unreachable from every scoring
and weight module: Carbon's scoring engine and weight profile
(`carbon/scoring`), the reward and weight policies (`carbon/rewards`), the
weight publisher (`carbon/chain/sdk_weights.py`) and every Challenge's
validator scoring.

Checked on the code with the attack-store invariant's own walk
(`test_attack_store_unreachable.py`): every import statement, however deep
and however lazily, and every parent package on the way. An import naming a
snapshot module, or a string constant naming it by module or path, counts as
reaching it. Nothing is patched.

Specimen: a planted lazy import of the snapshot builder from a scoring module
is found and fails the same assertion the real check makes.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
#: The snapshot modules, by import name and by path.
MODULES = {
    "carbon.challenge_validator.network_snapshot": (
        "carbon/challenge_validator/network_snapshot.py"
    ),
    "carbon.dashboard.snapshot": "carbon/dashboard/snapshot.py",
    "carbon.dashboard.snapshot_fixtures": "carbon/dashboard/snapshot_fixtures.py",
}
#: Text that names a snapshot module. Kept literal, so a rename fails
#: `test_the_names_searched_for_are_the_modules_own` first.
NAMES = tuple(
    name
    for module, path in MODULES.items()
    for name in (module, path, path.removesuffix(".py"))
)
#: Every scoring and weight surface.
SURFACES = (
    "carbon/scoring",
    "carbon/rewards",
    "carbon/chain/sdk_weights.py",
    "carbon/challenge_validator/scoring.py",
    "carbon/challenge_validator/battery_scoring.py",
    "carbon/challenge_validator/cooling_scoring.py",
    "carbon/challenge_validator/design_scoring.py",
    "carbon/challenge_validator/motor_scoring.py",
)


def _walk_module():
    """The attack-store invariant's import walk, loaded from its own file."""
    path = ROOT / "tests/invariants/test_attack_store_unreachable.py"
    spec = importlib.util.spec_from_file_location("_network_snapshot_walk", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WALK = _walk_module()


def _snapshot_import(name):
    return any(name == m or name.startswith(m + ".") for m in MODULES)


def reach(root=ROOT, surfaces=SURFACES):
    """`(file, how)` for every way the surfaces reach a snapshot module."""
    found = set()
    paths = set(MODULES.values())
    for path in WALK.closure(root, surfaces):
        label = path.relative_to(root).as_posix()
        if label in paths:
            found.add((label, "is a snapshot module"))
            continue
        for name in WALK.SCAN.imported_names(path, root):
            if _snapshot_import(name):
                found.add((label, "imports " + name))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and type(node.value) is str:
                for text in NAMES:
                    if text in node.value:
                        found.add((label, "names " + text))
    return found


def test_no_scoring_or_weight_module_reaches_the_network_snapshot():
    for surface in SURFACES:
        assert (ROOT / surface).exists(), surface
    found = reach()
    assert not found, sorted(found)


def test_the_walk_covers_the_scoring_and_weight_code():
    names = {path.relative_to(ROOT).as_posix() for path in WALK.closure(ROOT, SURFACES)}
    assert {
        "carbon/scoring/engine.py",
        "carbon/scoring/weight_profile.py",
        "carbon/rewards/winner_decay.py",
        "carbon/rewards/testnet_winner_publication.py",
        "carbon/chain/sdk_weights.py",
        "carbon/challenge_validator/scoring.py",
    } <= names


def test_the_names_searched_for_are_the_modules_own():
    for module, path in MODULES.items():
        assert (ROOT / path).is_file(), path
        assert WALK.SCAN._module_name(ROOT / path, ROOT) == module
    builder = (ROOT / MODULES["carbon.challenge_validator.network_snapshot"]).read_text(
        encoding="utf-8"
    )
    assert 'SNAPSHOT_SCHEMA = "carbon.validator.network-snapshot.v1"' in builder


def test_a_planted_import_of_the_snapshot_fails_the_check(tmp_path):
    """Specimen: a lazy import from a scoring module is found and fails the
    assertion the real check makes."""
    for name, text in {
        "carbon/__init__.py": "",
        "carbon/challenge_validator/__init__.py": "",
        "carbon/challenge_validator/network_snapshot.py": "X = 1\n",
        "carbon/challenge_validator/scoring.py": (
            "def score():\n"
            "    from carbon.challenge_validator import network_snapshot\n"
            "    return network_snapshot.X\n"
        ),
    }.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    found = reach(tmp_path, ("carbon/challenge_validator/scoring.py",))
    assert (
        "carbon/challenge_validator/scoring.py",
        "imports carbon.challenge_validator.network_snapshot",
    ) in found
    with pytest.raises(AssertionError):
        assert not found, sorted(found)
