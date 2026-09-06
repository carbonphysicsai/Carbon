# B-06 plan — Validation Dossier and qualification manifest

**Ticket:** B-06
**Status:** second complete-diff review returned three findings; bounded
repairs implemented locally and fresh exact-head CI/review required
**Branch:** `agent/b-06-dossier-manifest`
**Worktree:** dedicated worktree; absolute host path intentionally not tracked
**Exact starting main:** `2500e51042f39a31f5056c74ce2ac5065657ec2a`
**Exact starting tree:** `89763523576cef09f40fd8a205aa86d169d679de`
**Working contract:** `Design_Specs/Validation_Dossier_Manifest_Contract.md`
**Evidence:** `.agent/evidence/wave_b/b-06.md`
**Primary Hub map_ref:** `WAVE-B/B-06`

## 1. Owner-directed activation

PR #87 merged B-05's repaired tree into the exact starting main above. The
owner explicitly accepts that merged implementation as the B-06 dependency
despite incomplete routine B-05 delivery steps. Record the exception in
B-06-D0 and current Wave selection without inventing reviews, approval,
completed CI, or an external receipt. Do not reopen B-05 or wait for another
confirmation.

The one-time opening observation recorded PR #87 as merged. Delivery
preflight, Development Hub, and canonical-environment checks were successful;
the GPT review gate failed; a clean-image job and the main CI run were still
in progress at observation time. Do not poll or retrigger them. No observed
failure changes the B-06 structural dependency.

## 2. Selected engineering decisions

- **B-06-D0:** accept the exact merged B-05 tree as the owner-directed
  dependency for this transition only; preserve the incomplete ordinary
  delivery history.
- **B-06-D1:** implement the first slice under the already reserved
  `carbon.qualification` package, reusing A3 identity/digest grammar and
  B-02A strict primitives while leaving A3's legacy manifest and gate
  unchanged.
- **B-06-D2:** encode D1–D12 as exact ordered slots with slot-specific primary
  evidence classes, explicit requirement/completeness/status states, and
  supplemental campaign refs that cannot substitute for the primary class.
- **B-06-D3:** require the exact B-06 accountable signer-role tuple but expose
  only missing or populated-unverified bindings. Keep signer authorization,
  qualification-manifest issuance, active-registry comparison, and scientific
  signoff outside Slice 1.
- **B-06-D4:** use exact B-02A owner/top-level refs and B-05 measurement refs
  for the evidence subject graph, preserving B-03/B-04 reverse-import
  boundaries; require explicit closed claim mappings.
- **B-06-D5:** represent the dependence/coverage identity graph only under
  `OWNER_RATIFICATION_PENDING`; do not treat the v2.1/v4.1 proposal or B-05
  types as scientific ratification.
- **B-06-D6:** keep intended/realized attempt accounting, secrecy evidence,
  and scoped limitations opaque, typed, non-substitutable, and
  non-authorizing.
- **B-06-D7:** KEEP/WRAP A3's immutable public values only; compare one
  caller-supplied snapshot without store/gate imports, lookup, I/O, mutation,
  or activation.
- **B-06-D8:** domain-separate the B-06 candidate and exact A3 qualification
  snapshot fingerprints; neither fingerprint establishes trust or approval.
- **B-06-D9:** consume external identity-validation, exact-role authorization,
  and cryptographic-verification facts as separate typed inputs without
  implementing their trust policy or scientific signoff.
- **B-06-D10:** retain decision-resolution acquisition/result identities only
  under `OWNER_RATIFICATION_PENDING`; implement no dependence-aware engine.
- **B-06-D11:** treat campaign outcomes as externally supplied observations;
  blocked, invalid, deferred, or upstream-failure records cannot become
  dossier evidence, and no outcome self-qualifies.
- **B-06-D12:** use one closed, separately canonicalized acquisition/result
  manifest architecture with family-specific roles and no execution seam.

The first final review added no new delegated policy decision. Its three
repairs enforce the existing B-06-D1/D2/D3/D6/D8/D12 invariants: monotonic
fixture provenance, one exact dossier/evidence graph, and symmetric canonical
size acceptance.

The second final review likewise adds no new delegated policy. Its bounded
repairs enforce existing fail-closed authority: one shared structural-origin
join (`FIXTURE_ONLY` > `DRAFT_OR_UNRESOLVED` > `REGISTERED_REFERENCE`), exact
reuse of A3's pure missing/placeholder slot-reference semantics, and separate
nominal collision versus full canonical ordering keys. `B06-CR-001/002/003`
remain regression-verified; `B06-CR-004/005/006` are repaired in the new tree.
All prior exact-head CI and reviews are stale after the tree change.

These are reversible engineering decisions within the active ticket. Notify
issue #42 mentioning `@harshaa765`; development continues without waiting for
a response unless an explicit blocking direction arrives.

## 3. Implementation slices

### Slice 1 — dossier identity and evidence-slot foundation

Implement exact enums, nominal evidence and signer-artifact refs,
`DossierSection`, `ValidationDossier`, same-Challenge/version/supersession
validation, fixture-origin propagation, canonical bytes/digest/ref and strict
decode. Add focused CPU and invariant tests for missing/placeholder evidence,
slot and signer substitution, wrong Challenge/version, deterministic identity,
and fixture inability to qualify.

