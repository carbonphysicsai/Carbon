# Owner acceptance: the two-host exact replay study

**Recorded 2026-09-21. Owner decision, programme #209.**

`VALIDATOR_TWO_HOST_EXACT_REPLAY_PLAN.md` states that no attempt is spent until
the specification is accepted and the outstanding inputs are decided. Seven gates
stood. Two were already met - the same-device precondition passed at
representative scale, and the study is quoted. **The remaining five are decided
here.**

This is the first document in this programme that authorizes spending. Its bounds
are stated in section 7 and are not to be widened by inference.

---

## 1. Owner acceptance of the specification

**Granted.**

What is accepted is a study capable of returning a result that **blocks the
declared execution class**: `delta` fixed in advance from prior evidence,
calibration restricted to public or synthetic DEVELOPMENT material,
larger-margin controls retained so a null can be distinguished from a study that
looked where nothing could be seen, and comparison carried at every layer through
to gate outcomes rather than weight digests alone.

## 2. MQ-008 domain acceptance

**Accepted by the owner in the absence of named domain holders.**

Recorded plainly because it matters. MQ-008 names its owner as *"SciML +
infrastructure"* - **roles, not people** - and `.agent/DECISIONS.md` records that
the Carbon owner must still identify who holds them. There is therefore no
separate SCI or SRE signature on this study, and this document does not pretend
otherwise.

The owner accepts in their stead. This is legitimate for a development-evidence
study; it is **not** equivalent to domain review.

> **Follow-up, not optional.** MQ-008 sits in **Gate 1 - before first
> authoritative Challenge or LIVE planning.** Before that gate, the roles must be
> filled and this acceptance revisited by whoever holds them. Evidence produced
> under this acceptance is development evidence and does not become qualified by
> the study succeeding.

## 3. The declared execution class

**L40S.** Replaces `HUMAN_INPUT` in the plan's execution-class table.

Datacenter-grade rather than consumer, so matched pairs are constructible from
standardized providers; 48 GB gives ample headroom; the Ada generation supports
the pinned CUDA 13 stack; and at about $1.09/hr it is low enough that validators
are not priced out of participating.

RTX 4090 was rejected as the declared class despite its popularity on Bittensor:
it is concentrated in heterogeneous marketplaces, which is precisely where a
matched pair cannot be constructed. A100 remains the defensible alternative if
availability ever argues for it.

**Declaring a class is not qualifying it.** `compare_r1` still returns
`BACKEND_UNSUPPORTED`.

## 4. The provider, and a hard pre-run check

**RunPod Secure Cloud**, for standardized datacenter hardware with the GPU model
selectable - which is what makes a matched pair constructible at all.

A heterogeneous marketplace is refused for this purpose. Two listings of the same
GPU there differ in host CPU (EPYC 9355 versus 9335 was the observed case), and
W3 established that CPU instruction-set level changes the weights, so such a pair
confounds the only question the study asks.

**This constrains how Carbon procures its own evidence. It does not narrow
validator provider freedom**, which is about who may run Carbon. D3 is unaffected.

> **Hard gate before any run: both hosts must report the same driver build.**
> The plan records driver per host and does not pin it. If the builds differ,
> re-provision or record it as a named limitation - otherwise a driver difference
> is indistinguishable from a device difference and the study loses its question.

## 5. Delta per candidate pair

Derived from **previously retained evidence**, fixed here, before the comparison
runs.

| Pair | Target `delta` (relative) | Basis |
| --- | --- | --- |
| Near-margin | **1e-5** | peak prediction relative divergence from the CPU instruction-set work, `1.151e-05` at 8 steps |
| Control | 1e-3 | larger margin |
| Control | 1e-2 | larger margin |

**Stated limitation.** CPU cross-instruction-set divergence is a **proxy** for GPU
cross-device divergence, not a prediction of it. It is the only measured
cross-configuration figure Carbon holds. The alternative - deriving `delta` from
this study's own results - is the soundness hole already closed, and a proxy with
its limitation recorded is better than a number chosen after seeing the answer.

Every pair and its `delta` are fixed before the comparison runs, recorded with the
evidence, and **not revised afterwards.**

---

## 6. Gate status

