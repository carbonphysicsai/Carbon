"""Shared storage for symbolic artifacts discovered by miners and validators.

This is the common location where:
- PySR-evolved loss weights
- Discovered scoring expressions
- Symbolic priors

...will be stored so the Landscape agent can consume and distribute them.
"""

import json
import os
import time
from typing import Dict, Any, List, Optional

STORAGE_DIR = "./data/landscape"
os.makedirs(STORAGE_DIR, exist_ok=True)


def save_symbolic_artifact(
    artifact_type: str,
    challenge_id: str,
    content: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Save a symbolic artifact (e.g. PySR expression or evolved weights).

    artifact_type examples: "pysr_scoring", "evolved_loss_weights", "symbolic_prior"
    """
    timestamp = int(time.time())
    filename = f"{artifact_type}_{challenge_id}_{timestamp}.json"
    filepath = os.path.join(STORAGE_DIR, filename)

    data = {
        "artifact_type": artifact_type,
        "challenge_id": challenge_id,
        "timestamp": timestamp,
        "content": content,
        "metadata": metadata or {},
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return filepath


def load_symbolic_artifacts(
    artifact_type: Optional[str] = None,
    challenge_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Load recent symbolic artifacts."""
    artifacts = []
    if not os.path.exists(STORAGE_DIR):
        return artifacts

    files = sorted(
        [f for f in os.listdir(STORAGE_DIR) if f.endswith(".json")],
        reverse=True,
    )[:limit]

    for fname in files:
        try:
            with open(os.path.join(STORAGE_DIR, fname)) as f:
                data = json.load(f)

            if artifact_type and data.get("artifact_type") != artifact_type:
                continue
            if challenge_id and data.get("challenge_id") != challenge_id:
                continue

            artifacts.append(data)
        except Exception:
            continue

    return artifacts