Checkpoint result: implemented with focused native diagnostics. The canonical
Docker environment remains unavailable and is recorded as infrastructure, not
as a passing result. Issue #42 comment `5554513577` carries the required
non-gating notification.

### Slice 2 — evidence-class and cross-section completeness

Add the ticket's complete typed evidence manifests for population,
SamplingPlan, generator, reference, representation, measurement, statistical
sufficiency, secrecy, censoring, uncertainty, campaign, and limitation
evidence. Enforce claim-support/non-substitution matrices without choosing
scientific sufficiency.

Checkpoint result: the common manifest and exact slot-specific subject graph,
claim matrix, statistical scope, accounting, secrecy, limitation, canonical
identity, and focused tests are implemented. The supplemental campaign
classes are structurally representable as typed refs with explicit claim
mappings. Campaign-specific acquisition/result schemas for MMS observed-order,
mutation, analytic-anchor, witness/convergence/disagreement,
generator-oracle-adversarial, and measurement-floor studies remain a later
B-06/B-E1 concern and are not marked implemented by this checkpoint.

#### Slice-2 rule-to-source-to-test matrix

| Rule | Authority status and controlling source | Claim/evidence and exact binding | Structural accept / reject | Human-owned judgment | Positive / negative proof |
|---|---|---|---|---|---|
| S2-R1 exact subject graph | Existing ratified architecture: `Generator_Validation.md` v2.0 D1-D12; `Challenge_Instance_Distribution.md` §§4-8, 26 | Every manifest pins the exact Challenge plus the applicable physical-system, claim-scope, population, SamplingPlan, generator, reference, representation, and measurement refs | Accept the slot-specific minimum graph; reject shared-Challenge-only, cross-Challenge, wrong nominal role, and omitted required object bindings | Whether any pinned object is scientifically adequate | valid D3-D9 graphs / missing object, wrong population role, cross-Challenge and wrong-version scope tests |
| S2-R2 explicit claim support | Existing evidence doctrine: `Evidence_and_Envelope_Standards.md` §§1-2; merged B-05-D2; B-06 ticket | Each evidence ref is explicitly mapped to a closed claim role and exact claim-scope ref | Accept authorized one-to-many mappings; reject unsupported roles and implicit cross-section satisfaction | Sufficiency and applicability of eligible evidence | explicit reuse / MMS-to-physical, product, LIVE and generator-reference-measurement substitution tests |
| S2-R3 statistical scope | Delegated structural requirement: active B-06 ticket; merged B-05-D4 types. Scientific dependence amendment remains proposal-only: `Generator_Validation.md` v2.1 and scientific canon v4.1 | Exact uncertainty policy, estimand, sampling/resampling/independence units, case/stratum scope, interval method, dependence/applicability, coverage, stopping, missing-cell, and evidence-set refs | Accept a structurally complete graph only with `OWNER_RATIFICATION_PENDING`; reject missing/wrong-kind/wrong-Challenge refs and any claimed ratified dependence policy | Method choice, independence, covariance, coverage, power, minima, stopping, false-promotion control, and applicability | pending complete graph / different-seed inference, component-table substitution, wrong-kind and false-ratification tests |
| S2-R4 intended/realized accounting | Existing ratified architecture: `Generator_Validation.md` v2.0 D4/D6/D12; `Challenge_Instance_Distribution.md` §§19, 26 | Exact SamplingPlan, protected intended-unit, realized-accounting, censoring, missingness, exclusion refs, plus typed attempt dispositions | Accept distinct registered dispositions; reject missing plan/accounting, cross-Challenge refs, duplicates, or reclassification of reference failure as candidate failure | Whether censoring or missingness is acceptable and how it affects inference | complete accounting / duplicate, omitted, cross-Challenge, and failure-collapse tests |
| S2-R5 secrecy and role separation | Existing ratified architecture: `Generator_Validation.md` v2.0 D11; current disclosure standards | Exact disclosure/blinding policy plus decontamination and role-separation audit refs; no seed, realization, truth payload, path, or locator fields | Accept opaque protected refs; reject missing policy/audit roles and unsafe field expansion | Security adequacy, decontamination, identity, authorization, and separation-of-duties acceptance | complete D11 graph / omitted role and public-surface/invariant tests |
| S2-R6 scoped limitations | Existing ratified architecture: `Generator_Validation.md` v2.0 D12; evidence standards §2 | Each limitation binds affected evidence, claim roles, and exact claim scope | Accept explicit scoped limitations; reject dangling evidence, empty scope, cross-Challenge, duplicate bindings, or automatic envelope mutation | Residual-risk acceptance and any prospective envelope/population revision | scoped limitation / dangling, duplicate, empty-scope and no-mutation tests |
| S2-R7 honest completeness | Existing B-06 contract §§4-7 and ticket | Manifest shape, section completeness, fixture origin, and signer state stay distinct | Accept incomplete/deferred values; reject a complete section whose required typed manifest is absent/mismatched; fixture and unverified signer state never gain authority | Section verdicts, signer authorization, qualification, and LIVE activation | valid incomplete round trip / unsupported completeness, fixture laundering, and signer-inference tests |
| S2-R8 deterministic identity | Delegated implementation decision under A3/B-02A canonical conventions and B-06-D1 | Evidence-manifest ID/version, same-ID supersession, exact canonical bytes and digest | Accept canonical ordering and byte-exact round trip; reject duplicates, stale/wrong-version supersession, tampering, unknown fields, and trailing bytes | No scientific judgment is encoded | stable permutation digest / tamper, duplicate-key, wrong predecessor and trailing-byte tests |