| Gate | State |
| --- | --- |
| Same-device precondition at representative scale | **met** - pinned held, 1 digest across sessions at 100,680 parameters |
| Quotes | **met** |
| Owner acceptance | **met** - section 1 |
| MQ-008 domain acceptance | **met with limitation** - section 2 |
| Declared class | **met** - L40S |
| Matched-hardware provider and driver check | **met** - section 4 |
| `delta` per pair | **met** - section 5 |

## 7. What is authorized, and its bounds

**Authorized:** the two-host exact replay study as specified, on two classes -
the declared **L40S** and **A40** as the second class, so agreement reads as a
property rather than a coincidence of one kernel set.

| Bound | Value |
| --- | --- |
| Hosts | 2 per class, provisioned and released together |
| Classes | 2 - L40S and A40 |
| Billed hours | up to 4 per host, per class |
| **Ceiling** | **USD 30 total** |
| Provider | RunPod Secure Cloud |
| Invocations | per the plan - 144 across the pair |

**Stop and report, do not continue, if:** the two hosts report different driver
builds and cannot be re-provisioned to match; the billed total would exceed the
ceiling; a matched pair of the declared class is unavailable; or an in-class
mismatch appears whose cause is unestablished.

**Not authorized by this document:** any further hardware, any MQ-008 campaign
beyond this study, any qualification, any change to `compare_r1`, scoring, gates
or tolerances, and any spend beyond the ceiling. The four-attempt strict batch is
untouched and remains at zero consumed.

## 8. What success would and would not mean

If both hosts in a class produce one digest, that is **evidence toward** MQ-008 and
nothing more. It does not qualify the backend, does not make `compare_r1` return
`SUPPORTED`, and does not survive the follow-up in section 2.

If they diverge, that is the finding, and it outranks the schedule. Diagnose it as
an incident with cause unestablished. Do not average it, do not select a
favourable repeat, and do not choose a tolerance to make the classes agree.

---

# Amendment 1 to the acceptance - single chassis before two hosts

**Recorded 2026-09-21. Owner decision, programme #209.**

The accepted study went straight to two hosts. It now runs in two stages, **B
gated on A**. Bounds in section 7 of the acceptance are unchanged: the USD 30
ceiling and the four stop conditions cover both stages together.

## Why - two questions were being conflated

| | Question | Right instrument |
| --- | --- | --- |
| **Q1** | Do two same-class GPUs produce the same result, *all else equal*? | one chassis, two devices |
| **Q2** | Do two validators on **different hosts** agree? | two hosts |

A two-host test answers Q2 with every confound present at once - different host
CPUs, different drivers, different everything. **W3 established that CPU
instruction-set level changes the weights**, so a two-host disagreement would be
genuinely ambiguous between device, CPU and driver, and no analysis afterwards
separates them.

A 2-GPU pod answers Q1 almost exactly: same chassis, same host CPU, same driver,
same OS, two physically distinct dies of one model. Every confound is removed
except the device itself.

**Q1 is a precondition for Q2.** If two devices in one chassis disagree, two
hosts certainly will, and that is learned cheaply with nothing to disentangle. If
they agree, then any two-host disagreement is **attributable to host
differences** - which is actionable, because the response is to pin CPU class or
driver in the execution class rather than to guess.

This is the same sequencing that has paid off repeatedly here: CPU determinism
before GPU, same-device before representative scale, representative scale before
cross-device. Single chassis belongs between the last two.

## Stage A - single chassis

One 2-GPU pod per class, both devices in one chassis. The declared class
(**L40S**) and the second class (**A40**), as before.

Everything else is unchanged: the same orchestration through
`validator_launch.launch()`, the same pinned image by digest, the same fresh
processes with compilation never shared between sessions, the same comparison at
every layer through to gate outcomes and candidate ranking, and the same `delta`
values fixed in section 5 of the acceptance.

**What stage A establishes.** Whether two same-class devices agree when nothing
else differs.

**What it does not.** It is **not** a two-host test and must never be reported as
one. It says nothing about host CPU or driver variation, which is precisely what
it removes, and nothing about whether validators on different machines agree.

### The accepted orchestration cannot run on the chosen provider

`validator_launch.launch()` spawns a container - it goes through `DockerCLI` and
`load_image_identity` in `worker.docker_runtime` - and so requires a Docker
daemon on the host. RunPod pods **are** containers, built from a custom image,
and cannot build or run containers. The provider's own documentation says so.
The two requirements are incompatible: on RunPod, stage A cannot be run through
`validator_launch.launch()` at all.

