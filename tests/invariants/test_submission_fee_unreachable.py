"""Constitutional invariant (`AGENTS.md` §6.11, `B1`, `B2`):
- Submission fee modules never reach scoring, weights, KOTH, Ladder, or top-level receiver imports.
- `pyproject.toml` and `carbon/reconstruction/worker/build_inputs.txt` carry no fee edits (`B1`),
  and `lean_recipe._source_identity()` / `_implementation_identity()` remain untouched.
- No live `submission_fee_policy.json` is tracked inside `scripts/validator_host_classes/` (`B2`).
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
FEE_MODULES = (
    "carbon.chain.fee_burns",
    "carbon.chain.fee_poster",
    "carbon.challenge_validator.submission_fee",
)
#: Protected scientific, ranking, and reward surfaces that must never load fee code.
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
    "carbon/challenge_validator/version_close.py",
    "scripts/dev/miner_launchpad/controller.py",
)
#: Closed allow-list of files in `carbon/` and `scripts/` that may name the new fee modules.
NAMERS = {
    "carbon/chain/fee_burns.py",
    "carbon/chain/fee_poster.py",
    "carbon/chain/external_signer.py",
    "carbon/challenge_validator/submission_fee.py",
    "carbon/challenge_validator/version_close.py",
    "carbon/challenge_validator/direct_intake.py",
    "carbon/challenge_validator/direct_receiver.py",
    "carbon/development_session/direct_submission.py",
    "scripts/dev/rehearse_testnet_submission_fee.py",
}


def _attack_store_check():
    path = ROOT / "tests/invariants/test_attack_store_unreachable.py"
    spec = importlib.util.spec_from_file_location("_fee_walk", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = _attack_store_check()


def _modules(root: Path, surfaces: tuple[str, ...]) -> list[str]:
    names = []
    for path in CHECK._starts(root, surfaces):
        names.append(CHECK.SCAN._module_name(path, root))
    return sorted(set(names))


def _leaked(loaded: set[str]) -> list[str]:
    return sorted(
        name
        for name in loaded
        if any(name == f or name.startswith(f + ".") for f in FEE_MODULES)
    )


def test_importing_scoring_weights_koth_ladder_and_receivers_loads_no_submission_fee_module():
    for surface in SURFACES:
        assert (ROOT / surface).exists(), surface
    modules = _modules(ROOT, SURFACES)
    assert "carbon.scoring.grade_feedback" in modules
    assert "carbon.rewards.waterfall" in modules
    assert "carbon.challenge_validator.direct_intake" in modules
    assert "carbon.challenge_validator.direct_receiver" in modules
    assert "carbon.challenge_validator.version_close" in modules
    loaded, _ = CHECK.import_all(modules)
    assert set(modules) <= loaded
    assert not _leaked(loaded)


def test_only_allowlisted_intake_signer_and_client_modules_name_submission_fee_modules():
    pattern = re.compile(r"\b(?:fee_burns|fee_poster|submission_fee)\b")
    found = set()
    for top in ("carbon", "scripts"):
        for path in (ROOT / top).rglob("*.py"):
            if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
                found.add(path.relative_to(ROOT).as_posix())
    assert found <= NAMERS, sorted(found - NAMERS)
    assert "carbon/challenge_validator/submission_fee.py" in found
    assert "carbon/chain/fee_burns.py" in found


def test_planted_submission_fee_import_in_scoring_fails_runtime_check(tmp_path: Path):
    for name, text in {
        "carbon/__init__.py": "",
        "carbon/scoring/__init__.py": "",
        "carbon/scoring/planted.py": (
            "from carbon.challenge_validator import submission_fee\n"
        ),
        "carbon/challenge_validator/__init__.py": "",
        "carbon/challenge_validator/submission_fee.py": "X = 1\n",
    }.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    loaded, _ = CHECK.import_all(_modules(tmp_path, ("carbon/scoring",)), root=tmp_path)
    assert _leaked(loaded) == ["carbon.challenge_validator.submission_fee"]


def test_miner_signer_fee_burn_imports_nothing_from_carbon():
    signer_file = ROOT / "carbon_miner_signer/fee_burn.py"
    text = signer_file.read_text(encoding="utf-8")
    assert not re.search(r"^\s*(?:from|import)\s+carbon\b", text, re.MULTILINE)
    assert not (ROOT / "carbon_miner_signer/fee_burn_record.json").exists()


def test_worker_build_inputs_source_identity_and_repo_policy_cleanliness():
    """Enforce `B1`, `B2`, and actual `_source_identity()` assertion."""
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "fee_burn_record" not in pyproject_text
    assert not (
        ROOT / "scripts/validator_host_classes/submission_fee_policy.json"
    ).exists()

    build_inputs = {
        line.strip()
        for line in (ROOT / "carbon/reconstruction/worker/build_inputs.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    fee_paths = {
        "carbon/chain/fee_burns.py",
        "carbon/chain/fee_poster.py",
        "carbon/challenge_validator/submission_fee.py",
        "carbon_miner_signer/fee_burn.py",
    }
    assert not (build_inputs & fee_paths)

    from carbon.challenge_validator import lean_recipe

    source_paths = {str(p) for p in getattr(lean_recipe, "_SOURCE_PATHS", ())}
    assert not (source_paths & fee_paths)
    # `N17`: Pin exact `origin/main` baseline digests so any accidental movement fails CI!
    assert (
        lean_recipe._source_identity()
        == "sha256:8179b321fe782305d17c5a5d14b193de0ed65ae9a7d044539be15615fcaa2053"
    )
    assert (
        lean_recipe._implementation_identity()
        == "sha256:a368723b719a86d943018e5902de0228681e7b825f3e3084e58572e932ebfc43"
    )
