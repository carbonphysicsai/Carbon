## 2026-10-07 — OWNER-LAUNCHPAD-ACCEPTANCE-GRANT-01: a capped grant for the Launchpad's real acceptance matrix

**Authority.** The owner, 2026-10-07. The decision was relayed verbatim by the
Test Lead session to the Launchpad Acceptance session. It answers the grant
proposal in `docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md` §7 (PR #769):

> grant full, AX42 stays private, approve all

**Context.** LAUNCHPAD-ACCEPT-01 accepts the miner Launchpad on real
infrastructure: real machines, keys, chain and validator, never fixtures. The
remote-compute cells and the model-spend cells need money. Carbon's code still
rents nothing for miners (OWNER-MINER-COMPUTE-LINK-ONLY-01). For these cells
the owner acts as the miner:
- the owner starts and stops each machine;
- the Launchpad reaches each machine only through the owner's own SSH.

**Decision: the full grant, USD 13.55.**

| Line | Platform, transport | Plan cell | Machines | Rate ceiling | Deadline | Worst case |
|---|---|---|---|---|---|---|
| T1-a | RunPod pod, ssh-container | C4 | 1 | USD 0.50/h | 2 h | USD 1.00 |
| T1-b | Vast.ai VM instance, ssh-docker | C5 | 1 | USD 0.40/h | 2 h | USD 0.80 |
| T1-r | One replacement each for T1-a and T1-b | C4, C5 | ≤ 2 | as its line | 2 h | USD 1.80 |
| T2-a | Vast.ai standard instance, ssh-container | C6 | 1 | USD 0.40/h | 2 h | USD 0.80 |
| T2-b | Lambda instance, ssh-docker | C7 | 1 | USD 1.50/h | 2 h | USD 3.00 |
| T2-c | Lium pod, ssh-container | C8 | 1 | USD 0.60/h | 2 h | USD 1.20 |
| T2-d | Targon VM, ssh-docker | C9 | 1 | USD 1.00/h | 2 h | USD 2.00 |
| CL | Cleanup allowance | | | | | USD 0.25 |
| M1 | Inference checks, all seven `INFERENCE_ORDER` providers | I1–I7 | 7 | USD 0.10 per check | | USD 0.70 |
| M2 | Chutes, one 1-epoch Graphite BUILD campaign | I2 | 1 | | 1 epoch | USD 0.50 |
| M3 | Graphite commit-and-submit campaign | A1 | 1 | | 1 epoch | USD 0.50 |
| M4 | Hermes campaign | A2 | 1 | | 1 epoch | USD 0.50 |
| M5 | Retry allowance, one failed campaign | | | | | USD 0.50 |
| | **Tier 1** (T1-a, T1-b, T1-r, CL, M1–M5) | | | | | **USD 6.55** |
| | **Tier 2** (T2-a to T2-d) | | | | | **USD 7.00** |
| | **Monetary cap** | | | | | **USD 13.55** |

**Runs:** one per cell. Every replacement must be a T1-r line.

**Conditions:**
- **Tier 2 runs only where the owner holds the account.** That covers Vast.ai,
  Lambda, Lium and Targon. A line whose account the owner does not hold is
  recorded BLOCKED, never run another way. No agent creates an account.
- **A machine above its line's rate ceiling is not rented.** Rates are read
  from the provider when renting.
  - The ceilings were set from published rates read on 2026-10-07.
  - The Lium and Targon rates were UNVERIFIED when the ceilings were set.
- **The owner rents.** The owner starts every machine, stops it at its
  deadline or sooner, and confirms the cleanup.
  - For T1-a, the operator layer (`operator_compute`) may instead start the
    pod on the operator's own RunPod account, as under
    OWNER-A40-ACCEPTANCE-GRANT-01.
  - The Launchpad's code never rents, stops or bills.
- **Model spend uses the owner's own provider keys.** Keys are passed to setup
  by owner-only file path only.
  - Each check runs under its consent quote.
  - Each campaign runs under its own money ceiling, set no higher than its
    line.
- **Spend is booked privately, never in the repository.** Evidence records
  `within_cap` only.

**Outside this grant:**
- the OWNER-LAUNCHPAD-PROD-02 live smoke test (plan cell F07), already
  approved;
- Claude Code and Codex, which run on the owner's own plans;
- testnet 567 commitment fees, measured at 0 rao and paid in test TAO;
- anything on the AX42.

**Entry condition.** Nothing in this grant spends until this record is on
main.

**Not decided here:**
- any scientific value, threshold or gate;
- security acceptance of any Launchpad change;
- mainnet anything.

**No execution** happens through this record.