**Resolved by amendment 2 at the end of this document**, which decides that stage
A runs pod-native with the deviation recorded. Read it before running anything:
it fixes the words the result must be reported in, and it is the authority for
the deviation.

## Stage B - two hosts

The study as originally accepted: two separate single-GPU hosts per class,
co-located in one datacenter.

**Gated on stage A.** If stage A shows disagreement, **stop and report**. A
two-host study whose devices do not agree in one chassis would be measuring
several things at once and could not attribute any of them.

## Two pre-run checks, both hard

1. **Driver builds must match** across the compared units, as already required.
2. **Availability is re-verified at provisioning time, never trusted from a
   report.** Stock is live and moves between reads - an earlier report of no
   CUDA 13 A100 PCIe hosts was contradicted within the same session. Confirm at
   the moment of provisioning or do not provision.

## A known unknown, carried rather than assumed

Availability work proved that **two or more units exist** in the named
datacenters, by confirming the API will serve a 2-GPU pod there. That two
*separate single-GPU pods* can be **held simultaneously** in one datacenter is
likely but **unconfirmed**, because confirming it requires provisioning, which
spends.

Stage A does not depend on that fact. Stage B does. Treat it as a stage B
precondition to be established at provisioning, not as an established fact.

## Availability as measured

| Class | $/hr | CUDA 13 datacenters with a co-located pair |
| --- | --- | --- |
| A40 | 0.49 | CA-MTL-1, EU-SE-1 |
| L40S | 1.09 | EUR-IS-2, OC-AU-1, US-MO-1, US-TX-4 |

A40 and L40S share no datacenter. That does not matter: each pair needs only its
own two co-located units, and the comparison is within class.

**No stop condition is triggered.** The declared class has co-located pairs
available, and the earlier "thin, LOW everywhere" reading was drawn from stock
grade, which was the wrong instrument.

## Unchanged

Ceiling USD 30 across both stages. The four stop conditions stand. No
qualification, no tolerance, no change to `compare_r1`, scoring, gates or
thresholds. The four-attempt strict batch remains untouched at zero consumed.
`compare_r1` still returns `BACKEND_UNSUPPORTED`, and success at either stage is
evidence toward MQ-008 and nothing more.

---

# Amendment 2 to the acceptance - stage A runs pod-native

**Recorded 2026-09-21. Owner decision, programme #209.**

Section 7 of this acceptance, and the plan's execution-class table, name
`validator_launch.launch()` as the orchestration. **Stage A cannot satisfy that on
RunPod**, and the reason is a platform constraint rather than a preference:
`validator_launch` spawns a container through `DockerCLI` and
`load_image_identity`, a RunPod pod *is* a container, and RunPod's documentation
states that a pod cannot build or run containers.

**Decided: stage A runs pod-native, with the deviation recorded.**

## What this costs, and what it does not

**It does not change the numbers.** The pod-native path reproduces the
containerised path's weights digest exactly on the same device. That is a
measurement, not an argument, and it is why the deviation is acceptable: the
quantities stage A compares are unchanged.

**What is lost is the layer around them.** Admission, the worker profile, the
device lease, task-owned cleanup, and Carbon's containment - no `--network none`,
no read-only root, no dropped capabilities, no seccomp profile, no cgroup
ceiling. The provider's runtime supplies whatever isolation the pod has.

So, stated exactly:

> **Stage A establishes whether two same-class devices agree. It establishes
> nothing about whether the validator orchestration agrees.**

Those were always different questions. Stage A's is the numerics one, and
pod-native answers it. Do not report it as the other.

## The execution class is amended to describe what runs

Record the path in these words, which are the runner's own:

> **direct execution inside the pinned image; not `validator_launch`;
> containment from the provider's runtime**

A study that measured a different path than it claims is not an exact replay of
anything. Both pins still apply - the image digest **and** the Carbon revision -
because the image predates the current code.

## Scope

**This covers stage A only.** Stage B's hosts are not yet chosen. If they are
pods, the same constraint applies and the same deviation is recorded. If a host
with a container runtime the validator controls is chosen instead,
`validator_launch` becomes available and stage B should use it - that would make
stage B strictly stronger than stage A, which is the right direction.

## A consequence to carry, not to bury