The v2.1 dependence additions in `Generator_Validation.md` and matching v4.1
scientific-canon additions remain explicit owner-ratification proposals. This
slice may preserve their exact identity fields because the active B-06 ticket
and merged B-05 types require a forward-compatible structural seam, but it
must label their scientific-policy status `OWNER_RATIFICATION_PENDING` and
must expose no accepted/qualified alternative.

### Slice 3 — qualification-manifest candidate and registry comparison

**Selected implementation decisions before code:**

- **B-06-D7 — KEEP/WRAP A3 values, not its store or gate.** Consume only the
  exact public `ChallengeRecord`, `QualificationManifest`,
  `QualificationEvidence`, `ArtifactBinding`, required-slot constants, and
  digest grammar. The caller supplies one exact record snapshot. B-06 performs
  no lookup, filesystem verification, registry mutation, or LIVE transition.
- **B-06-D8 — domain-separate the B-06 candidate and A3 snapshot fingerprints.**
  Current A3 exposes no public qualification-manifest digest API. B-06 may
  canonically fingerprint the exact current public A3 manifest fields solely
  as a comparison input. That fingerprint is not an A3 qualification hash,
  artifact-byte verification, scientific verdict, or activation token.
- **B-06-D9 — external authorization is a typed input, not a signer.** A pure
  comparison accepts exact per-role results that keep identity structure,
  role authorization, and cryptographic signature verification distinct.
  It implements none of those trust decisions and records no scientific
  approval state.

#### Slice-3 source-to-rule-to-test matrix

| Rule | Controlling source and existing A3 seam | Structural accept / reject | Human-owned decision | Positive / negative proof |
|---|---|---|---|---|
| S3-R1 candidate identity | B-06 ticket; Build Out §8; A3 `ChallengeKey` and tagged digest grammar | Exact candidate id/version/profile and domain-framed digest; reject malformed, duplicate, tampered, or trailing bytes | Whether the candidate should be issued or accepted | deterministic round trip / malformed, tampered, duplicate-key, trailing-byte tests |
| S3-R2 exact Challenge binding | Generator Validation v2.0 §5; A3 `ChallengeKey` | Every nested dossier, evidence, artifact, signer, subject, measurement, and authorization input equals one exact key | Whether that Challenge is scientifically defensible | matching key / wrong challenge and version tests |
| S3-R3 dossier binding | Generator Validation v2.0 §§5, 14-15; B-06 `ValidationDossierRef` | Exact dossier id/version/digest/currentness and structural completeness; reject missing, placeholder, fixture, stale, or registry-digest mismatch | D1-D12 adequacy and signoff | exact dossier artifact / wrong digest, fixture, stale, incomplete tests |
| S3-R4 exact artifact set | Build Out §8; A3 `ChallengeRecord.artifacts` and `ArtifactBinding` | Closed ordered refs with exact id/version/digest/kind/origin/currentness; reject duplicates, implicit latest, missing/extra registry IDs, or digest mismatch | Trust, provenance authenticity, and artifact adequacy | exact set equality / missing, extra, duplicate, stale and wrong-digest tests |
| S3-R5 signer population vs authorization | B-06 signer contract; A3 reserved-binding boundary | Exact five populated signer roles plus exact external identity-valid, role-authorized, signature-verified results | Identity proof, trust roots, role policy, crypto verification, and scientific approval | all exact results / missing, wrong-role, unverified and unauthorized tests |
| S3-R6 active-record comparison | Build Out/overlay A3 KEEP+EXTEND; exact public `ChallengeRecord` snapshot | Pure caller-supplied snapshot comparison only; reject wrong key, fixture provenance, or incompatible lifecycle | Registry selection and whether supplied snapshot is authoritative/current | compatible draft snapshot / wrong key, fixture, lifecycle tests |
| S3-R7 qualification/hash comparison | Build Out §8; A3 public `QualificationManifest`, record/manifest authoring-graph fingerprint, required slots/states, artifact IDs/digests | Exact B-06-domain snapshot fingerprint, equal non-missing A3 record/manifest graph fingerprint, and slot/artifact binding; reject missing/wrong state, artifact, graph, mode, or digest | Truth of human-owned A3 state strings and artifact contents | exact fingerprint / changed graph, slot, state, ref and digest tests |
| S3-R8 lifecycle compatibility | A3 `LIFECYCLE_STATES` and checked draft-to-LIVE activation ownership | Candidate comparison accepts only exact pre-activation `draft`; fixture/live reject; no state is mutated | Activation and LIVE decision | draft comparison / fixture and live tests, before/after record equality |
| S3-R9 fixture/placeholder isolation | Constitution; Generator Validation v2.0; B-06 origin/completeness types; A3 `fixture_origin` | Represent incomplete candidates honestly but never ready; any fixture or placeholder input rejects | Whether non-fixture evidence is authentic and sufficient | incomplete round trip / fixture and placeholder readiness tests |
| S3-R10 stale/superseded rejection | Constitution historical-evidence invariant; B-06 prospective versioning | Exact currentness enum and predecessor refs; non-current inputs and record digest drift reject; no `latest` lookup | Which version is the approved active scientific version | current exact refs / superseded, revoked, wrong-version tests |
| S3-R11 deterministic reasons | A3 deterministic diagnostic precedent; disclosure invariants | Closed enum in fixed evaluation order; no paths, protected bytes, signer secrets, or free text | Meaning/acceptance of underlying evidence | stable multi-error tuple / ordering and no-leakage tests |
| S3-R12 readiness ceiling | Constitution; Generator Validation §§15, 18-19; A3 reserved-binding boundary | `machine_prerequisites_satisfied` means only represented structural checks succeeded | Scientific/security adequacy, approval, production qualification, and LIVE | fully matching synthetic graph / assertions that no approval/LIVE API or side effect exists |

