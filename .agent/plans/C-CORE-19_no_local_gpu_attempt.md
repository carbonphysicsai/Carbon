# No GPU attempt is planned on the owner's device

Recorded 2026-09-20 under programme #209, ticket C-CORE-19.
Decision record. **Zero of four authorized attempts are consumed and none is
planned.** `/var/lib/carbon/accelerators` is absent, no grant or approval is
installed, no device has been attached, and `ESTABLISHED_OBSERVATION_CONTRACTS`
is empty.

This supersedes an earlier preparation plan, written under a previous revision of
the completion work package, which staged a first local attempt. That plan is
withdrawn and was deleted rather than left to be found and followed.

## Why not

The device available here is a **laptop GPU under WSL2**, and it serves neither
goal the programme exists for.

**It does not verify the launchpad.** Goal 1 is that Carbon's worker starts on
hardware nobody chose in advance. That is verified by starting the worker on
rented hardware. One known laptop — in an environment where compute-process
enumeration returns empty, which is the condition that blocked the host in the
first place — is the least representative case available, not the most.

**It does not qualify validator GPU.** MQ-008 qualifies a **narrow backend
profile**, and validators run datacenter Linux GPUs. Divergence measured on this
laptop would qualify this laptop and nothing else, and the envelope of four
attempts exists to produce MQ-008 evidence.

## The mistake this avoids

The registry already corrected this error once. `RTX3060_LAPTOP_PROFILE` was
demoted to `HISTORICAL_PROFILES` precisely because pinning one laptop's device
into the workload was wrong, and the portable profile replaced it. Spending
attempts to measure that same laptop would repeat the same mistake in a new form
— this time by making one machine's numbers the evidence rather than one
machine's identity the profile.

## What a local run would actually buy

Narrower than it first appears, and worth stating so the option is refused on its
merits rather than dismissed:

- free crash discovery before paying for cloud time;
- a qualitative read on whether GPU training is run-to-run deterministic at all.

Both are **engineering convenience**. If either is ever wanted, it is a debugging
run under an explicit owner decision, framed as development evidence and never as
qualification — not a spend of an envelope built for MQ-008. The distinction
matters because attempts do not come back.

## What still holds

`docs/development/MQ008_EVIDENCE_SPECIFICATION.md` remains the gate on goal 2. It
is drafted against the hardware validators will actually use, not against this
host, and the owner decides when and where to spend against it.

The one thing still uncovered by test — reaching `ASSOCIATED` under a GPU profile
— stays uncovered, and this record is why. It is named as a limit rather than
quietly closed.