`validator_launch` remains **`HARDWARE_EXERCISED: no`**. C-CORE-20 is implemented
and engineering-tested, and no real run exercises it. This decision does not
change that and should not be read as having done so. Whenever a host with a
daemon is available, exercising it is outstanding work.

## Unchanged

Ceiling USD 30 across both stages. The four stop conditions stand. Pre-run checks
unchanged: re-verify availability at the moment of provisioning, and confirm
driver builds match across compared units. Nothing is qualified,
`compare_r1` still returns `BACKEND_UNSUPPORTED`, and success is evidence toward
MQ-008 and nothing more.

---

# Amendment 3 to the acceptance - stage A runs from a study image

**Recorded 2026-09-22. Owner decision.**

Amendment 2 settled that stage A runs pod-native. This settles what it runs
*from*, and it is an owner decision rather than an executor's: it changes a pin
the acceptance fixes.

## Why the volume path had nowhere to run

The pod needs the Carbon checkout, and the pinned worker image cannot fetch it -
no `git`, no `curl`, no `wget`, no CA bundle. A network volume was the route, and
a network volume exists only in a datacenter that offers one.

`EUR-IS-2` carried a live L40S 2-GPU pod at 2026-09-22T11:51Z and reports
`networkVolumeTypes: []`. No volume can be created there at all, by a staging pod
or by the S3 API. On the acceptance's own datacenter survey the declared classes
and the thirteen volume-capable datacenters **do not intersect**, and the
volume-capable sites are different numbered facilities in the same metros as the
GPU-dense ones. RunPod's documentation acknowledges the tension directly, so the
exclusion is treated as structural rather than momentary.

## Decided: build the study image from the pinned digest

`ghcr.io/carbonphysicsai/carbon-determinism-study`, built `FROM` the pinned
worker digest with the Carbon checkout, `pytest` and `pynvml` added and the
entrypoint replaced. No volume, no S3, no staging pod, no template.

**This collapses the two pins into one.** The execution class previously
recorded an image digest *and* a Carbon revision, because the published image
predated the code; the study image's digest now pins both. That is the end state
the plan already names - circumstance moved it earlier, and it is the opposite of
the entrypoint-only wrapper rejected before Amendment 2, which would have added
a second digest for nothing.

**The declared class was not refitted to a storage constraint.** L40S remains
the declared class and A40 the second, chosen on validator-realism grounds.

## Verified before publication, not argued

Two gates, both run on the merge commit rather than a branch head:

| Gate | Result |
|---|---|
| The pinned image's layers survive unchanged | all **10** preserved; 3 added on top |
| The numerics are unchanged | reproduced `83e523384fd44db6207583cede3294bd3f2f8b690802b11f661ade1eb825f10a` |

The base's own `site-packages` is untouched - the two added packages live in
their own directory on `PYTHONPATH` - so "only Carbon and two packages are
added" is checkable rather than asserted.

```text
image   ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:3ebfe68571f2396b1b32259fd5263daac1cce256ebe9e37ba7373f62b0234e52
carbon  74ff35ead1e5e571e6ac47601ea3f7780676a155   (pinned by the image digest above)
```

## Supersedes the volume-capability pre-check

The runbook's step 0 required a conjunction: the class available **and** that
same datacenter volume-capable. With no volume, **the condition is class
availability alone.** The conjunction is superseded rather than deleted, because
it remains correct for any future variant that mounts a volume.

## Outstanding before a run

The published package is `internal`, so an anonymous pull is refused and RunPod
cannot fetch it without a registry credential - which this study does not use.
Making it public is an organization package setting. **Until that is done the
image exists and cannot be run**, and that is recorded here rather than
discovered at provisioning.

## Unchanged

Ceiling USD 30 across both stages. The four stop conditions stand. Availability
re-verified at the moment of provisioning. Stage A reports **device agreement
and explicitly not orchestration agreement**; `validator_launch` remains
`HARDWARE_EXERCISED: no`. Nothing is qualified, `compare_r1` still returns
`BACKEND_UNSUPPORTED`, and success is evidence toward MQ-008 and nothing more.

---

# Amendment 4 - domain holders named, delta measured on GPU, four classes

**Recorded 2026-09-22. Owner decision, programme #209.**

Three changes, following the A40 stage A result and its review.

## 1. MQ-008 domain holders are named

