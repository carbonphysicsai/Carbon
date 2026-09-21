# Work package: the most deterministic GPU reconstruction achievable, as validator policy

Owner direction, 20 September 2026: *test and solve for the most deterministic
way possible to run fair training (reconstruction) runs on GPUs, and make that
the validator policy.*

Authority is `docs/development/GPU_EXECUTION_LANES.md`,
`GPU_INITIAL_POLICY.md`, `GPU_PROGRAMME_PLAN_CORRECTION.md` and
`GPU_COMPLETION_WORK_PACKAGE.md` on `agent/gpu-execution-lane-design` (PR #248).
Fetch that branch first.

---

## What changed, and why this supersedes the last package

W3 measured cross-host divergence on **CPU**: the same strategy under identical
R0 identities produces different weights at different instruction-set levels, and
every identity Carbon records is the same across all three. That finding stands.

What it did not account for is that production reconstruction will run on **GPU**,
where every divergence source CPU has is present and more are added: autotuning
selects kernels per device and sometimes per run, SM count changes reduction
splits, atomics have no fixed order, and TF32 silently drops mantissa bits on
matmuls from Ampere onward.

The consequence is sharper than anything W3 found. **On an unpinned GPU a
validator may not reproduce its own run** - same host, same seed, same plan. R1
asks whether a repeat execution reproduces the numerical results, and the honest
answer on an unpinned GPU is no. No tolerance rescues that, and choosing one to
make GPU pass is what MQ-008 explicitly rejects.

So pinned determinism is not an improvement to make later. **It is a
precondition for a GPU profile ever qualifying**, and `worker_environment`
currently pins none of it - no `XLA_FLAGS`, no TF32 control, no autotune policy.

Two consequences for the earlier package:

- **The QEMU AVX-512 experiment is demoted.** It answers an x86-CPU-specific
  question. Keep it only as a footnote to the CPU exam environment.
- **The local GPU becomes the right instrument for one specific question**,
  which the W6 withdrawal did not cover. See D3.

---

## D1. Record what determines numerics

`observed_environment` captures backend, library versions, `machine: x86_64`,
Python and `x64`. It does not capture the CPU feature level, `XLA_FLAGS`, or any
GPU attribute. Two runs that compute different weights are indistinguishable in
the record.

Extend it to carry what actually determines the result. On GPU that is at least
the device model, driver version, CUDA and cuDNN versions, the TF32 setting, the
autotuning policy and any deterministic-execution flag. On CPU, the effective
instruction-set level and `XLA_FLAGS`.

Free, constrains no validator, and every later question is unanswerable without
it. **Do this first.**

Treat the digest change deliberately: recording new fields changes
`observed_environment_digest` for everything produced afterward. Say so, and say
what it means for records already accepted.

## D2. Establish the achievable determinism configuration

Research what the **pinned jaxlib and XLA versions actually provide** - do not
assume flag names from memory, and do not carry over a flag that a newer or older
build spells differently. Verify each one against the pinned build, and record
which were tried and rejected as well as which were kept.

The configuration should address, at minimum: deterministic kernel selection,
autotuning (disable or pin its results), TF32 on matmuls and convolutions,
reduction determinism, and any cuBLAS workspace setting the build honours.

Pin the resulting set in `worker_environment` for the GPU profile, the same way
the CPU lane's environment is pinned. Record the throughput cost - it is the real
trade and SCI should see the number rather than be told it is small.

## D3. Test it on the device that is here

This is a change from the previous package, and the reasoning is narrow enough
to state exactly.

The W6 withdrawal was right that a laptop GPU under WSL2 **qualifies nothing**
and verifies nothing about the launchpad, and that remains true. But the
question here is different in kind:

> Do the determinism settings work at all - does pinning them turn divergent
> repeats into identical ones?

That is a question about whether the CUDA and XLA machinery honours the settings,
not a claim about any device. If deterministic execution holds on this device it
is evidence the configuration functions; if repeats still diverge with everything
pinned, that is a finding about the settings and it transfers.

Two conditions, and the second is the one that matters:

1. **Unpinned repeats** on the same device, identical R0 identities. Establishes
   whether the problem is real here.
2. **Pinned repeats** under the D2 configuration. Establishes whether the fix
   works.

**Design this to consume as few attempts as possible.** Prefer repeats *within*
a single admission over one admission per repeat, if the envelope permits it -
work out whether it does before proposing a count. Four attempts cover failures
and retries too, and they do not come back.

**Report the proposed attempt count and the exact plan, then stop.** The owner
decides whether to spend. P7's gate is that an evidence specification exists and
the MQ-008 owners accept it; W2 drafted the specification, but drafting is not
acceptance, and this test is a determinism check rather than qualification
evidence - say which of the two you are asking to spend on.

## D4. Write the validator policy

The deliverable the owner asked for. It states the configuration a validator runs
GPU reconstruction under, and it must be honest about its own reach:

- **What pinned determinism delivers.** Whatever D3 measured - most plausibly
  same-device reproducibility.
- **What it does not.** Different GPU models will still produce different
  weights, and no setting changes that. Do not imply otherwise.
- **What that means for fairness.** Two validators on different devices compute
  different weights. The continuous score legs absorb that proportionally. A
  mandatory hard gate does not - it flips, and the submission goes from scored to
  `MANDATORY_GATE_FAILED`.
- **Provider freedom is preserved.** D3 gives validators their choice of
  provider, and the policy constrains the configuration, not where it runs.

Declare and disclose. Do not qualify anything, and do not set a tolerance.

## D5. Not yours to decide: gate robustness

Residual cross-device divergence meets the scoring gates, and that is where it
becomes unfairness rather than noise. The options - mandated margins relative to
measured divergence, or determining gate admissibility once from a reference run
or consensus median rather than per validator - are a protocol and scientific
decision for the owner and SCI.

**Write up the options and the trade-offs. Implement none of them.**

---

## Rules that do not bend

1. **Exact stays exact.** R0 identities, schemas, provenance and artifact byte
   integrity. Only repeat-execution numerics admit a registered tolerance.
2. **Never choose a tolerance** to make a device pass. If pinned determinism is
   not enough, that is a finding, not a licence to pick an epsilon.
3. **Never relabel B as A.** A fresh reconstruction is its own artifact.
4. **Protected material stays off this path**, with the invariant test holding.
5. **Do not build on the strict host apparatus.** Leave it; do not remove it.
6. Do not edit a worktree while a suite runs against it.
7. Zero paid spend. Nothing here requires renting anything.

---

# Amendment 1 - staged experiments, decision-layer criteria, and exactness by construction

Added after external review. D1 and D2 are unchanged and in progress. This
replaces D3's experiment design, adds a criterion to D4, and adds section E,
which is the strategy the measurements are meant to serve.

## A1. D3 is restaged

The original D3 asked one question - do repeats diverge unpinned, and stop
diverging pinned. That detects divergence without locating it, and a single
"the checkpoint differs" result does not distinguish an arithmetic difference
from a reproducibility bug from packaging metadata.

Run these as separate stages, in order, and stop at the first that fails:

| Stage | Held fixed | What it isolates |
| --- | --- | --- |
| 1. Replay from a saved state | Exact parameters, inputs, measurement code. No training. | Whether inference or measurement varies at all. |
| 2. First updates | Initial parameters, optimiser state, keys, data, precision. | Where divergence first appears in training. |
| 3. Same-seed reconstruction, fresh processes | Recipe, data, initialisation, prescribed work. Separate compilation. | Whether a full run reproduces on one configuration. |
| 4. Matched execution, second machine | The same intended experiment; host differences recorded, never erased. | Whether another machine changes results or decisions. |
| 5. Independent reconstruction repeats | Registered method; training randomness varied per policy. | Reconstruction variability the comparison must account for. |

Stages 1 to 3 need one device. Stage 4 needs a second and is the one this host
cannot supply.

**Distinguish numerical state from packaging metadata.** Two archives can differ
because run metadata differs - the determinism baseline already established that
`artifact_digest` covers wall-clock timings. Explain such a difference; never
resolve it by weakening an integrity check.

## A2. Weights are not the acceptance criterion

Report divergence at every layer it passes through, because the magnitudes differ
by orders of magnitude and only the last two decide anything:

parameters, then predictions, then the physical measurements a Score Pack
consumes, then gate outcomes, then the ranking between candidates.

W5 already showed predictions diverging about five hundred times less than
parameters. A criterion stated on parameters would overstate the risk by roughly
that factor; one stated on gate outcomes is the only one that means anything.

## A3. Candidate-by-hardware interaction

Neither W3 nor W5 tests this and it is the sharpest version of the fairness
question:

> Two devices may agree on a reference model and still favour *different
> submitted strategies*.

Repeated runs of one convenient baseline cannot detect it. Any hardware
qualification study must include several admissible strategies, including
difficult ones, and report whether the **ranking between candidates** changes -
not only whether each candidate's numbers move.

A study that fails to find a difference is not evidence of absence. State what
difference the study was capable of detecting; a study that could not have
detected a decision-changing effect has not ruled one out.

## A4. Already settled, do not re-litigate

`carbon/reconstruction/service.py:416` makes the status `COMPLETE` if and only if
`completed_steps == steps`. Reconstruction is **fixed-step today**: a faster
device finishes sooner, it does not train longer and earn a better result. The
fairness requirement that prescribed work be equal is already met. A host that
cannot finish yields an infrastructure outcome, not a partially trained model
presented as comparable.

---

# E. The strategy: exactness by construction, divergence as a fault

Owner direction: find a solution that does not rely on per-challenge uncertainty.
Use uncertainty only if forced.

## E0. Why the cheap fixes do not work

A mandatory gate is a discontinuous function of a host-dependent input. Rounding,
quantising, or aligning thresholds to a grid **relocates the boundary; it does not
remove it.** Values near the new boundary still flip. No transformation of the
output makes a discrete decision robust to noise in its input.

That leaves four moves, and only four: drive divergence to zero, make the
decision continuous, compute the decision once, or accept an indeterminate band.
Making the decision continuous changes the science. The band is the thing to
avoid. So: zero, or once.

## E1. First line - one declared execution class per challenge

The exam environment declares a single execution class: device class, driver
floor, library versions, and the determinism configuration from D2. Every
validator scoring that challenge runs that class.

**This does not cost provider freedom.** A class is a specification, the way
x86-64 is. Any provider offering it qualifies, and D3's guarantee is about
provider choice, not about device interchangeability. It is what MQ-008's
"narrow backend/hardware profile" already points at.

The property being bought is that **two validators in the class produce identical
metrics**, so a gate cannot flip between them and no tolerance is needed.

## E2. What makes it enforceable rather than aspirational

1. **Fail loud.** `--xla_gpu_exclude_nondeterministic_ops=true` rejects a
   computation that has no deterministic implementation, at compile time. Keep
   it. **Never relax it to let a run through** - that converts a loud failure
   into silent divergence, which is strictly worse than not having the flag.
2. **Provenance makes the class checkable.** D1 is what turns "validators run the
   declared class" into something verifiable. Today divergent runs record
   identical `observed_environment_digest`, so out-of-class execution is
   invisible and unrejectable.
3. **Divergence in class is an incident.** Two in-class runs disagreeing is a
   fault: recorded, investigated, and blocking for that comparison. It is never
   averaged away and never absorbed into a tolerance.

If E1 and E2 hold, the `ScoreStatus` gap is moot. Gates do not flip, so nothing
needs a "too close to call" disposition and no closed scientific enum has to be
widened.

## E3. Second line - compute the decision once

If same-class exactness does not hold, the next option is still not a
per-challenge epsilon. It is to evaluate the gate on **one agreed value**: a
deterministic consensus over validator-reported metrics, with exact tie-breaking
so every validator computes the same consensus from the same inputs.

Gates then act on a single number and cannot flip. Hardware stays entirely
unconstrained, so this is the option that preserves the most provider freedom. It
costs protocol machinery rather than scientific qualification, and it carries
game-theoretic questions - collusion, fabricated reports, minority robustness -
that belong to the owner and SCI, not to engineering.

## E4. Third line - registered uncertainty, only where forced

Only where E1 and E3 are shown not to work for a specific challenge. Declared for
that challenge, never a default, never chosen to make hardware agree, and never
by widening a physics threshold or averaging away a failed mandatory condition.

## E5. What to measure, and in what order

1. **Stage 3 on one device, determinism pinned.** Does a full run reproduce on
   one configuration? If not, E1 fails immediately and nothing further matters
   until it is fixed.
2. **Stage 4 across two devices of the same class.** This is the load-bearing
   measurement for E1 and it is the one that needs hardware this host does not
   have. Two identical instances is a far cheaper purchase than a cross-device
   study, and it answers the question the entire strategy rests on.
3. **Stage 4 across classes**, only to size how wrong it goes when the class
   requirement is violated - which justifies enforcement, and is not a step
   toward tolerating it.
4. **A3's candidate-by-hardware test**, at whichever classes survive.

**Report and stop before spending.** State which stages need a device, how many
attempts each needs, and whether the request is a determinism check or
qualification evidence. They are not the same and P7 gates them differently.
