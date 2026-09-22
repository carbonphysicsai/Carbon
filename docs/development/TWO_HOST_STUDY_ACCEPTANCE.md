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

