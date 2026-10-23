"""No score, weight, KOTH, Ladder or receiver code loads the funding read
(Validator funding-door ruling, 2026-10-23, condition 3; invariant 11: a
balance or a joining cost is never a score input).

The snapshot invariant's static walk cannot state this: from `carbon/scoring`
it reaches the whole Launchpad through Battery's pinned modules
(`battery_dual_measurement` -> ... -> `battery/campaign` -> the Launchpad's
`installed`, `runner` and `controller`), so any Launchpad route "reaches"
whatever it imports. The check is therefore the attack store's runtime one:

- a fresh interpreter imports every module of the scoring, weight, KOTH,
  Ladder and receiver surfaces and then holds neither funding module;
- statically, only the funding modules themselves and the Launchpad's one
  onboarding door name them anywhere in `carbon/` or `scripts/`;
- specimen: a planted import from a scoring module fails the runtime check.
"""

import importlib.util
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
FUNDING = ("carbon.chain.funding_read", "carbon.development_session.onboarding_funding")
#: The surfaces a balance or cost must never reach.
SURFACES = (
    "carbon/scoring",
    "carbon/rewards",
    "carbon/chain/sdk_weights.py",
    "carbon/challenge_validator/scoring.py",
    "carbon/challenge_validator/battery_scoring.py",
    "carbon/challenge_validator/cooling_scoring.py",
    "carbon/challenge_validator/design_scoring.py",
    "carbon/challenge_validator/motor_scoring.py",
    "carbon/challenge_validator/koth_registry.py",
    "carbon/challenge_validator/ladder_store.py",
    "carbon/challenge_validator/exam_cap.py",
    "carbon/challenge_validator/direct_intake.py",
    "carbon/challenge_validator/direct_receiver.py",
    "carbon/challenge_validator/lean_recipe_retention.py",
)
#: The only files that may name a funding module.
NAMERS = {
    "carbon/chain/funding_read.py",
    "carbon/development_session/onboarding_funding.py",
    "carbon/development_session/chain_onboarding.py",  # the ruling's record
    "scripts/dev/miner_launchpad/onboarding.py",
    "scripts/dev/miner_launchpad/controller.py",
}


def _attack_store_check():
    path = ROOT / "tests/invariants/test_attack_store_unreachable.py"
    spec = importlib.util.spec_from_file_location("_funding_walk", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = _attack_store_check()


def _modules(root, surfaces):
    names = []
    for path in CHECK._starts(root, surfaces):
        names.append(CHECK.SCAN._module_name(path, root))
    return sorted(set(names))


def _leaked(loaded):
    return sorted(
        name
        for name in loaded
        if any(name == f or name.startswith(f + ".") for f in FUNDING)
    )


def test_importing_every_score_weight_koth_ladder_and_receiver_module_loads_no_funding_read():
    for surface in SURFACES:
        assert (ROOT / surface).exists(), surface
    modules = _modules(ROOT, SURFACES)
    # The Launchpad controller itself too: the door's import stays lazy.
    modules.append("scripts.dev.miner_launchpad.controller")
    assert "carbon.scoring.grade_feedback" in modules
    assert "carbon.challenge_validator.ladder_store" in modules
    loaded, _stubbed = CHECK.import_all(modules)
    assert set(modules) <= loaded
    assert not _leaked(loaded)


def test_only_the_funding_modules_and_the_onboarding_door_name_them():
    pattern = re.compile(r"funding_read|onboarding_funding")
    found = set()
    for top in ("carbon", "scripts"):
        for path in (ROOT / top).rglob("*.py"):
            if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
                found.add(path.relative_to(ROOT).as_posix())
    assert found <= NAMERS, sorted(found - NAMERS)
    # The funding module names its chain read; the door names the module.
    assert "carbon/development_session/onboarding_funding.py" in found
    assert "scripts/dev/miner_launchpad/onboarding.py" in found


def test_a_planted_import_from_a_scoring_module_fails_the_runtime_check(tmp_path):
    for name, text in {
        "carbon/__init__.py": "",
        "carbon/scoring/__init__.py": "",
        "carbon/scoring/planted.py": (
            "from carbon.development_session import onboarding_funding\n"
        ),
        "carbon/development_session/__init__.py": "",
        "carbon/development_session/onboarding_funding.py": "X = 1\n",
    }.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    loaded, _ = CHECK.import_all(_modules(tmp_path, ("carbon/scoring",)), root=tmp_path)
    assert _leaked(loaded) == ["carbon.development_session.onboarding_funding"]


def test_no_funding_module_has_a_write_path():
    """The address and the amounts are never persisted (Validator condition)."""
    writes = re.compile(
        r"bopen\(|write_text|write_bytes|\.write\(|sqlite3|json\.dumpb|"
        r"shelve|pickle|os\.open|tempfile|logging|print\("
    )
    for name in FUNDING:
        path = ROOT / (name.replace(".", "/") + ".py")
        found = writes.findall(path.read_text(encoding="utf-8"))
        assert not found, (name, found)