The A3 record's artifact paths and artifact bytes remain owned and verified by
the existing A3 gate. The pure B-06 comparator sees only artifact identifiers
and expected digests. A positive structural comparison is therefore not a
replacement for `ChallengeRegistry.assess_live_eligibility`, and neither
operation establishes scientific adequacy.

Checkpoint result: implemented. The candidate pins the exact dossier,
scientific objects, applicability-qualified representations, measurement set,
D1-D12 evidence manifests, signer records, closed artifact set, A3 slot
bindings, expected A3 snapshot fingerprint, and prospective supersession.
Canonical decode is byte-exact and the pure comparator returns a fixed-order
closed mismatch enum. A matching result is named only
`machine_prerequisites_satisfied`; the supplied A3 record remains `draft` and
is unchanged. Focused B-06/A3/boundary validation passed locally. The earlier
canonical Docker limitation was unchanged and was not retried.

### Slice 4 — campaign-specific evidence schemas

Implement one composable, closed campaign-manifest profile with distinct
prospective acquisition and externally supplied result records. Family-specific
required-role matrices preserve the scientific differences among MMS observed
order, mutation, analytic anchors, primary/witness convergence and disagreement,
generator-oracle adversarial work, measurement floors, decision resolution,
and residual limitations. Preserve the current evidence ref/claim graph and
leave every campaign engine and scientific conclusion to B-E1 or humans.

Field authority is explicit:

1. Challenge/upstream refs, campaign/acquisition/result identities, provenance,
   scope, versions, digests, status vocabulary, and canonical bytes are exact
   structural identity/provenance.
2. Result artifacts and outcome labels are externally supplied scientific
   results; B-06 validates their shape and binding but never calculates them.
3. Adequacy, acceptance, signer authority, qualification, and LIVE remain
   human-owned and are not represented as positive campaign results.
4. Dependence, resampling, coverage, power, stopping, and false-elimination
   fields remain `OWNER_RATIFICATION_PENDING`; presence cannot ratify policy.

#### Slice-4 campaign source-to-rule-to-test matrix

| Family | Controlling authority; allowed dossier role | Exact acquisition/result binding and required provenance | Allowed structural states; prohibited inference | Positive / hostile / non-substitution proof |
|---|---|---|---|---|
| MMS/refinement/observed order | Ratified Generator Validation v2.0 D5/D7; Evidence Standards §1; `IMPLEMENTATION_VERIFICATION`, `DISCRETIZATION_CONVERGENCE`, `REFERENCE_AGREEMENT`, `LIMITING_CASE_BEHAVIOR` | Exact implementation, manufactured/analytic definition, refinement family, discretizations, observable, environment/tool, case/stratum, acquisition/result/provenance; per-level and observed-order result refs | Specified/attempted/partial/result/blocked/invalid/inapplicable/pending; never expected order, physical validation, whole-reference adequacy, or LIVE | valid round trip / wrong implementation and malformed refinement / MMS-to-physical and LIVE rejection |
| Planted-defect/mutation | Generator Validation v2.0 D5; B-05 evidence-role matrix; `IMPLEMENTATION_VERIFICATION` only | Exact mutated component, campaign/operator/defect, affected property and MeasurementContract, acquisition scope, result/exclusion/failure/limitation refs | Detected/not-detected/indeterminate are external observations; no kill threshold or qualification | valid campaign / duplicate mutation and wrong measurement / product-qualification rejection |
| Analytic/limiting anchor | Evidence Standards §1; Generator Validation D7; `IMPLEMENTATION_VERIFICATION`, `REFERENCE_AGREEMENT`, `LIMITING_CASE_BEHAVIOR` | Exact anchor authority and applicability domain, compared implementation/reference/measurement, configuration, result, uncertainty and limitation refs | Comparison recorded/indeterminate/inapplicable; local anchor never becomes universal truth | valid scoped anchor / applicability and reference mismatch / physical-validity rejection |
| Primary/witness convergence/disagreement | Generator Validation D7; Evidence Standards §1; B-04 owner seam; `DISCRETIZATION_CONVERGENCE`, `REFERENCE_AGREEMENT` | Exact B-04 qualification-policy identity, distinct primary/witness identities and roles, case/stratum, refinement/configuration, comparison method, disagreement/result, uncertainty/failure/limitations | Agreement/disagreement/indeterminate/reference failure stay distinct; no independence, truth, physical validation, or candidate-failure inference | valid comparison / role confusion and scope mismatch / reference failure stays non-candidate |
| Generator-oracle adversarial | Generator Validation D5/D6; B-02A/B-03 owner seams; `IMPLEMENTATION_VERIFICATION`, `GENERATOR_CONFORMANCE_DIAGNOSTIC` | Exact population, SamplingPlan, generator, oracle/checker, targeted invariant, acquisition scope, generated result, exclusions/failures/limitations/provenance | Violation/no-observed-violation/indeterminate are external; no self-certification or SamplingPlan adequacy | valid campaign / wrong generator-population-plan and protected-field absence / conformance substitution rejection |
| Measurement floor | Generator Validation D9; Evidence Standards §4; B-05 exact MeasurementContract; `MEASUREMENT_FLOOR_DIAGNOSTIC` | Exact MeasurementContract, floor-study/source/reference/discretization/sampling configuration, case/stratum/applicability, external floor result, uncertainty/limitations/provenance | Floor recorded/indeterminate/inapplicable; no threshold choice, score eligibility, or production acceptance | valid result / wrong contract and scope / floor-to-score rejection |
| Decision resolution | Generator Validation D10/D12 proposal fields; Launch Bar v1.4 proposal; B-05 types; B-E1 ownership; `DECISION_RESOLUTION_DIAGNOSTIC` | Exact decision method, compared objects, estimand, population/scope, resampling/dependence, coverage/power diagnostics, censoring/missingness, stopping/false-elimination audit, external result and limitations | External superior/not-superior/indeterminate/deferred labels are structurally representable only with pending authority; no interval, power, winner, promotion, or false-elimination computation | valid pending record / wrong method and missing audit refs / pending-to-approved and LIVE rejection |
| Residual limitations | Generator Validation D12; Evidence Standards §2; `RESIDUAL_LIMITATION_DISCLOSURE` | Exact affected evidence, claim roles, case/stratum/envelope scope, authority/provenance, uncertainty/limitation result | Limitation recorded/pending only; no automatic population/envelope mutation or residual-risk acceptance | scoped round trip / dangling evidence and wrong claim / no scope mutation |

