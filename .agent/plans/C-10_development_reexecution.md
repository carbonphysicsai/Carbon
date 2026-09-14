# C-10 bounded DEVELOPMENT re-execution

**Decision:** `C-10-D1`
**Status:** implementation candidate; exact-head Linux service acceptance pending
**Base:** C-EA1 preparation PR #168 merge
`0ee4c9b8db8339740521e2afc72624c97d8e177a`
**Primary Hub map_ref:** `WAVE-C/C-10`

## Implemented flow

An exact retained C-07 result and active C-06 receipt are the source of one
prospectively frozen audit request. C-10 asks C-01 to admit a distinct
`REEXECUTION_OF` attempt, then delegates execution and result association to
the unchanged C-07 orchestrator. C-01's ordinary retry path still rejects a
new attempt after a successful result; the audit relation grants no retry,
replacement, miner-budget reset or additional scientific replica.

The request binds the candidate/Strategy, Challenge, public TRAIN commitment,
case and reference requests, reconstruction plan/policy, three registered
replica slots and randomness digests, resource policy, inference, reference,
measurement, source, image and environment identities. It freezes at most five
sequential worker launches under the existing C-03 profile: three
reconstruction workers, one reference worker and one measurement worker. The
primary and audit executions use distinct execution identities and scratch.

C-10 resolves both C-06 ledger references before comparison and compares only
the three reconstruction artifact digests, frozen prediction, reference and
measurement result digests. Exact bytes produce a non-official DEVELOPMENT
reproducibility observation. Different bytes remain scientifically unresolved;
there is no tolerance, averaging, vote or candidate-failure conversion.
Missing/revoked evidence, cancellation, execution failure, infrastructure
unavailability and indeterminate comparison remain distinct terminal outcomes.
Every non-exact outcome quarantines the affected result.

The hash-chained C-10 journal records intent before C-07 dispatch, makes exact
request/outcome replay idempotent, rejects changed bytes under one identity,
and marks interrupted RUNNING work for explicit reconciliation. A persisted
C-07 result can be reattached after controller loss without a new execution or
receipt. Public, reviewer and private reports are separate positive allowlists;
all official, publication, archive, network, weight, reward and scientific-
resolution eligibility remains false.

## Verification candidate

Focused tests cover fresh linked execution, exact replay, second-audit denial,
case/policy/request/receipt conflicts, numerical differences without a policy,
missing and revoked evidence, cancellation, failure, timeout-equivalent
infrastructure unavailability, restart, post-result crash, journal tamper,
quarantine and projection boundaries. C-01 regression tests confirm the new
relation does not change ordinary retry behavior.

The required Linux service test freezes one public synthetic Burgers recipe,
one case, the same three reconstruction randomness bindings and the unchanged
C-03 resource profile. It executes the complete C-07 numerical sequence twice
through fresh isolated reconstruction/reference/measurement workers, issues
two C-06 DEVELOPMENT receipts and associates their exact scientific-state
comparison. It records wall, CPU, cgroup memory, output and OOM counters when
available; scratch high-water remains explicitly unavailable without continuous
sampling. This is not a scientific stability sample, independent administration,
security assessment or protected execution.

The operator entry point is:

```text
./scripts/dev/c10_development_reexecution.sh
```

It retains private/reviewer/public non-official reports beneath
`.carbon-local/c10-development/`. Exact Linux service results and the final
image identity remain pending the one applicable CI acceptance.

## Maturity and exclusions

The candidate may earn `SPECIFIED / IMPLEMENTED / TESTED` only for this bounded
public DEVELOPMENT composition. The comparison policy is unqualified, the
same Carbon-controlled host is one administrator trust domain, and two
containers do not prove independent administration or host-root protection.
No official result, payable outcome, winner publication, archive
acknowledgement, weight input, protected-data use, public-network action,
scientific qualification or security qualification is authorized.
