# Two-host study: quoted rates and a procurement finding

Fills the `REQUIRES_QUOTE` lines in `VALIDATOR_TWO_HOST_EXACT_REPLAY_PLAN.md`.
Rates are **observed list prices, not commitments**; runtime is **estimated from
measured same-device timings** and marked as an estimate throughout.

Gathered 2026-09-21. Nothing was rented, reserved or paid for.

---

## 1. The procurement finding, first

**A heterogeneous GPU marketplace is the wrong instrument for this study**, and
that is not a pricing observation.

lium.io - one of the Bittensor-native providers D3 names - lists individual
operator pods. Two listings for the same GPU at the same price differ in their
host:

| Listing | GPU | Price | Host CPU | Location |
| --- | --- | --- | --- | --- |
| A | RTX PRO 6000 Blackwell | $1.29/hr | AMD EPYC 9355 | Washington |
| B | RTX PRO 6000 Blackwell | $1.29/hr | AMD EPYC **9335** | Beltsville |

Same GPU, different host CPU. **W3 established that CPU instruction-set level
changes the weights**, so a pair like this confounds the question the study
exists to answer: a difference could be the GPU, the CPU, or both, and the design
could not separate them.

The plan already requires that *"the CPU side must be matched or recorded as
differing."* This is what that requirement costs in practice - it constrains the
provider, not just the GPU.

**Implication.** Procure from a provider offering standardized datacenter
hardware where GPU model *and* host configuration are specified, rather than a
marketplace of independent operators. That is a study-design constraint. It does
**not** narrow validator provider freedom, which is about who may run Carbon, not
about how Carbon procures its own evidence.

**Second procurement requirement:** the plan records driver version per host and
does not pin it. Verify both hosts report the **same driver build before
running**. If they differ, either re-provision or record it as a named limitation
- otherwise a driver difference is indistinguishable from a device difference.

---

## 2. Quoted rates

RunPod Secure Cloud, observed list price 2026-09-21. Standardized hardware, GPU
model selectable, so a matched pair is constructible.

| Class | VRAM | $/hr |
| --- | --- | --- |
| RTX A5000 | 24 GB | 0.27 |
| A40 | 48 GB | 0.49 |
| L4 | 24 GB | 0.49 |
| RTX 3090 | 24 GB | 0.50 |
| RTX A6000 | 48 GB | 0.53 |
| RTX 4090 | 24 GB | 0.74 |
| L40S | 48 GB | 1.09 |
| A100 PCIe / SXM | 80 GB | 1.59 |

Storage: container disk $0.10/GB/month - negligible at these durations.

## 3. Runtime estimate

**Estimated, not quoted.** Derived from the stage-1 same-device measurements:
compile median 2.63 s pinned, training median 0.467 s at width 32 / modes 16 /
32 steps.

| Line | Estimate | Basis |
| --- | --- | --- |
| Compute per invocation | ~3.1 s | measured |
| Container lifecycle per invocation | ~30-45 s | staging, start, validate, stop, cleanup |
| Invocations per host | 72 | plan: 144 total across 2 hosts |
| Run time per host | ~55 min | 72 x 45 s |
| Image pull and verify | 10-25 min | one image, size not yet measured |
| Setup, verification, recover, release | ~30 min | |
| **Billed per host, with margin** | **~4 h** | includes idle between stages, which the plan notes bills both hosts |

The dominant cost is **container lifecycle and idle, not compute.** The science
occupies under four minutes per host; everything else is overhead. That is worth
knowing before optimising anything.

## 4. Total cost

Two hosts, provisioned and released together, 4 billed hours each:

| Class | 2 hosts x 4 h |
| --- | --- |
| RTX A5000 | **$2.16** |
| A40 | **$3.92** |
| RTX 4090 | **$5.92** |
| L40S | **$8.72** |
| A100 PCIe | **$12.72** |

A 50% runtime overrun changes these by a few dollars. The study is not
cost-constrained at any class.

## 5. Recommendation

**Run it on two classes, not one.** Total ~$11 at A40 plus L40S.

Agreement measured on a single class establishes that those two devices agree.
Agreement on **two different classes** is materially stronger evidence that the
pinned configuration delivers cross-device reproducibility as a property rather
than as a coincidence of one kernel set - which is the same reasoning that made
the stage-1 width/modes increase worth doing, since changing shape changed which
fixed kernels ran.

At these prices the second class costs less than the time spent deciding whether
to include it.

**The class to declare is still `HUMAN_INPUT` and this does not decide it.**
Pricing informs that choice; it does not make it. If the declared exam
environment is eventually an L40S or A100 class, the study should include that
class rather than infer it from a cheaper one.

## 6. What is still not quoted

- Image size, so transfer time is a range rather than a figure.
- Whether a given provider can guarantee two simultaneously available units of
  one class in one region at the time of purchase.
- Human time between stages, which bills both hosts.

## 7. Authorization unchanged

This is a quote. **P7 still governs**: no attempt is spent until the evidence
specification is accepted by the owner and the MQ-008 domain owners. Nothing here
is that acceptance, nothing was rented, and the journal at
`/var/lib/carbon/accelerators` remains absent.