All families use strict same-Challenge/version/digest checks, canonical set
ordering, duplicate rejection, strict decode, complete-byte consumption,
fixture propagation, and the existing closed claim compatibility matrix.
An explicit artifact may support multiple allowed roles only through separate
registered claim bindings; no family or D-section supplies another implicitly.

Checkpoint result: implemented and locally tested. `CampaignAcquisitionManifest`
separates prospective campaign identity/state from `CampaignResultManifest`'s
externally supplied observations. `CampaignEvidenceManifest` binds both under
one exact Challenge, family, evidence class, version, digest, origin,
currentness, and optional predecessor. The combined primary/witness family
retains distinct convergence and disagreement evidence classes. Only current,
non-fixture results in evidentiary states can derive a supplemental
`DossierEvidenceRef`; blocked, invalid, inapplicable, deferred, generator-
failure, and reference-failure results remain representable but cannot become
dossier evidence. No campaign, statistical, registry, or LIVE engine was
added.

### Slice 5 — reconciliation and mature candidate (no feature scope)

The complete ticket, contract, implementation ledger, evidence, Hub, code, and
tests were reconciled as one base-to-head candidate. The audit found no
machine-implementable feature gap or authority conflict. It found one bounded
diff-hygiene defect: Markdown hard-break trailing spaces in three new tracked
documents. Those spaces were removed without semantic change. This phase did
not expand into B-E1, B-07F, or new scope.

### Review repair — B06-CR-001 through B06-CR-003

The first fresh complete-diff review at defective tree
`f765d9408e38373defaf51aa89780a91bbc6ea47` returned `FINDINGS`. The repair:

- projects recursive fixture origin through evidence-manifest, dossier-
  evidence, and dossier refs; makes dossier predecessor origin canonical; and
  requires candidate artifact origins to agree with their derived refs;
- derives the exact primary ref from every supplied typed D1-D12 manifest and
  requires it in the corresponding required complete dossier section; and
- applies the existing 2 MiB campaign document ceiling to acquisition and
  manifest encoders, so digest/ref helpers fail closed too.

The unmerged v1 schemas are corrected in place under B-06-D1's explicit
pre-persistence rule. This creates no migration and no second provenance or
registry system. The prior exact-head CI and review are stale after the repair.
Fresh exact-head CI and a completely fresh complete-diff review remain
`FINAL_REVIEW_REQUIRED`; no human approval or closed review receipt exists.

### Complete-candidate reconciliation

