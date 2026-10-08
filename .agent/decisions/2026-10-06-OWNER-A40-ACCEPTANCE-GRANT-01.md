## 2026-10-06 — OWNER-A40-ACCEPTANCE-GRANT-01: a capped A40 acceptance run for the released validator image

**Authority.** The owner, 2026-10-06, in the Test Lead session. Answering the
Test Lead's proposal of the A40 acceptance run (USD 4.25 cap, or USD 2.22
with no replacements), the owner said:

> approve A40 grant

The owner also confirmed it directly in the Graphite Test executor session the
same day.

**Context.** The owner directed a mainnet-ready, released validator image,
built in CI from a main tag and pulled by digest, with JAX and PyTorch on CPU
and GPU ("I don't want to lose anything in this rebuild"). CI runners have no
GPU, so the GPU rows of that release stay UNVERIFIED until they run on the
owner's launch validator part, the NVIDIA A40 (OWNER-SHARED-ANSWER-KEY-01).

**Decision.**

| Field | Value |
|---|---|
| Purpose | Released-image A40 acceptance run only, per `docs/development/graphite/A40_ACCEPTANCE_BRIEF.md` |
| Platform | RunPod, A40 SECURE, 1 GPU per pod, through the operator layer (`operator_compute`), not Graphite |
| Pods | 2 concurrent, plus at most 2 replacements (one relaunch each, for a GPU-less host or a mismatched driver) |
| Rate ceiling | USD 0.492739726 per pod-hour (the EV4 pod tooling's `MAX_RATE` plus container disk) |
| Deadline per pod | 2.0 h |
| Worst case | 4 × 2.0 × 0.492739726 = USD 3.94 |
| Cleanup allowance | USD 0.25 |
| **Monetary cap** | **USD 4.25** |
| Runs | 1 |
| Model spend | none |

**Entry conditions.** The run launches only when all of these hold:
- this record is on main;
- the released validator image exists, pinned by sha256, carrying JAX and PyTorch on CPU and GPU;
- the released image includes the pinned PyTorch GPU determinism configuration (gap G1 in the brief);
- the recipe-selection rule in the brief's §2b is applied and recorded before any rebuild;
- the brief's §3 pre-run checks pass.

**Not decided here.**
- Any reproducibility tolerance: acceptance is digest equality, reported descriptively.
- Security acceptance of the released image.
- Any H100 or Blackwell class, or a larger part.

**No execution** happens through this record. Spend is booked privately, never
in the repository.

Community allowed per owner direction 2026-10-08

Vast.ai A40 allowed, owner-rented, per owner direction 2026-10-08

2026-10-08, owner: ceiling 0.65/h, cap USD 8

2026-10-08, owner: target device RTX 4090 (A40 unallocatable); ceiling and cap unchanged
