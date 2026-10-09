## 2026-10-09 — OWNER-DEV-LADDER-KIND-01: the development-ladder deployment is a `ladder` sub-kind of `development_only`

**Authority.** The owner, 2026-10-09, directly in the Carbon Validator
session. They chose "Approve (Recommended)" for the design that
OWNER-LADDER-THROUGH-LAUNCHPAD-01 left to the Carbon Validator ("Whether the
ladder deployment is one, or needs a new kind, is the Carbon Validator's
design to bring to the owner").

**Decided.** `battery-dev-ladder` (VALIDATOR-25) is a `development_only`
deployment with a `ladder: {level, hotkeys, variants}` key:
- **Weights are refused,** as for every `development_only` deployment
  (`check_weight_source`). Every result carries the development label.
- **Commitments.** It is the only development deployment that requires the
  chain commitment. That is because it is reached through the Launchpad with
  real hotkeys. It is valid on Carbon's testnet only (`testnet`, netuid 567).
- **Who and what.** It admits only its listed hotkeys: minerC, UID 7, first.
  It admits only the listed development variants of its one level, 1 to 3.
  Level 4 is refused.
- **Windows.** It shares the main deployment's live windows: import-only,
  under the main deployment's rule, with one exposure account.

**Not decided here:**
- opening Level 4 (Level 4 Phase 3, its bounds and security acceptance);
- any mainnet use (never, until the owner locks a level);
- security acceptance of the door (it needs a dedicated review).
