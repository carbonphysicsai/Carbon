# Wave I: Mainnet-critical treasury and network settlement

**Status:** PLANNED

**Map ref:** `WAVE-I`

**Purpose:** Route mainnet network allocation to treasury receivers and settle exact per-Challenge obligations without rewriting scientific merit.

## Sequence

- **Predecessor:** Wave H
- **Successor:** Wave J

## What and why

Wave I owns I-00 treasury receiver/custody/economic contract, I-01 immutable accrual and scientific-economic ledger plus SettlementObligation, I-02 TreasuryRoutingWeightIntent publication, I-03 exactly-once miner settlement, I-04 validator execution and audit economics, and I-05 direct-testnet-to-treasury migration and settlement soak.

Mainnet economic activation requires a treasury receiver path, exact event-bound accounting, non-duplicating retries, and evidence that validators execute or audit assigned scientific work instead of merely copying a treasury vector.

## Success and unlocks

G6 demonstrates frontier-to-obligation-to-settlement evidence, validator-service incentives and audit controls, no-overlap migration, non-paying rollback, custody and recovery review, and localnet/testnet settlement soak. G7 then requires separate explicit mainnet activation authority.

Treasury-routed mainnet economic activation only after legal, economic, governance, security, operational, and launch approval.

## Authority ceiling

Planning and compatibility context only; this wave is not active implementation authority.

## Still unavailable

Treasury or chain failure cannot create, erase, or change scientific merit; mainnet has no automatic fallback to direct-winner weights.

## Key objects

- `TreasuryReceiverSet`
- `TreasuryRoutingWeightIntent`
- `SettlementObligation`
- `TreasuryAccrualLedger`
- `ValidatorAssignment`
- `ValidatorExecutionReceipt`
- `ValidatorAuditReceipt`
- `ValidatorServiceObligation`
- `ValidatorServiceSettlement`
- `Exactly-once settlement record`
- `Migration rehearsal evidence`

## Tickets

No controlling ticket board is captured for this planned wave.

## Repository detail

- [Agentic Development Master Plan](https://github.com/carbonphysicsai/Carbon/blob/d0cff7f611aaf9598ebe16999cb20941f48655b8/Design_Specs/Agentic_Development_Master_Plan.md)
- [Repository constitution](https://github.com/carbonphysicsai/Carbon/blob/d0cff7f611aaf9598ebe16999cb20941f48655b8/CONSTITUTION.md)

> Orientation boundary: repository authority owns exact semantics, implementation, review, evidence, and activation.
