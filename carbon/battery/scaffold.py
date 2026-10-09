"""The published, unexecuted battery research starting recipe."""

from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

SCAFFOLD = {
    "schema_version": "1.0",
    "challenge_id": BATTERY_CHALLENGE,
    "backbone": "mlp",
    "parameters": {"steps": 2000, "width": 64, "depth": 3},
}
