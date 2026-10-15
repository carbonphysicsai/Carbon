# MOTOR-PUBLIC-UNCERTAINTY-NONZERO-01

PKT-13 / PR1282 bounded review repair, starting at 29569f1ac64adfe6e5627ef7a151cbb9a8e9d57a.
IMPLEMENTATION_LAG: Carbon Validator's [review](https://github.com/carbonphysicsai/Carbon/pull/1282#issuecomment-6157083034)
and [PR Head direction](https://github.com/carbonphysicsai/Carbon/pull/1282#issuecomment-6157093369)
require positive supplied uncertainty in PUBLIC_DEVELOPMENT; zero remains
allowed only for the existing SYNTHETIC_FIXTURE scope. This prospectively
supersedes the previous decision's nonnegative rule for public inputs only.

REPAIR the existing uncertainty validator before any preparation uses the
record. Keep finite/type/unit/content/identity and band-coverage checks.
Reject public zero with REFERENCE_UNCERTAINTY_NOT_COVERED; do not add a
numerical floor, fill a missing value, register a receipt or qualify adequacy.
An arbitrarily small positive supplied value is not scientific acceptance.
The self-hash still identifies content only. Real values and their scientific
acceptance remain Data Collection/Validator inputs; physical execution holds.

Use public-shaped synthetic records only at the real isolated validation
boundary, with each quantity independently zeroed and the remaining quantities
positive, plus public positive/equality and complete fixture-zero contrasts.
These controls never execute a public dataset or promote synthetic inputs.
Reject fixture promotion as before. No solver, training, host, provider, grant,
protected data, LIVE or qualification action is authorized by this repair.

Alternative rejected: inventing a positive physical uncertainty floor or
accepting a zero bound because its own receipt hash matches. Reversal removes
the public-zero predicate and its controls, reopening the same review finding.
Change sites: motor_pilot.py, isolated tests, runbook and active ticket.
No public interface/schema change; keep bundle v2 and fixture behavior.
Root owns integration; no new owner value is needed for this stated rule.
