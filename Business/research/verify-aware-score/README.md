# VERIFY-AWARE-SCORE-01

Research contract: public-data, offline screen-then-verify scoring design.
No solver, model construction, training, spend, sealed material, AX42 access,
or runtime/packet edits are authorized. The owner adopts any scoring rule.

KEEP the published EV4/EV5 decision outcomes and their existing reference
bands. WRAP them in a prospectively labelled DEVELOPMENT analysis; never
rescore their historical verdicts. Every input is bound to an explicit public
Git blob. The public evidence identifies one selected action per member and
question, not the real members' full top-k prediction order. Missing orders
must remain NOT_IDENTIFIABLE; sensitivity bounds are not measured top-k value.

Deliver the score contract, measured one-verification diagnostics, sensitivity,
registry-candidate handoff and source manifest in this directory, in one PR to
PR Head. k, wall/core budgets, normalisation, gates and adoption are HUMAN_INPUT.
The exact-head handoff belongs on the PR, not in an evidence-only commit.

Start with the [one-page owner summary](OWNER_SUMMARY.md). The
[score and evidence design](DESIGN.md) contains the measured single-pick
results, honest top-k bounds and comparison limitations.
[candidates.json](candidates.json) is the prospective Test Engineer handoff;
[SOURCES.md](SOURCES.md) gives exact public inputs and reproduction commands.
[results.json](results.json) records all measured tables and sensitivities.

Validation: meaningful standalone research tests, deterministic input/output
hashes and the applicable GitHub acceptance. Native Windows computations are
diagnostics, not canonical runtime or scientific qualification. The Development
Hub is retired; this research does not alter its frozen artefacts.
