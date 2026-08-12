"""Training entrypoint that fully respects miner strategy."""

from typing import Dict, Any

import torch

from hydrogen.training.trainer import get_model, train_model
from hydrogen.data.benchmark_loader import get_benchmark_loader


def train_physics_neural_operator(
    challenge,
    strategy: dict,
    epochs: int = 50,
) -> Dict[str, Any]:
    backbone = strategy.get("backbone", challenge.get_backbone() if hasattr(challenge, "get_backbone") else "physicsnemo_fno")

    model = get_model(backbone=backbone, in_channels=3, out_channels=1)

    challenge_id = getattr(challenge, "challenge_id", "unknown")
    train_loader = get_benchmark_loader(challenge_id, batch_size=strategy.get("batch_size", 8), split="train")

    result = train_model(
        model=model,
        train_loader=train_loader,
        strategy=strategy,          # Pass full strategy for optimizer, scheduler, AMP, clipping, etc.
        epochs=strategy.get("epochs", epochs),
    )

    trained_model = result["model"]

    # Generate real prediction from trained model
    model.eval()
    with torch.no_grad():
        try:
            sample_x, _ = next(iter(train_loader))
            u_pred = trained_model(sample_x[:1].to(next(trained_model.parameters()).device))
        except Exception:
            u_pred = torch.zeros(1, 1, 64, 64)

    return {
        "model": trained_model,
        "backbone": backbone,
        "history": result.get("history", {}),
        "u_pred": u_pred.cpu(),
    }
