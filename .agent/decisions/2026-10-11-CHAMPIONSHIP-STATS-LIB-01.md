# CHAMPIONSHIP-STATS-LIB-01 working contract

Status: DEVELOPMENT implementation decision. This is a pure statistics library
for VALIDATOR-32 to call; it does not choose a production rule or authorize a
takeover, weight, emission, or LIVE action.

Authority: owner ticket CHAMPIONSHIP-STATS-LIB-01 (2026-10-11),
`codex-queue/inputs/margin-sizing-01/MARGIN_SIZING_04.md` and `m04.py`,
`CONSTITUTION.md`, and the current battery v3 final rule. The referenced
VALIDATOR-32 daemon draft is not present on main; its exact confirmation
contract remains an integration input.

Decision CHAMP-STATS-D1: keep the current validator and battery scorer intact.
Place typed, immutable paired case and evidence functions in
`carbon/championship_stats`, with no I/O or defaults for alpha, epsilon,
sample size, candidate bounds, or confirmation margin. The caller owns sealed
case identity, reference validity, artifact digest and incumbent identity.
Reject duplicate case/round identities, non-finite values, changed artifacts,
and ambiguous ties. Accuracy uses incumbent error minus contender error, so
positive values favour the contender. A failed G-FEAS gate is ineligible before
any statistical comparison. An independent fresh confirmation sample checks
non-inferiority if the caller supplies its registered margin and level.

Decision CHAMP-STATS-D2: a bounded one-sided exponential mixture provides an
anytime-valid e-process for the composite no-improvement null. The caller
registers the paired-difference bounds and the mixture's positive betting
rates and weights; no noise or margin is inferred from a protected batch.
The state is keyed by exact rebuilt artifact and incumbent identities.
Restarting after either changes constructs a fresh state; an update against
the wrong key raises instead of silently carrying evidence. The M04 Gaussian
known-SD planning formula is reproduced separately in tests; it is not a
production variance claim.

Decision CHAMP-STATS-D3: spend daily familywise alpha conservatively by
artifact identity, then apply Holm to the compared contenders. No alpha is
replenished on a win; this is the safe zero-return case of alpha investing.
An artifact can receive one allocation per incumbent/day, and a sybil hotkey
cannot buy another allocation for the same artifact. Validator-32 may later
adopt a registered wealth-return rule, but none is inferred here.

Alternatives rejected: copying battery's fixed development values, using
unpaired scores, normal known-SD evidence for a general daemon, and treating
an e-value crossing as an automatic takeover. Each would cross an authority
or validity boundary. This choice is reversible by a versioned caller contract;
historical evidence is never reinterpreted.

Primary Development Hub map reference: `WAVE-H/FRONTIER-PROMOTION`.
Hub impact: none. `.agent/DELIVERY_PROTOCOL.md` retires Hub maintenance;
this bounded pure-library addition does not change wave placement, maturity,
owner route, or canonical Hub orientation.

Human input required before a daemon adopts this library: exact VALIDATOR-32
confirmation semantics and registered epsilon, alpha, N, difference bounds,
mixture and delta_c values. The library rejects missing values.
