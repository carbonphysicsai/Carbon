# F13-SAVED-INTEGRAL-CHECK-01 — report accounting, not repaired truth

Agent engineering decision, owner-requested ticket of the same name.

Use a dependency-free, read-only CLI with a closed operator sidecar mapping
the seven quantities to exact one-based SaveScalars columns and names. Hash
the data, names and deck; require the complete expected frequency list and
explicit equal-port area/source/phasor basis. This avoids silently inheriting
the acquisition extractor's six-column ordering assumption. Hashes establish
file identity, not the truth of operator-supplied mesh/BC assertions.

Return per-row old and inlet-variance-accounted residuals and separate 1%
closure findings. Always keep physical reference status UNRESOLVED. Reject
negative variance beyond arithmetic roundoff; retain it in findings, never
clamp or renormalize. A Robin-only pass is a mixed-extraction finding, not a
green reference. Malformed input returns a bounded non-echoing error.

Rejected: automatic ambiguous column inference; changing acquisition code;
calling the solver; changing tolerance; claiming evanescent variance is
physical propagating power. Change path: script, saved-integral instructions
and tests in this PR. Reversal costs one independent tool; no runtime migration.
Notify science on #42 and PR Head/Validator on #643 at handoff. Physical
adequacy, verified input provenance and any new solve manifest remain reserved.
