## 2026-10-05 — OWNER-GRAPHITE-TEST-WAVE-06: cooling promotion rule for testing, CPU and GPU lanes, a cooling Constructor grant, and coverage of every compute, inference and agent option

**Authority.** The owner, 2026-10-05, in the Test Lead session, answering the
Test Lead's three cooling questions (from the Graphite Test executor's cooling
readiness review, gaps 2, 13 and 11):

> yes, test GPUs, approve

Then:

> We need to make sure we're testing all compute/inference/agent options
> eventually

**Supplements** OWNER-GRAPHITE-TEST-WAVE-01 to -05.

1. **Cooling's promotion rule, for testing only (gap 2).** The owner's answer:
   "yes".
   - **Settings reused from battery.** Cooling's practice comparison uses
     battery's unit-free settings, from the DEVELOPMENT rule in
     `carbon/battery/exam.py` (OD-2):

     | Setting | Value |
     |---|---|
     | `n_min` | 30 |
     | `n_boot` | 4000 |
     | `alpha` | 0.05 |
     | `important_min` | 10 |

     Cooling's public PRACTICE set has 100 cases, 30 of them important
     (peak_c ≥ 85).
   - **The margin is measured, not chosen.** The relative equivalence margin
     is derived from the measured seed-to-seed spread of the reference
     construction's practice score on cooling's public PRACTICE set. The
     measurement is reproducible and committed, and it states how battery's
     OD-2 margin compares.
   - **Status.** A testing acceptance for the Graphite wave only, like
     OWNER-GRAPHITE-TEST-WAVE-04 §2. It is not a scientific qualification of
     cooling's rule. Until the margin is measured and committed, cooling's
     comparison stays `NO_REGISTERED_COMPARISON` and promotes nothing.

2. **Cooling's Graphite runs test both lanes, CPU and GPU (gap 13).** The
   owner's answer: "test GPUs".
   - **CPU lane.** The pinned isolated CPU carrier miners use at Level 0
     (COOL-L0-D4). It tests the real miner environment.
   - **GPU lane.** Graphite's GPU pod route, with a pinned GPU worker
     declaration for cooling, its own pod program and data, the Carbon-owned
     GPU probe (pod-attribution-v2), and a GPU rebuild-identity check.
   - **Not opened to miners.** A miner-facing cooling GPU lane is a separate
     ticket. Offering it to miners needs a recorded hardware acceptance; COOL-
     L0-D4's refusal stays until then.

3. **A cooling Constructor grant for the CPU lane is approved (gap 11).** The
   owner's answer: "approve".

   | Item | Value |
   |---|---|
   | Runs | 3, one at a time |
   | Worst case per run | USD 1.95, tokens only (no pods on the CPU lane) |
   | Cleanup allowance | USD 0.25 |
   | Ceiling | **USD 6.10** |

   - The grant file is bound by the runner to `chip-cold-plate` and to main's
     committed blob.
   - A GPU-lane cooling grant includes pod time. It is proposed with a price
     once the GPU lane exists.

4. **Every compute, inference and agent option is tested eventually.** This
   is the owner's direction. The wave keeps a coverage axis in
   `docs/development/graphite/TEST_WAVE_MATRIX.md`: each option is TESTED,
   PLANNED or NOT_RUN, never assumed to work because another one did.
   - **Compute:**
     - the miner's own CPU;
     - the miner's own GPU;
     - the operator host CPU and GPU;
     - rented CPU and GPU pods (RunPod);
     - the pinned isolated CPU carrier;
     - confidential compute later (Targon, deferred).
   - **Inference:**
     - Engy, chat and messages;
     - Chutes;
     - OpenAI-compatible endpoints;
     - every model rung in the role ladders, each at full context (GRAPHITE-D34
       and the Attacker equivalent).
   - **Agents:**
     - Graphite's miner edition: Research, Build and Full modes;
     - Graphite's internal Constructor, Attacker, Planner and Optimizer
       researcher;
     - a miner's own agent over MCP;
     - manual or no-agent campaigns.

   Testing an option needs its own grant where it spends, and the Level 4–5
   isolation gate where it runs participant code.

5. **Codex builds every challenge's scoring adapters.** The owner, in the
   same exchange: "also Codex is building all challenge scoring adapters".
   - **Codex's scope.** Each challenge's `ChallengeScoring`, its Interface v1
     validator adapter, its practice comparison (cooling's from §1 once the
     margin is measured) and its per-challenge pod worker and program,
     including cooling's GPU lane in §2.
   - **Carbon Validator's scope.** The challenge-neutral Validator and the
     neutral Graphite plumbing that takes a named challenge: profiles, pod
     data shipping, next-level checks, rebuilds and per-challenge dry runs.

**No execution.** This record dispatches, provisions and spends nothing. The
grant file, the margin measurement and the lane work ship in their own PRs.
