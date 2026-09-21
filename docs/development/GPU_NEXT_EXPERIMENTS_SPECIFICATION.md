# The next device experiments: specification

Ticket C-CORE-19, work package N item N5. Written 2026-09-20.

**Nothing here has been run.** No new GPU run, rental or paid call follows from
this document. P7 still requires the evidence specification, explicit attempt and
repeat counts, and owner and domain acceptance. This prepares; it does not spend.

Three experiments in priority order. Each states its finite coverage, invocation
and repeat counts, elapsed-time and output limits, what counts as a failed run
worth **not** repeating, its required acceptance, and its full resource profile.

## Standing position before any of them

| | |
| --- | --- |
| Authorized batch | 4 attempts, **0 consumed** (`attempts_consumed: 0`) |
| Per invocation | 32 steps maximum |
| Per attempt | 1800 s; 600 s productive with 120 s cleanup reserve |
| Per batch | 3600 s from first admission, **no restart reset** |
| Output | 64 MiB per attempt, 256 MiB per batch |
| Network | worker network disabled |
| Spending | zero paid |

Batching repeats inside one admission economises **admissions only**. Every other
limit still applies, which is why each experiment below carries a full resource
profile rather than an attempt count alone.

Measured cost inputs, from D3 on the local RTX 3060 Laptop under the pinned
configuration: compile median 2.54 s (9 runs), train execution median 0.041 s at
2 steps. Compile dominates and the training itself is negligible at this scale -
which is precisely why the pinning *execution* overhead could not be resolved and
why experiment 2 must run at a scale where training is not negligible. Container
start and artifact export are not in those figures and must be measured, not
assumed.

---

# Experiment 1 — Localization on one device

**Priority 1.** Cheapest, and the only one that answers a question the existing
evidence cannot.

## Why

D3 went straight to full reconstructions and compared end states. It established
*that* unpinned sessions diverge and pinned sessions do not. It cannot say
**where** divergence enters, because every stage is confounded in the final
digest. Stages 1 and 2 of the staged design were skipped.

Knowing where it enters is what makes the pinning policy explicable rather than
empirical. It also determines whether a cheaper mitigation exists.

## Design

Three stages, each a strict subset of the next, all on the one local device:

| Stage | What runs | What it isolates |
| --- | --- | --- |
| 1 | Load a saved state, forward pass only, **no training** | Inference/reduction nondeterminism alone |
| 2 | Load a saved state, **first update only** (1 step) | The optimiser's first application |
| 3 | Full run at the established 2-step scale | Reproduces D3 as the control |

Stage 1 needs no training at all, so divergence there would mean the forward
reduction order is itself unstable - a much simpler and more serious finding than
"training diverges".

## Coverage, counts and limits

| | |
| --- | --- |
| Conditions | 2 (unpinned, pinned) × 3 stages = 6 |
| Sessions per condition | 3 **separate processes** - across-session is the axis that showed divergence; within-session repeats showed none |
| Invocations per session | 3 |
| Total invocations | 6 × 3 × 3 = 54 |
| Steps per invocation | 0, 1, 2 by stage |
| Elapsed budget | ≤ 600 s productive per attempt; expect ≈ 3 s/invocation, so 54 × 3 s ≈ 162 s plus container starts |
| Output budget | state + manifest per invocation; **cap at 64 MiB per attempt**, and prune intermediates rather than retaining all 54 artifacts |
| Attempts | 1, batched |

## What counts as a failed run worth not repeating

- A refusal at admission, image verification or device binding. These are
  configuration faults; fix the configuration, do not re-attempt against the
  budget.
- A container that cannot write its output directory, or a missing scratch path
  for `ptxas` intermediates. Both were hit during D3 setup. **Verify both before
  the attempt, not inside it.**
- `CARBON_ACCELERATOR_DEVICE_KIND` unset. The worker correctly refuses; supply it
  as the controller would, from the host record.
- A run that dies from external host contention (display, another process). Not a
  result. Record it, do not count it, and do not average it in.

A run that *completes* and disagrees is **never** a failed run. It is the finding.

## Required acceptance

1. All three stages complete in both conditions.
2. Within-session digests are identical in every session, as D3 found. If they
   are not, stop: the premise of every prior result has changed.
3. The stage at which across-session digests first differ is stated explicitly,
   in both conditions.
4. Numerics record (D1) captured per invocation, with effective ISA, XLA flags,
   TF32 and cuBLAS controls.
5. If stage 1 diverges, that is an incident with cause unestablished and is
   diagnosed before anything else proceeds.

## Resource profile

CPU 2, memory 4 GiB, PIDs 256, scratch 512 MiB, network none, one device, no
paid spend. Pinned image, labels verified. Local host only.

