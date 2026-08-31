# B-02B plan — candidate assembly and Strategy compilation

**Status:** in_progress<br>
**Contract:** `Design_Specs/Candidate_Assembly_and_Strategy_Compiler_Contract.md` v0.1<br>
**Authority:** agent-selected bounded engineering work under the delegated
decision protocol<br>
**Starting base:** `6e2a2640a6bd26755064acb0616382c8dcc0ba37`, tree
`5cf1aaf1fd11ef4775c170dd938c3190fa14145b`

## 1. Scope and invariants

B-02B turns the inert A2 Strategy v1 envelope into an exact Challenge-bound
`ResolvedConstructionPlan` or a typed fail-closed rejection. It implements no
real reconstruction, generator, reference, measurement, score, resource
policy, research wire protocol, official adapter, or service composition.

Required invariants:

- preserve A2's exact four-field wire schema;
- reuse A3/B-02A identity, refs, primitives, and canonical value encoding;
- extract, do not duplicate, A7's exact Strategy identity algorithm;
- use fixed Challenge-owned assembly plus a flat strict public catalog;
- materialize all explicit defaults and `R_strategy` into plan identity;
- reject unknown, unused, coerced, clamped, stale, incompatible, role-confused,
  or authority-contaminating inputs;
- emit static resource metadata without a policy verdict;
- keep practice/official consumer context and randomness out of plan identity.

## 2. Contract phase

1. Verify live starting main and B-02A/B-07R completion evidence.
2. Reconcile A2, A7 Strategy identity, B-02A, B-07R, Data Management, MQ-005,
   MQ-008, MQ-015, and MQ-024.
3. Record B-02B-D1 through B-02B-D8 and issue #42 notification.
4. Publish this plan, the working contract, evidence, and prospective
   `in_progress` tracker state without runtime code.
5. Run host diagnostics, diff hygiene, exact-head GitHub CI, and Greptile;
   repair every valid finding and obtain rereview after tree changes.
6. Normally merge only the exact reviewed contract head with an exact-head
   guard; verify ordered parents, tree equality, current main, and exact-main
   CI.

## 3. Implementation phase

After contract exact-main CI only:

1. Create `agent/b-02b-strategy-compilation` from exact post-contract main.
2. Record KEEP/WRAP/REPAIR/REPLACE inventory and baseline diagnostics.
3. Add standard-library-only `carbon.construction`; update code-authority and
   package-installation inventories without changing project dependencies.
4. Extract the exact A7 Strategy identity implementation to public A7-owned
   `carbon.fees.strategy_identity`; retain compatibility wrappers, exact
   `StrategyHash` type, hash values, failure mapping, root exports, and
   regressions.
5. Implement exact refs/models, closed values/domains/defaults/applicability,
   assembly/components, catalog, `R_strategy`, static resources, plan,
   canonicalization/decoding, and compiler rejection.
6. Add focused B-02B tests plus A2/A7/B-02A/registry/invariant/package
   regressions, installed-wheel and outside-tree coverage.
7. Run focused tests continuously; run affected suites at milestones; attempt
   bootstrap/doctor/canonical CI and record native-host rejection honestly.
8. Open one draft implementation PR, post issue #42 notification, obtain
   exact-head CI and clean Greptile review, repair valid findings, and stop
   without merging.

## 4. Expected implementation manifest

The final exact manifest is evidence-owned, but the intended package shape is:

```text
carbon/fees/identity.py
carbon/fees/strategy_identity.py
carbon/construction/__init__.py
carbon/construction/errors.py
carbon/construction/refs.py
carbon/construction/model.py
carbon/construction/catalog.py
carbon/construction/policy.py
carbon/construction/plan.py
carbon/construction/canonical.py
carbon/construction/compiler.py
.agent/CODE_AUTHORITY.toml
tests/cpu/test_b02b_*.py
tests/invariants/test_b02b_construction_boundaries.py
tests/cpu/test_package_installation.py
```

No file is mandatory merely because it appears in this forecast; split or
combine private implementation modules only when the public contract and
dependency direction remain exact.

## 5. Validation matrix

- shared A7 hash golden parity, exact type/re-export, and service behavior;
- exact models/refs/exports, defensive reconstruction, canonical round trip,
  tamper/trailing/digest failure, and fresh-process determinism;
- capability-issued B-02A graph origin, exact ref membership, graph
  fingerprint binding, and fixture/draft/registered origin behavior;
- flat catalog surface/type/domain/default/applicability/compatibility laws;
- catalog duplicate/consumer/selector collisions and stale/downgrade pins;
- Challenge/ref/version/digest/compiler/dependency/environment mismatches;
- all six component roles, role confusion, interfaces, state/side effects,
  fail-closed fallback, graph/code/gate bypass;
- `R_strategy` training-only structure and `P`/`Q`/`w`/seed/entropy exclusion;
- resource exactness, overflow/unit conflict, and B-02C non-ownership;
- mutation/alias/hostile-value isolation and non-echoing typed errors;
- byte-identical nominal practice/official-shaped plan consumption;
- installed wheel, outside-tree imports, no optional dependencies, package
  direction, code authority, full CPU and invariant CI.

## 6. Stop and maturity

The implementation candidate may earn `IMPLEMENTED`, `TESTED`, and
`GREPTILE_REVIEWED` within bounded engineering scope. It remains unmerged until
separately authorized. `SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED`,
`PRODUCTION_QUALIFIED`, and `LIVE` remain `NO`. Do not start B-02C.