Section 2 of this acceptance recorded domain acceptance as *"accepted by the
owner in the absence of named domain holders"*, with a condition: the roles are
filled and the acceptance revisited before Gate 1. **That condition is now
discharged for the scientific half.**

| Role | Holder |
| --- | --- |
| MQ-008 scientific (SciML) | **Harshdeep Sharma** |
| Deputy, in his absence | **Ryan Bequette** (owner) |
| MQ-008 infrastructure | **Ryan Bequette**, for now, stated as a gap rather than a decision |

Harshdeep reviewed the A40 stage A result and approved it. The scientific half of
MQ-008 is therefore held by a named person with relevant domain work - his Burgers
v1 FNO parity note covers the model family this study trains.

**The infrastructure half remains thin.** It concerns whether the declared
execution environment is operationally sound, which is a different question from
whether the science is. Recording the owner as holder is accurate and is not the
same as having an SRE. Revisit before Gate 1.

**What a holder does, so the role is not just a name.** Accept the evidence
specification - which quantities, how many repeats, what constitutes adequate
evidence, and what a negative result looks like - and then judge the evidence
against it. Approving a result is not the same act and does not substitute.

## 2. Delta is derived from GPU measurement, not a CPU proxy

Section 5 fixed the near-margin `delta` at **1e-5**, taken from the peak
prediction relative divergence in the CPU instruction-set work, and recorded
plainly that CPU cross-instruction-set divergence is a **proxy** for GPU
cross-device divergence rather than a prediction of it.

**The owner has directed that the value be measured on GPU.** GPU is the platform
Carbon validates on, and a borrowed CPU figure is the weakest link in the study's
design.

**What that requires, because the obvious source does not exist.** Pinned GPU
divergence measured **zero** - identical digests across both A40 devices, and
identical to the RTX 3060's. There is no pinned epsilon to size `delta` against.
The GPU-native figure must come from the **unpinned** runs, which produced five
distinct digests across six sessions.

A digest establishes *different*, not *how different*. `delta` needs
prediction-level magnitude, and the retention rule keeps one representative
artifact per cell rather than all of them. **So this requires a short re-run of
the unpinned cells with full artifact retention**, from which the prediction
relative divergence is computed.

Until that run completes, `delta` remains 1e-5 **marked as provisional and
CPU-derived**. It is replaced by the measured GPU figure before any further class
is run, so the remaining classes are evaluated against the right value.

Unchanged: `delta` is fixed before the comparison it governs, is never derived
from the results being tested, and calibration uses public or synthetic
DEVELOPMENT material only.

## 3. The class set is four, chosen by architecture generation

Sections 3 and 7 named two classes. **The owner has directed reproduction across
two further classes.** They are chosen by architecture generation rather than by
price or availability, because the claim worth having is about the configuration
rather than about a hardware list.

| Class | Generation | State |
| --- | --- | --- |
| A40 | Ampere | **done** - two devices agree, pinned |
| L40S | Ada | pending stock |
| **H100 SXM** | **Hopper** | added |
| **B200** *or* **RTX PRO 6000 SE** | **Blackwell** | added |

Both additions showed CUDA 13 with a co-located pair in the recorded survey.
Choose between B200 and RTX PRO 6000 SE on availability; either supplies the
Blackwell generation.

**Why generation rather than count.** Four cards agreeing is evidence about four
cards. Four *generations* agreeing under one pinned configuration is evidence
that the configuration carries the determinism, which is the claim that would let
Carbon qualify a configuration instead of maintaining a hardware list. The A40
result already points this way - it matched a laptop RTX 3060 across both device
class and host instruction set.

## Unchanged

**Ceiling stays USD 30.** Four classes plus the retention run are estimated near
USD 3-4 at observed rates, against USD 0.14 spent. The four stop conditions
stand. Class order is not scientifically load-bearing for a single-chassis
comparison; run whichever class stock offers, and record why.

Nothing here qualifies anything. `compare_r1` still returns
`BACKEND_UNSUPPORTED`. Stage A establishes device agreement and not orchestration
agreement, and `validator_launch` remains `HARDWARE_EXERCISED: no`.

---

---

# Amendment 5 - preliminary divergence convention, pending ratification

**Recorded 2026-09-22. Owner decision, PROVISIONAL.**

