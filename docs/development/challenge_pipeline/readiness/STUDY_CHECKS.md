# PLT-09 batch 3: committed decision-study evidence

Starting main: `7f9d7a2fc99205b67d6e03393c68e1f85e716e58`. Batches 1
and 2 are merged (#1220 and #1234). Reviewer: Graphite Testing Manager.
This batch wraps existing public EV4 study data, the design-search adapter,
reference importer/decision functions, and historical EV5 code pins. It runs
no solver, model, rented compute or confirmation batch. No private reference
or sealed material is opened. No scientific or commercial value is chosen.

`studies_by_level` records D1-D6 under explicit level keys. Each entry names
the Challenge, `levels: [2, 3, 4]`, and a basis explaining why the same
historical evidence applies. Unlisted levels never inherit earlier reviews.
Missing registrations are NOT_BUILT; malformed, mismatched or stale evidence
is FAIL. Evidence includes file/source digests and test identifiers.

D1 checks a finite comparator, contract digest, labelled representative and
boundary groups, and an explicit first-reference-access timestamp against the
freeze. A boundary control is not a labelled boundary population. Missing
labels or timing proof are findings; commit time is not solve/access time.

D2 verifies the registered Challenge adapter's identity and executes the
existing equal-budget harness tests. A separate committed Test Lead review
must bind the B ladder digest. The ladder is read, never chosen here.

D3 reads an authoritative code registry symbol mapping Challenges to counted
plan paths. Registered plans need committed host/n/p95 timing and every
timeout at least 2*p95 (the gate's stated multiplier). The no-plan declaration
must cite the committed Test Lead D3 ruling and the code must still register
no plan. An unknown registry stays NOT_BUILT; a new plan reopens calibration.
The existing review alone cannot prove absence of a new plan. The registry
locator is unresolved at ticket start and has been requested from the owner.

D4 verifies the retained public reference hash, rejects fixture-labelled
records, and runs the existing importer in a temporary experiment root.
`references.sha256` hashes `decision.jsonl`, the decompressed payload; the
archive digest is also recorded. Import and successful output/wall-time
evidence are required, not existence alone. No reference solver runs.

D5 reuses the reference decision classifier over the registered public
decision set. It reports fully reference-determined scenarios (every finite
candidate FEASIBLE or INFEASIBLE), with count, denominator, fraction and a
report digest. The historical panel's common mask is a separate statistic:
it depends on the members' selections. A different count is a finding, never
an automatic failure. The current reference-only recount is 5/12 versus the
historical panel common mask 6/12. Refinement policy acceptance remains a
per-level Test Lead review; the L0/L1 D5 ruling is left unchanged.

D6 parses the analysis import closure without executing analysis. It checks
every repository module at the recorded historical freeze commit against
the run record's pins, then executes the existing pin-step tests. It never
re-pins old evidence against today's files or reads confirmation references.

Validation: known-answer cases and one mutation per protection, baseline and
focused regression tests, L2/L3/L4 gate output, full lint/import sorting,
diff check, delivery hygiene and exact-head canonical CI. Local noncanonical
results are labelled diagnostic. Hub maintenance is retired. Maturity is
development implementation/testing only; no qualification or LIVE authority.
