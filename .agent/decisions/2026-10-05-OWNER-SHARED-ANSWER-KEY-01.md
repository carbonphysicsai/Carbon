## 2026-10-05 — OWNER-SHARED-ANSWER-KEY-01: validators share one answer key; every miner is tested on the same data

**Authority.** The owner, 2026-10-05, in the Carbon Validator session.

> we have to trust validators with the answer key. we have to test miners
> with the same data or it's not a fair exam and our data we get isn't
> analyzable casually

The owner, correcting two open points the session raised:

> we've already defined that there will be a rotation schedule that depends
> on reference cost and we've tested that GPUs of the same class have
> identical weights with the same recipes

**Supplements** OWNER-VALIDATOR-MAINNET-PARITY-01 item 3 ("every participant
is scored on the same conditions, with the same solver results"). The owner's
"casually" reads as "causally": results must support causal analysis.

1. **Validators are trusted with the answer key.** Every validator holds the
   identical hidden cases and their reference (solver) results. Carbon draws
   each batch from its root seed and solves the references once; no validator
   draws or solves its own.
2. **Every miner is tested on the same data.** Within a scoring window, every
   miner is scored on the identical active batch. Rotation follows the
   per-Challenge, reference-cost-based schedule already set
   (OWNER-VALIDATOR-MAINNET-PARITY-01 item 5).
3. **Rebuilds are identical across validators by construction.** Same-class
   GPUs produce bit-identical weights from the same recipe under the pinned
   determinism configuration (`docs/development/GPU_DETERMINISM_STAGE_B_RESULT.md`:
   two A40 hosts, one digest; unpinned runs diverge; CPU and GPU do not
   match).
   - So a validator's scored rebuilds run on the pinned GPU class, with the
     pinned determinism configuration and image.
   - A rebuild on any other class, or on CPU, is not a scored result.

**Kept from earlier records:**
- each batch is committed before use and revealed at retirement, so the exam
  stays auditable even though validators are trusted;
- hidden results are sealed from miners (rule v2);
- the confirmation set is one-shot.

**Not decided here:**
- the distribution mechanism, encryption and custody;
- the validator set and its admission;
- the mainnet netuid;
- security acceptance.

These are designed in VALIDATOR-18, and acceptance stays the owner's.

### The validator GPU (the owner, the same day)

> A40 for launch, add it to VALIDATOR-18 unless we get exciting results that
> require more in testing, Pytorch should be able to GPU rebuild too.

- **The launch validator part is the NVIDIA A40 (48 GB),** with the pinned
  determinism configuration. A larger part is considered only if testing
  produces results that need it. That would be a new record, with the
  determinism test re-run on that part at real model sizes.
- **PyTorch recipes rebuild on GPU too.** Today they are CPU-only
  (`torch_profile.py`). A PyTorch GPU build, with its own pinned determinism
  configuration, is in scope.
