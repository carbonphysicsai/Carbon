"""Specialist Bank for Hydrogen.

Central registry for distilled specialists.
Supports registration, querying, and basic versioning.
"""

import os
import json
from typing import Dict, Any, List, Optional


SPECIALIST_BANK_DIR = "./data/specialist_bank"
os.makedirs(SPECIALIST_BANK_DIR, exist_ok=True)


class SpecialistBank:
    """
    In-memory + file-backed registry of specialists.
    """

    def __init__(self, bank_dir: str = SPECIALIST_BANK_DIR):
        self.bank_dir = bank_dir
        os.makedirs(bank_dir, exist_ok=True)
        self.specialists: Dict[str, Dict[str, Any]] = {}
        self._load_existing()

    def _load_existing(self):
        """Load all existing specialist manifests from disk."""
        for filename in os.listdir(self.bank_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.bank_dir, filename)) as f:
                        specialist = json.load(f)
                    specialist_id = specialist.get("specialist_id")
                    if specialist_id:
                        self.specialists[specialist_id] = specialist
                except Exception:
                    continue

    def register(self, specialist: dict) -> str:
        """
        Register a new specialist.
        Returns the specialist_id.
        """
        specialist_id = specialist.get("specialist_id")
        if not specialist_id:
            raise ValueError("Specialist must have a 'specialist_id'")

        # Save to disk
        manifest_path = os.path.join(self.bank_dir, f"{specialist_id}.json")
        with open(manifest_path, "w") as f:
            json.dump(specialist, f, indent=2)

        self.specialists[specialist_id] = specialist
        return specialist_id

    def get(self, specialist_id: str) -> Optional[Dict[str, Any]]:
        """Get a specialist by ID."""
        return self.specialists.get(specialist_id)

    def list_by_challenge(self, challenge_id: str) -> List[Dict[str, Any]]:
        """List all specialists for a given challenge."""
        return [
            s for s in self.specialists.values()
            if s.get("challenge_id") == challenge_id
        ]

    def list_all(self) -> List[Dict[str, Any]]:
        """List all registered specialists."""
        return list(self.specialists.values())

    def get_best_for_challenge(
        self, challenge_id: str, backbone: str = "PINO"
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent specialist for a challenge + backbone."""
        candidates = [
            s
            for s in self.specialists.values()
            if s.get("challenge_id") == challenge_id
            and s.get("strategy_config", {}).get("backbone", "PINO") == backbone
        ]
        if not candidates:
            return None

        # Return the most recently created
        return max(candidates, key=lambda x: x.get("created_at", 0))
