# MOTOR-REF-UNCERTAINTY-01: a measured reference uncertainty for the motor (10p12s) Challenge

Status: DRAFT (Data Collection, 2026-10-13), for PR Head's batch.
Owner of the run: Data Collection. Method owner: Carbon Validator. Spend: owner figure.

## Why

PKT-13 / #1282 makes the motor L0 pilot HOLD (`REFERENCE_UNCERTAINTY_NOT_COVERED`)
until `reference.uncertainty_record` gives a positive, measured absolute bound for
each of the seven limit quantities, and every question's band covers it. No public
motor reference uncertainty exists. Motor is a launch Challenge, so the pilot stays
held until this lands. The HOLD is honest refusal, not an outage.

## Prerequisites (each can fail on its own)

1. **Method (Validator).** The motor analogue of the battery plating D2/D3 study
   (OWNER-PLATING-REFERENCE-01, VALIDATOR-PLATING-REF-V2-01/-02):
   - which of the seven limit quantities;
   - a stratified public case panel (proposed 10–20 cases, including near-limit ones);
   - a refinement ladder (mesh and any time-step or solver tolerance, at three or more levels);
   - the observed-order and residual rule that turns the ladder into a bound;
   - the stop triggers, pre-registered.
   Same rule as battery: a bound is re-derived, never kept by default, when its
   assumptions fail.
2. **The image on the pod path (Data Collection, verified 2026-10-13).**
   `carbon.agent_campaign.pod_jobs` accepts only `image: study | pytorch`
   (`pod_jobs.py:239`). Neither includes GetDP/Gmsh. The pinned motor reference
   image is `sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05`.
   The older EV4-era `scripts/dev/exam_design/runpod/pod_control.py` installs GetDP
   3.5.0 at runtime with a sha256 check (~:1027). One of two routes is needed:
   - (a) a `getdp` image option in pod_jobs, pinned to that digest, plus a no-spend `check`; or
   - (b) a pod_jobs phase that installs and verifies GetDP/Gmsh the way pod_control does.

   Either needs an MMS/analytic code-verification run on that image before use
   (OWNER code-verification rule).
3. **Sizing, then the owner's figure.**
   - First a single-case timing probe at each ladder level on one 8-vCPU cpu5m pod
     (well under USD 1).
   - Historical scale: about 1.2 CPU-h per sweep at the standard mesh (369.6 CPU-h
     for 308 sweeps). 2D FE refinement typically costs about 4–5× per halving.
   - A 10–20-case, three-level panel is therefore on the order of tens of USD on
     cpu5m. That's an order of magnitude only; the probe replaces it with a figure.
   - Memory per finest-level solve is unmeasured; size pods from the probe, not a guess.

## Deliverables

- A public evidence directory: cases, the ladder, records, per-quantity observed
  order and residual, the derived bounds, and the stop-trigger outcomes.
- `carbon.motor.reference-uncertainty.v1` records bound to the export, domain,
  image and observer, with all bounds > 0, and their sha256 receipts.
- A Validator acceptance record before any bound reaches a PUBLIC_DEVELOPMENT bundle.

## Not in scope

- Sealed/hidden motor material.
- Choosing limit bands (the bands must cover the bounds; picking them is not this ticket).
- Any LIVE claim.
