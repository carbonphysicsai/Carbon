"""Real isolated JAX construction on manufactured engineering inputs.

This verifies the provider program, not Burgers quality or a model-backed agent.
No reference solver, provider API or campaign authorization is consumed here.
"""

import json
import os
from dataclasses import asdict
from pathlib import Path

import numpy as np

from carbon.development_session import research_training
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_carrier import _run
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)
from carbon.measurement_runtime import development as measurement
from carbon.reconstruction._vendor.carbon_jax_lab.config import (
    ModelConfig,
    TaskConfig,
    TrainConfig,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.worker.docker_runtime import load_image_identity


def test_actual_jax_learning_curve_checkpoint_and_physical_mean(tmp_path):
    ledger = CampaignLedger(tmp_path / "ledger")
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
            "campaign_id": "engineering-practice-program",
            "implementation": "candidate",
            "objective": "synthetic-engineering",
            "sampling": "manufactured-engineering-not-burgers-reference",
            "control": "none",
            "selection": "none",
            "replica_policy": "single-engineering-probe",
            "provider": "none",
            "owner": "fixture",
        }
    )
    x = np.arange(64, dtype=float) / 64
    times = np.tile(np.array([0.0, 0.05, 0.1]), (2, 1))
    files = {}
    for role, offset in [("train", 0.2), ("validation", 0.3)]:
        initial = np.array(
            [offset + np.sin(2 * np.pi * x), offset + 0.7 * np.cos(2 * np.pi * x)]
        )
        solution = np.array(
            [
                offset
                + (u - offset)[None, :]
                * np.exp(-4 * np.pi**2 * 0.01 * times[i, :, None])
                for i, u in enumerate(initial)
            ]
        )
        data = Trajectories(
            initial,
            np.array([0.01, 0.01]),
            times,
            solution,
            x,
            role,
            "MANUFACTURED_ENGINEERING_ONLY",
        )
        path = tmp_path / (role + ".npz")
        data.save(path)
        files[role + ".npz"] = path.read_bytes()
    recipe = {
        "model": asdict(ModelConfig(width=8, depth=1, n_modes=8)),
        "task": asdict(TaskConfig(enforce_mean=True)),
        "train": asdict(TrainConfig(steps=3, warmup_steps=0, batch_size=2)),
        "profile_digest": digest(b"manufactured-engineering-only"),
        "productive_seconds": 75,
    }
    files.update(
        {
            "recipe.json": canonical(recipe),
            "practice-scales.json": canonical(
                [{"amplitude": 1.0, "characteristic_time": 0.3}] * 2
            ),
            "research-randomness.bin": bytes(range(32)),
            "development-measurement.py": Path(measurement.__file__).read_bytes(),
        }
    )
    result = _run(
        ledger,
        owner="fixture",
        identity="practice-engineering-one",
        source=Path(research_training.__file__).read_text(),
        files=files,
        image=load_image_identity(Path(os.environ["CARBON_C03_IMAGE_MANIFEST"])),
        seconds=120,
        provenance="ENGINEERING_REAL_JAX_MANUFACTURED_INPUTS",
        extra_resources={"research_trials": 1},
    )
    snapshot = ledger.root / result["operation"] / "snapshot"
    report = json.loads((snapshot / "practice-result.json").read_bytes())
    curve = json.loads((snapshot / "learning-curve.json").read_bytes())
    assert report["completed_steps"] == 3 and len(curve) == 3
    assert report["measurement_version"] == measurement.VERSION
    assert report["summary"]["mean_drift_max"] < 2e-6
    assert not report["official_eligible"] and not report["accepted_improvement"]
    assert report["training_cases"] == 2 and report["practice_cases"] == 2
    assert any("checkpoint" in name for name in result["files"])
