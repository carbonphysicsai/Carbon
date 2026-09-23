# MQ-008 evidence package, for the pre-launch review

For the MQ-008 holder. **Nothing in this package qualifies anything.** It is
assembled so the review can be done from one document rather than from eight
amendments and four result files.

MQ-008 sits in **Gate 1**, before the first authoritative Challenge or LIVE
planning. Domain acceptance was granted in the owner's own hand in the absence of
named holders, with the condition that it be revisited by whoever held them.
Naming Harshdeep Sharma discharged the **naming**. **The review itself is still
owed, and this package does not discharge it.**

## 1. What was established

**Within one chassis, two identical devices produce bit-identical weights under
the pinned determinism configuration, and diverge without it.** Four architecture
generations, eight devices, four driver builds, 144 reconstructions, zero refused
cells.

| Generation | Part | Pinned digest |
| --- | --- | --- |
| Ampere | A40 | `83e523384fd44db6…` |
| Hopper | H100 SXM | `961cc4df99c52ad4…` |
| Ada | L4 | `83e523384fd44db6…` |
| Blackwell | RTX PRO 6000 SE | `ca46253059b20b3f…` |

**Across two separate hosts in one datacenter, the same class agrees.** Two
single-GPU A40 pods, three pinned sessions each, both `83e523384fd44db6…`.

**The agreement is caused by the configuration.** Every class diverged when the
pinning was removed, which is the control that makes the positive result mean
something rather than reflecting hardware that happens to be deterministic.

**Unpinned divergence is one float32 ulp.** `5.9604644775390625e-08` is exactly
`2^-24`, and the prediction field's maximum magnitude is `0.9803`, in `[0.5, 1)`
where one ulp *is* `2^-24`. Identical across all twelve measured pairs.

## 2. The decision this package puts in front of you

**Within a class, agreement was universal. Across classes it was not.**

| Digest | Produced by |
| --- | --- |
| `83e523384fd44db6…` | A40 (Ampere), L4 (Ada), a local RTX 3060 (Ampere, consumer) |
| `961cc4df99c52ad4…` | H100 SXM (Hopper) |
| `ca46253059b20b3f…` | RTX PRO 6000 SE (Blackwell) |

The grouping does not follow generation, class or price - a consumer laptop GPU
shares a digest with two datacenter cards, while two other datacenter cards each
stand alone. Nothing measured predicts which parts will coincide.

**The consequence is concrete.** Validators on the same **part** will agree with
each other. Validators on different parts may not, including parts of one
generation. Before a first authoritative Challenge, either the compute validators
must run is specified, or scoring tolerates the difference.

> **Corrected 2026-09-23.** This paragraph originally said validators on the same
> *generation* will agree. That overstated the evidence: agreement was measured
> between identical parts, and only one same-generation, different-part pair was
> ever observed (A40 and RTX 3060, incidentally). A100 against A40, L40S against
> L4 and B200 against RTX PRO 6000 were never compared. **Decided under
> Amendment 10:** validator compute requires the same part, qualified for the four
> parts measured, as the owner's provisional qualification in the holder's place.

**That is a scientific decision and it is yours.** This study measured the
phenomenon and does not resolve it. Note that it cuts against the provider freedom
the design otherwise promises, so the two have to be reconciled deliberately
rather than by default.

## 3. Two questions still awaiting your ratification

> **Ratified provisionally 2026-09-23 under Amendment 10**, by the owner as deputy
> for the holder: both provisional answers below, and `delta = 1e-07`. The
> holder's own review is still owed.

Routed to you on issue #42. Both are measurement-definition questions the
measurement cannot answer for itself.

**The denominator convention** for relative prediction divergence. Provisional:
relative L2 as headline, `|a-b| / max(|a|,|b|)` max as companion, absolute always
reported. Reason: `max(|a|,|b|)` is symmetric and bounded near zero, which matters
for a field that crosses zero.

**Whether `delta` is absolute, relative, or both.** Provisional: both, with the
relative convention stated, because the reproducibility implementation records an
absolute per-output difference while the study reasons in relative terms.

**Answering costs a recomputation, not a pod.** The emitter retains sufficient
statistics - both candidate denominators, the values at the position of the
largest difference - so a different ruling is recomputed from the record.

`delta` is currently **`1e-07`** near-margin, controls `1e-05` and `1e-04`,
**provisional and owner-set** under the deputy clause so that no class run waited
on a ratification. The figure it replaced, `1.151e-05`, came from CPU
instruction-set work whose **denominator convention was never recorded** - which
is part of why this is being asked rather than inherited. The CPU proxy was
conservative by roughly 500x.

## 4. What was substituted, and what that costs

**L40S was the declared Ada class and was unobtainable at two GPUs across a full
day** - visible in three catalog reads and gone at provisioning each time,
including two create calls seconds after a `Low` reading. Blackwell's declared
parts were likewise unavailable.

Ada ran on **L4** and Blackwell on **RTX PRO 6000 SE**, both permitted
substitutes, datacenter parts preferred over consumer ones.

> A substitute establishes that those kernel sets agree under the pinned
> configuration. It establishes **nothing about what a validator would deploy.**

L40S was chosen partly *because* a validator would plausibly run it. That purpose
was traded for generation coverage, deliberately and on the record.

**MIG slices were excluded by name.** They showed stock while every non-MIG
Blackwell part was `Out`. Two MIG instances are two partitions of one physical
GPU, so the comparison would very likely agree trivially and produce a number
that reads exactly like device agreement - worse than an absent result, because it
looks like a present one.

## 5. What remains unqualified

- **`compare_r1` still returns `BACKEND_UNSUPPORTED`.** The backend is not
  qualified and this evidence does not qualify it.
- **Device agreement, not orchestration agreement.** `validator_launch` remains
  `HARDWARE_EXERCISED: no` - implemented, engineering-tested, never exercised by a
  real run. Two hosts agreeing on numerics is **not** two validators agreeing on a
  score.
- **Containment was absent.** Direct execution inside the pinned image: no
  `--network none`, no read-only root, no dropped capabilities, no cgroup ceiling,
  no admission, no device lease. The provider's runtime supplied whatever
  isolation the pod had.
- **Nothing about the miner GPU consumer path**, which is a separate claim with a
  separate owner and must not be absorbed into this study.
- **H100 and Blackwell were each measured on one host only**, and their digests
  are distinct from the shared one, so neither is shown to reproduce across hosts.
- **The driver-match precondition was not enforced for stage B.** The compared
  hosts differed - `580.159.03` against `580.159.04`. Recorded as a deviation
  and applied retroactively under Amendment 9: it shows the pinned configuration
  held across a driver difference, but a patch-level one, one pair, discovered
  rather than chosen. The instrument gap is closed for future runs
  (`compare_units.py`); it does not reach back and verify stage B in advance.

## 6. Collection gaps

**H100 divergence figures are unrecoverable** - the report exceeded the pod log
window, since repaired by printing a compact summary before the body. Ada and
Blackwell ran without prediction capture deliberately, so their agreement results
would be retrievable.

**The Blackwell matrix ran twice**, so its per-cell counts are a union of two
executions. Every pinned cell agreed across both.

## 7. Provenance

Execution class, in the runner's own words: *direct execution inside the pinned
study image; not `validator_launch`; containment from the provider's runtime.*

One pin, `ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:998060ac…`,
which carries Carbon revision `77c5206116e01901cea0034a4791bc706c07f206` rather
than pinning it separately. Both gates passed before publication: all ten layers
of the base worker image preserved unchanged, and the image reproduced the
expected weights digest.

Total spend: approximately **USD 5.10** against a USD 30 ceiling.
