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

### Blocked: the accepted orchestration cannot run on the chosen provider

`validator_launch.launch()` spawns a container - it goes through `DockerCLI` and
`load_image_identity` in `worker.docker_runtime` - and so requires a Docker
daemon on the host. RunPod pods **are** containers, built from a custom image,
and cannot build or run containers. The provider's own documentation says so.
The two requirements are therefore incompatible: on RunPod, stage A cannot be
run through `validator_launch.launch()` at all.

This is a documentation lag rather than a discovered defect - the acceptance was
written before the provider constraint was known - but it is not one an executor
may resolve by quietly running something else, because it changes what stage A
demonstrates.

**What the deviation would cost is narrower than it sounds.** The pod-native
path was measured against the containerised path on the same device and produces
the **identical weights digest**, so the numerics stage A compares are unchanged.
What it does not exercise is the layer around them: admission, the worker
profile, the device lease, task-owned cleanup, and Carbon's containment - no
`--network none`, no read-only root, no dropped capabilities, no cgroup ceiling.
Stage A run this way would establish **whether two same-class devices agree**,
and would say nothing about whether the validator orchestration agrees.

**Smallest owner decision required.** Either:

1. accept stage A by the pod-native path, with the deviation recorded in those
   words wherever the result is reported; or
2. hold stage A until a host that owns a Docker daemon is chosen, which is a
   different provider and a different quote.

Until that is answered this sub-scope is **blocked and fail closed**: nothing is
provisioned and nothing is spent. The rest of the acceptance is unaffected.

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
