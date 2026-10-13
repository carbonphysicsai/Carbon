# Paired L5 candidate construction comparison

OPT-17 is an offline DEVELOPMENT comparison interface. It consumes construction
and measurement receipts; it trains no model, runs no reference solver and
launches no worker. The three hunt candidates remain hypotheses. PLT-27 owns
their construction implementations; GTM and the authorized host executor own
real reconstruction, measurement and authenticated metering.

## Zero-cost worked dry run

```sh
python -m carbon.development_comparison.l5_candidate_arms --standin --out /tmp/l5-standin.json
```

On a noncanonical host use `./scripts/dev/canonical.sh python -m ...` when that
runtime is available. Native output is a diagnostic, not canonical acceptance.
The stand-in imports OPT-15b's analytic `physics.build` and its example config,
with the declared loose-constraint toy knob. It compares identical analytic
arms on six target questions and six questions in each of four near variants:
objective, constraint, operating condition and boundary. Five synthetic seed
slots give 30 paired observations per group. No seed slot is a trained model.
Construction counters are explicit zero-cost placeholders, never measured work.

The dry run returns `SYNTHETIC_FIXTURE_RESULT`, five groups with
`NO_OBSERVED_DIFFERENCE`, point 0 and interval [0, 0]. It reports no equivalence
or accepted improvement. The fixture only exercises the mechanism, not any
recovered L5 candidate's benefit. Missing references instead produce
`UNRESOLVED_INCOMPLETE_PAIRS`; they cannot be dropped to improve the result.

## Execution interface

`PairPlan.from_document(plan)` constructs the immutable validated plan.
`compare(validated_plan, receipts)` produces the report. The same CLI accepts
`--plan <public-plan.json> --receipts <public-receipts.json> --out <pack.json>`.
Only those explicit files are read; input references are identities, never
paths the tool follows. The pack retains the plan, receipts, report and report
digest. Local non-symlink files and unique, finite JSON are required.

Use `standin()` to obtain the exact closed input shape and `seal(body, field)`
to bind a prospectively prepared plan or receipt. This is integrity, not an
executor signature or scientific acceptance. Public metering remains
`HOST_DECLARED_NOT_AUTHENTICATED`; authenticate it through the execution owner's
existing system before relying on it. No source is accepted because it says PASS.

The plan declares MONOTONE_CAPACITY, PHYSICS_LOSS or QUASI_NEWTON; the exact
baseline/candidate implementation references and derived construction digests; common
data digest, paired seeds, steps, width, depth, hardware route and resource
caps; all target and near-variant scenarios with public reference digests;
metric directions/units; and explicit bootstrap replicates/confidence/seed.
Each arm repeats the complete common configuration, including the full base
recipe family/settings. Both construction descriptors must carry that identical
base recipe. The baseline excludes the feature; the candidate supplies its exact
hypothesis/definition. Their digests are derived from those full descriptors and
implementation references, not accepted as opaque labels. Every receipt binds
the descriptor and a measured model-artifact digest. Freeze these identities and
measurement/scenario definitions before execution. GTM still must authenticate
that the executor used the reviewed construction: hashing a descriptor cannot
prove execution. This tool does not compile or admit a new construction.

The executor supplies one closed receipt per arm and reconstruction seed, with
COMPLETE or FAILED_INFRA, all metering events, exact event-derived totals and
every declared measurement. Every event includes updates, objective evaluations,
gradient evaluations, tokens, line-search trials and wall/core seconds. Include
setup, construction, prediction and verification costs; prediction/verification
phases must be explicit even when cached and zero-cost. Each line-search trial
counts its loss AND gradient evaluations; it is never collapsed into one outer
polish step. QUASI_NEWTON requires an explicit line-search phase in both arms.
Missing counters, unmatched seeds/data/hardware, omitted work, unreconciled
totals and any actual cap overrun refuse before comparison. PUBLIC_DEVELOPMENT
cannot relabel the zero-cost stand-in as measured execution.

Shared caps are matched allocations, not a claim that the two observed runtimes
are numerically equal. The pack discloses both caps and actual consumption.
Same steps alone are insufficient: line search and all auxiliary work count
against the same limits. The harness wraps the existing BudgetCap/BudgetLedger
for wall/core admission and the cost ledger for public charges. Verification
keeps its separate cost category. It chooses no hardware conversion or price.

## Interpreting the report

Each target/near-variant group and metric has a paired improvement estimate
(positive means improvement in that metric's declared direction), seed and
scenario counts, missingness and a percentile interval. Paired bootstrap draws
resample seed slots and conditions jointly for both arms, following the existing
EV hypothesis design. These are exploratory intervals; seeds are repetitions
and conditions need a scientifically justified sampling/dependence contract.
One seed or one scenario has no interval. Missing pairs suppress the full-group
estimate; infrastructure failure remains infrastructure failure.

Exact observed equality is `NO_OBSERVED_DIFFERENCE`. Mixed differences whose
interval spans zero are `UNRESOLVED`, never evidence of equivalence. Positive
and negative directions are descriptive: a gain only on the target cannot hide
neighbour harm. Every report retains thresholds/adoption as HUMAN_INPUT, null
accepted-improvement/equivalence fields, and false official/score/qualification/
settlement eligibility. No comparison adopts, ranks or qualifies a scoring rule.

GTM's real measurements can include decision loss, capacity/total errors,
Kendall tau and mechanism counts as separately defined metrics. Compute those
through their existing domain evaluators, not by substituting this stand-in.
Reuse PLT-27's public monotonicity precheck before candidate 1 training; zero
observed rises is a reportable stop, not an excuse to launch anyway. Candidate 2
still needs its exact loss expression. Candidate 3 needs authenticated true-cost
telemetry. Real candidate sequencing and stop/go remain with Test Lead.

Every result prints the hunt-recovery caveat: these are what one partly-broken
hunt recovered; a measurement of three is not a measurement of Level 5. No
hidden/sealed/holdout input, training, spend, host deployment, physical validity,
security acceptance or live benefit is established by this implementation.
