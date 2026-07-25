"""Carbon Protocol Definitions.

Defines the Synapses used for communication between miners and validators.
Follows Bittensor best practices from the official subnet template.
"""

import bittensor as bt
from typing import Optional, Dict, Any


class StrategySynapse(bt.Synapse):
    """
    Synapse for strategy submission / retrieval in Carbon.

    Miners can submit strategies for a given challenge.
    Validators can request strategies or confirm submissions.
    """

    # Required fields
    challenge_id: str = ""
    hotkey: str = ""  # miner's hotkey submitting the strategy

    # The actual strategy (JSON-serializable dict)
    strategy: Optional[Dict[str, Any]] = None

    # Response fields (filled by receiver)
    accepted: bool = False
    message: str = ""
    submission_id: Optional[str] = None

    def deserialize(self) -> Dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "strategy": self.strategy,
            "accepted": self.accepted,
            "message": self.message,
        }


class GetActiveChallengesSynapse(bt.Synapse):
    """
    Synapse for miners to discover currently open challenges.
    """

    challenges: Optional[list] = None  # List of challenge_ids

    def deserialize(self) -> list:
        return self.challenges or []
