# Stage B result - two separate hosts agree, and one precondition was not met

Two hosts, one class, one datacenter. **Device agreement across hosts**, not
orchestration agreement, and nothing here is qualified.

> **Driver deviation, applied retroactively under Amendment 9 (2026-09-23).**
> The two hosts ran `580.159.03` and `580.159.04` against a hard pre-run check
> that they match. Recorded in
> [`GPU_DETERMINISM_STAGE_B_DRIVER_DEVIATION.json`](GPU_DETERMINISM_STAGE_B_DRIVER_DEVIATION.json).
> **What it bought:** the pinned configuration held across a driver difference -
> two builds, one digest - which a matched-driver agreement could not show.
> **What it did not:** the builds differ in the patch component only, one pair,
> discovered rather than chosen; nothing here speaks to a wider driver
> difference. Cross-pod comparison now refuses differing builds unless a
> deviation names them exactly (`compare_units.py`).

## The result

| | Host 1 | Host 2 |
| --- | --- | --- |
| Pod | `gl890ny90kbw89` | `2sp0mat62jczk0` |
| Datacenter | CA-MTL-1 | CA-MTL-1 |
| Device | `GPU-6fb9f860-a693-1f05-8510-09300c93d617` | `GPU-b55ef9f3-5fd2-d26b-3a56-95b9b65260d7` |
| Driver build | **`580.159.03`** | **`580.159.04`** |
| Host CPU ISA | AVX512 | AVX512 |
| Pinned, 3 fresh sessions each | `83e523384fd44db6…` | `83e523384fd44db6…` |
| Unpinned | 2 distinct digests | 3 distinct digests |

**Two separate single-GPU hosts produced bit-identical weights under the pinned
configuration**, and the digest is the same one the 2-GPU A40 chassis produced in
a different datacenter. Unpinned, each host diverged across its own sessions.

Zero refused cells, all runs `COMPLETE` at 32 steps.

## The precondition that was not met, and why the result is stronger for it

The acceptance requires, as a hard pre-run check, that **driver builds match
across the compared units**. They did not: `580.159.03` against `580.159.04`.

That is recorded as a deviation rather than presented as a clean run. Two things
follow, in opposite directions:

**It strengthens the finding.** Agreement was obtained across hosts that differed
in driver build. Holding the driver constant would have tested less.

**It was not verified in advance, and the tooling cannot.** The matrix's
pre-flight reads the driver from NVML and refuses when builds differ **across
devices in one chassis** - which is where stage A needed it. Nothing compares
drivers **across pods**, which is exactly where stage B needs it. The mismatch
was discovered after the fact, by reading the two records side by side.

So the check the acceptance calls hard is enforced for stage A and unenforced for
stage B. That is a real gap in the instrument, not a footnote about this run, and
it should be closed before any stage B result is relied on: a future pair could
differ in driver *and* disagree, and nothing would have stopped the comparison or
flagged the confound.

**Closed under Amendment 9.** `run_on_pod.sh` now writes the NVML driver build
into every session record and refuses to run when it is unreadable;
`compare_units.py --preflight` refuses differing builds across pods before any
run; and a comparison of session records returns `REFUSED_DRIVER_MISMATCH`
unless a recorded deviation names exactly the builds observed.

## The precondition that was confirmed

The acceptance recorded, as a known unknown, that **two separate single-GPU pods
could probably but not certainly be held simultaneously** in one datacenter, and
that confirming it required spending.

Confirmed: both pods were created eleven seconds apart in CA-MTL-1 and ran
concurrently. At `$0.49` per hour each, stage B cost the same hourly rate as a
single 2-GPU stage A pod.

## What stage B added over stage A

Stage A had already produced cross-host agreement **incidentally**: a local RTX
3060, an A40 in EU-SE-1 and an L4 in EUR-IS-1 all produced
`83e523384fd44db6…` across three hosts, two drivers and two CPU instruction-set
levels.

That observation conflated **class** with **host**, because those are three
different GPU models. It showed that those particular parts agree; it did not
show that a given class reproduces across hosts. And cross-class agreement is
**not** universal - H100 and Blackwell each produced their own digest, each from a
single host.

Stage B closes that specific gap by holding class constant and varying host. A
companion run on 2x A40 in CA-MTL-1 also reproduced `83e523384fd44db6…`,
matching the EU-SE-1 chassis, so the same class now agrees across two
datacenters as well as across two hosts within one.

**What remains open:** H100 and Blackwell have each been measured on one host
only. Their digests are distinct from the shared one, so nothing here establishes
that either reproduces across hosts. If cross-host reproduction matters per class
rather than in general, those two classes are untested.

## Execution class

*Direct execution inside the pinned study image; not `validator_launch`;
containment from the provider's runtime.*

One pin: `ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:998060ac…`,
carrying Carbon revision `77c5206116e01901cea0034a4791bc706c07f206`.

`validator_launch` remains `HARDWARE_EXERCISED: no`. Stage B was run pod-native
under amendment 2, so it establishes nothing about the validator orchestration -
two hosts agreeing on numerics is not two validators agreeing on a score.

## Maturity

`MEASURED`. Device agreement across hosts. Not `SCIENTIFICALLY_QUALIFIED`, not
`SECURITY_QUALIFIED`, not `PRODUCTION_QUALIFIED`. `compare_r1` still returns
`BACKEND_UNSUPPORTED`. Evidence toward MQ-008 and nothing more.

Spend for stage B: approximately `$0.20`. Programme total approximately `$5.10`
against a `$30` ceiling.
