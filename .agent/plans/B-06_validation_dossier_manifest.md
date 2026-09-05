# B-06 plan — Validation Dossier and qualification manifest

**Ticket:** B-06  
**Status:** second coherent structural slice implemented; Slice 3 next
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

Define an exact manifest candidate, verified signer-authorization input seam,
artifact set, active A3 record snapshot comparison, deterministic mismatch
reasons, and fail-closed lifecycle tests. Extend A3 only through an explicit
one-way adapter after the contract is updated prospectively; do not create a
second registry or activate LIVE.

### Slice 4 — integration and mature candidate

Compose a fully synthetic fixture graph, prove it cannot satisfy a production
qualification path, add package/wheel and cross-owner tests, reconcile the
Hub, run scope-required validation, and prepare the complete candidate for
fresh exact-head review. Do not begin B-E1 or B-07F execution.

## 4. Baseline and validation

The canonical wrapper was attempted once and correctly failed because Docker
or the exact Dev Container is unavailable. It will not be retried in this
checkpoint. Native Python 3.11.11 with the existing repository-pinned B-05
development environment ran the focused registry/B-05/invariant baseline:

```text
242 passed in 1.14s
```

After each slice, run the new B-06 tests and directly affected registry,
package, code-authority, and predecessor-boundary tests. Slice 2's expanded
local run passed 815 tests. Native results remain diagnostic. No full
canonical run or complete-diff review occurs at this checkpoint.

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
