"""Real DEVELOPMENT practice adapter; B-07C fixture execution stays unchanged."""

from __future__ import annotations

import json
from pathlib import Path

from carbon.measurement_runtime import development as measurement

from .profile import canonical
from .research_carrier import PRECHARGED_TRIAL, _run
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
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
    )
    return result


class PublicPractice:
    """Real callback for the B-07 provider, with useful bounded diagnostics."""

    def __init__(self, *, data, ledger, owner, image, seconds=600):
        self.data, self.ledger, self.owner, self.image, self.seconds = (
            data,
            ledger,
            owner,
            image,
            seconds,
        )

    def __call__(self, identity, strategy):
        import os

        from .data import write_once
        from .profile import digest
        from .research_workspace import ResearchWorkspace

        train, _ = self.data.prepare("research-train")
        validation, metadata = self.data.prepare("research-validation")
        key = self.ledger.root / (
            "practice-randomness-"
            + digest(canonical([self.owner, identity]))[7:]
            + ".bin"
        )
        if not key.exists():
            write_once(key, os.urandom(32))
        if key.is_symlink() or key.stat().st_size != 32:
            raise ValueError("invalid retained practice randomness")
        worker = run_practice(
            self.ledger,
            owner=self.owner,
            identity=identity,
            strategy=strategy,
            train_bytes=train,
            validation_bytes=validation,
            practice_scales=metadata["scales"],
            randomness=key.read_bytes(),
            image=self.image,
            seconds=self.seconds,
        )
        snapshot = self.ledger.root / worker["operation"] / "snapshot"

        def checked(name, maximum):
            path = snapshot / name
            if path.is_symlink() or not 0 < path.stat().st_size <= maximum:
                raise ValueError("bounded practice result required")
            body = path.read_bytes()
            if digest(body) != worker["files"].get(name):
                raise ValueError("practice result changed")
            return body

        metrics = json.loads(checked("practice-result.json", 1024**2))
        curve_body = checked("learning-curve.json", 8 * 1024**2)
        curve = json.loads(curve_body)
        if type(curve) is not list:
            raise ValueError("practice learning curve shape differs")
        # Preserve the complete real curve in owner scratch; bound only the
        # inline model observation. Selection indices are outcome-independent.
        indices = (
            sorted(
                {
                    int(i * (len(curve) - 1) / min(7, len(curve) - 1))
                    for i in range(min(8, len(curve)))
                }
            )
            if len(curve) > 1
            else list(range(len(curve)))
        )
        workspace = ResearchWorkspace(self.ledger, self.owner)
        name = "trial-" + digest(identity.encode())[7:23] + "-learning-curve.json"
        workspace.put(name, curve_body)
        from carbon.scoring.development import practice_diagnostics

        metrics_name = "trial-" + digest(identity.encode())[7:23] + "-practice.json"
        workspace.put(metrics_name, canonical(metrics))
        diagnostic = practice_diagnostics(metrics["measurements"], metadata["scales"])
        operation = next(
            op
            for op in self.ledger.status(owner=self.owner)["operations"]
            if op["id"] == identity
        )
        print(
            json.dumps(
                {
                    "stage": "practice_complete",
                    "trial": identity,
                    "recipe": strategy,
                    "completed_steps": metrics["completed_steps"],
                    "score": diagnostic["descriptive_score"],
                    "gate_failures": diagnostic["sampled_gate_failures"],
                    "worker_seconds": operation["actual"]["numerical_milliseconds"]
                    / 1000,
                },
                allow_nan=False,
            ),
            flush=True,
        )
        return {
            "schema": "carbon.autoresearch.practice-feedback.v1",
            "provenance": "REAL_JAX_PUBLIC_PRACTICE",
            "recipe": strategy,
            "metrics_file": metrics_name,
            "diagnostics": diagnostic,
            "completed_steps": metrics["completed_steps"],
            "training_cases": metrics["training_cases"],
            "practice_cases": metrics["practice_cases"],
            "worker_seconds": operation["actual"]["numerical_milliseconds"] / 1000,
            "curve_file": name,
            "curve_points": len(curve),
            "inline_curve_indices": indices,
            "inline_curve": [curve[i] for i in indices],
            "sampling": "uniform index sample including endpoints; full curve retained",
            "worker": worker,
            "adaptively_seen": True,
            "final_exam": False,
            "accepted_improvement": False,
            "official_eligible": False,
        }
