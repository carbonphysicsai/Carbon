# B-E1 evidence — R0/R1/R2 reproducibility harness

**Tracked evidence class:** implementation and deterministic engineering tests
**Starting main:** `527877bdd132c33569ac64c11b0a4360f5a08718`
**Primary Hub map_ref:** `WAVE-B/B-E1`
**Maturity ceiling:** bounded SPECIFIED / IMPLEMENTED / TESTED only

## Implemented behavior

`carbon.reproducibility` keeps R0 exact identity, R1 numerical comparison, and
R2 decision comparison as separate nominal results. R0 binds exact B-02A
physical-system, candidate-output, target-population, SamplingPlan, and case
refs; B-02B resolved-plan identity; B-04 reference policy/outcomes; B-05
uncertainty and reconstruction-evidence policies; and exact fixture artifact,
generator, scoring, backend, environment, execution, seed-role, receipt, and
hardware identities. Neither R1 nor R2 is inferred from R0.

R1 accepts no built-in tolerance. An injected, backend-bound numerical
procedure supplies the test-only comparison rule and per-output deltas.
Unsupported backend identity, absent authority, mismatched outputs, malformed
material, or procedure failure stays typed and fail closed.

R2 consumes a complete incumbent/challenger × producer-independent
reconstruction × B-02A canonical-case graph. Each cell retains stress stratum,
reference realization, common-random and deliberately paired seed/hardware
roles, representation, execution, provenance, missing/censored state, and all
six separately represented evidence factors. Every registered or detectable
shared dependency is an explicit graph edge. B-04 reference run/comparison
outcomes remain exact upstream types.

Decision combination is constructor-injected. Applicable joint propagation is
preferred, followed by a conservative bound. Quadrature, independence, or
zero-covariance is callable only when one exact B-05 shortcut matches the
evidence sets, case/stratum scopes, dependence assumption, applicability test,
and Dossier qualification, and the injected applicability result repeats the
exact test and scopes. Otherwise R2 is indeterminate.

The reconstruction campaign audit wraps B-05 assessment and retains distinct
static-admission, complete-base, frozen-reuse, repeat-promotion,
random-stability, scientific-sequential, and heuristic-futility events. A
pre-base or heuristic stop is only `EVIDENCE_DEFERRED`. B-04/B-05 reference,
reconstruction, measurement, and infrastructure failures never become
negative candidate evidence.

## Verification

Native diagnostics currently report:

```text
56 B-E1 focused CPU/direct invariant and B-04/B-05 boundary tests passed
1112 B-02A/B-02B/B-02C/B-04/B-05/B-E1 affected tests passed
152 complete invariant tests passed
Ruff 0.16.3 and Black 26.5.1 check the changed Python files
```

Coverage includes deterministic replay and ordering; R0 exact match/mismatch;
R1 supported/unsupported backends and injected comparisons; R2 joint,
conservative, null, coverage/power, unqualified and exactly qualified shortcut
scenarios; a full crossed heteroscedastic interaction graph; all six factor
classes; common case/reference/random/seed/hardware/representation/execution
dependencies; missing/censored cells; every required contested/failure class;
manufactured-anchor overreach; policy and provenance mismatch; scientific
sequential continue/stop/exhaustion; heuristic and pre-base deferral; hostile
inputs; and absence of ranking/frontier side effects.

The canonical wrapper was invoked once and failed closed because Docker is
unavailable on this host. Native results are diagnostics; the ready-head
GitHub acceptance and Merge gate are the canonical shipping predicate.

## Decisions and conditional completion

Working decisions B-E1-D1 through B-E1-D7 are recorded in
`.agent/DECISIONS.md`. They preserve one-way package ownership, nominal
R0/R1/R2 separation, exact crossed evidence, separate factors, injected
decision authority, joint/conservative precedence, exact shortcut
qualification, staged B-05 audit reuse, and structural TEST_ONLY isolation.
The SciML / Technical Lead notification is routed through issue #42 under the
delegated-decision protocol; silence is non-blocking under OWNER-DX-03.

That boundary is now satisfied. Accepted head
`831a34598f3f28ad8c05490244a4e0509473ac41` passed run `34124228848`,
including `Merge gate`, and normally merged as the second parent of main
`c484fd308d866d4b05a2765a984ec014dd96386e`. B-E1 is therefore `done` in its
bounded engineering scope; the merged records selected B-E2 next.

## Human-owned inputs and unavailable capability

No real tolerance, sample size, minimum resolvable improvement, dependence
model, interval or applicability procedure, coverage or power target,
scientific stopping/extension rule, heuristic-error bound, stability-audit
rate, or supported production backend is supplied. Scientific and security
qualification, production, LIVE, ranking, frontier promotion, network,
settlement, weights, and emissions remain absent and unearned.
