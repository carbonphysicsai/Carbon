"""Graph route v2's closed build refusal classes, beside `build_refusal`.

`build_refusal` is staged byte for byte into v1's graph build (the F08/F02
graph golden), so graph route v2's codes are registered here instead: each
`graph_route_*` code `physical_graph_adapter_v2` raises, with its class
(OWNER-BUILD-REFUSAL-SPLIT-01), and every other code keeps `build_refusal`'s
class. Anything neither lists is a gap, as there.
"""

from __future__ import annotations

from .build_refusal import CODES as V1_CODES
from .build_refusal import GAP, REFUSED

#: The adapter's refusal suffixes (`physical_graph_adapter_v2.REFUSED_SUFFIXES`
#: and `GAP_SUFFIXES`, which a test holds equal), by class.
_REFUSED_SUFFIXES = (
    "batch_exceeds_train",
    "challenge_version_unregistered",
    "ensemble_invalid",
    "input_invalid",
    "loss_unsupported",
    "nonfinite_state",
    "output_unsupported",
    "output_weights_invalid",
    "procedure_invalid",
    "seed_invalid",
    "train_empty",
    "train_invalid",
    "training_field_invalid",
    "training_value_invalid",
    "untrained",
)
_GAP_SUFFIXES = ("surface_unserved",)
CODES = {
    **V1_CODES,
    **{"graph_route_" + suffix: REFUSED for suffix in _REFUSED_SUFFIXES},
    **{"graph_route_" + suffix: GAP for suffix in _GAP_SUFFIXES},
    "ensemble_graph_state_combine_invalid": REFUSED,
}


def outcome(code: str) -> str:
    """The class of a registered code; anything else is Carbon's gap."""
    return CODES.get(code, GAP)
