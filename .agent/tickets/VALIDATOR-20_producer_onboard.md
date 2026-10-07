# VALIDATOR-20: `producer onboard --challenge <id>`, one resumable command per Challenge

**Status:** design. Built alongside the motor and cooling producer adapters
(Test Lead ruling 2026-10-07): battery is the registered test case, motor
joins when VALIDATOR-21 lands, cooling with VALIDATOR-22. Security-sensitive
(AGENTS.md §13): it runs as root on the producer host and drives hidden
material, so it needs a dedicated review.

**Authority:**
- OWNER-REHEARSAL-AND-RELEASE-01 (testnet runs the mainnet way);
- OWNER-VALIDATOR-MAINNET-PARITY-01;
- OWNER-ANSWER-KEY-INTAKE-EXPOSURE-01;
- the owner's question, relayed by the Test Lead on 2026-10-06: "Do I have
  to do this for every challenge". It asks for one Challenge-neutral command
  in place of the hand-run HETZNER_PART2 steps 4 and 9–14.

**Builds on** VALIDATOR-19 (producer, answer key, distribution, rotation),
VALIDATOR-17 (tuning set and quiz) and the TRAINING-BUDGET study sets.

**Executor:** the Carbon Validator session.

## What it replaces

Today a new Challenge on the producer host is about 30 copy-paste commands
across HETZNER_PART2. `onboard` runs the same commands in order, from one
entry point. It records what it has done and stops by name wherever an owner
action is needed.

## Design

1. **One Challenge-neutral orchestrator**
   (`carbon/challenge_validator/onboard.py`, CLI
   `python -m carbon.challenge_validator.onboard --challenge <id> --state <dir>`).
   - Every stage calls an existing command's function. No stage
     re-implements one.
   - Its stages come from a per-Challenge `OnboardAdapter` registry.
   - An unregistered Challenge fails closed with `onboard_no_adapter`.
2. **Stages** (the battery adapter):
   1. `truth`: materialize and verify the truth overlay or solver image
      (battery: the step-4 overlay against the `worker-images` manifest).
   2. `deployment`: write the deployment config from the operator's inputs
      file, then `init` the root. An existing root is verified, never
      re-initialized.
   3. `pool`: run producer ticks until the first windowed pool batches are
      prepared, solved, ingested and open, with their quiz predictions.
   4. `tuning`: export the pool, seal the tuning set with its registered
      priors, then the quiz: jobs, solve, refine, solve refine, select, seal.
   5. `study` (opt-in, `--study`): create the training-budget study sets.
   6. `verify`: the producer timer and the push unit exist and are enabled
      for this Challenge, and the last push succeeded.
3. **Resumable and idempotent.**
   - The state directory holds one `onboard-state.json`, owner-only (0600).
     It holds stage name, status, the public digests a stage produced, and
     the code commit.
   - A rerun skips completed stages after re-checking their recorded
     digests.
   - A digest mismatch is refused with `onboard_state_mismatch`; it is never
     redone silently.
   - A run on a different code commit than the recorded one is refused with
     `onboard_code_changed`. Resuming after an `upgrade` takes
     `--accept-code <commit>`.
   - The solve stages reuse the existing resumable `solve --work`.
4. **Owner stops.** These are named exits, each with the exact next command:
   - `onboard_needs_approval`: no approval record, or a digest mismatch
     (VALIDATOR-19 §4);
   - `onboard_needs_solver_licence`: an adapter declares a licensed solver
     that is not yet attested present;
   - `onboard_needs_input:<name>`: an operator input is missing (panel, dev
     results, priors);
   - `onboard_send_back`: a stage produced a value the owner sends back (the
     tuning commitment, the quiz digest and sequence, the refine total). The
     run continues; these values are also printed in the final summary.
   - Every quiz refusal (`tuning_quiz_*`) passes through unchanged, with its
     runbook step.
5. **Public output only.** It prints only:
   - stage names and statuses;
   - fingerprints and digests;
   - journal sequences;
   - counts.

   It never prints references, cases, seeds, salts, roots or key material.
   It never writes them outside the producer-owned paths the existing
   commands already use. A test asserts this over the captured output of a
   full fixture run.
6. **Privilege.** It starts as root only to check and install the systemd
   units and their ownership. Every stage that touches hidden material runs
   as `carbon-producer`, through the same `sudo -u carbon-producer -H` entry
   the sheets use.

## Cooling and motor (the first users after battery)

Read on main at 0e7308fe9. They are **not onboardable yet**:

| Need (stage) | Battery | Cooling | Motor |
|---|---|---|---|
| Hidden draw | `seeds.make_batch` | `population.draw` (used today only by confirmation sets) | `population.draw` (same) |
| Producer `BatchSource` | yes | no: `source_for` refuses with `producer_no_source` | no |
| Truth solve (stage 1) | pinned overlay | `reference_campaign` ledger only; no producer solve path | `getdp` plus `reference_campaign`; no producer solve path |
| Validator deployment, pool and windows | yes | public PRACTICE adapter only | public TRAIN/PRACTICE adapter only |
| Quiz and tuning definitions | yes | none | none |

Each needs a separate producer-adapter ticket first, covering the source,
solve path and deployment. Its quiz strata, lattice and tolerances are
science values and stay HUMAN_INPUT. Until then, `onboard --challenge
<cooling|motor>` refuses with `onboard_no_adapter`.

## Tests

- A full fixture run on synthetic material: every stage, in order.
- Kill and resume at each stage boundary; the final state is identical.
- A rerun with completed stages does no work.
- Each owner stop exits with its code and next command.
- Tampered state is refused with `onboard_state_mismatch`; a changed code
  commit with `onboard_code_changed`.
- An output scan finds no hidden field names or values.
- An unregistered Challenge is refused with `onboard_no_adapter`.

## Out of scope

- Cooling and motor adapters.
- Distribution-host setup (HETZNER_DIST stays a sheet).
- Releasing retired batches (HUMAN_INPUT).
- Any threshold or tuning value.

## Maturity ceiling

IMPLEMENTED and TESTED on fixtures. It is not SECURITY_QUALIFIED until the
dedicated review, and its first real run on the AX42 is the owner's.

## Size

About 1–2 days for the battery adapter, the orchestrator and its tests.
Cooling and motor are multi-day each, in their own tickets.
