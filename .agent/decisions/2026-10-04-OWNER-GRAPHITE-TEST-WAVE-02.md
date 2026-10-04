## 2026-10-04 — OWNER-GRAPHITE-TEST-WAVE-02: Attacker oracle and exposure semantics accepted; one-retry timeout rule; canonical coverage regeneration

**Authority.** The owner, 2026-10-04, answering the Test Lead session's four
decisions from the review of carbonphysicsai/Carbon#563 (the Graphite attack
engine, OWNER-GRAPHITE-ATTACKER-01):

> 1 accept 2 accept 3 your recommendation 4 approve

**Supplements** OWNER-GRAPHITE-TEST-WAVE-01. Nothing here changes a score,
gate, tolerance, construction contract, expansion record or EV5 artifact.

1. **AT-B-D5, the oracle's semantics, is accepted as designed.**
   - **Over-refusal is a finding.** When the path refuses a construction that
     Carbon would admit and run, the result is `BREACHED` with
     `FAILING_TRIGGER`. A valid construction refused by the boundary is a
     defect, not a defence.
   - **Protected-naming attempts are logged as not run.** An attempt that
     names protected material, and is refused or never sent, is recorded as
     `PROTECTED_WITHHELD`: NOT_RUN, with no finding.
   - **The gap stays visible.** Protected-naming probes are never counted as
     held evidence, and the coverage report shows that attack class as not
     covered.

2. **AT-C items 3 and 14, exposure handling, are accepted as designed.**
   - Two cases are each an `OTHER_SIGNAL` finding, failing closed:
     - a result Graphite withholds because it carries protected material;
     - an agent echoing its own request for protected material.
   - The finding blocks later expansion until the technical owner grades it.
     `UNDETERMINED` was rejected because it could hide a real exposure.
   - #563's repair F1 narrows the over-broad protected markers and adds a
     registered list of sealed identities, to cut false blocks.

3. **Worker timeouts get one retry before blame (the Test Lead's
   recommendation).**
   - **Retry.** A candidate's worker timeout on a pod is never treated as a
     scientific failure. It is retried once on a fresh pod, under the same
     declared budget.
   - **Blame only on repetition.** It counts as the candidate exceeding its
     declared resource budget only if the retry also times out. That outcome
     is never scored and never a physics failure.
   - **Otherwise it's infrastructure.** A timeout that doesn't recur is
     `FAILED_INFRA`. So are a pod's lifetime timeout, a launch failure and a
     lost pod, as today.
   - **Who records the stage.** The failure stage (timeout or program) is
     recorded by the supervising process outside the candidate. It is never
     taken from a file the candidate's own process could write.
   - **Who builds it.** Carbon Validator, in VALIDATOR-01 slice 2, which
     already owns the files involved (`graphite/pod_phase.py`, `pods.py`,
     `experiment.py`). It lands after #563.
   - **What it doesn't block.** #563's merge, because phase 4 launches no
     pods. It must land before any construction pod is scored in this test
     wave.

4. **The coverage file is regenerated on main.** After #563 merges,
   `docs/development/challenge_pipeline/SUITE_V1_BATTERY_COVERAGE.json` is
   regenerated through the canonical Linux runner on main, by its own small
   PR. Native-host output is not used.

**No execution.** This record dispatches, provisions and spends nothing.
