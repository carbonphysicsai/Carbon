"""Hard physics gates for Burgers PoC. Any fail → combined_score = 0."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_gate_config() -> dict:
    path = _repo_root() / "poc" / "configs" / "gates_burgers1d.yaml"
    with open(path) as f:
        return yaml.safe_load(f)["gates"]


def run_gates(
    metrics: Dict[str, float],
    gate_cfg: dict | None = None,
    strategy: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    cfg = gate_cfg or load_gate_config()
    results: List[Dict[str, Any]] = []

    # finite
    if cfg.get("finite", {}).get("enabled", True):
        ok = bool(metrics.get("finite_ok", 1.0) == 1.0)
        results.append({"id": "finite", "pass": ok, "value": float(ok), "tau": 1.0})

    # conservation
    if cfg.get("conservation", {}).get("enabled", True):
        tau = float(cfg["conservation"]["tau_mass"])
        val = float(metrics.get("conservation_error", 0.0))
        results.append(
            {"id": "conservation", "pass": val <= tau, "value": val, "tau": tau}
        )

    # residual ceiling
    if cfg.get("residual_ceiling", {}).get("enabled", True):
        tau = float(cfg["residual_ceiling"]["tau_residual"])
        val = float(metrics.get("residual_mean", 0.0))
        results.append(
            {"id": "residual_ceiling", "pass": val <= tau, "value": val, "tau": tau}
        )

    # accuracy ceiling (eval rel L2)
    if cfg.get("accuracy_ceiling", {}).get("enabled", False):
        tau = float(cfg["accuracy_ceiling"]["tau_rel_l2"])
        val = float(metrics.get("eval_rel_l2", metrics.get("rel_l2", 1.0)))
        results.append(
            {"id": "accuracy_ceiling", "pass": val <= tau, "value": val, "tau": tau}
        )

    # at least one loss term enabled
    if cfg.get("loss_signal", {}).get("enabled", False) and strategy is not None:
        loss = strategy.get("loss") or {}
        any_on = bool(
            loss.get("data_mse", False)
            or loss.get("physics_residual", False)
            or loss.get("conservation_penalty", False)
        )
        results.append(
            {
                "id": "loss_signal",
                "pass": any_on,
                "value": float(any_on),
                "tau": 1.0,
            }
        )

    return results


def all_passed(gate_results: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    failures = [g["id"] for g in gate_results if not g.get("pass", True)]
    return len(failures) == 0, failures
