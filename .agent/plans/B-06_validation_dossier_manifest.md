# B-06 plan — Validation Dossier and qualification manifest

**Ticket:** B-06  
**Status:** first coherent slice implemented; Slice 2 next  
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

After Slice 1, run only the new B-06 tests and directly affected registry,
package, code-authority, and predecessor-boundary tests. Native results remain
diagnostic. No full canonical run or complete-diff review occurs at this
checkpoint.

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
