"""Fixed real DEVELOPMENT practice program; no synthetic metric substitution.

Executed only in the isolated research carrier, separately from miner scripts.
Inputs are public TRAIN/validation trajectories plus physical scale metadata.
The same installed lab Trainer, configs and inference implement C-02 recipes.
"""

from __future__ import annotations


def main():
    import json
    import runpy
    from pathlib import Path

    import numpy as np

    measurement = runpy.run_path("/input/development-measurement.py")
    VERSION, measure = measurement["VERSION"], measurement["measure"]
    from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import save_checkpoint
    from carbon.reconstruction._vendor.carbon_jax_lab.config import (
        ModelConfig,
        TaskConfig,
        TrainConfig,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.data import (
        Trajectories,
        assert_case_disjoint,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.training import Trainer

    root = Path("/scratch/workspace")
    output = Path("/scratch/output")
    recipe = json.loads((root / "recipe.json").read_bytes())
    training = Trajectories.load(root / "train.npz")
    practice = Trajectories.load(root / "validation.npz")
    if training.role != "train" or practice.role != "validation":
        raise ValueError("research data roles differ")
    assert_case_disjoint(training, practice)
    scales = json.loads((root / "practice-scales.json").read_bytes())
    if len(scales) != len(practice.initial):
        raise ValueError("practice scale association differs")
    trainer = Trainer(
        ModelConfig(**recipe["model"]),
        TaskConfig(**recipe["task"]),
        TrainConfig(**recipe["train"]),
        training,
        runtime_key_material=(root / "research-randomness.bin").read_bytes(),
    )
    try:
        trainer.fit(wall_budget_seconds=recipe["productive_seconds"])
    finally:
        # Retain real completed updates if a cooperative failure occurs. A hard
        # process kill may prevent export; its operation still consumes budget.
        (output / "learning-curve.json").write_text(
            json.dumps(trainer.history, allow_nan=False)
        )
    summary, predictions = trainer.audit(practice, batch_size=8)
    measurements = []
    for i, scale in enumerate(scales):
        measurements.append(
            measure(
                predictions[i],
                practice.solution[i],
                times=practice.times[i],
                length=practice.domain_length,
                viscosity=float(practice.viscosity[i]),
                initial=practice.initial[i],
                amplitude=scale["amplitude"],
                characteristic_time=scale["characteristic_time"],
            )
        )
    save_checkpoint(trainer, output / "checkpoint")
    np.save(output / "practice-predictions.npy", predictions, allow_pickle=False)
    result = {
        "schema": "carbon.autoresearch.real-practice.v1",
        "provenance": "REAL_JAX_PUBLIC_PRACTICE",
        "measurement_version": VERSION,
        "training_cases": len(training.initial),
        "practice_cases": len(practice.initial),
        "completed_steps": int(trainer.state.step),
        "timing": trainer.timing,
        "summary": summary,
        "measurements": measurements,
        "recipe_identity": recipe["profile_digest"],
        "official_eligible": False,
        "accepted_improvement": False,
    }
    (output / "practice-result.json").write_text(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
