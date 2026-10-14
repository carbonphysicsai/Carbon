# OPT-15c component subsets: prospective Goodhart tranche

Authority: existing OPT-15c experiment plan sections 2F, 3, 4 and 6; Root's
direction to continue authorized synthetic controls/Goodhart work while gates
wait. DEVELOPMENT only; no new ticket, scientific values or rule adoption.

Compare baseline `component_spec=None` with all 15 nonempty subsets of the
four existing `components-example.json` entries. Copy their values unchanged:
cheap-relative margin weight 0.25, Gaussian CRPS weight 0.25, gradient-sign
weight 0.25, and score-CVaR tail fraction 0.25. These remain illustrative toy
ASSUMPTION inputs, not recommended thresholds or physical values.

Order is baseline, then subset size 1 through 4, using lexicographically sorted
component keys and ordinary combination order. Freeze this complete catalogue
before any evaluation. Use every one of the ten candidate proxies pinned at
sha256 157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235.
Use unchanged `physics-error-example.json` and `goodhart-search-example.json`:
search seed 42, 20 random draws, four hill epochs, eight registered toy trait
axes, neighbourhood-blend buyer value. Only its existing OFF physics switch
is used by Goodhart; the error64 seven-switch experiment remains separate.

Run the existing historical-public/toy controls gate first. Stop the entire
tranche on a failed control, failed command or the first capped combination;
retain any completed rows as partial evidence, never select favourable cells.
Every combination has a 160 CPU-s, 240 wall-s and 1 GiB address-space limit.
Sixteen combinations allow at most 2560 evaluation CPU-s, leaving room below
the one-CPU-hour envelope after the 266.571 CPU-s error64 analysis and auxiliary
commands. No provider, pod, solver, model construction or spending is allowed.

The existing scorer's gate/FLOOR and CVaR refusal semantics remain unchanged.
Search settings are shared; actual attempted query counts can vary and must
be reported rather than claimed equal. The value-search optimum is approximate.
Signed negative gaps indicate an imperfect oracle, not a superior-to-truth rule.
Missing/unscored/capped results remain explicit and cannot become zero regret.

Bind actual source, config, search, component catalogue, candidate and output
identities. Record actual runtime separately from this contract. No experiment
is a completed full synthetic/real campaign or an independent confirmation.
No EV4 fitting/selection, realism calibration, held-out generator or material,
AX42, chain, LIVE, threshold selection, qualification or deployment is permitted.
Old numerical artifacts remain immutable. Correct the already identified
error64 readout metadata phrase to specify neighbour-blend gamer flags, without
changing its counts, code or source identities. Root owns review and merge.
