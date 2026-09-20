# W6 preparation: the first GPU attempt, prepared and not started

**Nothing here has been run.** `/var/lib/carbon/accelerators` is absent, so
**0 of 4 attempts are consumed**, no grant or approval is installed, no device
has been attached and `ESTABLISHED_OBSERVATION_CONTRACTS` is empty.

`GPU_INITIAL_POLICY.md` P7 holds: no attempt is spent until a written evidence
specification exists **and the MQ-008 owners have accepted it**. The
specification is drafted (W2). It has not been accepted. This document prepares
everything that does not consume an attempt, so that when the owner decides, the
first attempt is executed rather than designed.

## 1. Preconditions, none of which spend an attempt

| # | Precondition | State |
| --- | --- | --- |
| 1 | MQ-008 owners accept the evidence specification | **not done** — owner/SCI+SRE |
| 2 | Owner decides how many attempts to spend | **not done** — see sizing below |
| 3 | Host device record installed | not installed |
| 4 | `doctor` passes the miner-lane required checks | unrun |
| 5 | Worker image built against the current profile digest | **owed** — the portable profile digest moved to `sha256:e1d8aefd…` |
| 6 | CPU arm recorded at a fixed CPU feature level | see W3 |

Precondition 5 is engineering work that can be done now. Preconditions 1 and 2
are the owner's.

## 2. The sizing decision the owner must make first

The minimum design that can distinguish anything needs **two identical GPU
repeats** — with one run, "the device computes differently" and "this workload is
not deterministic on this device" cannot be separated, and they have opposite
consequences.

Four attempts include failures, retries and controls. Two are the minimum useful
payload, leaving two for every failure mode.

> **Engineering's number: four suffices only if nothing fails. Tolerating one
> failure and still yielding a comparable pair needs three; any margin needs
> five or six.**

Recommendation: scope the batch explicitly as a **first probe** whose success
criterion is one comparable GPU pair, with an agreed follow-on if it fails.

## 3. The plan

1. Observe the device and install the host record — read-only observation, then
   `carbon-accelerator prepare`. Consumes nothing.
2. `carbon-accelerator doctor`. Must show no BLOCKED finding among the miner-lane
   required checks. Consumes nothing.
3. Verify the worker image matches the current profile digest and its labels.
   Rebuild if it does not. Consumes nothing.
4. Admit the execution into the durable queue with its binding.
5. **Attempt 1:** `carbon-accelerator run <manifest> --state-root <dir>`.
6. Capture the record in §5 before doing anything else.
7. **Attempt 2:** identical configuration, identical R0 identities, nothing
   varied. This is the repeat that makes attempt 1 interpretable.
8. Compare `checkpoint/state.npz` between the two, and against the CPU arm.

## 4. The command

```
carbon-accelerator run <manifest.json> --state-root <state-root>
```

The manifest carries materials only — plan, training archive, randomness, their
references, the resource-policy references and the pinned image identity. The
execution identity comes from the durable queue, and the manifest's digests are
checked against the admitted binding before anything is staged.

Cancellation, if needed mid-run:

```
carbon-accelerator cancel <execution-id> --state-root <state-root>
```

Afterwards, whether or not the run succeeded:

```
carbon-accelerator recover --state-root <state-root> --dry-run
carbon-accelerator recover --state-root <state-root>
```

`recover` matters on rented hardware specifically: a container left running bills
until someone notices.

## 5. What to capture, per attempt

Captured **before** the run: source commit and tree digest, image ID and labels,
environment lock digest, profile digest, plan and input digests, host device
record digest, the `doctor` report, and the exact command.

Captured **during and after**: the exact container command line, start and end
times, real process exit code, full stdout and stderr, the worker profile body as
staged, the resource observation, and the launch state transitions.

Captured **from the artifact**: `checkpoint/state.npz` sha256, the checkpoint
manifest sha256, the 25 stable artifact manifest keys, and the recorded
`compile_seconds` / `train_execution_seconds` **kept separately** and excluded
from every comparison — they are why `artifact_digest` is not a determinism
signal.

Captured **about the host**, because Carbon's `observed_environment` does not
record it and W3 showed it changes the weights: CPU model and feature level,
driver version, and the exact `XLA_FLAGS` in force.

## 6. The expected record

A successful attempt reaches `ASSOCIATED`, with the store showing the full
transition sequence and the container removed. The CPU-lane equivalent is already
covered by test, so the shape of a successful record is known; what is unknown is
whether a GPU-profiled run reaches it.

A successful attempt establishes **only** that the run completed and produced an
artifact the bounded validator accepted. It is not a qualification, it does not
make the backend `SUPPORTED`, and one attempt establishes nothing about
reproducibility.

## 7. What counts as a failed attempt worth not repeating

Worth **fixing before spending another**, because a repeat would fail the same
way:

- `doctor` BLOCKED on a required check;
- image or toolkit label mismatch, or a profile digest that does not match the
  image;
- driver or container-runtime mismatch;
- a manifest whose digests disagree with the admitted binding;
- silent CPU fallback — a successful computation that did not run on the device
  is a failure, not a result.

Worth **one retry**, because the cause is plausibly transient:

- a container that failed to start with no label or runtime mismatch;
- an infrastructure failure typed `FAILED_INFRA`.

Worth **stopping the batch entirely**:

- cleanup that cannot be confirmed, leaving device state uncertain;
- two attempts failing for the same root cause — a third will not learn more;
- any result that would need an invented tolerance to be called a success.

Every attempt counts against the four whether it succeeds or fails. A failure
whose cause is understood is worth more than a retry that is not.

## 8. What W6 must not do

Spend an attempt before precondition 1. Register an entry in
`ESTABLISHED_OBSERVATION_CONTRACTS`. Install or modify a strict host grant.
Choose a tolerance. Relabel a fresh reconstruction as an existing artifact.
Report "the GPU ran something" as a result — a measured divergence under pinned
identities is the result; a run that merely completed is not.
