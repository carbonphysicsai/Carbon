"""Validate strategy JSON against poc_v1 schema + validator clamps."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_limits(fast: bool = False) -> dict:
    path = _repo_root() / "poc" / "configs" / "validator_limits.yaml"
    with open(path) as f:
        limits = yaml.safe_load(f)
    if fast:
        limits.update(limits.get("fast", {}))
    return limits


def validate_strategy(strategy: Dict[str, Any], fast: bool = False) -> Tuple[Dict[str, Any], None] | Tuple[None, str]:
    """Return (normalized_strategy, None) or (None, error_message)."""
    s = deepcopy(strategy)

    if s.get("schema_version") != "poc_v1":
        return None, "schema_version must be 'poc_v1'"
    if s.get("challenge_id") != "burgers1d_v0":
        return None, "challenge_id must be 'burgers1d_v0'"
    if s.get("backbone") != "fno1d":
        return None, "backbone must be 'fno1d'"

    # Reject unknown top-level keys
    allowed = {"schema_version", "challenge_id", "backbone", "backbone_cfg", "loss", "optim", "budget"}
    unknown = set(s.keys()) - allowed
    if unknown:
        return None, f"unknown keys: {sorted(unknown)}"

    cfg = s.get("backbone_cfg") or {}
    for req in ("modes", "width", "layers"):
        if req not in cfg:
            return None, f"backbone_cfg.{req} required"

    loss = s.get("loss") or {}
    for flag in ("data_mse", "physics_residual", "conservation_penalty"):
        if flag not in loss:
            return None, f"loss.{flag} boolean required"
        if not isinstance(loss[flag], bool):
            return None, f"loss.{flag} must be boolean"

    optim = s.get("optim") or {}
    if "lr" not in optim or "name" not in optim:
        return None, "optim.name and optim.lr required"

    budget = s.get("budget") or {}
    if "max_steps" not in budget or "batch_size" not in budget:
        return None, "budget.max_steps and budget.batch_size required"

    limits = load_limits(fast=fast)
    cfg["modes"] = int(max(1, min(int(cfg["modes"]), limits["max_modes"])))
    cfg["width"] = int(max(4, min(int(cfg["width"]), limits["max_width"])))
    cfg["layers"] = int(max(1, min(int(cfg["layers"]), limits["max_layers"])))
    s["backbone_cfg"] = cfg

    lr = float(optim["lr"])
    optim["lr"] = max(limits["lr_min"], min(limits["lr_max"], lr))
    optim["weight_decay"] = float(optim.get("weight_decay", 0.0))
    s["optim"] = optim

    budget["max_steps"] = int(max(1, min(int(budget["max_steps"]), limits["max_steps"])))
    budget["batch_size"] = int(max(1, min(int(budget["batch_size"]), limits["max_batch_size"])))
    s["budget"] = budget

    return s, None


def load_strategy_file(path: str | Path, fast: bool = False):
    with open(path) as f:
        raw = json.load(f)
    return validate_strategy(raw, fast=fast)
