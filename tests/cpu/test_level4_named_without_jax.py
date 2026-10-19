"""A Torch build base has no JAX. Lowering a named call (torch's relu) admits
the name against `named.NAMES`, so it must not import JAX; only rebuilding the
graph runs Carbon's kernels. The name set and the kernels stay identical.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import named

pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[2]

LOWER_RELU_WITHOUT_JAX = """
import sys
sys.modules["jax"] = None  # any `import jax` now raises ImportError
from pathlib import Path
import torch
from carbon.level4 import allowlist as allowlist_module
from carbon.level4.tooling import lower_torch

class Relu(torch.nn.Module):
    def forward(self, x):
        return torch.relu(x) * 2.0

v5 = Path(allowlist_module.__file__).with_name("allowlist_v5.json")
program = torch.export.export(Relu(), (torch.ones(2, 3),)).run_decompositions()
doc, _ = lower_torch.lower(program, allowlist=allowlist_module.load(v5))
nodes = doc["graphs"][doc["entry"]]["nodes"]
print([n.get("params", {}).get("name") for n in nodes if n["op"] == "named_function"])
"""


def test_lowering_a_torch_relu_does_not_import_jax():
    done = subprocess.run(
        [sys.executable, "-c", LOWER_RELU_WITHOUT_JAX],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip().splitlines()[-1] == "['relu']"


def test_the_name_set_is_exactly_the_kernels():
    pytest.importorskip("jax")
    assert set(named.kernels()) == named.NAMES
