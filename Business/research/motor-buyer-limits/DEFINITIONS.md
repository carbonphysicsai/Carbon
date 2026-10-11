# Measurement crosswalk and contract seam

The immutable repository evidence reviewed is main `59fc17a74134afd5628771e462ac567bf79e9120`. These are prospective development documents, not proof of a physical motor or the latest panel's actual cutoff.

| Record | What it says | Interpretation |
|---|---|---|
| [Precision-joint v2](https://github.com/carbonphysicsai/Carbon/blob/59fc17a74134afd5628771e462ac567bf79e9120/docs/development/challenge_pipeline/round1/motor-precision-joint-v2.md), sections 1–2 | Holding mean ≥6 N·m; peak-command mean ≥12 N·m; energized pp ≤5% of mean AND ≤0.30 N·m holding / ≤0.60 N·m peak; zero-current cogging pp ≤0.05 N·m. Each constant's low/base/high is its listed value. | Mock direct-drive precision-assembly elbow. Requirements are owner-delegated role-play, not sourced OEM limits. Both relative and absolute ripple conditions apply. |
| [Motor round-2 question law](https://github.com/carbonphysicsai/Carbon/blob/59fc17a74134afd5628771e462ac567bf79e9120/docs/development/challenge_pipeline/question-laws/motor-round2.md) | 10p/12s, selected commands and three-slice skew. | Static electromagnetic geometry question; same geometry must meet the full conjunction. No borrowing different designs' separate passes. |
| [Historical development packet](https://github.com/carbonphysicsai/Carbon/blob/59fc17a74134afd5628771e462ac567bf79e9120/docs/development/MOTOR_DECISION_DESIGN_PACKET.md) | Different 8p/24s task, 0.30 fractional ripple. | Historical semantics must not be imported into the new precision-joint job. |
| Latest owner report in this task | Peak ≥12 N·m; holding pp fraction ≤0.30; unspecified cogging cap; 0/83 joint passes; pending 6-degree skew. Fixed OWNER_REPORT values, no remeasurement. | Literal fraction is 30%, not 0.30 N·m. Current manifest, numeric cogging cap and connection to v2 are HUMAN_INPUT. |

**Classification: NEW_OWNER_DECISION_REQUIRED for the active limit/definition seam.** Research can document the discrepancy but cannot resolve it by changing the packet or interpreting a looser number as authorization. The smallest next decision is Test Lead/owner confirmation of the active manifest, fraction-versus-absolute units and all three gates. Until then no changed-limit pass/qualification is claimed.

For a declared angular sweep and fixed current-command convention:

`Tpp = max(T(theta)) - min(T(theta))`

`rpp = Tpp / abs(mean(T(theta)))`

`rRMS = sqrt(mean((T(theta) - mean(T))**2)) / abs(mean(T))`

`rPositivePeak = (max(T(theta)) - mean(T)) / abs(mean(T))`

These are different measurements. For a **pure sinusoid with positive mean**, a mathematical illustration gives `rpp = 2*sqrt(2)*rRMS = 2*rPositivePeak`; it is not a conversion for arbitrary multi-harmonic, PWM or asymmetric waveforms. Fixed constants in this identity are mathematical, not estimated physical thresholds. [Mihic et al., equation 3](https://mdpi-res.com/d_attachment/machines/machines-10-00642/article_deploy/machines-10-00642.pdf) illustrates why checking the numerator matters.

Cogging at zero current uses **absolute pp N·m**, or a percentage of an independently established rated torque. Dividing by its near-zero mean is undefined/unhelpful. Never substitute a holding-command mean for continuous thermal rating. [Source S1](SOURCE_EVIDENCE.md) supplies an explicit pp convention; S2–S5 do not support every required normalization.

At a single settled rotor position, “holding ripple” is not a mechanical oscillation over a revolution. Carbon's static position sweep can quantify electromagnetic nonuniformity under its declared command law; it does not measure temporal PWM ripple, closed-loop position error, speed ripple, gearbox ripple or noise. Record whether phase angle tracks rotor electrical angle, the command frame, load, sweep coverage/resolution and statistic. Current density in the model is not automatically a catalog RMS phase current.

“Peak torque” here is mean torque across the sweep at the selected peak command, not the largest curve sample. A short-duty catalog peak requires a stated duration, cooling, ambient temperature, bus/current limits and thermal protection. [Kollmorgen's manual](https://www.kollmorgen.com/sites/default/files/2023-08/TBM2G_Installation-ge-en-it-sp-fr_0.pdf) supports this rating distinction. Carbon's static panel alone cannot certify continuous holding or safe overload duty.

No empirical low/base/high physical error band is available for this exact architecture. Angular refinement, mesh convergence, multi-slice adequacy, material uncertainty and physical calibration remain HUMAN_INPUT. Supplier typical figures cannot substitute for those errors.