| Source / requirement | Intended and actual candidate behavior | Tests / evidence | Maturity | Result |
|---|---|---|---|---|
| Generator Validation v2.0 D1-D12 | Exact ordered slots, typed primary evidence, status, signer, supersession, and Challenge binding in `model.py`, `refs.py`, and `evidence.py` | B-06 dossier/evidence CPU tests and contract §§3-12 | Implemented and native-tested structurally | `NO_CONFLICT` |
| Evidence and Envelope Standards | Explicit claim mappings, reference roles, disagreement, applicability, and scoped limitations without source-count voting | Evidence/campaign negative tests; contract §§9, 11, 14 | Implemented and native-tested structurally | `NO_CONFLICT` |
| B-02A/B-03/B-04/B-05 ownership | Existing exact authoring and measurement refs are reconstructed; runtime owners remain upstream | B-06 invariant import tests and predecessor boundary suites | Implemented dependency seam | `NO_CONFLICT` |
| A3 registry/qualification | Pure comparison consumes one supplied `ChallengeRecord`; no store/gate import, mutation, lookup, or LIVE transition | qualification-candidate and A3 registry tests; contract §13 | Implemented and native-tested structurally | `NO_CONFLICT` |
| Ticket campaign families | Eight closed acquisition/result families with externally supplied outcomes and no engines | campaign tests and contract §14 | Implemented and native-tested structurally | `NO_CONFLICT` |
| Canonical/security boundary | Four domain-framed strict serializers reject duplicate, malformed, numeric, tampered, trailing, oversized, and disclosure-unsafe input | all B-06 canonical and invariant tests | Implemented and native-tested structurally | `NO_CONFLICT` |
| Generator Validation v2.1 / canon v4.1 additions | Dependence fields remain structural and `OWNER_RATIFICATION_PENDING`; no policy acceptance is encoded | pending-authority tests and B-06-D5/D10 | Proposal only | `HUMAN_RESERVED` |
| Tracked checkpoint wording | Slice-4/local wording lagged the reconciled final-candidate phase | ticket, plan, evidence, contract, Wave, ledger, and Hub source reconciled prospectively | Documentation | `DOCUMENTATION_LAG` repaired |
| Complete-range whitespace hygiene | Prior slice checks inspected a clean worktree, not the committed base-to-head range | `check_diff_hygiene.py --base origin/main` exposed three files | Delivery hygiene | `TEST_LAG` repaired |
| Exact-head CI, fresh review, human approval, merge, closeout | Candidate is prepared; no future receipt or outcome is recorded in-tree | Delivery protocol and external receipt template | Not yet earned | `FINAL_REVIEW_REQUIRED` |
| Scientific/security/signer/production/LIVE judgments | Remain external and fail closed | Contract §§6, 10, 13, 16 | Not earned | `HUMAN_RESERVED` |

No `AUTHORITY_CONFLICT`, `IMPLEMENTATION_LAG`, `MIGRATION_REQUIRED`,
`NEW_OWNER_DECISION_REQUIRED`, or remaining machine `TEST_LAG` was found.

### Final-slice Definition-of-Done criterion audit

| Ticket criterion | Classification at Slice-4 tree | Evidence / remaining boundary |
|---|---|---|
| Single-ticket contract, notification, coherent slices, delivery gates, review, approval, merge | `FINAL_REVIEW_REQUIRED` | Contract, plan, decisions, notification, and four implementation slices exist; exact-head review, gates, approval, PR, merge, and closeout remain the later delivery process |
| Exact D1-D12 identities, refs, status, signers, supersession, Challenge binding | `SATISFIED_BY_CURRENT_TREE` | Slices 1-3 model and test exact identities, currentness, canonical history, and fail-closed signers |
| Population, SamplingPlan, generator, reference, representation, measurement, statistics, secrecy, censoring, limitations, reproducibility | `SATISFIED_BY_CURRENT_TREE` | Slice 2 exact subject/evidence manifests and canonical tests |
| All ticket-named campaign manifests | `SATISFIED_BY_CURRENT_TREE` | Slice 4 implements and tests all eight acquisition/result families, including distinct convergence/disagreement evidence classes |
| Cross-section and cross-campaign non-substitution | `SATISFIED_BY_CURRENT_TREE` | Closed evidence/claim matrix plus hostile negative tests; one-to-many reuse remains explicit |
| Generator/reference/measurement separation | `SATISFIED_BY_CURRENT_TREE` | Exact nominal upstream bindings and role-confusion tests |
| Statistical, coverage, dependence, reconstruction, censoring, and stopping identities | `SATISFIED_BY_CURRENT_TREE` for structural representation; `HUMAN_RESERVED` for policy/adequacy | Exact refs exist under pending authority; computation, thresholds, method acceptance, and adequacy remain B-E1/human-owned |
| Qualification candidate and exact A3 comparison | `SATISFIED_BY_CURRENT_TREE` | Slice 3 pure exact snapshot comparison and deterministic mismatch tests |
| Fail-closed malformed/placeholder/fixture/unsigned/wrong-version/stale/mismatched/role-confused/claim-inadequate inputs | `SATISFIED_BY_CURRENT_TREE` | Slices 1-4 negative, canonical, lifecycle, authorization, and campaign tests |
| Human approval distinct from schema completeness/execution | `SATISFIED_BY_CURRENT_TREE`; real signoff `HUMAN_RESERVED` | No scientific-approval state or LIVE/mutation operation exists |
| Lifecycle/signature/mismatch/MMS-only/substitution/no-LIVE fixture tests | `SATISFIED_BY_CURRENT_TREE` | Focused B-06 and A3 suites cover the ticket's structural cases |

#### Individual B-06 criterion disposition at reconciliation

`SATISFIED` below is bounded to machine-checkable structure. Governing sources
are the B-06 ticket and contract plus Generator Validation v2.0 unless a more
specific source is named.

