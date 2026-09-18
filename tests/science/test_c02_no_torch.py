"""Real registered reconstruction in a fresh process that forbids Torch imports.

This proves the tested JAX route does not import Torch. Optional historical
wrappers and other repository routes are outside that claim.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_all_registered_reconstruction_routes_without_torch(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib.abc
import sys
from pathlib import Path

blocked = {'torch', 'neuralop', 'physicsnemo'}
attempted = []
assert not any(name.split('.')[0] in blocked for name in sys.modules)
class RejectTorch(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in blocked:
            attempted.append(fullname)
            raise AssertionError('JAX reconstruction imported forbidden runtime: ' + fullname)
sys.meta_path.insert(0, RejectTorch())
repository = Path(sys.argv[1])
sys.path[:0] = [str(repository / 'tests' / 'science'), str(repository / 'tests' / 'cpu')]
from test_c02_jax_conformance import (
    test_compiled_plan_service_update_reload_and_target_free_prediction,
    test_foundax_exact_profile_updates_resumes_and_predicts,
)
root = Path(sys.argv[2])
for family in ('fno', 'deeponet'):
    destination = root / family
    destination.mkdir()
    test_compiled_plan_service_update_reload_and_target_free_prediction(destination, family)
destination = root / 'foundax'
destination.mkdir()
test_foundax_exact_profile_updates_resumes_and_predicts(destination)
assert not attempted, attempted
assert not any(name.split('.')[0] in blocked for name in sys.modules)
print('three registered JAX reconstruction routes completed without Torch imports')
""",
            str(repository),
            str(tmp_path),
        ],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "three registered JAX reconstruction routes completed" in result.stdout
