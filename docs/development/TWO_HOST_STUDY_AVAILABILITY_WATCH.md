# Stage A availability watch - a falsifiable wait, not an indefinite one

Stage A cannot be provisioned as accepted, for a reason that is not stock.

The pod needs a **network volume** to carry the Carbon checkout, because the
pinned worker image has no `git`, no `curl`, no `wget` and no CA bundle and so
cannot fetch it. A network volume exists only in a datacenter that supports one.
**The declared classes and the volume-capable datacenters do not intersect.**

| | Datacenters |
|---|---|
| **L40S**, the declared class (acceptance §"Two pre-run checks") | EUR-IS-2, OC-AU-1, US-MO-1, US-TX-4 |
| **A40**, the second class | CA-MTL-1, EU-SE-1 |
| **Support a STANDARD network volume** | AP-JP-1, CA-MTL-3, CA-MTL-4, EU-NL-1, EU-RO-1, EUR-IS-1, EUR-IS-3, EUR-NO-1, US-CO-1, US-IL-1, US-MO-2, US-NC-2, US-TX-3 |

`EUR-IS-2`, where an L40S 2-GPU pod was live at 2026-09-22T11:51Z, reports
`networkVolumeTypes: []` - no volume can be created there at all, by a staging
pod or by the S3 API. Provisioning into it would have bought a pod whose mount
could never exist.

The volume-capable sites are **different numbered facilities in the same metros**
as the GPU-dense ones: US-MO-**2** not US-MO-**1**, US-TX-**3** not US-TX-**4**,
CA-MTL-**3/4** not CA-MTL-**1**, EUR-IS-**1/3** not EUR-IS-**2**. RunPod's own
documentation acknowledges the tension - *"Attaching a single network volume
constrains worker deployments to that volume's datacenter, which may limit GPU
availability"* - so the exclusion may be structural rather than momentary, and
this watch should not be planned on succeeding.

## What is actually unknown

Volume capability is **known**: the thirteen datacenters above. The catalog
reports *current availability* rather than capability, so what is unknown is
narrower and precisely this:

> **Do L40S or A40 appear at 2 GPUs, on any CUDA line, in any of those thirteen
> datacenters?**

A sighting settles it and stage A provisions immediately under the standing
authorization. A defined run of checks with no sighting settles it the other
way. **The bound is fixed now rather than when waiting becomes tiresome: one
week of periodic checks from the first row below.** After that the fallback is
taken without further deliberation.

## The fallback, decided in advance

If the watch expires unsatisfied, **build the study image from the pinned digest
with the Carbon checkout baked in.** That needs no volume, so the datacenter
constraint disappears entirely.

This is not the wrapper image that was rejected earlier, and the difference is
the point. That wrapper added a second digest for nothing - identical layers,
entrypoint metadata only - and became unnecessary once `dockerEntrypoint` turned
out to be reachable. Baking the checkout in **collapses the image digest and the
Carbon revision into one pin**, which the plan already records as where this
should end up; circumstance would only move it earlier.

It is verifiable before any spend: build it, run the existing harness locally,
and confirm it reproduces `83e523384fd44db6…`. Only the Carbon checkout is
added and the CUDA and JAX layers are untouched, so the numerics should be
identical - and if they are not, that is a finding worth having before renting
anything.

**Changing the declared class is not the fallback.** The class was chosen on
validator-realism grounds - datacenter-grade, matched pairs constructible,
affordable enough that a validator is not priced out. Changing it to fit a
storage constraint would make the study describe hardware nobody picked for a
scientific reason.

## Superseded: the two-slot staging requirement

An earlier reading of this required **two simultaneous** availability windows -
the L40S 2-GPU pod and a separate cheap single-GPU stager in the same
datacenter, since CPU pods are not offered where the L40S was. That requirement
is **superseded**: RunPod's S3-compatible API populates a network volume with no
compute at all, so the volume can be filled before any window opens and only one
window is needed.

It is recorded rather than deleted because it remains true wherever the S3 API
is unavailable, and because the observation that produced it - `EUR-IS-2` had no
single-GPU capacity even while its L40S 2-GPU was live - is what led to checking
volume capability at all.

## Checks

Each row is one read of the catalog at the stated time. Absence of a sighting is
recorded as such, and is not evidence that the class cannot appear - only that
it had not, when looked at.

| Checked (UTC) | Probe | Result |
|---|---|---|
| 2026-09-22T11:51Z | L40S, A40 @ 2 GPU, CUDA 13.0/13.2, SECURE | L40S **LOW in EUR-IS-2** at $2.18/hr; A40 Out. EUR-IS-2 later found volume-incapable. |
| 2026-09-22T13:2xZ | L40S, A40 @ 2 GPU, CUDA 13.0/13.2/12.8, SECURE, global | both **Out** on every line |
| 2026-09-22T13:39Z | volume-capable datacenter list, GPU availability | no L40S or A40 in any of the thirteen |
| 2026-09-22T13:5xZ | L40S, A40 @ 2 GPU, 13.0/13.2, SECURE | both **Out** |
| 2026-09-22T14:1xZ | volume-capable datacenters, GPU availability | no L40S or A40 among the thirteen |
| 2026-09-22T15:0xZ | L40S, A40 @ 2 GPU, 13.0/13.2, SECURE | both **Out** |

## Resolved by amendment 3, and why this watch continues anyway

The watch's question - *does either class appear in a volume-capable
datacenter?* - **no longer gates the study.** Amendment 3 builds the checkout
into the image, so no volume is needed and the condition reduces to class
availability in any of the class's own datacenters.

The rows continue because the remaining question is narrower and still open:
whether L40S appears at 2 GPUs **anywhere**. If a week of checks records no
sighting in any of EUR-IS-2, OC-AU-1, US-MO-1 or US-TX-4, that is a different
finding from the one resolved here - it would mean the declared class is broadly
unobtainable at 2 GPUs on this provider, which no image change addresses.

