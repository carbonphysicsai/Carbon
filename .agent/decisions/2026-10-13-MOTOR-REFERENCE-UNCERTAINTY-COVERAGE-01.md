## 2026-10-13 - MOTOR-REFERENCE-UNCERTAINTY-COVERAGE-01: fail closed on uncovered reference uncertainty

PKT-13 / PR #1282 review repair at base 2f561cbd3. Carbon Validator's
comment 6153491526 requires each buyer limit band to cover its quantity's
stated reference uncertainty; missing motor uncertainty remains HOLD.
Data Collection's three operational repairs are included in the same push.

Use an embedded, content-pinned uncertainty record in the retained reference
document, bound to the same export, domain, observer and image. Require all
limit quantities with finite nonnegative bounds and matching units. Require
every question's limit band >= its supplied bound. The worker defines no
physical value and never fills a default. Bump the input bundle to v2 so
older v1 bundles are refused instead of reinterpreted. The fixture states
zero synthetic uncertainty explicitly; it cannot supply public uncertainty.
A digest identifies content and does not qualify its scientific adequacy.

Keep seven source files and the current fit/CPU/memory/lifecycle/spend caps.
Make flavor and vCPUs required operator inputs, validated by the existing
CPU placement/launcher contract. Catch the per-fit SIGXCPU soft limit as
PilotHold, restore the handler and retain the hard CPU cap. Document the
possibility of external hard-limit kills separately from that caught soft
limit. Clarify that 64h/32-vCPU/USD77.20 is the acquisition scenario, not a
measurement or prescription for this retained-data worker.

Changes: motor worker, fixture, tests, runbook and active ticket. Reversal
restores bundle v1 and old validation/operational behavior; that would reopen
the review blocker. No public motor uncertainty, physics adequacy, real fit
time, grant or quote is invented. Data Collection/Validator must provide and
accept their actual inputs; Root Test Lead owns engineering merge.
