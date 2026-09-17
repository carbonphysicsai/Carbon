"""Real DEVELOPMENT practice adapter; B-07C fixture execution stays unchanged."""

from __future__ import annotations

import json
from pathlib import Path

from carbon.measurement_runtime import development as measurement

from .profile import canonical
from .research_carrier import _run
from .research_catalog import compile_recipe


def run_practice(
    ledger,
    *,
    owner,
    identity,
    strategy,
    train_bytes,
    validation_bytes,
    practice_scales,
    randomness,
    image,
    seconds=600,
):
    # This function is trusted service composition, not the miner API. Miners
    # select recipes; the service supplies its own public data and randomness.
    if type(randomness) is not bytes or len(randomness) != 32:
        raise ValueError("research randomness identity required")
    _compiled, profile = compile_recipe(strategy)
    recipe = {
        "model": json.loads(profile.model_config_json),
        "task": json.loads(profile.task_config_json),
        "train": json.loads(profile.train_config_json),
        "profile_digest": profile.profile_digest,
        "productive_seconds": max(1, seconds - 90),
    }
    source = (Path(__file__).with_name("research_training.py")).read_text()
    result = _run(
        ledger,
        owner=owner,
        identity=identity,
        source=source,
        files={
            "recipe.json": canonical(recipe),
            "development-measurement.py": Path(measurement.__file__).read_bytes(),
            "train.npz": train_bytes,
            "validation.npz": validation_bytes,
            "practice-scales.json": canonical(practice_scales),
            "research-randomness.bin": randomness,
        },
        image=image,
        seconds=seconds,
        provenance="REAL_JAX_PUBLIC_PRACTICE",
        extra_resources={"research_trials": 1},
    )
    return result
