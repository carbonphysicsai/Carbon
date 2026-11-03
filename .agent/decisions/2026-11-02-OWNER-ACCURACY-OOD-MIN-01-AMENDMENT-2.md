# OWNER-ACCURACY-OOD-MIN-01, amendment 2: three cheap conditions replace the tuned-operator gate

Date: 2026-11-02 (CST), ~04:00
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722). It amends OWNER-ACCURACY-OOD-MIN-01 (497b5817) and its amendment 1 (c1f57f0a).
Owner's words: "Amend the accuracy-side rule: the strict min(in, out) applies to a version if (1) its registered fits/formula/engineer shortcut score poorly out of range, (2) the noise ceiling sits well above them, and (3) one default trained model beats them in range or the training set provably covers the out-of-range physics. The tuned-operator separation read becomes optional evidence, not a gate."

## Context
The owner asked whether proving that fits and formulas score poorly is a better test than being forced to find an operator that beats them. The Lead's view had three parts:
- The fit-failure check is the necessary one.
- It is not sufficient alone: an exam where everything scores badly (noisy references, or training data missing the needed physics) is indistinguishable from a good one.
- Miners will find stronger fits than the registered ones.
Motor 1.7's stage-1 separation read returned no verdict, because both contenders gate-failed once each.

## Decided
- The strict A = min(in, out) applies to a version when all three conditions hold:
  1. Its registered fits, formula and engineer shortcut score poorly out of range.
  2. The noise ceiling (the score a perfect model would get, given the reference uncertainty) sits well above them.
  3. One default trained model (no tuning search) beats them in range, or the training set provably covers the out-of-range physics.
- The tuned-operator separation read (S4a) becomes optional evidence, not a gate.
- **Not set by this record (owner values):** what "poorly" and "well above" mean numerically. Until registered, each version reports the measured gaps and the owner picks; nothing is invented.
- The noise pass on A = min(in, out) from amendment 1 still applies.
- Each version's checks are receipted by the Validator. Nothing already graded is rescored.