| # | Criterion | Disposition | Exact implementation and test proof |
|---:|---|---|---|
| 1 | D1-D12 identities | `SATISFIED` | `enums.py:DossierSlot`, `DOSSIER_SLOT_TITLES`; `test_exact_slot_order_titles_and_primary_classes` |
| 2 | Exact Challenge binding | `SATISFIED` | `model.py:ValidationDossier`, `evidence.py:DossierEvidenceManifest`; cross-Challenge tests in all four B-06 CPU files |
| 3 | Evidence references | `SATISFIED` | `refs.py:DossierEvidenceRef`, `DossierEvidenceManifestRef`; dossier/evidence round-trip tests |
| 4 | Section status | `SATISFIED` structurally; scientific status `HUMAN_RESERVED` | `enums.py:EvidenceSectionStatus`, `model.py:DossierSection`; missing/placeholder and rationale tests |
| 5 | Signer roles | `SATISFIED` structurally; authorization `HUMAN_RESERVED` | `SignerRole`, `SignerBinding`; signer-order and populated-unverified tests |
| 6 | Supersession/currentness | `SATISFIED` | dossier/evidence/candidate/campaign refs and `ArtifactCurrentness`; supersession/currentness tests across all B-06 CPU files |
| 7 | Population | `SATISFIED` structurally; adequacy `HUMAN_RESERVED` | `EvidenceSubjectBindings.target_population_ref`; exact subject-graph tests |
| 8 | SamplingPlan | `SATISFIED` structurally; adequacy `HUMAN_RESERVED` | `EvidenceSubjectBindings.sampling_plan_ref`; plan/version and accounting tests |
| 9 | Generator conformance | `SATISFIED` structurally; adequacy `HUMAN_RESERVED` | B-02A `GeneratorRef`/`DistributionConformanceRef` seams; generator separation tests |
| 10 | Reference | `SATISFIED` structurally; adequacy `HUMAN_RESERVED` | B-04 `ReferenceQualificationPolicyRef` owner seam; D7 and disagreement tests |
| 11 | Representation | `SATISFIED` structurally; fidelity `HUMAN_RESERVED` | `EvidenceSubjectBindings.representation_refs`, `candidate.py:RepresentationBinding`; D8 and applicability tests |
| 12 | Measurement | `SATISFIED` structurally; adequacy `HUMAN_RESERVED` | B-05 `MeasurementContractRef` and qualification-evidence refs; D9 and floor tests |
| 13 | Statistical sufficiency/reproducibility | `SATISFIED` structurally; adequacy `HUMAN_RESERVED` | `StatisticalScopeManifest`; complete/pending statistical-scope tests |
| 14 | Secrecy | `SATISFIED` structurally; security acceptance `HUMAN_RESERVED` | `SecrecyEvidenceManifest`; serialized-surface and disclosure invariant tests |
| 15 | Censoring | `SATISFIED` structurally; policy acceptance `HUMAN_RESERVED` | `EvidenceAccountingManifest`; attempt-disposition and missingness tests |
| 16 | Limitations | `SATISFIED` structurally; residual-risk acceptance `HUMAN_RESERVED` | `LimitationBinding`; scoped/dangling limitation tests |
| 17 | MMS/refinement/observed order | `SATISFIED` structurally | MMS family matrices and campaign manifests; MMS valid/malformed/non-substitution tests |
| 18 | Mutation/planted defect | `SATISFIED` structurally | mutation family matrices; duplicate/wrong-measurement/non-qualification tests |
| 19 | Analytic/limiting anchors | `SATISFIED` structurally | analytic family matrices; applicability/reference-binding tests |
| 20 | Primary/witness convergence | `SATISFIED` structurally | combined reference family with `PRIMARY_WITNESS_CONVERGENCE`; role-confusion tests |
| 21 | Reference disagreement | `SATISFIED` structurally | distinct `REFERENCE_DISAGREEMENT` class; disagreement/reference-failure tests |
| 22 | Generator-oracle adversarial evidence | `SATISFIED` structurally | generator-oracle family; exact population/plan/generator and no-self-certification tests |
| 23 | Measurement floors | `SATISFIED` structurally | measurement-floor family; contract/scope/no-score-eligibility tests |
| 24 | Decision-resolution evidence | `SATISFIED` structurally; policy `HUMAN_RESERVED` | pending-authority family; audit-ref/no-computation tests |
| 25 | Residual limitations | `SATISFIED` structurally; acceptance `HUMAN_RESERVED` | residual-limitation family; exact claim/evidence/scope tests |
| 26 | Cross-section non-substitution | `SATISFIED` | `EVIDENCE_CLASS_ALLOWED_CLAIMS`, `EvidenceClaimBinding`; forbidden-role tests |
| 27 | Generator/reference/measurement separation | `SATISFIED` | distinct primary classes/subject refs; `test_generator_reference_and_measurement_primary_roles_do_not_substitute` |
| 28 | Qualification-manifest construction | `SATISFIED` structurally | `build_qualification_manifest_candidate`; candidate construction/round-trip tests |
| 29 | Exact A3 registry comparison | `SATISFIED` structurally | `compare_qualification_candidate`, `a3_qualification_snapshot_digest`; matching/mismatch/no-mutation tests |
| 30 | Missing evidence | `SATISFIED` | `EVIDENCE_MISSING` and completeness validation; missing-evidence tests |
| 31 | Placeholder evidence | `SATISFIED` | placeholder states/identifier rejection; placeholder tests |
| 32 | Fixture evidence | `SATISFIED` | recursive `fixture_derived` properties and mismatch reasons; fixture-propagation tests |
| 33 | Unsigned/unverified signer handling | `SATISFIED` structurally; real verification `HUMAN_RESERVED` | `SignerAuthorizationResult` states; missing/unverified signer tests |
| 34 | Wrong-version/stale evidence | `SATISFIED` | exact versions, currentness, supersession rules; wrong-version/stale tests |
| 35 | Malformed/mismatched evidence | `SATISFIED` | strict model/canonical validation and typed error codes; hostile/tamper tests |
| 36 | Role confusion | `SATISFIED` | nominal role matrices and `ROLE_CONFUSION`; cross-role negative tests |
| 37 | Claim inadequacy | `SATISFIED` structurally; adequacy judgment `HUMAN_RESERVED` | closed claim matrix rejects unsupported roles; substitution tests |
| 38 | Human approval separation | `SATISFIED`; approval `HUMAN_RESERVED` | no scientific-approval field/API; readiness-ceiling tests and invariant surface scan |
| 39 | Lifecycle tests | `SATISFIED` | draft-only comparator and A3 record immutability; lifecycle tests |
| 40 | Signature-slot tests | `SATISFIED` | signer artifact kinds, exact roles, external auth states; signature-slot tests |
| 41 | Mismatch tests | `SATISFIED` | `QualificationMismatchReason` closed ordering; exact and multi-mismatch tests |
| 42 | MMS-only qualification rejection | `SATISFIED` | MMS allowed-claim set excludes qualification/LIVE; MMS substitution tests |
| 43 | Generator/reference collapse rejection | `SATISFIED` | distinct primary classes and exact required subject bindings; collapse tests |
| 44 | No LIVE with fixtures | `SATISFIED` structurally; LIVE decision `HUMAN_RESERVED` | fixture rejection plus absence of activation API; B-06 invariants and A3 fixture tests |

