"""Model Card — SPEC validator output + Landscape Agent D1 ingest contract.

Every full evaluation must emit a card with strategy, seeds, gates, scores,
and software provenance. Cards feed the Landscape Agent (appendices/Landscape_Agent.md).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def strategy_hash(strategy: Dict[str, Any]) -> str:
    payload = json.dumps(strategy, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_model_card(
    *,
    challenge_id: str,
    backbone: str,
    strategy: Dict[str, Any],
    seeds: Dict[str, Any],
    metrics: Dict[str, float],
    gates: List[Dict[str, Any]],
    score: Dict[str, Any],
    budget_used: Optional[Dict[str, Any]] = None,
    generator_version: str = "unknown",
    software: Optional[Dict[str, str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    card_id = str(uuid.uuid4())
    card: Dict[str, Any] = {
        "card_id": card_id,
        "schema_version": "model_card_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "challenge_id": challenge_id,
        "backbone": backbone,
        "strategy_hash": strategy_hash(strategy),
        "strategy": strategy,
        "seeds": seeds,
        "generator_version": generator_version,
        "software": software or {},
        "metrics": metrics,
        "gates": gates,
        "score": score,
        "budget_used": budget_used or {},
        "tier1_passed": not score.get("gate_failed", False),
        "full_eval_completed": True,
    }
    if extra:
        card["extra"] = extra
    return card


def write_model_card(card: Dict[str, Any], directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{card['card_id']}.json"
    path.write_text(json.dumps(card, indent=2, sort_keys=True))
    # Append lightweight registry line
    registry = directory / "registry.jsonl"
    with registry.open("a") as f:
        f.write(
            json.dumps(
                {
                    "card_id": card["card_id"],
                    "strategy_hash": card["strategy_hash"],
                    "combined_score": card.get("score", {}).get("combined_score"),
                    "challenge_id": card["challenge_id"],
                }
            )
            + "\n"
        )
    return path
