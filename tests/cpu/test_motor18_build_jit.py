"""Motor 1.8's graph build runs its forward compiled (carbon/level4/train.py JIT_FORWARD_VERSIONS; owner via the Lead,
Sun 15 Nov 2026: "Just don't count it out due to a tiny difference", item 7 y).

Claims, on a PUBLIC synthetic Motor 1.8 graph fitted on Motor 1.8's public TRAIN through the real
physical_graph_adapter_v2 build: the compiled build repeats bit for bit (a second fit in the same process, and a build in
a fresh process), and its trained parameters and train_loss equal the eager build's (so the graded score, a function of
the trained parameters, the graph and the inference program, cannot move). Synthetic data only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from carbon.level4 import train

MOTOR_18 = ("electric-motor-magnetics", "1.8")
CONFIGURATION = {"training": {"steps": 64, "batch_size": 16}}


def _fitted(monkeypatch, *, compiled):
    from test_graph_route_v2 import _fit

    monkeypatch.setattr(
        train,
        "JIT_FORWARD_VERSIONS",
        frozenset({MOTOR_18}) if compiled else frozenset(),
    )
    model, fitted, inputs = _fit(MOTOR_18, CONFIGURATION)
    return model, fitted, inputs


def test_motor_1_8_builds_compiled_and_matches_the_eager_build(monkeypatch):
    assert train.forward_mode(*MOTOR_18) == train.FORWARD_JIT
    _model, eager, _ = _fitted(monkeypatch, compiled=False)
    model, compiled, _ = _fitted(monkeypatch, compiled=True)
    assert model.prepared.isolated_apply is not None  # really the compiled forward
    assert compiled["params_sha256"] == eager["params_sha256"]
    assert compiled["train_loss"] == eager["train_loss"]
    assert compiled["member_losses"] == eager["member_losses"]


def test_the_compiled_build_repeats_bit_for_bit_in_the_same_process(monkeypatch):
    from test_graph_route_v2 import _train

    model, first, _ = _fitted(monkeypatch, compiled=True)
    _raw, inputs, targets = _train(MOTOR_18)
    assert model.fit(inputs, targets, seed=0)["params_sha256"] == first["params_sha256"]


_CHILD = """
import json, sys
sys.path[:0] = [{here!r}]
from test_graph_route_v2 import _fit
print(json.dumps(_fit({key!r}, {configuration!r})[1]["params_sha256"]))
"""


@pytest.mark.skipif(os.name != "posix", reason="a fresh-process build")
def test_the_compiled_build_repeats_bit_for_bit_in_a_fresh_process(monkeypatch):
    _model, here_fit, _ = _fitted(monkeypatch, compiled=True)
    here = os.path.dirname(os.path.abspath(__file__))
    source = _CHILD.format(here=here, key=MOTOR_18, configuration=CONFIGURATION)
    done = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr[-3000:]
    assert json.loads(done.stdout.strip().splitlines()[-1]) == here_fit["params_sha256"]
