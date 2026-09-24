# R1 on real hardware - two simulated validators per part

**Recorded 2026-09-24.** The first time `compare_r1` decided on real GPU runs.
Owner direction of 2026-09-23: *"step 1 and step 2. We don't have validators yet
but we can simulate it."* Spend authorized at about USD 2.10; actual about
**USD 0.75** (estimated from pod run times; billing had not posted when this was
written).

## What ran

Two simulated validators per part: separate single-GPU pods of one part in one
datacenter. Each ran the pinned session three times and the unpinned contrast
twice, each session a fresh process, recording its device identity, material
digests, software versions and exact predictions.

| Part | Datacenter | Validator pods | Driver (both) |
| --- | --- | --- | --- |
| L4 | EU-RO-1 | `aqvpyvu1pa8hcl`, `umk2b3g8swyrj3` | `580.159.04` |
| H100 SXM | US-NE-1 | `yqjui1wxdel7sh`, `oflmalqzbsvovy` | `580.126.09` |

Image `ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:2d19b261e722…`,
built at Carbon `d0c19830d095`: the pinned worker digest's ten layers unchanged,
stage B's dependency layer byte for byte, the checkout and its staged manifest.
Before any pod, it reproduced `83e523384fd44db6…` on the local RTX 3060.

Records: `docs/development/evidence/r1-simulated-validators-2026-09-24/`.
`tests/cpu/test_study_r1_simulated_validators_evidence.py` re-derives every
outcome below from them.

## Result

| Part | Condition | Cross-validator pairs | R1 | Max absolute difference |
| --- | --- | --- | --- | --- |
| L4 | pinned | 9 | **REPRODUCIBLE** | `0` |
| L4 | unpinned | 4 | NOT_REPRODUCIBLE | `5.96e-08` (one float32 ulp) |
| H100 SXM | pinned | 9 | **REPRODUCIBLE** | `0` |
| H100 SXM | unpinned | 4 | NOT_REPRODUCIBLE | `5.96e-08` (one float32 ulp) |

R0 matched on every pair: the two validators' identities were exact. The pinned
weight digests are the ones measured earlier on single hosts - `83e523384fd44db6…`
for L4, `961cc4df99c52ad4…` for H100 - so **H100 now reproduces across two
hosts**, which the MQ-008 package listed as open.

**The unpinned control is the positive control on real data.** R1 refused, by
exactly the one-ulp margin Amendment 7 measured on A40, so the REPRODUCIBLE
verdicts come from a check that demonstrably can say no.

## A finding: identical weights, different predictions

Unpinned, H100 validator 1's second session and validator 2's sessions trained
**bit-identical weights** (`c27004ec…`) and still produced different predictions -
18 of 128 elements, by one ulp. The prediction pass has its own nondeterminism
when unpinned, independent of training. Pinned, predictions were identical.

So a matching weights digest does not establish that outputs reproduce. R1
compares predictions, not weights, and this is the evidence that it must.

## NVML names, now recorded

| Part | NVML device name |
| --- | --- |
| L4 | `NVIDIA L4` |
| H100 SXM | `NVIDIA H100 80GB HBM3` |

These are the only entries in `r1_capture.PART_BY_NVML_NAME`, each pointing at the
evidence it was read from. **A40 and RTX PRO 6000 SE** are qualified but were out
of stock on CUDA 13 hosts; their names were not guessed, so they have no capture
until read.

## What this is not

- **Not validator_launch.** Each validator was direct execution in the pinned
  image with containment from the provider's runtime. This is two independent
  executions agreeing, not two validators' orchestration agreeing;
  `validator_launch` remains never hardware-exercised.
- **The owner's DEVELOPMENT qualification** (Amendment 10) on
  `fixture_authoring 1.0`, in place of the MQ-008 holder, whose review is still
  owed. No official or LIVE authority, no security or production qualification.
- **Two parts.** A40 and RTX PRO 6000 SE were not run here.
- Different parts ran different drivers, so a cross-part comparison is refused by
  the driver check before R1, as designed.