Amendment 4 names Harshdeep Sharma as the MQ-008 scientific holder and moves
`delta` to a GPU measurement. Two questions the measurement cannot answer for
itself - the denominator convention, and whether `delta` is absolute or relative -
are his. **They are decided here provisionally so work continues, and they are
subject to his ratification.**

**This is safe to decide provisionally for one specific reason:** the emitter
prints sufficient statistics - max, mean and L2 absolute difference, differing
count and fraction, both candidate denominators, and the values at the position
of the largest difference. **Every convention is derivable afterwards from a
completed run.** A different ratification costs a recomputation, not a pod.

## 1. Denominator convention - provisional

| Figure | Definition | Role |
| --- | --- | --- |
| **Headline** | relative **L2** over the prediction field | comparable to the model family's literature |
| **Companion** | **max** `|a-b| / max(|a|,|b|)` | worst-case, gate sensitivity |

**Why relative L2 as the headline.** It is the conventional error metric for
neural-operator surrogates, which is the model family this study trains, and it is
the figure the scientific holder's own parity work reports. A number stated in the
field's own convention is easier to ratify or reject than one invented here.

**Why a max companion, not L2 alone.** L2 averages over the field and can hide a
single element diverging badly. A mandatory gate acts on a scalar metric that may
be dominated by a worst case, so the worst case is reported beside the aggregate
rather than folded into it.

**Why `max(|a|,|b|)` rather than `|a|`.** The comparison is device against device.
Neither run is the reference, so a denominator that privileges one is wrong on its
face; `max` is symmetric and stays bounded where one side approaches zero.

## 2. Absolute or relative - provisional: both

Report both, always, and never one alone.

- **Absolute** is the form the implementation records. `NumericalDelta` carries
  `absolute_delta`, an observed per-output difference, so the absolute figure is
  what any future connection to `compare_r1` would be expressed in.
- **Relative** is the form the study reasons in, and the only form comparable
  across workload scales and model sizes.

Reporting both costs nothing, defers nothing, and keeps the seam visible -
implementation records absolute while the study reasons relative - rather than
resolving it silently in favour of whichever was convenient.

## 3. What this does not decide

**No `delta` value is set here.** The measurement produces figures; the holder
sets `delta`. The provisional `1e-5`, marked CPU-derived in Amendment 4, stands
until replaced.

**Flagged for the holder, from local sanity figures and not a conclusion.** Two
unpinned RTX 3060 sessions gave max absolute `5.96e-08` and L2 `9.49e-08` against
denominators near 0.98 and 6.13 - relative figures around `1e-7` to `1e-8`, **two
to three orders of magnitude below the CPU-derived `1e-5`.**

If the A40 measurement agrees, the CPU proxy was **too loose** rather than too
tight, and that matters more than a refinement: the power condition states that a
`delta` much larger than the observed divergence makes the study report *"no
ranking change" by construction*. A `delta` of `1e-5` against a real divergence
near `1e-7` is that failure. **The holder should see this alongside the
convention question, because it bears directly on what he is choosing.**

One device is not a finding. The A40 run settles whether it holds.

---

# Amendment 6 - the scientific holder is off the development critical path

**Recorded 2026-09-22. Owner decision.**

Amendment 4 requires the measured `delta` to replace the provisional one **before
any further class runs**, and Amendment 5 leaves `delta` to the scientific holder.
Chained, those put Harshdeep Sharma between one completed class and the remaining
three - so an open stock window could close while a decision waits.

**Decided: he is removed from the development critical path.**

## What changes

**The owner sets `delta` from the measurement**, under the deputy clause Amendment
4 already records, and the remaining classes run on it. No class waits on a
ratification.

`delta` set this way is **provisional and owner-set**, recorded as such in the
evidence, exactly as the convention in Amendment 5 is.

## What does not change, and must not be read as changed

**The MQ-008 scientific review still happens, before launch.** The owner will work
through final implementation with the holder ahead of it. This amendment moves
that review out of the development sequence; **it does not remove it.**

**The Gate 1 condition stands.** Section 2 of this acceptance records domain
acceptance as granted in the owner's own hand pending named holders, with the
condition that it is revisited before the first authoritative Challenge or LIVE
planning. Naming Harshdeep discharged the naming. **The review itself is still
owed, and nothing here discharges it.**

