# Development plan correction: aligning GPU execution with the recovered roadmap

**Status: proposal.** It authorizes nothing, qualifies no hardware, sets no
tolerance and changes no allowance. It corrects three drifts between recent GPU
work and the owner's recorded direction, and states the sequence that follows.

Source: *Carbon Recovered Roadmap and Owner Decisions*, 20 September 2026 - a
recovered working copy, whose own caveat applies: an owner direction describes
desired behaviour and does not establish implemented code, passed acceptance or
production qualification.

---

## 1. The direction being aligned to

The roadmap's core-execution statement:

> Make GPU computation usable for **miner research and validator
> reconstruction**. Preserve provider freedom, **establish the validator's
> prescribed exam environment**, and build reusable execution infrastructure
> rather than a permanent laptop-specific implementation.

Three owner answers carry most of the weight:

- **D3.** *"I want carbon to be provider agnostic... a miner **or validator**
  should be able to use whatever provider they want."*
- **D9.** *"I want full GPU support tested... no matter what the results people
  will use GPUs to mine and validate Carbon."*
- **G4.** *"This is not needed. We define the validators compute requirements.
  Since the miner is only submitting a design, it doesn't matter what they used
  to get to it. **The miner should just know what the validator is going to use
  for the exam.**"*

---

## 2. Actual programme state

Verified against `origin/main`, not assumed:

| Ticket | State |
| --- | --- |
| C-CORE-01 … 14, 17 | **merged** - backend discovery, CPU science, accelerators, Workbench studies, update chunks, portable state, Julia research, operating envelope, TPU preparation, MCP tasks/apps/material, public GPU diagnostic, telemetry capability |
| C-CORE-15 | **paused**, unpublished, preserved at `3f3eec3b` |
| C-CORE-18 | open - PR #247 |
| C-CORE-19 | open - PR #249 |

This matters for sequencing. The roadmap's *"finish the required JAX and native
Julia workflows and their Workbench and Miner Launchpad/MCP consumers"* is
substantially **already merged**, not pending. The open work is the GPU lane
thread and whether those merged consumers still hold under it.

---

## 3. Three corrections

### C1. Restore the exam-environment disclosure requirement

`GPU_EXECUTION_LANES.md` justified the miner lane on the launchpad renting
arbitrary hardware. That is correct and is the requirement driver. But an earlier
revision had justified it on "fidelity", and removing that went too far.

G4 says miner hardware is unconstrained **and** that *"the miner should just know
what the validator is going to use for the exam."* That is a **disclosure
obligation on Carbon**, not a constraint on miner hardware. Both hold:

- Miner hardware: unconstrained. Permissive lane stands.
- Carbon: must publish the validator exam environment so miners can see it.

**Applied.** `GPU_EXECUTION_LANES.md` section 3 now carries the disclosure
obligation as a named requirement, distinct from any execution constraint.

### C2. Validator provider freedom

Earlier reasoning drifted toward "validator hosts should be dedicated Linux
machines." D3 says the opposite, explicitly including validators.

This resolves cleanly and improves the design: **MQ-008 qualifies a backend
profile, not a provider or a host.** Any provider offering a qualified profile is
usable. Qualification attaches to the profile; provider choice stays free.

**Applied.** `GPU_EXECUTION_LANES.md` section 3 now states that qualification
attaches to the backend profile, that no provider or host ownership model is
prescribed, and that a contention finding would constrain run conditions rather
than provider choice. The section 8 owner table is corrected to match.

### C3. "Establish the validator's prescribed exam environment" is a deliverable

Neither document captures it. It is a distinct work item: Carbon **defines** the
prescribed exam environment and **publishes** it in a form miners can consult.

It is also the thing C1's disclosure obligation discloses, so the two are one
deliverable with two halves - define, then expose.

**Applied.** Named in `GPU_EXECUTION_LANES.md` section 3 as two deliverables,
define then publish, and placed at stage 2 of the sequence below.

