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
