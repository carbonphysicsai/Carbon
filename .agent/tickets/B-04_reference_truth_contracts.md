# Ticket B-04 - ReferencePolicy, TruthAsset, and reference runners

**Wave:** B active in bounded development scope
**Status:** in_progress
**Phase:** bounded engineering contract ratified; runtime implementation paused
behind B-01F
**Depends on:** B-02A
**Build Out:** C19 and truth/reference authoring
**Master questions:** MQ-004
**Authority:** `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §9; `Evidence_and_Envelope_Standards.md`; reconciled target `Runtime_Julia_Truth_Oracle.md`
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

**Working contract:** `Design_Specs/Reference_and_TruthAsset_Contract.md`<br>
**Plan:** `.agent/plans/B-04_reference_truth_contracts.md`<br>
**Evidence:** `.agent/evidence/wave_b/b-04.md`

PR #72 normally merged the exact reviewed contract tree and exact-main
canonical, clean-container, and Development Hub checks succeeded. The B-04
contract is ratified engineering authority. Owner decision `OWNER-DX-01`
inserts B-01F before runtime implementation without reopening or demoting that
contract. B-04 runtime may begin only after B-01F's exact reviewed candidate
normally merges with reviewed-tree preservation and exact-main `Merge gate`
succeeds.

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
- [ ] Define `ReferencePolicy`, `TruthAsset`, primary/corroborating roles, provenance, uncertainty, applicability, failure, and disagreement contracts.
- [ ] Define orthogonal closed evidence-kind, authority-function, and source-
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
- [ ] Make the support boundary for every role explicit. MMS evidence normally
      supports code verification and convergence; it cannot by itself establish
      target-population relevance, model-form validity, customer context of use,
      engineering qualification, or product fitness.
- [ ] Define nominal primary and witness runner interfaces with no generic caller-selected truth mode.
- [ ] Before the first runtime model, record and notify B-04-D11 with the exact
      v1 record field/type/order registry and outcome/reason compatibility
      matrices plus the exact ordered `carbon.evaluation.__all__` tuple
      required by the contract's fixed canonical profile, ref inventory, and
      root-surface boundary.
- [ ] Bind exact case, reference policy, role, implementation, environment,
      numerical method/configuration, artifact or typed absence, applicability,
      uncertainty representation, and qualification identities. Keep grant
      issuance structural/capability-only; make an available admission
      authority reject `SUPPORTED` plus absent/ineligible artifact, and never
      fabricate a terminal ref for bare issuer/authority absence.
- [ ] Preserve primary authority, witness corroboration, generator-under-test,
      and verification-anchor roles as separate. Agreement cannot promote an
      unqualified role, and evidence authority cannot transfer across another
      PDE, envelope, geometry/BC class, implementation, environment, or hardware
      path.
- [ ] Require independence/correlation disclosures for shared equations,
      discretizations, meshes, transforms, libraries, generated code,
      calibration data, personnel, floating-point paths, and hardware where
      material.
- [ ] Return typed supported, uncertain, conditioning, unsupported/not-
      applicable, disagreement, numerical-failure, malformed/provenance, and
      infrastructure-failure outcomes.
- [ ] Ensure reference failure cannot become candidate gate failure or score zero.
- [ ] Add the minimal standard-library deterministic B-04 primary/witness
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

## Runtime resumption gate

The unchecked items above remain B-04 runtime Definition-of-Done requirements.
They are neither undone nor implemented by B-01F. After B-01F satisfies its
exact reviewed normal-merge and exact-main `Merge gate`, start B-04 runtime
from that exact main on a fresh `agent/b-04-reference-truth` branch/worktree.
Until then no runtime, solver, fixture runner, Julia service, Cole–Hopf method,
artifact store, transport, measurement, scoring, Dossier, or later-ticket
interface is authorized.

The final runtime candidate uses the prospective delivery review contract in
`GOV-REVIEW-01-D1`: fresh read-only Codex/GPT review of the complete exact-head
diff, repair or disposition of every finding, distinct non-author human
approval carrying the closed exact-head/tree receipt, successful `GPT review
gate`, and zero unresolved review threads. This procedural review grants no
reference or scientific qualification.

```text
SPECIFIED: YES — BOUNDED ENGINEERING CONTRACT
RATIFIED_ENGINEERING_CONTRACT: YES
IMPLEMENTED: NO
TESTED: CONTRACT/DOCUMENT AND EXISTING-BASELINE VALIDATION ONLY
REFERENCE_QUALIFIED: NO
OPERATIONS_APPROVED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
SCIENTIFICALLY_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE: NO
```
