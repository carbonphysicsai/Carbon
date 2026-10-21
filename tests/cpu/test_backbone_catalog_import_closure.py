"""The catalog reaches miner surfaces as data only (OWNER-BACKBONE-CATALOG-01):
the validator door, the registry, Launchpad's capabilities and Motor's campaign
import no torch, and nothing reaches the catalog's torch modules."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = (
    "carbon.challenge_validator.dispatch",
    "carbon.challenge_validator.lean_recipe",
    "carbon.challenge_registry.campaigns",
    "carbon.challenge_registry.motor",
    "carbon.backbone_catalog.served",
    "carbon.motor.campaign",
    "carbon.motor.catalog_practice",
    "carbon.development_session.construction_recipe",
)


def test_miner_surfaces_import_no_torch():
    program = (
        "import importlib, json, sys\n"
        f"for name in {MODULES!r}:\n"
        "    importlib.import_module(name)\n"
        "from carbon.challenge_registry import describe\n"
        "describe('electric-motor-magnetics', '1.2')\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.split('.')[0] in ('torch', 'neuralop', 'physicsnemo') or m.startswith('carbon.backbone_catalog.torch'))))\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            f"import sys; sys.path.insert(0, {str(ROOT)!r})\n" + program,
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    assert json.loads(result.stdout.strip().splitlines()[-1]) == []


def _attack_invariant():
    import importlib.util

    path = ROOT / "tests/invariants/test_attack_store_unreachable.py"
    spec = importlib.util.spec_from_file_location("_catalog_closure_scan", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_miner_surface_reaches_the_owner_pipeline_or_the_receiver():
    # Validator, 2026-10-20: the catalog is cut at its boundary. Miner paths
    # read `listing` only; the owner pipeline, its installers and the receiver
    # are unreachable, by the attack invariant's own static closure (every
    # import anywhere in a file, function-level ones included).
    invariant = _attack_invariant()
    reached = {path.relative_to(ROOT).as_posix() for path in invariant.closure(ROOT)}
    assert "carbon/backbone_catalog/listing.py" in reached
    assert "carbon/agent_campaign/graphite/miner/driver.py" in reached
    for owner_only in (
        "carbon/backbone_catalog/pipeline.py",
        "carbon/challenge_validator/direct_receiver.py",
        "scripts/dev/library_bundle.py",
        "scripts/dev/catalog_install.py",
    ):
        assert owner_only not in reached, owner_only


def test_the_catalog_package_imports_nothing_from_scripts():
    invariant = _attack_invariant()
    for path in sorted((ROOT / "carbon/backbone_catalog").glob("*.py")):
        names = invariant.SCAN.imported_names(path, ROOT)
        assert not [n for n in names if n.split(".")[0] == "scripts"], path.name
