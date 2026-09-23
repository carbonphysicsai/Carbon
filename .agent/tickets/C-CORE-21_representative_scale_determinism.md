# C-CORE-21: representative-scale GPU determinism

Status: authorized by owner direction of 2026-09-21 — "I authorize
representative-scale GPU determinism runs on this machine", followed by explicit
direction to widen the fixture before spending device time.
Base: `f2975761` on `main` (the C-CORE-20 merge), integrated with `1f4cb5e5`.
Primary Hub map_ref: `SYSTEM/AGENT-EXECUTION`; impact `map_structural`.
Dependencies: C-CORE-19 N3 (step-count widening), C-CORE-19 D2/D3 (the pinned
determinism configuration and its one-shape characterization).

The ID was verified free before it was claimed: no remote branch, no ticket file
and no reference on `main`.

## The gap this closes

Every determinism result Carbon held — the CPU instruction-set finding, the gate
margin figures and the D3 GPU characterization — was measured at **`width=8`,
`n_modes=8`, 4,696 parameters**, because the C-02 fixture could express no other
model. N3 had widened the *step count*; nothing had widened the *shape*.

Those are different dimensions and only one changes kernels. With
`--xla_gpu_autotune_level=0` pinned — which the validator determinism policy
requires — the kernel is fixed **per shape**. More steps run the same kernel more
times; a different width or mode count selects a **different fixed kernel whose
determinism had never been measured**.

So the policy's central claim had been tested on one kernel set.

## Scope

**Two parts, and the free one came first.**

1. **Device-free.** Widen the C-02 compile fixture to express `width` and
   `n_modes`, opt-in, with the default plan digest asserted unchanged — the same
   discipline N3 used for the step count. Define the target scale against
   Carbon's own registered material and write down the justification before
   running, so "representative" names a stated scale rather than "bigger".
2. **Authorized device time.** Re-run the D3 characterization at that target.

Running the second without the first would have exercised one kernel path more
often and answered almost nothing, and would have invited the same overclaim
retracted from the W3 and W5 packets.

## The target, and where it comes from

`width=32`, `n_modes=16`, 32 steps — **100,680 parameters**.

Not judgement: the registered catalog `carbon.burgers-autoresearch-recipes.v1`
gives width 2–128 default 24 and `n_modes` 2–64 default 16, and
`research_campaign.py` configures width 32 with 16 modes. The reconstruction
defaults of 8 and 8 sit below both. Recorded with its reasoning and its limits in
`docs/development/REPRESENTATIVE_SCALE_TARGET.md`.

## Not authorized by this ticket

Any rental, any paid call, any external provisioning, any change to `compare_r1`,
backend qualification, thresholds, gates, tolerances, scoring or rank logic, any
entry in `ESTABLISHED_OBSERVATION_CONTRACTS`, and the two-host study — which has
its own acceptance and its own ceiling.

The four-attempt strict batch is untouched and remains at zero consumed.

## Definition of done

- The fixture expresses model shape, opt-in, default digest unchanged, bounds
  and evenness enforced from the registered catalog rather than restated.
- The target is written down with its justification **before** the run.
- The characterization is run at that target with a baseline control that
  reproduces D3's pinned digest, so the comparison is attributable to the shape.
- The harness is committed and verified to reproduce from the repository, not
  left in a scratch directory.
- Documents whose recorded scope this widens are reconciled rather than left to
  imply the policy rests on less evidence than it does.

## Maturity, reported as distinct states

`SPECIFIED`, `IMPLEMENTED`, `TESTED` and — uniquely among the GPU tickets so far —
`HARDWARE_EXERCISED`, on one device, for this measurement only.

**Not** `SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED` or
`PRODUCTION_QUALIFIED`. `compare_r1` still returns `BACKEND_UNSUPPORTED` and
MQ-008 at G4 still owns backend qualification. A determinism property measured on
one device is evidence toward that decision and is not that decision.

## Kept separate

#242, #246, #251, #252. #248 merged during this work and is integrated normally.

## Stage B driver deviation and cross-pod enforcement (2026-09-23)

Approved by the owner on 2026-09-23 as the follow-up the stage B result named.
Stage B's hosts ran `580.159.03` and `580.159.04` against the acceptance's hard
driver-match check, which nothing enforced across pods. Amendment 9 to
`docs/development/TWO_HOST_STUDY_ACCEPTANCE.md` applies the deviation
retroactively (`docs/development/GPU_DETERMINISM_STAGE_B_DRIVER_DEVIATION.json`)
and `scripts/dev/gpu_determinism_study/compare_units.py` enforces the check
before and after a run; tests in `tests/cpu/test_study_compare_units.py` use the
published stage B pair as the specimen. No device time, no spend, nothing
qualified. Hub event `C-CORE-21-STAGE-AB-01`, the ticket's first per-event file.
