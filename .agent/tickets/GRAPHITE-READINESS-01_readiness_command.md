# GRAPHITE-READINESS-01: one command that runs the Graphite readiness gate for a challenge

**Status:** QUEUED. It waits for a new owner session, which the owner will
start. The Test Lead briefs it.

**Authority:** the owner, 2026-10-05:
- "This should be the messiest run we ever have. Create a system to make sure
  that is the case."
- "Put it in the queue for a new agent."

**Specification:** `docs/development/graphite/GRAPHITE_READINESS_GATE.md`. The
lessons behind it are in `docs/development/graphite/LESSONS_REGISTER.md`
(both from PR #622).

## Goal

```
python -m carbon.challenge_pipeline readiness --challenge <challenge_id> [--level N] [--json OUT]
```

The command runs every item of the readiness gate for one challenge, at
Level 0 or a named construction level. For each item it prints:
- PASS / FAIL / NOT_BUILT / REVIEW_REQUIRED;
- the evidence: a test id, file and digest, or the decision id;
- the lesson id it enforces.

It exits 0 only when every item is PASS, or REVIEW_REQUIRED with a recorded
review. The JSON report is digest-bound so it can be cited in a launch record.

## Scope

1. **A challenge-neutral runner.** Each gate item is a registered check with:
   - an id (O1…V3);
   - a kind ([auto] or [review]);
   - a lesson reference;
   - a function `(challenge, level) -> Result`.

   Adding a gate item means adding a check. The item list in the gate
   document and the registered checks must match, and a test enforces that.
2. **Reuse, don't rebuild.** Wire the existing tests and tools as checks:
   - registry and contract;
   - `ChallengeScoring` and validator registration, and the unnamed-call
     refusal;
   - the no-op audit (#619);
   - `phase4 prelive` and `real_path_check`, plus the containment check;
   - the grant binding;
   - the designated admission controller (#615);
   - VALIDATOR-03's confirmation-role registry;
   - the Track B adapter and B ladder;
   - the gate margin study;
   - attack-adapter family and authority coverage.

   Where a check needs Docker, a pinned image or the operator host, the
   runner says so and FAILS CLOSED on a host that can't run it. It never
   passes by default.
3. **[review] items** read a recorded review from a committed file, e.g.
   `carbon/challenge_pipeline/readiness/<challenge>/<item>.json`, giving the
   reviewer, date, decision and evidence. A missing review is
   REVIEW_REQUIRED, never PASS.
4. **Metrics.** The runner appends one result line per run to the
   challenge's readiness history, so the register's §8 metrics ("items failed
   on the first gate run", "date the gate went green") come from data, not
   memory.
5. **First users:**
   - run it on battery, cooling and motor;
   - report the current gaps to the Test Lead, which will be many;
   - don't fix the gaps in this ticket; each one routes to its component
     owner.

## Out of scope

- Fixing any challenge's gaps.
- Live runs.
- Spend.
- Changing any frozen rule, contract or study.

The readiness gate never grants authority to run. The per-run launch
checklist (OWNER-GRAPHITE-TEST-WAVE-05 §3) still applies.

## Process

- Normal ticket flow, with a lessons entry for every execution.
- One PR, or a runner PR followed by a wiring PR, sent to PR Head with the
  Test Lead copied.
- Don't edit files pinned by a live study freeze.
- Battery-specific logic stays in battery's adapters; the runner names no
  challenge.
