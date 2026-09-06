# Credibility Crosswalk and Evidence Manifest Contract

**Ticket:** B-E3 — Credibility crosswalk and evidence manifest
**Contract version:** 0.1
**Status:** delegated working engineering contract
**Maturity ceiling:** bounded structural engineering only
**Implementation owner:** `carbon.qualification.credibility`

This contract adds a deterministic claim-to-evidence projection over B-06's
Validation Dossier machinery. It does not create another evidence store,
scientific judge, reference resolver, registry, signature verifier, campaign
runner, or qualification authority.

## 1. Reuse and authority

The crosswalk keeps B-06's exact `DossierEvidenceRef`,
`DossierEvidenceManifestRef`, `ValidationDossierRef`, claim-role matrix,
Challenge identity, structural origin, and canonical digest grammar. It wraps
those identities with source-use metadata and validates them against the exact
caller-supplied B-06 evidence manifests. It never dereferences a path, URL,
registry record, protected case, sample, seed, or hidden result.

`KEEP -> WRAP -> REPAIR -> REPLACE` disposition:

| Existing seam | Disposition | B-E3 use |
|---|---|---|
| B-06 Dossier/evidence/campaign identities | KEEP | Exact claim and evidence identity authority |
| B-06 claim compatibility matrix | KEEP | First role/substitution guard |
| B-02A/B-05 canonical ID/version/digest grammar | KEEP + WRAP | Opaque source-description and contract/reference identities |
| B-06 structural origin/currentness vocabulary | KEEP | Fixture and stale evidence remain visible |
| Free-form claim/evidence spreadsheets | REPLACE | Closed immutable model and deterministic canonical form |

## 2. Crosswalk identity

Schema version is exact string `"1.0"`. Canonical profile is exact string
`carbon_credibility_crosswalk_canonical_v1`. Domain header is exact bytes
`carbon.qualification.credibility-crosswalk.canonical.v1\x00`.

`CredibilityCrosswalk` binds:

- one exact Challenge;
- one crosswalk ID/version and optional same-identity predecessor;
- one exact B-06 `ValidationDossierRef`;
- exactly one current `DossierEvidenceManifestRef` for every D1–D12 slot;
- a canonical source inventory;
- a canonical explicit claim-to-source link set; and
- an exact structural origin that composes monotonically with nested evidence.

Canonical JSON is strict UTF-8 with sorted keys, fixed separators, no floats,
no unknown or missing fields, duplicate-key rejection, complete-byte
consumption, a 2 MiB ceiling, and byte-for-byte decode/re-encode verification.

## 3. Evidence categories and maturity

The source inventory keeps these categories distinct:

```text
EXTERNAL_SCIENTIFIC_RESULT
CARBON_DESIGN_OR_HYPOTHESIS
PROPOSED_CARBON_EXPERIMENT
CARBON_IMPLEMENTATION
CARBON_TEST_EVIDENCE
QUALIFIED_CARBON_EVIDENCE
INDEPENDENT_REPLICATION
COMMERCIAL_VALIDATION
PRODUCTION_QUALIFICATION
```

Availability is separately `AVAILABLE`, `PENDING`, `ABSENT`, or
`NOT_APPLICABLE`. Maturity is separately `UNAVAILABLE`, `SPECIFIED`,
`IMPLEMENTED`, `TESTED`, `EXTERNALLY_REPORTED`, `QUALIFIED`, `REPLICATED`,
`COMMERCIALLY_VALIDATED`, or `PRODUCTION_QUALIFIED`. A closed category/maturity
matrix rejects upward relabeling. A non-available source must remain
`UNAVAILABLE` and cannot support a claim.

The source-kind vocabulary includes analytic/semi-analytic references, MMS
code verification, converged numerical primaries, independent witnesses,
experiments, industrial goldens, qualified accelerators/surrogates, population,
generator conformance, reconstruction, representation, measurement, reference
independence, uncertainty, security/role separation, decision resolution, and
limitations. Presence does not infer adequacy.

## 4. Exact permitted-use record

Every available source binds:

- exact B-06 evidence identity and currentness;
- responsible source owner and evidence category/kind/maturity;
- exact contract and framework/reference identities;
- exact physical-regime, equations/model-class, assumptions,
  geometry/boundary/initial-condition, method, applicability, uncertainty,
  independence/correlation, validation-evidence, failure-policy, and limitation
  identities; and
- an explicit set of exact Dossier claim roles it may support.

These descriptive identities are opaque, versioned, tagged-digest refs. They
contain no embedded scientific payload, path, locator, protected case, sample,
seed, or reconstruction-sensitive metadata. Pending/absent/inapplicable
sources instead carry explicit unresolved-input identities and do not satisfy
the missing evidence.

## 5. Claim links and fail-closed assessment

Each `ClaimEvidenceLink` binds an exact D1–D12 evidence-manifest ref, exact
claim-scope ref, exact B-06 evidence ref, responsible claim owner, and exact
source identity. Assessment receives the exact B-06 evidence-manifest objects
as caller-supplied authority and verifies:

1. all D1–D12 refs are present once and match the supplied manifest bytes;
2. every B-06 claim binding has an exact crosswalk link;
3. no unknown, duplicate, or differently bound link exists;
4. each source evidence identity is present in that exact B-06 manifest;
5. B-06 evidence-class compatibility and B-E3 source-kind compatibility both
   permit the claim;
6. every linked source and contract/reference identity is current;
7. each linked source is available and has no required unresolved human input;
8. maturity exactly matches the source category rather than asserting a later
   stage; and
9. sources that claim independent, qualified, replication, commercial, or
   production authority have distinct source/claim owners and explicit
   independence/correlation evidence.

Assessment returns closed issue codes and paths without echoing caller values.
`validate_credibility_crosswalk` rejects any issue. A successful result means
only that the exact represented links are structurally supported. Its
`certifies_scientific_adequacy` value is permanently `False`.

MMS has an additional hard boundary. It may support only implementation
verification, discretization convergence, reference agreement, or limiting
case behavior for the manufactured problem. It cannot support target-
population adequacy, model-form/physical validation, customer context of use,
product qualification, production qualification, or LIVE activation.

## 6. Report and disclosure

The deterministic Markdown report has explicit audiences `PUBLIC`,
`INDEPENDENT_REVIEW`, and `CARBON_PRIVATE`. Each source declares its maximum
disclosure tier. The report exposes only allow-listed opaque identities and
closed statuses. A lower-tier report retains the claim row but renders an
unavailable source as `WITHHELD`; it never leaks the hidden identity through
content, errors, logs, object representation, or exception chaining.

Reports identify the Challenge, Dossier/crosswalk identity, structural
validation outcome, claim support status, evidence category/kind/maturity,
owners, limitations, and unresolved-input counts. They always state that the
crosswalk is not scientific, security, commercial, product, production, or
LIVE qualification.

## 7. Human-reserved and deferred work

Independent scientific reviewers decide evidence adequacy and interpretation.
Counsel or standards specialists approve any future compliance claim. Physics,
statistics, protocol, security, product, commercial, and launch owners retain
their existing decisions. This contract adds no thresholds, evidence weights,
scientific verdict, standard-compliance assertion, signer authority, registry
mutation, campaign execution, B-07 service behavior, or LIVE path.
