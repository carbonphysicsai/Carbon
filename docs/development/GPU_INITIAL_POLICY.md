# GPU execution: initial policy and the decisions still open

**Status: proposal for ratification.** Companion to
`GPU_EXECUTION_LANES.md`. It ratifies what is decidable without measurement,
gates what is not, and names one thing worth doing immediately.

It sets no numerical tolerance, qualifies no hardware, and authorizes no
attempt.

---

## 1. Why an initial policy is possible now

The expensive mistakes available here are **structural**, not numerical: scope
drift, rebuilding a strictness apparatus nobody needs, and choosing a tolerance
to make hardware pass. None of those need a measurement to rule out.

The decisions that *do* need measurement are separable and are left open in §5.

---

## 2. Ratified now

### P1. The miner lane requires no backend qualification

**While** no miner-produced artifact is accepted into the scientific record
without independent reconstruction, the miner lane requires no qualification of
any kind.

That condition is the entire basis. Carbon's submission is a declarative
training strategy; validators train from scratch; a miner need not train locally
at all. If Carbon ever accepts a miner-produced artifact directly, this policy
lapses and the miner lane must be reconsidered from scratch.

### P2. Validator GPU stays unqualified until narrowly qualified

`compare_r1` returns `BACKEND_UNSUPPORTED` while
`identity.backend_support` is not `SUPPORTED`. That is the correct behaviour and
is ratified as policy, not left as an implementation detail.

This matters because §3 shows the gate does not self-resolve, and the tempting
fix - marking a backend `SUPPORTED` to unblock throughput - is a policy violation
rather than a patch. MQ-008 asks for a **narrow** profile: qualify one exact
configuration, then widen.

### P3. Exactness is never traded for hardware support

R0 identities, schemas, provenance and artifact byte integrity remain exact.
Only repeat-execution numerics admit a registered tolerance, supplied by a
qualified procedure. A fresh reconstruction is its own artifact and is never
relabelled as the one it was compared against.

### P4. No tolerance is chosen to make a device pass

Where a comparison procedure or qualification is absent, the result is
unqualified or development evidence. Never an invented threshold. This restates
MQ-008's own recommendation, which explicitly rejects broadening hardware support
by loosening scientific tolerances.

### P5. Protected material stays off the GPU path, structurally

Enforced by three facts, each of which must have a test that fails if it stops
holding: the accelerator profile is imported only by `carbon/reconstruction`,
`carbon/reconstruction/worker` and `carbon/development_session`; the staged
worker request field set is closed; `PublicTrainingArchive` rejects any role but
`TRAIN` at construction.

GPU-accelerated evaluation against hidden material, if ever wanted, is a separate
lane designed then.

### P6. Scope is the two goals

Enable the launchpad; let validators use GPUs for reconstruction. The strict host
apparatus is not extended, rebuilt or justified further. Existing code is left in
place for the validator lane and is not built upon.

---

## 3. The gate does not self-resolve

An unqualified backend short-circuits **before any comparison is computed**:

```python
if first.identity.backend_support is not BackendProfileSupport.SUPPORTED:
    return R1Result(R1Outcome.BACKEND_UNSUPPORTED, r0_result, (), None, None)
```

Empty deltas. No procedure invoked. The check sits above the
`procedure is None` check, so supplying a procedure does not help.

This is correct - `compare_r1` is a gate, not an instrument, and it should not
quietly become one. But the consequence must be stated plainly:

> **Running validators on GPU while unqualified produces no evidence toward
> MQ-008. Waiting does not resolve MQ-008. Only a deliberate measurement
> campaign does.**

Anyone reading "we are waiting on MQ-008" should understand that as "someone must
run a measurement campaign", not as "this will resolve in time".

---

## 4. Ratified now: the batch gate, and what to do first

### P7. The batch is not spent until an accepted evidence specification exists

The authorized four-attempt batch is the only mechanism that can unblock
validator GPU. It cannot be un-spent.

**No attempt is spent until a written evidence specification exists and the
MQ-008 owners have accepted it** - which quantities are compared, how many
repeats on each backend, and what would constitute adequate evidence.

Carbon may draft that specification for the owners to accept; it does not require
them to originate it. What it must not be is implicit.

This gate costs nothing. Goal 1 does not depend on the batch, and goal 2 is
already blocked by MQ-008, so the gate delays nothing that was moving.

### P8. Establish the CPU determinism baseline first

Before any GPU attempt, run the same registered strategy twice on CPU under
identical R0 identities and record whether the outputs are bit-identical.

This needs no GPU attempt, no hardware authority and no spend, and it answers a
prerequisite question nobody has answered: **is this workload deterministic at
all under fixed identities?**

- If CPU repeats are bit-identical, the workload is deterministic and any GPU
  divergence is attributable to the device and its kernels. That sharply narrows
  what MQ-008 must assess.
- If CPU repeats already diverge, there is a determinism problem that is not
  about GPUs, and it should be understood before spending attempts.

**It does not remove the need for repeats on GPU.** Separating GPU run-to-run
variation from device attribution requires at least two GPU runs of an identical
configuration. That constrains batch design directly: of four attempts including
failures, at least two must be an identical repeat pair, which leaves very little
margin. §6 records this as an open sizing question.

---

## 5. Not decidable yet

| Question | Decided by | Blocked on |
| --- | --- | --- |
| The numerical tolerance, if any | SCI + SRE via MQ-008 at G4 | the evidence specification, then measurements |
| Whether device contention affects numerics | MQ-008, empirically | the same |
| Whether validator hosts must be dedicated | Owner + SRE | the contention finding |
| Whether a telemetry observation source is established | Owner | evidence about that source's visibility |

None of these should be settled by engineering preference, and none is urgent
while goal 1 is the critical path.

---

## 6. Open, and needing an owner decision

**Batch sizing.** Four attempts including failures, retries and controls, with at
least two needed as an identical repeat pair. That may be too few to separate
run-to-run from device-to-device variation. Decide before spending: scope it as a
first probe with an explicit follow-on, or expand with justification.

**The paid-spend boundary.** The launchpad model has miners approving budgets and
calling compute providers. This programme specifies zero paid spend. Those are
different scopes and the line should be drawn explicitly before anyone needs a
rented instance to test goal 1.

**Miner artifact retention.** If a miner's run produces a checkpoint, what
happens to it - retained, discarded, theirs alone? Not urgent, but it is a
storage and privacy question nobody has answered, and the answer interacts with
P1.

---

## 7. What would change this policy

**P1 lapses** if Carbon accepts any miner-produced artifact without independent
reconstruction.

**P2 lapses** for a specific configuration when MQ-008 qualifies it, and only for
that configuration.

**P6 widens** only by an explicit owner decision to add a goal, not by a workload
appearing that seems to need it.

**P3, P4 and P5 do not lapse.** If they appear to block something necessary, the
thing being attempted is wrong, not the policy.
