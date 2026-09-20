# Work package: complete the GPU setup

Authority is `docs/development/GPU_EXECUTION_LANES.md`, `GPU_INITIAL_POLICY.md`
and `GPU_PROGRAMME_PLAN_CORRECTION.md` on `agent/gpu-execution-lane-design`
(PR #248). Fetch that branch before starting; the plan correction is new and
changes two things you were told earlier.

The owner wants the GPU setup **complete**. W1 to W5 need no GPU attempt, no
hardware authority and no spend, and they are everything that can be finished
without consuming something that cannot be returned. W6 is the attempt itself and
is gated - see the bottom.

---

## What changed since your last brief

**Validator provider freedom (D3).** Qualification attaches to a **backend
profile**, not to a provider or a host. Do not build anything that prescribes
where a validator runs. A contention finding would constrain a profile's run
conditions, never the choice of provider.

**Exam-environment disclosure (G4).** Miner hardware stays unconstrained, and
Carbon owes miners a published statement of what the validator will use for the
exam. That is a disclosure obligation, not an execution constraint. It is W4.

**Your determinism finding changed W2.** `ReconstructionReceipt.artifact_digest`
is a tree digest over a manifest carrying `compile_seconds` and
`train_execution_seconds`. It is not a determinism signal. Any evidence
specification built on it would measure a clock and report nondeterminism in
every case. Build W2 on `checkpoint/state.npz` and the named stable manifest
keys instead.

---

## W1. Close stage 1

A full CPU acceptance run is in flight at `b0b04d44` on
`agent/core-platform-19-gpu-lane-split`, logging to
`/tmp/carbon-acceptance.log`, started from a clean worktree with the revision
recorded in the log header. **Do not edit that worktree while it runs** - an
edit mid-run invalidates it, which has already happened once.

When it lands: if green, build the matching worker image against that revision
and land PR #247 and PR #249. If red, the failures are the work.

## W2. Draft the MQ-008 evidence specification

This is the gate on everything in goal 2, and it is the item that unblocks the
batch. Draft it for SCI + SRE to accept; you are not deciding it.

It must state:

- **Which quantities are compared.** `checkpoint/state.npz` bytes, and the
  manifest keys you established are stable. Name the excluded wall-clock keys
  explicitly and say why, so the exclusion is a recorded decision rather than an
  omission.
- **How many repeats on each backend.** At least two identical GPU repeats are
  needed to separate run-to-run variation from device-to-device variation. Say
  so plainly, including that four attempts covering failures and retries may not
  be enough - the owner has an open sizing decision and needs your number.
- **What would constitute adequate evidence**, and what would constitute a
  negative result. A specification that cannot fail is not a specification.
- **What the specification does not establish.** One device, one driver, one
  environment.

Set no tolerance. If the evidence supports one, that is SCI + SRE's output.

## W3. CPU determinism across execution configurations

The baseline is scoped to one host and one environment. The question that
actually governs validator consensus is whether two **different** machines
produce the same weights, and it is unmeasured.

You cannot rent a second host under this programme's zero-spend constraint, but
you can probe the dominant variance source for free. Reduction order is what
changes numerics, and it moves with thread count and kernel dispatch. Vary
`OMP_NUM_THREADS` away from the pinned 2, vary XLA's CPU client threading, and
compare `state.npz` across configurations on the one machine.

If weights stay bit-identical across thread counts, cross-host CPU determinism is
likely and the residual risk is microarchitectural dispatch. If they diverge,
**there is a consensus problem today that has nothing to do with GPUs**, and it
outranks the entire GPU programme. Either way, record it.

## W4. Define and publish the prescribed exam environment

Two halves, neither dependent on MQ-008:

1. **Define** it - which backend profile, pinned versions, precision and
   allocator policy, and resource envelope a validator runs reconstruction under.
2. **Publish** it where a miner can consult it before submitting.

Defining the environment is not qualifying it. Say in the document that it is
declared and not yet qualified, and that a validator may run it on any provider.

## W5. Gate margin analysis

Scoring-side, no GPU, and it decides whether GPU validators are safe at all.

`carbon/scoring/pack.py` defines `hard_gates` with a `less_than` operator against
a bare threshold, at least one mandatory, and a failure yields
`MANDATORY_GATE_FAILED` - the whole submission, not a deduction. The continuous
legs absorb small numeric differences proportionally. A gate does not; it flips.

Examine the registered Score Packs. For each mandatory gate, how close does a
typical input sit to its threshold, in units of the noise established in W3? If
margins are wide relative to the noise, record that and the risk is closed. If
any threshold sits within noise of typical inputs, that is a live design problem
and it belongs in front of the owner before any validator runs on GPU.

Do not change a threshold. Report.

---

## W6. The first GPU attempt - gated, do not start

Reaching `ASSOCIATED` under a GPU profile is the one thing still uncovered, and
it needs the device. It is also irreversible: attempts do not come back, and
`/var/lib/carbon/accelerators` is currently absent, so **0 of 4 are consumed.**

`GPU_INITIAL_POLICY.md` P7 holds: no attempt is spent until a written evidence
specification exists and the MQ-008 owners have accepted it. W2 produces that
specification. **Stop when W2 is drafted and W1, W3, W4 and W5 are done, and
report.** The owner decides whether to spend, and how many.

Prepare everything that does not consume an attempt: the plan, the command, the
expected record, what you would capture, and what would count as a failed
attempt worth not repeating.

---

## Rules that do not bend

1. **Exact stays exact.** R0 identities, schemas, provenance and artifact byte
   integrity. Only repeat-execution numerics admit a registered tolerance.
2. **Never choose a tolerance** to make a device pass. Missing procedure means
   unqualified or development evidence.
3. **Never relabel B as A.** A fresh reconstruction is its own artifact.
4. **Protected material stays off this path**, with the invariant test holding.
5. **Do not strengthen or build on the strict host apparatus.** Leave it; do not
   remove it.
6. Do not edit a worktree while a suite runs against it.
