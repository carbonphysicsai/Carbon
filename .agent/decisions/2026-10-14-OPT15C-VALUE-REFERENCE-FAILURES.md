# OPT-15c section E: synthetic value-reference availability

Authority: OPT-15-SCORE-LAB-01, owner experiment plan section 2E and the
2026-10-14 Test Lead direction to finish one existing synthetic gap. DEVELOPMENT
only. This is not a new reference, scientific gate or production failure policy.

Implement optional value-side outages on synthetic panels. The caller must
supply the fraction within the plan's 0-5% range, a synthetic seed and one of
REQUIRE_COMPLETE or EXCLUDE_COMMON. No adopted defaults. Whole value questions
are selected by a keyed hash, independent of model order, predictions and losses.
The count is floor(fraction * offered questions); report both requested and
realized fractions so small panels cannot pretend to have measured 5% outages.

REQUIRE_COMPLETE leaves the entire measurement unscored if any value question
is unresolved. EXCLUDE_COMMON reuses core.analyze on the common resolved mask
across all panel members, including controls. Existing unresolved outcomes are
reported separately from injected outages; no missing outcome becomes a
candidate failure, zero loss or a model-specific denominator. Exclusion changes
the estimand to conditional-on-common-resolved; no recovery of the population
estimand or independent power is claimed.

Keep scoring predictions, scoring references, metadata, candidate gates and
score formulas unchanged. Value mask identities/accounting never enter the
score callback. The CLI option exists only on synthetic, not public replay;
the library also refuses PUBLIC_DEVELOPMENT panels. Inputs are copied rather
than rewritten. Historical artifacts, reference labels and hidden/holdout
custody remain unchanged. Score-side failures, P/Q/w design, large question
banks, block studies and competition remain outside this bounded slice.

Reuse the unchanged canonical Score Lab regression as baseline; add focused
parity, partial/common/strict failure, nonmutation, malformed-input and CLI
controls. Finish one coherent implementation PR to main; Root owns CI/merge.