---

## 4. Corrected sequence

### Stage 1 - finish the GPU lane thread *(in progress)*

1. Land C-CORE-18 (#247) and C-CORE-19 (#249).
2. **CPU determinism baseline.** Same registered strategy twice on CPU under
   identical R0 identities; record whether outputs are bit-identical. No GPU
   attempt, no spend, no authority needed. Answers whether the workload is
   deterministic at all, which conditions everything downstream.
3. **The successful result path to `ASSOCIATED`.** The one genuine unknown. D9
   requires a real end-to-end test; a device listing, package install or image
   build does not satisfy it.
4. **Protected-material invariant test** - the three structural facts that keep
   held-out material off the GPU path. H14: *"we have to protect exam leakage at
   all costs and swap exams if detected."*
5. Full acceptance against a fixed, unedited revision. Then the matching image.

### Stage 2 - the prescribed exam environment

6. **Define** the validator's prescribed exam environment: which backend
   profile, pinned versions, precision and allocator policy, resource envelope.
7. **Publish** it where miners can consult it, satisfying G4.

This is independent of MQ-008. Defining and disclosing the environment does not
require qualifying it.

### Stage 3 - confirm the merged consumers still hold

8. Verify that the already-merged consumers - C-CORE-14's public GPU diagnostic,
   the Workbench studies, the MCP surfaces, the Julia services - still work under
   the portable profile and lane model. They were built against the
   pre-portability GPU contract.
9. Deliver the *tested representative workflow* the roadmap names as the
   prerequisite, rather than every possible Julia/GPU combination.

### Stage 4 - miner reach *(needs one decision)*

10. Start the worker on a rented instance from a Bittensor-native provider. D3
    names chutes, lium and engy as preferred cheap options, explicitly not an
    exclusive-provider rule.
11. This requires a bounded test budget. See §5.

### Stage 5 - MQ-008 evidence *(needs the specification first)*

12. Draft the evidence specification for SCI + SRE to accept: which quantities,
    how many repeats per backend, what constitutes adequate evidence.
13. Two-attempt shakedown within existing authority.
14. Size the real campaign from what it teaches.

### Stage 6 - optimization *(deferred, #244)*

Unchanged and still after the core integrations. D5 asked for an optimally
efficient setup, *"kernels and everything"*; the roadmap sequences the dedicated
programme after this work. Ordinary correctness and necessary efficiency fixes
remain in scope throughout.

---

## 5. Decisions owed

| Decision | Blocks | Recommendation |
| --- | --- | --- |
| Bounded test budget for launchpad verification | Stage 4, the highest-value stage | Authorize a small named budget. Goal 1 cannot be verified without renting hardware. D4 records a $20 GPU figure treated as a separate allowance; confirm whether that applies. |
| Batch sizing | Stage 5 | Spend two within existing authority as a shakedown; size the campaign from the result. Do not squeeze a measurement study into four. |
| Miner artifact retention | Not blocking | Retain the run receipt, never the artifact. Makes the miner-lane policy structurally true rather than policy-true. |

---

## 6. Open questions the roadmap records and does not resolve

- **G9**: *"Yes but that doesn't seem optimal for our reconstruction
  environment."* The objection's subject was not recovered. It concerns the
  reconstruction environment and should be recovered from the original chat
  export before anyone assumes it is satisfied.
- **H8**: whether Carbon mining may be used purely as a research platform
  without participating. Unresolved policy, delegated to Ryan and Nick with
  counsel (I16).
- The paid-spend boundary between the launchpad product, which has miners
  approving provider budgets, and this programme's zero-spend constraint.

---

## 7. What this does not do

It does not qualify hardware, register a telemetry contract, create a grant,
authorize an attempt, set a tolerance, renew the $20 figure, or change what
evaluation accepts. It does not treat the recovered roadmap as repository
authority: current code, specifications, Build_Out and the delivery protocol
remain controlling where they conflict.