---

# Experiment 2 — Representative workload, same device

**Priority 2.** Tests the assumption the current policy rests on.

## Why

`VALIDATOR_GPU_DETERMINISM_POLICY.md` says pinning eliminates cross-session
divergence. That was measured at **2 steps and 4,696 parameters**. Whether it
holds at realistic reduction sizes and op mixes is unknown, and N3 has now made
the larger workload expressible.

The CPU scale measurement is a direct warning against assuming it transfers: over
2→32 steps, absolute divergence grew about 5× while **relative divergence did not
grow monotonically**, and at 32 steps the parameter figure was *below* its 2-step
value. Scale did not behave as the earlier evidence assumed it would. There is no
reason to expect a GPU to be more obliging.

## Design

Repeat the D3 characterization at 8 and 32 steps.

| | |
| --- | --- |
| Conditions | 2 (unpinned, pinned) × 2 scales (8, 32 steps) = 4 |
| Sessions per condition | 3 separate processes |
| Invocations per session | 3 |
| Total invocations | 36 |
| Elapsed budget | compile dominates and is scale-insensitive; training grows with steps. **Measure at 8 first**; do not commit the 32-step block until the 8-step block's elapsed time is known |
| Output budget | 64 MiB per attempt; retain digests and numerics records, not every artifact |
| Attempts | 1–2, depending on what the 8-step block costs |

## What counts as a failed run worth not repeating

As experiment 1, plus:

- An out-of-memory failure at 32 steps. That is a sizing fact to record, not a
  result to retry at the same size.
- Any run exceeding the 600 s productive deadline. Record the scale at which the
  envelope binds; do not extend the envelope to make the run fit.

## Required acceptance

1. The pinned condition produces **one** digest across sessions at each scale, or
   the policy's central claim fails at that scale and must be restated.
2. The unpinned condition is reported whatever it shows, including if it happens
   to agree - a single agreeing set of sessions does not establish determinism.
3. The pinning cost is re-measured at each scale, with enough repeats to resolve
   it. At 2 steps the compile cost is +0.93 s (median of 9) and the **execution
   cost is not resolvable at all** - median and mean disagree in sign. Execution
   is the component that scales, so experiment 2 is where it must actually be
   measured; discard per-session warm-up runs or report them separately.
4. Results are compared at every layer listed in the common protocol below, not
   by weight digest alone.

## Resource profile

As experiment 1. Memory headroom must be checked before the 32-step block; the
declared 4 GiB ceiling was never exercised at that scale.

---

# Experiment 3 — Matched two-host test

**Priority 3 by sequence, first by importance.** This is the milestone the whole
exactness strategy rests on, and **nothing to date touches it.**

## Why it cannot be substituted

Every result so far is one device. Two container configurations on one device are
not two hosts. Two names for one device are not two devices. The CPU
instruction-set work simulated a narrower feature set on one machine - useful, and
explicitly not a second machine.

The quantity that matters is: **do two same-class devices produce the same
result?** It is unmeasured. Not small, not bounded, not estimated - unmeasured.

## Design

Two actual same-class physical devices. Class identity and per-run identity are
different things and neither may be erased to make a comparison pass.

| | |
| --- | --- |
| Hosts | 2, same declared class |
| Conditions | pinned configuration on both; unpinned on both as a contrast |
| Strategies | **several admissible strategies**, not one baseline (see below) |
| Sessions per host per strategy | 3 |
| Invocations per session | 3 |
| Scales | 2 steps (comparable to all prior evidence) and 32 steps |

### Several strategies, deliberately close

Repeated runs of one baseline **cannot** detect the effect that matters. Two
devices may agree on a reference model and still favour different submissions.
The study must therefore include several admissible strategies, and they must be
chosen so their scores are **close enough that a rank swap is possible**.

This is the study's power condition and it must be stated before running:

> If the candidates' score separation δ is much larger than the observed
> divergence ε, the study will report "no ranking change" **by construction** and
> will have ruled out nothing.

So: select strategies spanning a range of separations, including at least one
pair with δ on the order of the divergence measured in experiments 1 and 2. State
δ for every pair in advance. A study that could not have found a
decision-changing effect has not ruled one out.

## Host, device and software — to be filled, not guessed

| Field | Value |
| --- | --- |
| Provider | `HUMAN_INPUT` |
| Region / partition | `HUMAN_INPUT` |
| Device model and class | `HUMAN_INPUT` |
| Driver version | `HUMAN_INPUT` |
| Host CPU model, ISA level | `HUMAN_INPUT` |
| Host memory, cores allocated | `HUMAN_INPUT` |
| Container runtime and version | `HUMAN_INPUT` |
| Worker image digest | pinned; must be byte-identical on both hosts |
| Profile / lock digests | `sha256:e1d8aefd79a540de086a293e430f4b6b255c749b60dc7bd8d3c51235534671cf`, lock `sha256:a197af53…` |
| jax / jaxlib / python | 0.10.2 / 0.10.2 / 3.11.16 |

