# Work package: the most deterministic GPU reconstruction achievable, as validator policy

Owner direction, 20 September 2026: *test and solve for the most deterministic
way possible to run fair training (reconstruction) runs on GPUs, and make that
the validator policy.*

Authority is `docs/development/GPU_EXECUTION_LANES.md`,
`GPU_INITIAL_POLICY.md`, `GPU_PROGRAMME_PLAN_CORRECTION.md` and
`GPU_COMPLETION_WORK_PACKAGE.md` on `agent/gpu-execution-lane-design` (PR #248).
Fetch that branch first.

---

## What changed, and why this supersedes the last package

W3 measured cross-host divergence on **CPU**: the same strategy under identical
R0 identities produces different weights at different instruction-set levels, and
every identity Carbon records is the same across all three. That finding stands.

What it did not account for is that production reconstruction will run on **GPU**,
where every divergence source CPU has is present and more are added: autotuning
selects kernels per device and sometimes per run, SM count changes reduction
splits, atomics have no fixed order, and TF32 silently drops mantissa bits on
matmuls from Ampere onward.

The consequence is sharper than anything W3 found. **On an unpinned GPU a
validator may not reproduce its own run** - same host, same seed, same plan. R1
asks whether a repeat execution reproduces the numerical results, and the honest
answer on an unpinned GPU is no. No tolerance rescues that, and choosing one to
make GPU pass is what MQ-008 explicitly rejects.

So pinned determinism is not an improvement to make later. **It is a
precondition for a GPU profile ever qualifying**, and `worker_environment`
currently pins none of it - no `XLA_FLAGS`, no TF32 control, no autotune policy.

Two consequences for the earlier package:

- **The QEMU AVX-512 experiment is demoted.** It answers an x86-CPU-specific
  question. Keep it only as a footnote to the CPU exam environment.
- **The local GPU becomes the right instrument for one specific question**,
  which the W6 withdrawal did not cover. See D3.

---

## D1. Record what determines numerics

`observed_environment` captures backend, library versions, `machine: x86_64`,
Python and `x64`. It does not capture the CPU feature level, `XLA_FLAGS`, or any
GPU attribute. Two runs that compute different weights are indistinguishable in
the record.

Extend it to carry what actually determines the result. On GPU that is at least
the device model, driver version, CUDA and cuDNN versions, the TF32 setting, the
autotuning policy and any deterministic-execution flag. On CPU, the effective
instruction-set level and `XLA_FLAGS`.

Free, constrains no validator, and every later question is unanswerable without
it. **Do this first.**

Treat the digest change deliberately: recording new fields changes
`observed_environment_digest` for everything produced afterward. Say so, and say
what it means for records already accepted.

## D2. Establish the achievable determinism configuration

Research what the **pinned jaxlib and XLA versions actually provide** - do not
assume flag names from memory, and do not carry over a flag that a newer or older
build spells differently. Verify each one against the pinned build, and record
which were tried and rejected as well as which were kept.

The configuration should address, at minimum: deterministic kernel selection,
autotuning (disable or pin its results), TF32 on matmuls and convolutions,
reduction determinism, and any cuBLAS workspace setting the build honours.

Pin the resulting set in `worker_environment` for the GPU profile, the same way
the CPU lane's environment is pinned. Record the throughput cost - it is the real
trade and SCI should see the number rather than be told it is small.

## D3. Test it on the device that is here

This is a change from the previous package, and the reasoning is narrow enough
to state exactly.

The W6 withdrawal was right that a laptop GPU under WSL2 **qualifies nothing**
and verifies nothing about the launchpad, and that remains true. But the
question here is different in kind:

> Do the determinism settings work at all - does pinning them turn divergent
> repeats into identical ones?

That is a question about whether the CUDA and XLA machinery honours the settings,
not a claim about any device. If deterministic execution holds on this device it
is evidence the configuration functions; if repeats still diverge with everything
pinned, that is a finding about the settings and it transfers.

Two conditions, and the second is the one that matters:

1. **Unpinned repeats** on the same device, identical R0 identities. Establishes
   whether the problem is real here.
2. **Pinned repeats** under the D2 configuration. Establishes whether the fix
   works.

**Design this to consume as few attempts as possible.** Prefer repeats *within*
a single admission over one admission per repeat, if the envelope permits it -
work out whether it does before proposing a count. Four attempts cover failures
and retries too, and they do not come back.

**Report the proposed attempt count and the exact plan, then stop.** The owner
decides whether to spend. P7's gate is that an evidence specification exists and
the MQ-008 owners accept it; W2 drafted the specification, but drafting is not
acceptance, and this test is a determinism check rather than qualification
evidence - say which of the two you are asking to spend on.

## D4. Write the validator policy

The deliverable the owner asked for. It states the configuration a validator runs
GPU reconstruction under, and it must be honest about its own reach:

- **What pinned determinism delivers.** Whatever D3 measured - most plausibly
  same-device reproducibility.
- **What it does not.** Different GPU models will still produce different
  weights, and no setting changes that. Do not imply otherwise.
- **What that means for fairness.** Two validators on different devices compute
  different weights. The continuous score legs absorb that proportionally. A
  mandatory hard gate does not - it flips, and the submission goes from scored to
  `MANDATORY_GATE_FAILED`.
- **Provider freedom is preserved.** D3 gives validators their choice of
  provider, and the policy constrains the configuration, not where it runs.

Declare and disclose. Do not qualify anything, and do not set a tolerance.

## D5. Not yours to decide: gate robustness

Residual cross-device divergence meets the scoring gates, and that is where it
becomes unfairness rather than noise. The options - mandated margins relative to
measured divergence, or determining gate admissibility once from a reference run
or consensus median rather than per validator - are a protocol and scientific
decision for the owner and SCI.

**Write up the options and the trade-offs. Implement none of them.**

---

## Rules that do not bend

1. **Exact stays exact.** R0 identities, schemas, provenance and artifact byte
   integrity. Only repeat-execution numerics admit a registered tolerance.
2. **Never choose a tolerance** to make a device pass. If pinned determinism is
   not enough, that is a finding, not a licence to pick an epsilon.
3. **Never relabel B as A.** A fresh reconstruction is its own artifact.
4. **Protected material stays off this path**, with the invariant test holding.
5. **Do not build on the strict host apparatus.** Leave it; do not remove it.
6. Do not edit a worktree while a suite runs against it.
7. Zero paid spend. Nothing here requires renting anything.
