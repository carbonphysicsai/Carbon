"""Deterministic-aware modular trainer."""

from typing import Dict, Any, Optional

import torch
import torch.nn as nn

from hydrogen.backbones import get_backbone


def set_deterministic_mode(seed: int):
    """
    Enable deterministic mode for reproducibility across runs and GPUs.

    Note: This can reduce performance. Some operations may still be
    non-deterministic or raise errors if they cannot be made deterministic.
    """
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    # cuDNN settings
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    # Enable PyTorch's deterministic algorithms (PyTorch >= 1.8)
    try:
        torch.use_deterministic_algorithms(True, warn_only=True)
    except Exception:
        pass  # Older PyTorch versions


def get_model(
    backbone: str = "physicsnemo_fno",
    in_channels: int = 3,
    out_channels: int = 1,
    strategy: dict = None,
    seed: int = 42,
    **kwargs,
) -> nn.Module:
    if strategy is None:
        strategy = {}

    set_deterministic_mode(seed)

    BackboneClass = get_backbone(backbone)
    model_kwargs = strategy.get("model_kwargs", {})
    model_kwargs.update(kwargs)

    model = BackboneClass(in_channels=in_channels, out_channels=out_channels, **model_kwargs)

    init_type = strategy.get("weight_init", "default").lower()
    if init_type != "default":
        _initialize_weights(model, init_type)

    return model


def _initialize_weights(model: nn.Module, init_type: str):
    for m in model.modules():
        if isinstance(m, (nn.Conv2d, nn.Linear)):
            if init_type == "kaiming_normal":
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
            elif init_type == "kaiming_uniform":
                nn.init.kaiming_uniform_(m.weight, mode="fan_out", nonlinearity="relu")
            elif init_type == "xavier_normal":
                nn.init.xavier_normal_(m.weight)
            elif init_type == "xavier_uniform":
                nn.init.xavier_uniform_(m.weight)
            elif init_type == "normal":
                nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)


def get_optimizer(model: nn.Module, strategy: dict):
    opt_name = strategy.get("optimizer", "AdamW").lower()
    lr = strategy.get("learning_rate", 0.001)
    weight_decay = strategy.get("weight_decay", 1e-4)

    if opt_name == "adamw":
        return torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    elif opt_name == "adam":
        return torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    elif opt_name == "sgd":
        momentum = strategy.get("momentum", 0.9)
        return torch.optim.SGD(model.parameters(), lr=lr, momentum=momentum, weight_decay=weight_decay)
    else:
        return torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)


def get_scheduler(optimizer, strategy: dict, epochs: int):
    scheduler_name = strategy.get("scheduler", "CosineAnnealingLR").lower()

    if scheduler_name == "cosineannealinglr":
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    elif scheduler_name == "steplr":
        step_size = strategy.get("step_size", max(1, epochs // 4))
        gamma = strategy.get("gamma", 0.5)
        return torch.optim.lr_scheduler.StepLR(optimizer, step_size=step_size, gamma=gamma)
    elif scheduler_name == "reducelronplateau":
        return torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", patience=10)
    else:
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)


def train_model(
    model: nn.Module,
    train_loader,
    val_loader: Optional[Any] = None,
    strategy: dict = None,
    epochs: int = 50,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
    physics_loss_fn: Optional[callable] = None,
    physics_loss_weight: float = 1.0,
) -> Dict[str, Any]:
    if strategy is None:
        strategy = {}

    # Derive a deterministic seed
    seed = strategy.get("seed", 42)
    set_deterministic_mode(seed)

    model = model.to(device)
    optimizer = get_optimizer(model, strategy)
    scheduler = get_scheduler(optimizer, strategy, epochs)

    grad_clip_norm = strategy.get("grad_clip_norm", None)
    accumulation_steps = strategy.get("accumulation_steps", 1)
    use_amp = strategy.get("use_amp", False) and device.startswith("cuda")
    scaler = torch.cuda.amp.GradScaler() if use_amp else None

    early_stop_patience = strategy.get("early_stop_patience", None)
    best_val_loss = float("inf")
    epochs_no_improve = 0

    physics_weight = strategy.get("physics_loss_weight", physics_loss_weight)

    history = {"train_loss": [], "val_loss": []}

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        optimizer.zero_grad()

        for i, batch in enumerate(train_loader):
            x, y = batch[0].to(device), batch[1].to(device)

            if use_amp:
                with torch.cuda.amp.autocast():
                    pred = model(x)
                    data_loss = torch.nn.functional.mse_loss(pred, y)
                    physics_loss = physics_loss_fn(pred, x) if physics_loss_fn else 0.0
                    loss = data_loss + physics_weight * physics_loss
                scaler.scale(loss).backward()
            else:
                pred = model(x)
                data_loss = torch.nn.functional.mse_loss(pred, y)
                physics_loss = physics_loss_fn(pred, x) if physics_loss_fn else 0.0
                loss = data_loss + physics_weight * physics_loss
                loss.backward()

            if (i + 1) % accumulation_steps == 0:
                if grad_clip_norm:
                    if use_amp:
                        scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip_norm)

                if use_amp:
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    optimizer.step()

                optimizer.zero_grad()

            total_loss += loss.item()

        avg_train = total_loss / len(train_loader)
        history["train_loss"].append(avg_train)

        current_val_loss = None
        if val_loader is not None:
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for batch in val_loader:
                    x, y = batch[0].to(device), batch[1].to(device)
                    pred = model(x)
                    val_loss += torch.nn.functional.mse_loss(pred, y).item()
            current_val_loss = val_loss / len(val_loader)
            history["val_loss"].append(current_val_loss)

            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs} - Train: {avg_train:.6f} | Val: {current_val_loss:.6f}")
        else:
            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs} - Train Loss: {avg_train:.6f}")

        if isinstance(scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau) and current_val_loss is not None:
            scheduler.step(current_val_loss)
        else:
            scheduler.step()

        if early_stop_patience and current_val_loss is not None:
            if current_val_loss < best_val_loss - 1e-6:
                best_val_loss = current_val_loss
                epochs_no_improve = 0
            else:
                epochs_no_improve += 1

            if epochs_no_improve >= early_stop_patience:
                print(f"Early stopping triggered at epoch {epoch+1}")
                break

    return {"model": model, "history": history}