**CPU-side conditions must be matched or recorded as differing.** W3 established
that the host CPU instruction-set level changes the weights. A two-host GPU study
run on hosts with different CPU feature levels cannot attribute a difference to
the device, and would be a wasted study. Either match the CPU ISA across hosts or
pin `--xla_cpu_max_isa` identically on both, and record which was done.

## Costs — no comparative claim without a quote

| Line | Amount |
| --- | --- |
| Provisioning | `REQUIRES_QUOTE` |
| Image download / transfer | `REQUIRES_QUOTE` |
| Setup time (billed) | `REQUIRES_QUOTE` |
| Productive compute | `REQUIRES_QUOTE` |
| Idle between stages | `REQUIRES_QUOTE` |
| Cleanup / teardown | `REQUIRES_QUOTE` |
| Storage / egress | `REQUIRES_QUOTE` |
| **All-in total** | `REQUIRES_QUOTE` |

No provider is named and no figure is estimated here, in either direction. **No
comparative cost claim may be made without a quote** - including the claim that
one option is cheaper than another, and including any claim that the cost is
small. Obtaining quotes is an owner action; this document does not authorize a
rental.

Idle cost deserves separate attention: a two-host study bills **both** hosts for
the duration of the slower one, plus any time a human spends between stages. Stage
the work so both hosts are provisioned and released together.

## What counts as a failed run worth not repeating

As experiments 1 and 2, plus:

- A host that does not match its declared class on arrival. Release it; do not
  substitute a different class and do not adjust the class to fit.
- Any mismatch in image, profile, lock or driver identity between the two hosts.
  Fix it before running; a study on two different software stacks measures the
  software stack.
- A device that cannot be confirmed idle at start. Record and release.

## Required acceptance

1. Both hosts verified to the same declared class, with all identity digests
   recorded and matching where they must.
2. Every comparison layer reported (below), for every strategy.
3. Any mismatch treated as **an incident with cause unestablished**. Diagnose it.
   Never average it away, never select a favourable repeat, never relabel a fresh
   reconstruction as the original artifact, and never relax an R0 check to make
   it pass.
4. The power condition stated: δ for every candidate pair, and the smallest
   effect the study could have detected.
5. Owner and domain (SCI + SRE) acceptance before any spend.

---

# Common comparison protocol

All three experiments compare at **every layer the divergence passes through**,
not at the weight digest alone. A digest comparison answers "identical or not"
and nothing else; it cannot say whether a difference would have changed a
decision.

| Layer | Quantity | Why it is separate |
| --- | --- | --- |
| 1 | Numerical state (weights) | Where divergence originates |
| 2 | Predictions | What downstream metrics actually inherit - two to three orders of magnitude smaller than parameter divergence on CPU |
| 3 | Physical measurements a Score Pack consumes | The gate acts on these, not on predictions directly |
| 4 | Gate outcomes | A step function; a tiny difference either flips it or does not |
| 5 | Ranking between candidates | The decision that binds others |

Layers 4 and 5 are the only ones that can show a **decision-changing** effect, and
they are exactly the ones a single-baseline repeat study cannot reach.

A known obstruction, stated rather than worked around: **no production Score Pack
exists.** Only synthetic A5 fixtures, with a `less_than 1.0` mandatory gate. Layers
3–5 must therefore be reported against a stated fixture pack, and the report must
say plainly that the gate margin in a real pack is unknown. Do not invent a
threshold to make layers 4 and 5 computable.

# Rules these experiments do not bend

1. Exact stays exact - R0 identities, schemas, provenance, artifact byte
   integrity. Only repeat-execution numerics admit a **registered** tolerance.
2. Never choose a tolerance to make hardware agree.
3. Never relabel B as A. A fresh reconstruction is its own artifact.
4. Do not erase device or run identities to make a cross-host comparison pass.
5. A mismatch is an incident with cause unestablished.
6. Do not widen `ScoreStatus`; never record an execution incident as a mandatory
   physics failure to fit the closed enum.
7. Protected material stays off this path.
8. Do not build on the strict host apparatus.
9. Do not edit a worktree while an experiment consumes it.

# Status

SPECIFIED. None of these is implemented, run, accepted or funded. Experiments 1
and 2 require no spend beyond local device time; experiment 3 requires quotes and
owner acceptance before anything is provisioned.
