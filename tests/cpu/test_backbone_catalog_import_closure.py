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
