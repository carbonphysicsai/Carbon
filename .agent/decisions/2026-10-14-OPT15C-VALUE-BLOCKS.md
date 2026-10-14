# OPT-15c section E: synthetic value-block resampling

Authority: OPT-15-SCORE-LAB-01, the owner's experiment plan section 2E
(3-30 blocks), and Test Lead selection of the next existing synthetic gap.
DEVELOPMENT only. This does not register physical independent draw units,
production reference policy, a confidence threshold or scoring coefficients.

Add an opt-in `value_blocks` specification to the existing core.analyze API.
Require an explicit ASSUMPTION label, complete partition of the synthetic value
questions into 3-30 equal-size named blocks and an explicit missing policy.
Do not infer blocks from IDs or treat real data as synthetic. Public panels
refuse this option. No new CLI or dependency and no changes to registered rules.

Equal-size block means preserve the uniform-case point estimand while enabling
the unchanged score_proof crossed recipe/question bootstrap to resample blocks.
The question dimension of its loss matrix is now the number of retained blocks.
Return original-question counts separately from resampling-unit counts; keep
input/spec/analysis identities and the conditional block estimand explicit.
Supplied block independence is an assumption, not established by the software.

REQUIRE_COMPLETE returns an unscored measurement on any incomplete block.
EXCLUDE_COMPLETE_BLOCKS removes each incomplete block for every member/control,
including otherwise resolved questions in that block. Report those additional
exclusions. Fewer than the plan's three complete blocks stays unscored, not a
candidate penalty or evidence of statistical adequacy at three blocks.

Keep score-side inputs/metadata, gates and score formulas unchanged. Reuse core
analysis on a copied block view; optional missing exact-oracle data retains the
existing best-member regret interpretation. No block accounting enters scorer
metadata. Without the option all old behavior remains unchanged.

Implement focused synthetic controls including an actual bootstrap-input spy,
point-mean parity, malformed/unequal/partial partitions, missing-block positive
and no-scorer negative controls, public refusal and input nonmutation. No new
experiment, real fitting, holdout access, full sweep, solver, rebuild or spend.
Root owns final review, CI and merge. Other A/E/G gaps remain explicit.