**Nothing becomes qualified.** `compare_r1` still returns `BACKEND_UNSUPPORTED`.
Stage A remains device agreement and not orchestration agreement, and
`validator_launch` remains `HARDWARE_EXERCISED: no`. This changes who decides a
development parameter and when - not what the evidence establishes.

## Why this is safe

The emitter records **sufficient statistics**, so every convention and every
`delta` in Amendment 5's scheme is derivable from the retained numbers of a
completed run. A later ratification that differs is a **recomputation, not new
hardware time**, and no class has to be re-run to honour it.

That property is what makes the holder's decision deferrable without making the
evidence provisional in any way that costs money to correct. If it ever stops
being true - if a future measurement bakes a convention into what is retained -
this amendment must be revisited, because the deferral rests on it.

---

# Amendment 7 - delta set from the GPU measurement

**Recorded 2026-09-22. Owner decision, under the deputy clause.**

Amendment 4 moved `delta` from CPU proxy to GPU measurement and required the
measured value before any further class runs. Amendment 6 put that decision in
the owner's hands so no class waits on a ratification. The measurement is done.

## What was measured

Eight unpinned sessions on 2x A40, four per device, each a fresh process, twelve
pairs. Predictions produced through the registered `predict()` from identical
archive inputs, compared under Amendment 5's convention.

| Quantity, predictions (128 elements) | Device 0 | Device 1 |
| --- | --- | --- |
| Differing elements | 24-29 of 128 | 24-29 of 128 |
| `max abs difference` | `5.960e-08` | `5.960e-08` |
| Relative L2 (headline) | `2.008e-08` | `2.006e-08` |
| `max/max(abs)` (companion) | `6.080e-08` | `6.080e-08` |

**Unpinned divergence is a single float32 ulp.** `5.9604644775390625e-08` is
exactly `2^-24`, and the field's max magnitude is `0.9803`, in `[0.5, 1)` where
one float32 ulp is exactly `2^-24`. Every pair, both devices, the same value.
The runs agree to the last representable bit and differ only in which elements
land on which side of a rounding boundary - the smallest nonzero disagreement
float32 can express, and qualitatively unlike the CPU instruction-set divergence,
which moved values by more than an ulp.

## Decided

| Pair | `delta` (relative) | Basis |
| --- | --- | --- |
| **Near-margin** | **`1e-07`** | measured max-relative `6.080e-08`, one significant figure above |
| Control | `1e-05` | 100x |
| Control | `1e-04` | 1000x |

**Sized to the companion rather than the headline.** Relative L2 is `2.0e-08`
and max-relative is `6.08e-08`. A mandatory gate acts on a scalar that a single
worst element can dominate, so the worst case is what could flip it; the
companion is the gate-relevant figure even though L2 is the headline.

**`1e-07` rather than `6e-08`.** The power condition wants `delta` *on the order
of* epsilon - not below it, which manufactures findings, and not far above, which
manufactures nulls. One significant figure just above the measured maximum keeps
the near-margin pair inside the noise band while staying a round number.

**The controls scale with it**, preserving the 100x and 1000x structure the
original `delta` carried. Left at the old `1e-05`, the first control would now
sit *below* the near-margin value and invert its purpose.

## Carried with it

**Provisional and owner-set**, exactly as the convention in Amendment 5 is. The
MQ-008 scientific review still happens before launch and nothing here discharges
it.

**A40 only, and unpinned.** One class, one chassis. The three remaining classes
may differ, and pinned divergence measured exactly *zero* - so this sizes the
noise that pinning removes, not a residual under pinning. `delta` is insurance:
it makes stage B able to detect divergence if pinning ever partially fails,
which is the only circumstance in which it matters.

**The CPU proxy was conservative by roughly 500x**, not understated. Had stage B
run on `1e-5`, the near-margin pair would have sat two to three orders outside
the real noise and the study would have returned a confident null that ruled out
nothing. That is the failure the power condition exists to catch, caught before
it cost anything.

**Recomputable.** The emitter retains sufficient statistics, so a later
ratification under a different convention is a recomputation from the retained
numbers rather than new hardware time.

## Unchanged

Ceiling USD 30. Stop conditions unchanged. Stage A remains **device agreement and
explicitly not orchestration agreement**; `validator_launch` remains
`HARDWARE_EXERCISED: no`; nothing is qualified and `compare_r1` still returns
`BACKEND_UNSUPPORTED`.

