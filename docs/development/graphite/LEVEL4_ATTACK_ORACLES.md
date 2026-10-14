# PKT-15: Level 4 oracle work and remaining evidence

This is DEVELOPMENT software evidence. Adapter/controls v2 retain the
original seven graph checks and all six NOT_RUN seams, thirteen identities
in total. Three independent fixed diagnostic probes live in
`battery_level4_checks`; they are not registered as session adapter families
or controls. This does not add actual runtime attack coverage.

Only the original seven graph families are reachable through a session's
family declaration. The separate diagnostic module requires exact engine
declarations; even such declarations return NOT_RUN with unavailable
evidence when passed to the session adapter. Actual unknown evidence stays
UNDETERMINED. Shared reachability and stop-rule tests remain unchanged.

## Reachability and implemented checks

| Family | Executable probe | Valid and known-bad contrasts | Actual-session boundary |
|---|---|---|---|
| compile_isolation | Calls the real `carbon.level4.compile.compile_in_isolation` entry point with a nonexecuting capture runner; checks registered scope/deadline, fixed Carbon program, provenance and extra-resource fields | Development/testnet dispatch; mainnet/unknown scope and unset deadline must stop before dispatch. Weak caller bypasses the guard; mutations of actual scope/program code are caught | The adapter rebuilds only a record and does not invoke G5. No real compile worker or adversarial compiler executed; session views are NOT_RUN |
| compute_under_counting | Calls the frozen `carbon.training_budget.analysis.r6` and `r7` functions on explicitly synthetic observations | Ordinary and exact-threshold records; underprediction must name its setting factor and R7 must retain its three-times safety limit. Missing factors/limits and changed R6 threshold are caught | No runtime or FLOP estimate was measured. Actual R6 stress/R7 enforcement evidence remains unavailable; session views are NOT_RUN |
| nonfinite_outputs | Lowers, parses, validates and executes Carbon-owned CPU graph fixtures, then calls G7's real `nonfinite_cases` helper | Two finite graphs; zero-division NaN and positive/negative infinity. Missing detection or the wrong case of the same count is caught against an independent scalar reference | No candidate-supplied graph or actual exam is executed by this adapter. Session views are NOT_RUN |

Reachability changes the proposed priority: graph outputs can reach the
battery exam through the staged worker, so finite-output detection is the
closest executable check. This probe exercises G7's diagnostic, not the
separate battery exam's mandatory gate. Its predicate needs no numerical
tolerance. R6/R7 rule checks follow; G5's dispatch entry point is callable,
but this adapter does not invoke it. Neither of those probes supplies its
unavailable host/runtime evidence.
The inference-cost rule remains HUMAN_INPUT (`carbon.level4.grade`). The
R6/R7 thresholds are reused from the existing frozen study, not selected here.

Only an exact engine `AttackInput` selects one fixed fixture case. Ordinary
oracle session views, including claimed timing/GPU/execution fields, cannot
become those declarations and return NOT_RUN with `NO_ORACLE_EVIDENCE`.
An unknown declaration also remains unavailable (its digest records
`unsupported_declared_probe`). Verification reads unavailable evidence as
UNDETERMINED with `oracle_evidence_or_inputs_unavailable`, never HELD, NA or
agreed-admissible closure. The three remaining L4 seams use that same reading.
Existing INCONCLUSIVE and genuine out-of-scope mappings are retained.
Readiness A2 and the attacker stop rule use the same seven session families.
The diagnostic module's known-bad/specimen/valid assertions are separate
software evidence, not counted session attempts or runtime evidence. The
readiness registry is unchanged from the starting main.
Actual worker and exam entry points are intercepted in the tests so a
regression that invokes them fails instead of executing a host workload.

## Full-ticket blockers

| Family / requirement | Missing authority or evidence |
|---|---|
| fresh_cases_rerun | Authorized Phase 3/Launchpad fresh confirmation. This lane cannot generate a replacement for a real host run |
| procedural_tables | D4's declared priors/hybrids rule and an independent violation criterion. The proposal explicitly says a compact procedure cannot be ruled out by graph inspection; legitimate cheap methods must not be declared attacks |
| gpu_nondeterminism | Actual GPU reconstruction/R1 evidence under its registered policy. CPU execution, a backend label or an execution Boolean does not establish a GPU result |
| Runtime interpretation of the three new software probes | A trusted execution/evidence path and actual host results; declared fixtures cannot silently substitute for them |
| Two historical L4 INCONCLUSIVE results | The queue names constant_smuggling but supplies no second name/reasons. The released #1293 snapshot at `41a84542bf78e9cc3ef325d5634afb7fcb272d60` has `l4.base_recipe: NOT_ATTACKED` and no L4 family rows. This is a bounded source observation, not a claim about the private current register |

The original seven gate functions, attacks and valid controls are preserved.
An INCONCLUSIVE verdict retains its current meaning: the specimen did not
demonstrate the detector on that input, or evidence was not sufficient.
It is never relabelled coverage. The existing constant-smuggling session
path needs a document; a strategy carrying only a graph digest supplies no
rebuilt graph to `graph_view` and is NOT_RUN. This identifies a code path,
not the recorded reason for a historical result.

Full PKT-15 remains incomplete until the six requested families have their
required decidable oracles/controls and the actual evidence/owner seams are
resolved. Carbon Validator retains comprehensiveness and acceptance. No
scientific/security/production qualification, spend, or host authority is
earned here. No private attacker root, finding record, official seed or
protected case was read or generated.
