# CANARY-01: a Carbon-owned canary miner on the real path

**Authority:**
- OWNER-CANARY-MINER-01 (2026-10-08);
- the plan, `docs/development/CANARY_MINER_PLAN.md`.

**Status:** SPECIFIED. The plan is written.

**S1, the runner** (`scripts/dev/canary/`, runbook
`docs/development/CANARY_RUNBOOK.md`):
- It is IMPLEMENTED and TESTED at fixture level by the PR that carries it
  (`tests/cpu/test_canary_runner.py`).
- It has not run against the live path, so no stage timing is measured yet.
- S2, the weights check, is not built.

**Working decisions for S1** (delegated engineering choices):

| # | Decision | Choice |
|---|---|---|
| W1 | Where the runner lives | `scripts/dev/canary/`, beside the Launchpad it drives (`scripts/dev/miner_launchpad/`). It is an operator tool, not product runtime, and nothing on a miner surface imports it. |
| W2 | The variant grid | kNN, `neighbours` 1–64 at each `train_fraction` in 1.0, 0.95, 0.9, 0.85 and 0.8: 320 recipes, about 48 days at one cycle per rotation. The plan's example of 2 fractions would last about 19 days. |
| W3 | When a variant is spent | It is claimed before its campaign launches. A REFUSED submission or a failed verdict closes the cycle. An UNAVAILABLE outcome, or any other failure, leaves the cycle open for the next run. No variant is ever reused. |
| W4 | One run, or one cycle | One `once` run waits at most `poll.max_wait_seconds`, which is not a deadline and never alerts. It then leaves the cycle open (PENDING) for the next run, and every run writes one journal line. |
| W5 | Admission | Seen from the readback alone: the first `evaluation_queued` (QUEUED), or the verdict. When the verdict comes on the first submit, the journal says that admission and scoring cannot be told apart. |

**Scope:**
- a canary runner that drives the Launchpad's MCP door every cycle:
  freeze, commit, submit, then a sealed verdict and the weights check;
- stage deadlines and Ops 2 alerts.

**Depends on:**
- SIGNER-AUTOCONFIRM-01, for unattended commitments. It is blocked until
  the owner confirms it in the building session.
- A registered canary list on the validator, which is the Carbon
  Validator's work.
- The owner's decisions in plan §9.

**Boundaries:**
- Testnet 567 only.
- No hidden material, and no access to the AX42 or the distribution host.
- Canary scores never win (plan §5).
- No model spend: the canary is a scripted own-agent client.
- Deadlines are owner-set (HUMAN_INPUT).
- Engineering evidence only.
