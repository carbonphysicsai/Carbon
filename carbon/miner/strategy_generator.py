"""SOTA Strategy Generator for Carbon.

Produces validator-complete strategy JSONs matching SPEC schema v1.0:
- Explicit boolean loss enables (no weight-threshold hacks)
- Training block with clamped ranges
- Optional curriculum / UQ

Miners control training config — validators control data splits & stress.
"""

from typing import Any, Dict, Optional

from carbon.common.strategy_schema import validate_and_normalize_strategy


def generate_strategy(
    challenge_id: str = "poisson_2d_v1",
    backbone: Optional[str] = None,
    use_curriculum: bool = True,
    use_uq: bool = True,
    use_physics_residual: bool = True,
    use_conservation: bool = False,
) -> Dict[str, Any]:
    """Generate a SPEC v1.0 strategy JSON focused on training configuration."""
    try:
        from carbon.challenges import load_challenge

        challenge = load_challenge(challenge_id)
        symbolic = getattr(challenge, "symbolic_metadata", {}) or {}
        suggested = symbolic.get(
            "suggested_loss_weights",
            {
                "data_mse": 1.0,
                "physics_residual": 0.5,
                "boundary_mse": 0.3,
                "conservation_penalty": 0.0,
            },
        )
        chosen_backbone = backbone or getattr(
            challenge, "get_backbone", lambda: "fno"
        )()
        resolution = list(getattr(challenge, "resolution", [128, 128]))
    except Exception:
        suggested = {
            "data_mse": 1.0,
            "physics_residual": 0.5,
            "boundary_mse": 0.3,
            "conservation_penalty": 0.0,
        }
        chosen_backbone = backbone or "fno"
        resolution = [128, 128]

    raw = {
        "schema_version": "1.0",
        "challenge_id": challenge_id,
        "backbone": chosen_backbone,
        "backbone_config": {
            "modes": 16,
            "width": 32,
            "depth": 4,
            "activation": "gelu",
            "normalization": "instance_norm",
        },
        "resolution": resolution,
        "loss": {
            "data_mse": {
                "enabled": True,
                "weight": float(suggested.get("data_mse", 1.0)),
            },
            "physics_residual": {
                "enabled": bool(use_physics_residual),
                "weight": float(suggested.get("physics_residual", 0.5)),
            },
            "boundary_mse": {
                "enabled": True,
                "weight": float(suggested.get("boundary_mse", 0.3)),
            },
            "conservation_penalty": {
                "enabled": bool(use_conservation),
                "weight": float(suggested.get("conservation_penalty", 0.2)),
            },
        },
        "training": {
            "optimizer": "adamw",
            "learning_rate": 0.0008,
            "weight_decay": 1e-4,
            "epochs": 100,
            "batch_size": 8,
            "gradient_clip": 1.0,
            "lr_schedule": "cosine",
            "mixed_precision": True,
        },
        "budget": {
            "max_steps": 2000,
            "batch_size": 8,
        },
        "curriculum": {
            "enabled": use_curriculum,
            "phases": [
                {
                    "phase": 1,
                    "spatial_resolution_scale": 0.5,
                    "mode_budget_scale": 0.5,
                    "epochs": 35,
                },
                {
                    "phase": 2,
                    "spatial_resolution_scale": 1.0,
                    "mode_budget_scale": 1.0,
                    "epochs": 65,
                },
            ],
        },
        "uq_config": {
            "enabled": use_uq,
            "method": "deep_ensemble",
            "num_members": 4,
            "calibration_target": 0.92,
        },
        "data": {
            "train_split": 0.8,
            "noise_level": 0.01,
        },
    }

    # Normalize through SPEC validator (clamps + boolean enforcement)
    return validate_and_normalize_strategy(raw)


def get_local_validation_score(
    challenge_id: str,
    strategy: dict,
    use_real_training: bool = False,
    quick_epochs: int = 5,
):
    """Lightweight local validation used by the miner neuron.

    Returns (estimated_improvement, hard_pass, gate_details).
    Full local light-training loops replace this stub in Phase 0 PoC.
    """
    try:
        validate_and_normalize_strategy(strategy, require_challenge_id=None)
        schema_ok = True
    except Exception as e:
        return 0.0, False, {"schema_error": str(e)}

    # Stub signal until Light Training path is wired
    return 0.05, schema_ok, {"stub": True, "challenge_id": challenge_id, "schema_ok": schema_ok}


def list_available_backbones():
    try:
        from carbon.backbones import list_backbones

        return list_backbones()
    except Exception:
        return ["fno", "fno1d", "gino", "physicsnemo_fno"]
