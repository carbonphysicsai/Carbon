"""Hard physics gates for Burgers PoC. Any fail → combined_score = 0."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_gate_config() -> dict:
    path = _repo_root() / "poc" / "configs" / "gates_burgers1d.yaml"
    with open(path) as f:
        return yaml.safe_load(f)["gates"]


def run_gates(metrics: Dict[str, float], gate_cfg: dict | None = None) -> List[Dict[str, Any]]:
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

    return results


def all_passed(gate_results: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    failures = [g["id"] for g in gate_results if not g.get("pass", True)]
    return len(failures) == 0, failures
