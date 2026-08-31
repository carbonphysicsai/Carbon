# B-02C plan — research resource policy contract and implementation

**Ticket:** B-02C — Research resource policy contract<br>
**Status:** `in_progress` in bounded contract-first engineering scope<br>
**Contract branch:** `agent/b-02c-resource-policy-contract`<br>
**Contract worktree:** `/Users/nickfitzpatrick/Documents/Codex/2026-08-31/files-pasted-by-the-user-continue/work/Carbon-b-02c-resource-policy-contract`<br>
**Exact contract base:** `b10b6e74fb3f8ab8a7427a6763c7db4f41341083`<br>
**Exact base tree:** `45273c527684b94afeb2f01b66a774b5426b6e0e`<br>
**Working contract:** `Design_Specs/Research_Resource_Policy_Contract.md`

## 1. Authority and dependency gate

The controlling orientation set is `CONSTITUTION.md`, root `AGENTS.md`,
`agent_pack/EXECUTION_PROTOCOL.md`, `.agent/DELEGATED_DECISION_PROTOCOL.md`,
`.agent/INVARIANTS.md`, the Wave/Wave-B board and handoff, this ticket, the
merged B-02B contract and public implementation, the B-07R research contract,
`Compute_Optimization.md`, `JAX_Optimization.md`, the relevant Operations,
Build Out, constitutional overlay, and Master Plan sections, MQ-008, MQ-015,
MQ-017, MQ-024, and current environment, ref, canonicalization, persistence,
package, and code-authority patterns. No legacy archive is selected or read.

B-02B's gate was satisfied before B-02C began: PR #64 exact reviewed head
`68189e7068715a5d8054f0f7e64dc981ae1c37aa`, tree
`45273c527684b94afeb2f01b66a774b5426b6e0e`, normally merged as
`b10b6e74fb3f8ab8a7427a6763c7db4f41341083`; exact-head CI `33362051770`,
Greptile check `99413062552` at 5/5 with zero unresolved threads, and
exact-main CI `33368352662` passed.

## 2. Ownership and invariants

B-02C consumes exact immutable B-02B `ResolvedConstructionPlan`, ref,
`StaticResourceRequirement`, and resource-impact-tag values. It never changes
Strategy/compiler semantics, plan bytes/hash, static requirements, or their
order. A policy change changes only a B-02C assessment/result.

The implementation owner is a new standard-library-only
`carbon.resource_policy` package with one-way dependencies into public
`carbon.construction`, `carbon.authoring`, and `carbon.registry` primitives.
It owns no persistence, scheduler, backend, process control, forecast model,
binding quote/admission, price, scientific evidence, score, or official
lifecycle transition.

## 3. Contract phase

1. Reconcile B-02B's proven closeout and select only B-02C.
2. Replace stale affirmative multi-human approval wording with
   record/notify/validate/CI/Greptile/normal-merge/exact-main governance.
3. Define exact policy/class identity, immutable plan consumption, static
   assessment, fixture readiness, enforcement/cancellation, and receipts.
4. Keep static requirement, calibrated forecast, binding quote/admission, and
   observed receipt as distinct nominal epistemic layers and owners.
5. Record B-02C-D1 through B-02C-D8; notify applicable protocol, SRE,
   security, operations, economics, and lead owners through issue #42 without
   waiting for an affirmative response.
6. Run host diagnostics and diff hygiene, obtain exact-head GitHub Linux CI
   and Greptile correctness review, repair every valid finding, and require
   zero unresolved Greptile threads. Every tree change requires rereview.
7. Normally merge only the exact reviewed contract head with an exact-head
   guard, verify ordered parents and exact tree preservation, then require
   exact-main CI before implementation.

The tracked record is necessarily conditional until immutable GitHub and Git
metadata satisfy step 7. No recursive closeout PR is required.

## 4. Implementation phase

After the contract merge and its exact-main CI only:

1. Fetch without pull and create fresh branch `agent/b-02c-resource-policy`
   in its own worktree from exact new `origin/main`; record base SHA/tree.
2. Record KEEP/WRAP/REPAIR/REPLACE disposition and baseline diagnostics.
3. Implement exact frozen/slotted policy, class, context, requirement,
   availability, assessment, decision, enforcement, cancellation, build/reuse,
   replicate, observed-quantity, and receipt values plus distinct nominal refs.
4. Implement a closed domain-separated codec, exact ref recomputation, strict
   stale/cross-Challenge/binding checks, pure static assessment, fixture-only
   readiness, pure enforcement, cancellation records, and resource receipts.
5. Update only code/package authority inventories required by the new package;
   make no dependency/lock change unless current evidence proves it necessary.
6. Add focused B-02C tests and affected B-02B construction/ref/canonical,
   invariant, installed-wheel, outside-tree, import-direction, and quality
   regressions. Never weaken an existing test or invariant.
7. Attempt bootstrap, doctor, canonical CI, and diff hygiene; use canonical
   GitHub Linux as final environment evidence when Darwin is rejected.
8. Open one draft PR titled `B-02C: implement research resource policy`,
   notify issue #42, obtain clean exact-head CI and Greptile review, repair
   valid findings with rereview after changes, and stop without merging.

## 5. Verification matrix

- exact policy/class/derived ref identity, canonical round trip, digest tamper,
  trailing bytes, field order, strict type, mutation, and fresh-process tests;
- exact Challenge, scope, policy, class, assembly, catalog, compiler,
  environment, context, expected-active-ref, plan, and dependency bindings;
- byte-identical plan/ref before and after all B-02C operations;
- unsupported class/tag/dimension/unit, structurally missing-ceiling hard
  rejection, exact limit,
  over-limit, hostile UInt64/Boolean/float inputs, duplicates, and overflow;
- unavailable capacity, funding, queue, and evidence budget independently and
  jointly producing deterministic non-scientific deferral;
- enforcement points, continue/over-limit/cancel/enforcement-failure/
  infrastructure-failure/deferral outcomes, actor authority, and provenance;
- complete-build, reuse-window, replicate, stage, observed cost/latency,
  cancellation binding, and receipt coherence;
- exact-type rejection across static/forecast-canary/quote-canary/receipt
  roles and absence of scientific, price, quota, protected-topology, or
  production-authority inference;
- installed wheel, outside-tree imports, public exports, standard-library
  dependency set, code authority, and one-way package direction.

## 6. Reserved inputs and fail-closed progress

Real hardware/resource classes, ceilings, operational enforcement rails,
validator capacity, reconstruction funding, queue policy, evidence budgets,
calibrated-forecast eligibility, binding execution quotes/admission, prices,
quotas, security acceptance, operational approval, production provenance,
qualification, and LIVE remain human/domain-owned and unavailable. Missing
values stop only their affected real behavior. Exact fixture-only types and
typed fail-closed seams may proceed and cannot be upgraded in place.

## 7. Stop and maturity ceiling

The contract merge may establish only bounded `SPECIFIED` and
`RATIFIED_ENGINEERING_CONTRACT`. The implementation candidate may establish
bounded `IMPLEMENTED`, `TESTED`, and `GREPTILE_REVIEWED`; it remains an
unmerged draft at this session's stop. Scientific, security, operations,
economics, network, production, qualification, LIVE, launch, frontier,
settlement, weight, and emission authority remain `NO`.
