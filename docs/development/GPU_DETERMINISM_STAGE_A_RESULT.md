# Stage A result - four architecture generations, eight devices

Device agreement, measured. **Not** orchestration agreement, and nothing here is
qualified.

## What was asked, and what was found

Carbon's validators each retrain a submitted design in order to score it. If two
validators disagree, a miner's reward depends on whose machine ran the work. So:
do two devices, given the same registered material, produce the same model?

Two identical GPUs in one chassis, the same reconstruction on each, weights
compared byte for byte. Across four generations of NVIDIA hardware:

| Generation | Part | Pinned digest | Devices agree |
| --- | --- | --- | --- |
| Ampere | A40 | `83e523384fd44db6…` | **yes** |
| Hopper | H100 SXM | `961cc4df99c52ad4…` | **yes** |
| Ada | L4 *(substitute)* | `83e523384fd44db6…` | **yes** |
| Blackwell | RTX PRO 6000 SE *(substitute)* | `ca46253059b20b3f…` | **yes** |

**With the pinned determinism configuration the two devices produced bit-identical
weights, in every class. Without it they diverged, in every class.** So the
agreement is caused by the configuration rather than by the hardware happening to
be deterministic - which is what the unpinned contrast is for, and why it is run.

Eight devices, four drivers, 144 reconstructions, zero refused cells.

## The cross-generation pattern

**This is the policy-relevant finding, and it is not the same claim as the one
above.**

Within a class, agreement was universal. **Across classes it was not.** A40 and
L4 landed on the same digest; H100 produced its own; Blackwell produced a third.

| Digest | Produced by |
| --- | --- |
| `83e523384fd44db6…` | A40 (Ampere), L4 (Ada), and a local RTX 3060 |
| `961cc4df99c52ad4…` | H100 SXM (Hopper) |
| `ca46253059b20b3f…` | RTX PRO 6000 SE (Blackwell) |

So bitwise identity crosses some architecture boundaries and not others, and
nothing in the measured set predicts which. The consequence for Carbon is
concrete: **validators on the same generation will agree with each other;
validators on different generations may not.** Before a first authoritative
Challenge that is a decision - either the generation validators must run is
specified, or scoring tolerates the difference. It is a scientific decision for
the MQ-008 holder, not an engineering one, and it is **not** resolved by this
study.

Note also what it is not. The three parts sharing a digest include a consumer
laptop GPU, a datacenter Ampere card and a datacenter Ada card, so the grouping
does not follow generation, price or class. It is a fact about kernel selection
under the pinned configuration and it should not be extrapolated past the parts
measured.

## The substitution, stated as amendment 8 requires

L40S was the declared Ada class and B200 or RTX PRO 6000 the declared Blackwell
class. **L40S was unobtainable at two GPUs across a full day** - visible in
catalog reads three times and gone at provisioning each time - so Ada ran on L4
and Blackwell on RTX PRO 6000 SE, both permitted substitutes.

> An Ada or Blackwell substitute establishes that those kernel sets agree under
> the pinned configuration. It establishes **nothing about what a validator would
> deploy.**

A datacenter part was preferred over a consumer one where both were available -
L4 over RTX 4090 - because it retains more of the realism being traded, not on
price.

## MIG slices were excluded, by name

`RTX PRO 6000 ... MIG 1g.24gb` and `MIG 2g.48gb` showed stock while every non-MIG
Blackwell part was `Out`. They were **not** used. A MIG instance is a partition of
one physical GPU, so two instances are two partitions of the same silicon: the
comparison answers a different question and would very likely agree trivially,
producing a number that reads exactly like device agreement.

That failure mode is worse than an absent result, because it looks like a present
one.

## Divergence, and delta

Pinned divergence measured **exactly zero**, so there was no pinned epsilon to
size a tolerance against. The measurement came from the unpinned runs: eight
sessions on 2x A40, four per device, twelve pairs.

| Quantity, predictions (128 elements) | Value |
| --- | --- |
| Differing elements | 24-29 of 128 |
| `max abs difference` | `5.9604645e-08` |
| Relative L2 | `2.0e-08` |
| `max abs / max(abs)` | `6.080e-08` |

**Unpinned divergence is a single float32 ulp.** `5.9604644775390625e-08` is
exactly `2^-24`, and the field's maximum magnitude is `0.9803`, which sits in
`[0.5, 1)` where one float32 ulp *is* `2^-24`. Identical across all twelve pairs
and both devices. The runs agree to the last representable bit and differ only in
which elements fall on which side of a rounding boundary - unlike the CPU
instruction-set divergence, which moved values by more than an ulp.

`delta` is set at **`1e-07`** near-margin with controls at `1e-05` and `1e-04`
(amendment 7), sized to the max-relative companion because a mandatory gate acts
on a scalar a single worst element can dominate. It is **provisional and
owner-set** under the deputy clause; the convention is provisional pending the
scientific holder's ratification, routed to him on issue #42.

**The CPU proxy was conservative by roughly 500x**, not understated. Had stage B
run on `1e-5`, the near-margin pair would have sat orders outside the real noise
and returned a confident null that ruled out nothing.

## Collection gaps, recorded rather than smoothed

**H100 divergence figures are unrecoverable.** The class measured correctly and
the report scrolled past the log window - begin marker present, end marker absent
in all three read attempts from different offsets. Repaired afterwards by printing
a compact summary *before* the body, since the window takes the first entries from
wherever a read begins. Ada and Blackwell ran without prediction capture for the
same reason, deliberately, so their agreement result would be retrievable.

**The Blackwell matrix ran twice.** Two `STAGE_A_END` markers - 00:40:02Z and
01:20:39Z - with one `STAGE_A_BEGIN` in the retrievable window, so the container
restarted and re-ran. Its per-cell counts are therefore a **union of two
executions**, which is why some cells show six runs rather than three. Every
pinned cell across both executions produced `ca46253059b20b3f…`, so the result
holds and is if anything better supported; it is recorded as a union rather than
presented as one matrix.

## Execution class

*Direct execution inside the pinned study image; not `validator_launch`;
containment from the provider's runtime.*

One pin: `ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:998060ac…`,
which carries the Carbon revision `77c5206116e01901cea0034a4791bc706c07f206`
rather than pinning it separately.

Admission, the worker profile, the device lease, task-owned cleanup and Carbon's
containment are **absent** - no `--network none`, no read-only root, no dropped
capabilities, no cgroup ceiling. The provider's runtime supplies whatever
isolation the pod has.

## Maturity

`MEASURED` on rented hardware. **Device agreement, explicitly not orchestration
agreement.** `validator_launch` remains `HARDWARE_EXERCISED: no`: it is
implemented and engineering-tested and no real run has exercised it.

Not `SCIENTIFICALLY_QUALIFIED`, not `SECURITY_QUALIFIED`, not
`PRODUCTION_QUALIFIED`. `compare_r1` still returns `BACKEND_UNSUPPORTED`.
Evidence toward MQ-008 and nothing more, and it says nothing about the miner GPU
consumer path, which is a separate claim with a separate owner.

Total spend: **USD 4.76** against a USD 30 ceiling.
