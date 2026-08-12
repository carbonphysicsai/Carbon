"""Strategy Store for Carbon Validator.

Provides a clean abstraction for retrieving and storing miner strategies.
Supports local file-based storage for development/testing and is designed
to be easily extended with a platform/off-chain backend later.

This replaces the previous placeholder _get_strategy_for_uid() logic.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Any

from datetime import datetime

import bittensor as bt


class StrategyStore:
    """
    Abstract interface + local file implementation for strategy storage/retrieval.

    In production this can be swapped for a platform-backed implementation
    (e.g. via ValidatorPlatformClient or similar).
    """

    def get_strategy(self, hotkey: str, challenge_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve the latest strategy for a given hotkey (and optionally a challenge).

        Returns None if no strategy is found.
        """
        raise NotImplementedError

    def save_strategy(self, hotkey: str, strategy: Dict[str, Any], challenge_id: Optional[str] = None) -> bool:
        """
        Persist a strategy for a given hotkey.

        Returns True on success.
        """
        raise NotImplementedError

    def list_strategies(self, challenge_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        List all known strategies (optionally filtered by challenge).
        """
        raise NotImplementedError


class LocalFileStrategyStore(StrategyStore):
    """
    Simple file-based strategy store for development and testing.

    Stores strategies as JSON files in a local directory.
    File naming: {hotkey}_{challenge_id or 'default'}.json
    """

    def __init__(self, storage_dir: str = "./strategies"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        bt.logging.info(f"LocalFileStrategyStore initialized at {self.storage_dir}")

    def _get_file_path(self, hotkey: str, challenge_id: Optional[str] = None) -> Path:
        safe_hotkey = hotkey.replace("/", "_")  # just in case
        cid = challenge_id or "default"
        return self.storage_dir / f"{safe_hotkey}_{cid}.json"

    def get_strategy(self, hotkey: str, challenge_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        path = self._get_file_path(hotkey, challenge_id)
        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                data = json.load(f)
            return data.get("strategy")
        except Exception as e:
            bt.logging.warning(f"Failed to read strategy for {hotkey}: {e}")
            return None

    def save_strategy(self, hotkey: str, strategy: Dict[str, Any], challenge_id: Optional[str] = None) -> bool:
        path = self._get_file_path(hotkey, challenge_id)

        payload = {
            "hotkey": hotkey,
            "challenge_id": challenge_id or "default",
            "strategy": strategy,
            "saved_at": datetime.utcnow().isoformat() + "Z",
        }

        try:
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
            bt.logging.debug(f"Saved strategy for {hotkey} (challenge={challenge_id or 'default'})")
            return True
        except Exception as e:
            bt.logging.error(f"Failed to save strategy for {hotkey}: {e}")
            return False

    def list_strategies(self, challenge_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        strategies = {}
        prefix = challenge_id or "default"

        for file_path in self.storage_dir.glob(f"*_{prefix}.json"):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                hotkey = data.get("hotkey")
                if hotkey:
                    strategies[hotkey] = data.get("strategy")
            except Exception as e:
                bt.logging.warning(f"Failed to read strategy file {file_path}: {e}")

        return strategies


# Convenience function for quick local testing
def get_default_local_store() -> LocalFileStrategyStore:
    return LocalFileStrategyStore(storage_dir="./strategies")
