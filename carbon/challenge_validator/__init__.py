"""Carbon's challenge-neutral validator (VALIDATOR-01).

One validator scores any registered Challenge's submissions against that
Challenge's frozen rule, through one `ChallengeAdapter` per construction
contract. Battery is the first adapter (`battery.BatteryAdapter`); Cooling's
public-development adapter is `cooling.CoolingAdapter`.

- `interface`: the adapter contract, the outcome contract and the reserved
  seed roles;
- `strict_json`: strict parsing of the submitted strategy;
- `dispatch`: the miner-facing `Validator` and the operator-only `Operator`,
  dispatching by contract digest;
- `ledger`: the operator-side attempt ledger.

Scores are DEVELOPMENT only: no weights, rewards or chain action (OD-4b).
Nothing here is security-qualified; it awaits a dedicated security review.
"""

from .dispatch import Adapters, Operator, Validator
from .interface import (
    RESERVED_SEED_ROLES,
    ChallengeAdapter,
    ReservedRole,
    Submission,
    Unavailable,
)
from .ledger import AttemptLedger

__all__ = [
    "RESERVED_SEED_ROLES",
    "Adapters",
    "AttemptLedger",
    "ChallengeAdapter",
    "Operator",
    "ReservedRole",
    "Submission",
    "Unavailable",
    "Validator",
]
