## 2026-10-15 — F02-SCIENCE-VALUES-01: f02 reference-path and bank values (DEVELOPMENT)

**Authority.** OWNER-SOLVER-READINESS-SCIENCE-DELEGATION-01 (2026-10-15). These
are DEVELOPMENT values for the f02 burst-thermal reference path and its public
bank. They grant no qualification, Tier 2/3 claim, LIVE status, reward or
spend. Hidden and sealed material is untouched. The owner may change any value
by a later record. Values are prospective; sealed evidence keeps its contract
(the 8bcd864d triage, the 6fab746f MMS acceptance and the f02 controls keep
their records).

**Buyer and what flips the decision** (packet `round1/f02-burst-thermal.md`
§1, §5, §6; `question-laws/f02-round2.md` §1–§5). A thermal architect picks a
burst (peak W, on-time s) for a known cooling/initial/split/waveform context to
maximise extra joules above 20 W while the top-die spatial/temporal maximum
stays at or below a ceiling of at most 95 °C over 120 s. The decision flips
when an action's peak is mis-stated across the ceiling. Adjacent seed-menu
actions differ by about 0.9 °C per watt and several °C per 5 s step
(cool-rect-low 80 W/5 s peaks at 90.8 °C, 110 W/10 s at 119.4 °C: triage on
8bcd864d), so a numerical error that stays well under 1 °C cannot reorder
actions that are a menu step apart; only actions within about 1 °C of the
ceiling are decision-sensitive. Energy is the declared waveform integral, an
exact input, not a solver output.

Section A–D values were set **before** the local-image runs they judge
(commit order on this branch is the record). Section E was set **after** the
local-image menu sample; the record says what was observed.

### A. Rebuild acceptance (a locked package rebuilt on another host)

Docker builds are not byte-reproducible, so a rebuild from the same lock gets a
new image ID. OWNER-CODE-VERIFICATION-ACCEPT-01 says a rebuild needs a new run
and a new acceptance. Mechanical criteria (all must hold):