The first ticket checkbox remains `FINAL_REVIEW_REQUIRED` because exact-head
CI, fresh complete-diff review, distinct non-author approval, protected review
gate, merge, external receipt, and closeout are intentionally not performed by
this reconciliation phase.

`NOT_YET_IMPLEMENTED`: none for machine-implementable B-06 scope.
`BLOCKED`: none for structural implementation. Real evidence production,
scientific/security judgments, signer authority, pending dependence
ratification, production qualification, and activation remain expressly
human-owned or assigned to later tickets; they are not B-06 implementation
gaps.

## 4. Baseline and validation

The canonical wrapper was attempted once during implementation and correctly
failed because Docker or the exact Dev Container was unavailable. The final-
candidate phase re-evaluates that environment once, without repeated retry if
the limitation is unchanged. Native Python 3.11.11 with the existing
repository-pinned B-05 development environment ran the focused
registry/B-05/invariant baseline:

```text
242 passed in 1.14s
```

After each slice, run the new B-06 tests and directly affected registry,
package, code-authority, and predecessor-boundary tests. Slice 2's expanded
local run passed 815 tests. Slice 3's final focused invocation passed 270
tests, its expanded invocation passed 1431 tests in 651.55 seconds, and its
post-repair focus passed 233 tests. Slice 4's final B-06/A3 focus passed 318
tests in 2.14 seconds, its expanded affected invocation passed 1480 tests in
667.87 seconds, and its post-documentation package/authority/invariant run
passed 129 tests in 8.28 seconds. One earlier expanded Slice-4 invocation was
interrupted after 325 passes because a result-identity schema repair changed
the tree; it is not validation evidence for the final tree. Counts are per
overlapping invocation, not a summed unique-test total. Native results remain
diagnostic. No canonical Docker run or complete-diff review occurs at this
checkpoint.

Review-repair native validation on the repaired working tree:

```text
B-06 dossier/evidence/candidate/campaign plus qualification-boundary focus:
123 passed in 0.98s

complete native CPU lane:
4064 passed, 2 skipped in 863.52s

complete native invariant lane:
97 passed in 7.88s

Ruff 0.16.3 and Black 26.5.1 on all 12 touched Python files:
passed

compileall, RUNTIME_FULL classification, quality ratchet, delivery hygiene,
complete-range diff hygiene, and git diff --check:
passed
```

The single repaired-tree canonical-wrapper attempt exited 2 because Docker or
the Carbon Dev Container remains unavailable. It was not retried. Native test
counts are overlapping invocations and are not summed. Canonical acceptance
must come from the new exact-head GitHub workflow.

Second-review repair validation on the new working tree:

```text
B-06/A3 repair and boundary focus: 464 passed in 2.65s
complete native CPU lane: 4196 passed, 2 skipped in 809.62s
complete native invariant lane: 97 passed in 5.91s
Ruff 0.16.3 / Black 26.5.1 / compileall / RUNTIME_FULL classification /
delivery hygiene / quality ratchet / complete-range diff hygiene: passed
```

One earlier CPU run was interrupted at 96% after 4043 passes and 2 skips and is
not treated as successful evidence. The second repair's one canonical-wrapper
attempt again exited 2 for the unchanged Docker/Dev Container limitation and
was not retried. Counts above are overlapping invocations, not a unique total.

## 5. Hub and commit shape

The selection/authority and implementation change requires a structural Hub
update at `WAVE-B/B-06`. Commit the contract, decisions, plan/evidence,
selection records, implementation, and tests as the authority commit **A**.
Then update Hub source, pin it to **A**, regenerate only through the normal Hub
renderer, validate the affected Hub surface, and commit it as **H**. Do not
push, open a PR, merge, or perform final review in this checkpoint.

## 6. Human-reserved blockers

Real evidence, scientific section status, signer identity/key custody and
authorization, separation-of-duties exceptions, statistical sufficiency,
security acceptance, qualification, Launch Bar approval, and LIVE activation
remain human-owned. They block positive real qualification but do not block
the bounded structural slices.
