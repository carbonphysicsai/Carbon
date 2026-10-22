# OWNER-WORKER-RESOURCES-LARGE-MODELS-01: larger worker resources so large models can run

Date: 2026-10-21
Status: APPROVED by the owner, directly in the Carbon Validator's session ("Approve"). This includes the security acceptance of the widened sandbox limits, conditional on the re-test below.
Implementation: **not yet implemented.** The proposal is `codex-queue/reports/VALIDATOR_WORKER_RESOURCES_PROPOSAL_20261021.md`.

## Decided (next Challenge versions only)

| Limit | From | To |
|---|---|---|
| Worker output envelope | 128 MiB | 2 GiB |
| Scratch tmpfs | 512 MiB | 4 GiB |
| Lane memory (rebuild lane) | 4 GiB (C-03 MEMORY_BYTES) | 16 GiB |

- **Unchanged:** CPU, pids, network none, read-only root, and the rebuild wall-time limit.
- **Cost:** $0 extra compute, because the validator host class is unchanged. Storage is negligible.

## Conditions

- **Before any version serves these limits,** a real-lane containment run at the new profile must pass, as Run F did.
- **Scope:** testnet and rehearsal, like OWNER-CONTAINMENT-ACCEPT-TESTNET-01. Mainnet needs its own acceptance on its own class.

## Correction (Validator, 2026-10-21)

- **The "from" value was wrong.** The proposal gave lane memory as "8 GiB", but that is the G5 compile lane. The rebuild lane is 4 GiB today (C-03 `MEMORY_BYTES`).
- **The approved target (16 GiB) is unchanged.**
- **Implementation** `91b29d047d3517ea76a5cc86b884f962dc275f7e` keys these values to allowlist v7. v7 versions already serve on M1, so it lands only after the real-lane containment run at the new profile passes.
