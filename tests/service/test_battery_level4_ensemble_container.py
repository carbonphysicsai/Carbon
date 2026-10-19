"""Battery Level 4 graph ensembles rebuilt in a real container (Launchpad R2).

A miner's graph plus multi-member ensemble recipe crashed on `bounded_v`. This
runs that recipe shape through the validator's own `CarrierBackend` in a real
container (`battery_container_runner`: the carrier's isolation arguments) and
checks:
- the ensemble rebuilds with one independently trained graph state per member,
  each on `steps // members`;
- its fit equals the native Level 0 ensemble of the same recipe;
- inference from the frozen state in a second container equals in-process
  inference from the same state (the mean of its members).

Run against the pre-fix base, it is the control: lowering the same recipe
fails on `bounded_v` before any container starts.

Skipped unless `CARBON_BATTERY_TEST_IMAGE` names an available image. Not
established here: the host doctor, the accepted digest-pinned image, GPU.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY / "tests" / "service")]

import battery_container_runner as runner

from carbon.battery import level4 as battery
from carbon.battery import level4_model, level4_worker
from carbon.battery.compile import compile_recipe
from carbon.battery.pool_store import PoolStore
from carbon.battery.worker import CarrierBackend, DirectBackend, WorkLedger
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import intake, staging, submission

pytestmark = pytest.mark.skipif(
    not runner.available(), reason="CARBON_BATTERY_TEST_IMAGE is not available"
)
SEED = 11
STEPS = 40
MEMBERS = 2


def _ensemble(label):
    strategy = battery._steps(battery.level0_strategies()[label], STEPS)
    strategy["parameters"]["ensemble_members"] = MEMBERS
    return strategy


@pytest.mark.parametrize("label", ["scaffold_mlp", "panel_deeponet"])
def test_a_graph_ensemble_rebuilds_and_infers_in_the_isolated_container(
    tmp_path, label
):
    strategy = _ensemble(label)
    _, recipe = compile_recipe(strategy)
    manifest, files = battery.lower_recipe(
        strategy, allowlist_module.load(), max_bytes=intake.BOUNDS["document_bytes"]
    )
    found = {"schema": level4_worker.SCHEMA, "submission": submission.digest(manifest)}
    workspace = staging.workspace(submission.canonical(manifest), files)
    tmp_path.chmod(0o700)
    isolated = CarrierBackend(
        WorkLedger(PoolStore(tmp_path / "state.sqlite3"), tmp_path / "work"),
        None,
        root=REPOSITORY,
        runner=runner.run,
        identity=runner.IDENTITY,
    )

    state, fit = isolated.reconstruct(
        "rec-" + label, recipe, SEED, development=found, workspace=workspace
    )
    model = level4_model.model_from_bytes(state)
    assert isinstance(model, level4_model.GraphEnsemble)
    assert len(model.members) == MEMBERS
    assert all(m.settings["steps"] == STEPS // MEMBERS for m in model.members)

    _, native_fit = DirectBackend(REPOSITORY).reconstruct(None, recipe, SEED)
    assert fit["params_sha256"] == native_fit["params_sha256"], label

    inputs = {
        f"q{i}": {"c1": 1.0 + i * 0.01, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}
        for i in range(4)
    }
    predicted = isolated.infer("inf-" + label, state, inputs)
    assert predicted == DirectBackend(REPOSITORY).infer("y", state, inputs)