| Value | Slot | Chosen | Basis | Observed first? |
|---|---|---|---|---|
| A1 provenance | `evidence/reference-packages-01/elmer.json:local_rebuilds[].provenance` | built by `build.sh` from `sources.lock.json` (archive sha256 verified), repo `Dockerfile` byte-identical, runtime package list identical to the recorded list, build package count identical | same inputs are the precondition for treating the result as the same package | no |
| A2 upstream smoke | `...local_rebuilds[].smoke` | all three `smoke.sh` tests exit 0 with `TEST.PASSED = 1` | ElmerSolver's own reference-norm check, as for 8bcd864d | no |
| A3 code verification | `...local_rebuilds[].mms` | `mms_heat.py` (t_end 0.375): finest-pair observed order, max and RMS, space and time, each in [1.7, 2.3] | the owner-accepted band (OWNER-CODE-VERIFICATION-ACCEPT-01) | no |
| A4 controls | `...local_rebuilds[].controls` | packet bands: equilibrium drift ≤ 0.05 °C; slab step/pulse error ≤ max(0.25 °C, 1 % of rise); energy residual ≤ 1 % | packet §5 (adopted unchanged) | no (old-image results exist; the bands are the packet's) |
| A5 lineage reproduction | `...local_rebuilds[].lineage` | on decks byte-identical (case.sif + mesh) to decks solved on an earlier image: \|Δ peak\| ≤ 0.01 °C, \|Δ first-95 °C crossing\| ≤ 0.01 s, \|Δ control error\| ≤ 0.01 °C, \|Δ energy residual\| ≤ 1e-4 | same source/compiler/packages reproduce to solver tolerance (CG 1e-12); 0.01 °C is 1/50 of the 0.5 °C refinement band, so no verdict outside the 1 °C unresolved band can change | no |

Verdicts: A1–A4 pass → `ACCEPTED_FOR_DEVELOPMENT` (the rebuild may produce
new DEVELOPMENT evidence bound to its own ID). A5 also passing →
`EQUIVALENT_TO_PRIOR_LINEAGE` (earlier 8bcd864d/6fab746f results may be cited
next to it, each under its own ID). Any miss is a finding, never loosened. This
is engineering acceptance under the delegation; it does not rewrite or extend
the owner's 6fab746f code-verification acceptance.

### B. Numerical verification and convergence (per case, per rung)

Rungs: primary (mesh 1, dt 1), mesh × 2 (every cell halved, dt 1), dt / 2
(mesh 1, every step halved). Each rung is compared with the primary separately.

| Value | Slot | Chosen | Basis | Observed first? |
|---|---|---|---|---|
| B1 peak band | `question-laws/f02-round2.json:t2a.thermal_band_registered`; bands JSON | \|Δ top-die spatial/temporal peak\| ≤ 0.5 °C | packet §5, adopted: half the 1 °C decision-unresolved band, so a primary more than 1 °C from a ceiling cannot change side at an accepted rung | old image only (0.005–0.009 °C mesh, < 0.001 °C time) |
| B2 crossing band | bands JSON | \|Δ first 95 °C crossing\| ≤ 0.5 s; crossing at one rung only → UNRESOLVED | packet §5, adopted | old image only |
| B3 recovery band | bands JSON | \|Δ recovery time\| ≤ 0.5 s (within 1 °C of the steady 20 W baseline after the last event); one-rung-only → UNRESOLVED | packet §5/§6 cross-tool value applied to rungs, so the recovery observable is held to the same resolution | no |
| B4 label-curve band | bands JSON | max over 0.5 s samples \|Δ T_topmax(t)\| ≤ 0.5 °C | TRAIN labels are these curves (train-registry); packet's cross-tool curve value applied to rungs | no |
| B5 conservation | bands JSON | every primary and rung: \|(heat in − stored − Robin out)/heat in\| ≤ 1 % over 120 s | packet §5 energy control, now bound to every case family, not only the control | no |
| B6 steady baseline | bands JSON | direct solver (UMFPACK); \|(P − ∮h(T−T_c)dA)/P\| ≤ 1e-3 | a steady solve has no mass term; CG failed on it on 8bcd864d; the balance is exact to quadrature, so 0.1 % catches a wrong BC | no |
| B7 baseline consistency | bands JSON | \|T_topmax(120 s) of the 20 W transient baseline − steady top-die max\| ≤ 0.5 °C (same cooling/split) | recovery is measured against the steady value; the copper Robin time constant (ρc_pL/h ≈ 2.8–4.6 s) makes 120 s ample | no |
| B8 decision-unresolved band | bands JSON; `t2a` | a primary with peak within 1.0 °C of any ceiling in the law's support ([90, 95] °C), i.e. peak in [89.0, 96.0] °C, must have both rungs; verdict at ceiling c is PASS only if every rung ≤ c, FAIL only if every rung > c, else UNRESOLVED; a missing or out-of-band rung → UNRESOLVED | packet's 1 °C unresolved edge, extended from 95 °C to every ceiling the law can draw | no |
| B9 bank refinement policy | bands JSON; sizing note | refine every B8 contender (both rungs) plus an audit sample: one seeded primary per context (24) at both rungs | contenders are the only decision-sensitive cases; the audit keeps the B1–B5 evidence case-family-bound across all 24 contexts, not only the 8 triage cases | no |
| B10 family acceptance | bands JSON | the route (mesh 1, dt 1) is `ACCEPTED_FOR_DEVELOPMENT_BANK` when all 8 triage primaries pass B1–B5 at both rungs and all 4 steady baselines pass B6–B7; any miss is a finding and the route stays at its last accepted state | the 8 primaries span both cooling pairs, both initial states, both splits and all three waveforms | no |

### C. Cross-tool (Tier 2) and reduced routes

| Value | Slot | Chosen | Basis | Observed first? |
|---|---|---|---|---|
| C1 curve/peak | `round1/reference-route-panels.json:families.f02.registered_values` | ≤ 0.5 °C max curve and peak difference | packet §5 recommendation, adopted | no |
| C2 events | same | first-95 °C crossing and recovery ≤ 0.5 s; one-tool-only → UNRESOLVED | packet §5, adopted | no |
| C3 energy | same | integrated energy imbalance ≤ 1 % | packet §5, adopted | no |
| C4 decision agreement | same | 100 % verdict agreement on matched actions resolved outside the 1 °C band; identical argmax-J pick per matched context/ceiling; J-regret 0 J | a buyer cannot accept a reference that flips a resolved verdict; within-band cases are UNRESOLVED by B8 | no |
| C5 reduced routes | same | RC/POD screen stays SCREENING_ONLY; no reduced-vs-full tolerance is set because no reduced route is a truth route | reference-routes.md rank 1 | no |

### D. Value-check (T2a and checks A–D) thresholds

| Value | Slot | Chosen | Basis | Observed first? |
|---|---|---|---|---|
| D1 thermal truth band b_T | `f02-round2.json:t2a.thermal_band_registered` | 0.5 °C (= B1) | the rung agreement the reference is held to | no |
| D2 near window | `t2a` | a resolved action counts as near when its peak is within 2·b_T = 1.0 °C of the ceiling (feasible side ≤ c, infeasible side > c) | Test Lead's "two refinement bands" and the menu registry's 1 °C; never widened | no |
| D3 minimum each side | `t2a.minimum_each_side` | 5 distinct actions (distinct (peak W, on-time s)) | Test Lead working value, adopted | no |
| D4 energy band b_E | `t2a.energy_band_registered` | 0 J: energy is the exact declared integral ((P−20)·D; half for the ramp); a floor is met iff J ≥ floor | the md forbids a fabricated energy band; solver delivery is gated by B5 | no |
| D5 spread (check B) | `f02-round2.json:value_check_thresholds` | ≥ 100 J between the best and worst admissible action per live stratum | value-check-v1 recommendation (packet's low value increment), adopted | no |
| D6 answer changes (check D) | same | expected distinct winners per k-window ≥ 3 under P (sum_j [1−(1−p_j)^k]) and the winner changes with the ceiling in ≥ 1 live context | k = 8 windows must not be one repeated answer | no |
| D7 tie rule | `f02-round2.json:tie_rule` | max J; then lower resolved peak; then fixed bank order | f02-round2.md §3 recommendation, adopted | no |

### E. Question law and bank (set after the local menu sample)

See the section appended below once the sample is solved.
