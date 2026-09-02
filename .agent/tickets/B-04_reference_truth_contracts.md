# Ticket B-04 - ReferencePolicy, TruthAsset, and reference runners

**Wave:** B active in bounded development scope
**Status:** `done` only under the conditional completion gate below
**Execution state before that gate:** authoritative `in_progress`; the bounded
runtime candidate is complete but has not earned merged implementation/test
maturity
**Phase:** bounded engineering contract ratified; bounded fixture-runtime
candidate prepared after the satisfied B-01F predicate
**Depends on:** B-02A
**Build Out:** C19 and truth/reference authoring
**Master questions:** MQ-004
**Authority:** `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §9; `Evidence_and_Envelope_Standards.md`; reconciled target `Runtime_Julia_Truth_Oracle.md`
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

**Working contract:** `Design_Specs/Reference_and_TruthAsset_Contract.md`<br>
**Plan:** `.agent/plans/B-04_reference_truth_contracts.md`<br>
**Evidence:** `.agent/evidence/wave_b/b-04.md`<br>
**Branch:** `agent/b-04-reference-truth`<br>
**Exact base commit/tree:** `7161fe3c4a04821b7f676ab006bd5d313d0442d2` /
`619e366dead2288ccfd312f54ad09f17f86a1c62`<br>
**Delivery mode:** `SINGLE_TICKET_PR`<br>
**Separate-contract reason:** `NOT_APPLICABLE`<br>
**Primary Hub map_ref:** `WAVE-B/B-04`

PR #72 normally merged the exact reviewed contract tree and exact-main
canonical, clean-container, and Development Hub checks succeeded. The B-04
contract is ratified engineering authority. Owner decision `OWNER-DX-01`
inserts B-01F before runtime implementation without reopening or demoting that
contract. PR #73's normalized receipt at comment `5497405775` records that
B-01F's exact reviewed candidate normally merged with reviewed-tree
preservation and exact-main `Merge gate` succeeded. B-04 runtime starts from
exact main `7161fe3c4a04821b7f676ab006bd5d313d0442d2`, tree
`619e366dead2288ccfd312f54ad09f17f86a1c62`.

## Goal

Represent how one exact case receives an uncertainty-bearing answer key without defining any solver as truth by reputation.

## Definition of Done

- [x] Produce and ratify
      `Design_Specs/Reference_and_TruthAsset_Contract.md`; record B-04-D1
      through B-04-D10; route the required review; and leave all real reference-
      policy choices human-owned and fail closed. PR #72's external completion
      receipt carries the exact reviewed-head, check, finding/thread, merge-
      topology, and exact-main identities that earned this substantive
      maturity transition.
- [x] Define `ReferencePolicy`, `TruthAsset`, primary/corroborating roles,
      provenance, uncertainty, applicability, failure, and disagreement
      contracts through exact immutable B-04-owned records.
- [x] Define orthogonal closed evidence-kind, authority-function, and source-
      class axes capable of representing analytic or semi-analytic primary
      evidence, manufactured-solution verification anchors, mesh/time/
      tolerance-converged numerical primaries, independent numerical witnesses,
      experimental validation anchors, industrial goldens/customer-hosted
      references, and qualified accelerator/surrogate references. Represent a
      prospectively registered hybrid as an ordered policy composition whose
      entries retain their individual axes. Require every single target,
      composition, and component to occur exactly once in the same policy
      version; require entry, composition, registered-witness-target, and
      expanded-target inventories to reject canonical semantic duplicates;
      cross-bind the same Challenge/scope; and keep expanded primary and
      compared-witness entry sets disjoint.
- [x] Make the support boundary for every role explicit. MMS evidence normally
      supports code verification and convergence; it cannot by itself establish
      target-population relevance, model-form validity, customer context of use,
      engineering qualification, or product fitness.
- [x] Define nominal primary and witness runner interfaces with no generic
      caller-selected truth mode, arbitrary code, filesystem path, network
      retrieval, package installation, solver mode, or unregistered fallback.
- [x] Before the first runtime model, record and notify B-04-D11 with the exact
      v1 record field/type/order registry and outcome/reason compatibility
      matrices plus the exact ordered `carbon.evaluation.__all__` tuple
      required by the contract's fixed canonical profile, ref inventory, and
      root-surface boundary. Issue #42 comment `5497811877` is the durable
      non-gating lead notification; it is not scientific approval.
- [x] Bind exact case, reference policy, role, implementation, environment,
      numerical method/configuration, artifact or typed absence, applicability,
      uncertainty representation, and qualification identities. Keep grant
      issuance structural/capability-only; make an available admission
      authority reject `SUPPORTED` plus absent/ineligible artifact, and never
      fabricate a terminal ref for bare issuer/authority absence.
- [x] Preserve primary authority, witness corroboration, generator-under-test,
      and verification-anchor roles as separate. Agreement cannot promote an
      unqualified role, and evidence authority cannot transfer across another
      PDE, envelope, geometry/BC class, implementation, environment, or hardware
      path.
- [x] Require independence/correlation disclosures for shared equations,
      discretizations, meshes, transforms, libraries, generated code,
      calibration data, personnel, floating-point paths, and hardware where
      material.
- [x] Return typed supported, uncertain, conditioning, unsupported/not-
      applicable, disagreement, numerical-failure, malformed/provenance, and
      infrastructure-failure outcomes.
- [x] Ensure reference failure cannot become candidate gate failure, score zero,
      ranking loss, scientific rejection, or settlement consequence.
- [x] Add the minimal standard-library deterministic B-04 primary/witness
      fixture runners and fixture assets plus provenance/failure/cross-boundary
      tests, including
      evidence-role confusion, MMS-to-validation relabeling, correlated-witness
      disclosure, no authority transfer, and no silent fallback, without
      claiming Cole-Hopf or Julia qualification. B-E2 retains Julia/service
      adapters and expanded runtime/failure injection.

## Human input

SciML and an independent reviewer qualify the primary/witness hierarchy,
evidence roles, methods, uncertainty, failure regions, applicability,
independence, and acceptable disagreement.

## Must not

Average incompatible references into truth, let a generator certify itself,
fall back to mock or weaker unregistered truth, promote MMS into physical
validation, transfer one reference's authority to another regime or envelope,
or claim solver authority from successful execution, language, library,
reputation, cost, or nominal tolerance.

## Implemented bounded architecture

`carbon.evaluation` now owns the exact D11 policy/ref/canonical model,
role-specific request/grant/resolution/run/comparison graph, distinct raw/
fixture/truth assets, positive-only admission capabilities, protected
disclosure, and deterministic standard-library primary/witness fixture
runners. It keeps and wraps current B-02A canonical, identity, provenance,
disclosure, evidence-role, and case primitives through one-way explicit
submodule imports. Its exact package root remains the D11 ordered 22-name
allow-list; every authority-bearing record, ref, runner, codec, fixture,
capability, and diagnostic type remains protected below it.

The runtime implements no Julia service, Cole–Hopf method, production solver,
artifact store, cache service, transport, measurement, scoring, Dossier,
qualification, or later-ticket interface. Fixture provenance remains
structurally non-LIVE and scientifically unqualified.

## Conditional completion and B-05 selection

The `done`, bounded `IMPLEMENTED`/`TESTED`, and coordinated B-05 `in_progress`
states in this candidate are inert until all of the following are true for one
exact unchanged candidate:

1. every scope-required exact-head check succeeds, including `Merge gate`;
2. fresh read-only Codex/GPT review covers the complete exact-head diff and
   every finding is repaired or dispositioned;
3. a distinct non-author human approval carries the closed exact-head/tree
   receipt, `GPT review gate` succeeds, unresolved review-thread count is zero,
   and no applicable block remains;
4. the pull request normally merges with an exact expected-head guard;
5. the merge's ordered second parent equals the reviewed head and its tree
   equals the reviewed tree;
6. the reviewed head is ancestral to current `main` and fetched `origin/main`
   equals the merge;
7. exact-main `Merge gate` and every required push-only check succeed; and
8. the completed normalized external receipt, with no required `PENDING`
   field, is posted at its declared external location.

Only then is B-04 authoritatively `done` in its bounded fixture-runtime scope
and B-05 the selected `in_progress` ticket. If any predicate fails, the prior
merged B-04 `in_progress` / B-05 `todo` state remains controlling. Dynamic
head/tree, check, review, merge, exact-main, and receipt identities belong only
in the completed external receipt defined by
`.agent/templates/EXTERNAL_COMPLETION_RECEIPT.md`; no recursive closeout commit
or pull request is required. This session does not start B-05 contract or
runtime work.

## Maturity ceiling

The final runtime candidate uses the prospective delivery review contract in
`GOV-REVIEW-01-D1`: fresh read-only Codex/GPT review of the complete exact-head
diff, repair or disposition of every finding, distinct non-author human
approval carrying the closed exact-head/tree receipt, successful `GPT review
gate`, and zero unresolved review threads. This procedural review grants no
reference or scientific qualification.

```text
SPECIFIED: YES — BOUNDED ENGINEERING CONTRACT
RATIFIED_ENGINEERING_CONTRACT: YES
IMPLEMENTED: YES only when the conditional completion predicate passes, and
             only for the exact bounded merged fixture runtime
TESTED: YES only when that predicate passes, and only for the exact recorded
        engineering acceptance scope
REFERENCE_QUALIFIED: NO
OPERATIONS_APPROVED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
SCIENTIFICALLY_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE: NO
```
