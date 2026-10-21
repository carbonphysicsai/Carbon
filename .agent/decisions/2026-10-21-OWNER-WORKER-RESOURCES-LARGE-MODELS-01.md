# OWNER-WORKER-RESOURCES-LARGE-MODELS-01: larger worker resources so large models can run

Date: 2026-10-21
Status: APPROVED by the owner, directly in the Carbon Validator's session ("Approve"). This includes the security acceptance of the widened sandbox limits, conditional on the re-test below.
Implementation: **not yet implemented.** The proposal is `codex-queue/reports/VALIDATOR_WORKER_RESOURCES_PROPOSAL_20261021.md`.

## Decided (next Challenge versions only)

| Limit | From | To |
|---|---|---|
| Worker output envelope | 128 MiB | 2 GiB |
| Scratch tmpfs | 512 MiB | 4 GiB |
| Lane memory | 8 GiB | 16 GiB |

- **Unchanged:** CPU, pids, network none, read-only root, and the rebuild wall-time limit.
- **Cost:** $0 extra compute, because the validator host class is unchanged. Storage is negligible.

## Conditions

- **Before any version serves these limits,** a real-lane containment run at the new profile must pass, as Run F did.
- **Scope:** testnet and rehearsal, like OWNER-CONTAINMENT-ACCEPT-TESTNET-01. Mainnet needs its own acceptance on its own class.
