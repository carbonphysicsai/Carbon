# Prospective limit sets for Test Lead and owner

**No option is adopted.** Numerical choices for Carbon stay HUMAN_INPUT. Existing thresholds are recorded for comparison, not changed. The public literature establishes plausible application targets and definitions; it does not prove the current design family jointly feasible.

| Option / intended decision | Proposed requirement form | Source-supported low / base / high | What is lost or required |
|---|---|---|---|
| O1 Preserve precision assembly; recommended working direction | Keep the declared holding/peak floors, relative AND absolute energized ripple, absolute zero-current cogging, envelope and duty. | Existing role-play values: mean hold ≥6 / ≥6 / ≥6 N·m; mean peak ≥12 / ≥12 / ≥12 N·m; rpp ≤0.05 / ≤0.05 / ≤0.05; holding pp ≤0.30 / ≤0.30 / ≤0.30 N·m, peak pp ≤0.60 / ≤0.60 / ≤0.60 N·m, cogging pp ≤0.05 / ≤0.05 / ≤0.05 N·m. [Committed packet](DEFINITIONS.md). | Values remain ASSUMPTION/owner-delegated mock requirements, not buyer-confirmed. Active manifest conflict must be resolved. Await the authorized skew/refinement evidence; no readiness inference from one peak result. |
| O2 A supplier-family direct-drive comparison, if owner chooses to restate the job | Preserve ≥12 N·m peak and all other job requirements; compare unpowered cogging to a chosen supplier family as `Tc * c`, with validated continuous rating Tc. | Guideline `c`: QTL 0.01 / 0.01 / 0.01; QTR 0.03 / 0.03 / 0.03. [S1](SOURCE_EVIDENCE.md). Carbon cutoff = HUMAN_INPUT. | This is a family-specific supplier comparison, not proof that a precision buyer tolerates it. Increasing absolute cogging could lose the assembly/backdrivability claim. Tc requires thermal evidence; adoption cannot be based on filling the feasible set. |
| O3 Rotating pump design, a separate future job | Use the pump's mean-load, speed, thermal and hydraulic requirements; research-supported loaded-ripple targets are starting comparators only. | Study ceilings: 5% / HUMAN_INPUT / 10%, from **different** studies S6 and S10, not a market range. Exact Carbon numerator, chosen ceiling, cogging cap and hold/peak floors all HUMAN_INPUT. | Dropping precision holding changes the engineering job. Pump pressure/flow pulsation and vibration need system evidence; static torque alone is insufficient. Does not authorize relaxing the current joint. |
| O4 E-bike drive, separate future job | Define torque at the motor shaft versus geared crank, current/speed map and comfort/NVH decision. | Achieved S7 ripple: about 12.8% / HUMAN_INPUT / 14.2%, unharmonized. A smaller result in S8 uses a different statistic. Carbon limits HUMAN_INPUT. | Achieved papers do not provide procurement ceilings. Gearing, cycling duty and control change the product; these figures cannot justify a 30% holding-ripple cap. |
| O5 Aerial propulsion, separate future job | Specify thrust/power/weight, speed, inverter and ripple convention; do not retain a joint-holding claim. | S9 comparison-study pp ceiling: ≤2% / ≤2% / ≤2%; Carbon limits and denominator HUMAN_INPUT. | Slotless architecture and controller requirements differ. The source gives no permission to claim “zero cogging” for Carbon's slotted motor or to relax joint limits. |

S2's advertised cogging ceiling is a useful servo comparator but not a directly usable option until its numerator/test definition is confirmed. S3's qualitative ripple boundary and S4's commutation examples support measuring the intended waveform; they do not supply a complete contract.

## Numerical sensitivity without silently adopting a limit

Diagnostic conversion only: **ASSUMPTION** independently established continuous rating `Tc` low/base/high = **4 / 6 / 8 N·m**. This is an illustrative range, not a thermal claim or estimate for the current motor. Applying S1's separate family guidelines gives:

| Diagnostic quantity | Low | Base | High | Basis |
|---|---:|---:|---:|---|
| Cogging pp at `c=0.01` | 0.04 N·m | 0.06 N·m | 0.08 N·m | DERIVED `Tc*c`; Tc ASSUMPTION |
| Cogging pp at `c=0.03` | 0.12 N·m | 0.18 N·m | 0.24 N·m | DERIVED `Tc*c`; Tc ASSUMPTION |
| Existing 0.05 N·m cap as % Tc, increasing order | 0.625% | 0.8333% | 1.25% | DERIVED `100*0.05/Tc`; high Tc gives low percentage |

The first two rows are not proposed automatic relaxations. A comparison requires the same current state and waveform statistic, and evidence that the chosen application tolerates the resulting disturbance. No range here represents buyer willingness to accept it.

For the reported 6-degree skew, geometric smoothing can reduce harmonics while reducing mean torque. A purely illustrative three-equal-slice fundamental factor is `(1 + 2*cos(p*s/2))/3`; using the source family's pole-pair count `p=5` and mechanical spread `s=6 degrees` gives **0.97728 / 0.97728 / 0.97728**, about **2.272% / 2.272% / 2.272%** fundamental reduction (DERIVED, ASSUMPTION: identical shifted sinusoidal slices). This is not a prediction of the nonlinear solved torque or a feasible-design claim. The [committed question law](https://github.com/carbonphysicsai/Carbon/blob/59fc17a74134afd5628771e462ac567bf79e9120/docs/development/challenge_pipeline/question-laws/motor-round2.md) owns the slice convention. Manufacturing, end effects and harmonic-specific cancellation require evidence. S9 explains the general skew/mean-torque trade-off; S10 shows why physical cogging can exceed a calculation.

## Public-only next evidence record

The Test Lead's next record should identify the exact active limit manifest and metric formulas, then report each gate and their conjunction for **each geometry**, at the same declared holding/peak commands. Include the zero-current curve; angle/mesh refinements; skew mechanical/electrical convention; mean torque lost; and worst-case margins with unresolved numerical/model uncertainty marked explicitly. Research has not run or inspected these panels.

Retain joint failures as adverse findings. Evaluate feasibility under the registered contract first. If no feasible set remains, the owner may authorize an architecture/envelope/job revision with sourced buyer logic and prospective versioning, or hold the Challenge. Changing a precision joint into a pump/drone job must change its value claim and evidence plan. No source-confirmed basis was found for an after-the-fact relaxation solely to obtain passing designs.
