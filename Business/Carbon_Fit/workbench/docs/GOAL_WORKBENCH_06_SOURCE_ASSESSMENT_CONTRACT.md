# GOAL-WORKBENCH-06 source-assessment contract v1.0

## Status and scope

This document defines the detached `burgers-dynamics-public.v1` profile for one exact public Workbench question. It is a prepared contract, not a production Workbench reader, dispatcher, source-owner acceptance, scientific qualification, rights decision, execution record, score input, protected-use decision, or launch action.

The profile concerns the accepted `periodic_viscous_burgers_1d_v1` authoring path with active `Dynamics` and the exact retained `C05-PUBLIC-EVAL2-PERTURBED` public DEVELOPMENT fixture. It does not create a general capability registry. The Workbench consumer owner is `SYSTEM/BUSINESS-AUTHORITY`; the native contract domain is `WAVE-C/C-AUTH1`. The source-interface acceptance for this exact contract remains pending.

The immutable package is under `source_assessment/v1/`. Its manifest is `source_assessment/v1/manifest.json`. Production `carbon.goal-workbench.workspace.v0.6`, the standalone HTML, its import boundaries, and the C-05 fixture bytes are unchanged.

## Separate meanings

1. A capability declaration describes what the named implementation/template can express or consume.
2. An evidence relationship binds an exact artifact, fixed case, query, trace, claim, and lineage.
3. An applicability assessment is a scoped source claim with assumptions, exclusions, limitations, answered questions, and remaining reasons.
4. Claimed authorship is producer content. Origin verification is a separate consumer-derived receipt.
5. Scientific qualification is a different source-owned decision and is never inferred by this profile.
6. Rights, execution, scoring, protected use, and launch remain separate authorities and remain false.

An intent-preserved compiler result proves only the emitted authoring semantics within the accepted bridge boundary. The C-05 fixture proves correspondence with one retained public DEVELOPMENT artifact and its exact association. Neither fact establishes a suitable exam, target-population adequacy, live execution, independent review, customer suitability, rights, or owner acceptance.

## Records and byte identity

The package defines four closed schemas:

- `source-assessment-request.v1`: a minimal exact-snapshot question.
- `source-assessment-response.v1`: source facts, claimed issuer, scoped assessment, and an all-false authority ceiling.
- `source-assessment-profile.v1`: owners, source artifacts, trust rules, and the unavailable future authenticated route.
- `source-assessment-validation-receipt.v1`: consumer-derived detached validation and interpretation.

Request, source-response, and validation-receipt bytes remain separate. The producer never supplies the receipt's origin verdict.

Envelope identities use `UTF8_SORTED_KEYS_MINIFIED_JSON_LF_V1`: recursively sort object keys, preserve array order and scalar values, serialize as minified UTF-8 JSON, then append one LF. Exact source artifact identity uses SHA-256 over retained bytes without normalization. A canonical envelope digest never substitutes for an exact source-byte digest. Self-referential hashes are excluded: `content_digest` covers only the response `content`; manifests do not list themselves.

Malformed UTF-8, duplicate members, forbidden keys, unsafe integers, non-finite tokens, excessive nesting/size, unknown fields, unknown enums, changed bytes under the same identity, or an unsafe artifact path reject before output is written. A failed detached validation creates no receipt and mutates no Workbench state.

## Request meaning

The request binds:

| Field group | Source | Consumer meaning | Authority limit |
|---|---|---|---|
| Contract/profile versions | Contract v1.0 | Select exact closed semantics | Does not activate a reader |
| Handoff/request ID | Existing handoff conventions | Exact request lineage; fixture is exported but not dispatched | Exported is not sent or acknowledged |
| Job/design/revision/snapshot digests | Sealed public design snapshot | Exact content association, not revision number alone | Historical request does not update a changed design |
| Route/intended-use question | Workbench test-authored request | `ADAPT_SUPPORTED_CHALLENGE` question | Route is planning, not qualification |
| Requirement/trace/case/binding IDs | Existing Workbench and C-05 identities | Narrow claim and evidence scope | One fixed case is not population evidence |
| Dependency domains/reason IDs | State-integrity model plus source minimums | Cumulative review obligations | Omission cannot make native evidence current |
| Source target/artifacts | C-AUTH1 and exact retained source paths | Named recipient and facts to inspect | A module path does not prove owner authority |
| Permitted scope | Contract invariant | Public synthetic detached conformance only | No rights granted or customer transmission |
| Expected blocker/restart | Test-authored request | Exact decision needed to proceed | Does not fund, select, or execute work |

The design snapshot is sealed and separately hashed as exact artifact bytes and canonical content. A response to the same revision number with different content is stale/incompatible. Historical requests remain immutable records; a later request must receive a new identity and bind the applicable sealed snapshot.

## Response meaning

The response binds the originating request digest and all job/design/snapshot identities. It can report `DECLARATION`, `SCOPED_ASSESSMENT`, `PARTIAL_RESPONSE`, `UNSUPPORTED_SCOPE`, or `NAMED_BLOCKER`. It retains claimed issuer and role as unverified producer content until a future accepted consumer verifier establishes more.

The response carries field-level coverage, exact source-artifact identities, evidence/claim scope, assumptions, exclusions, limitations, answered/partial/unsupported/unanswered questions, addressed and remaining reason IDs, immutable supporting refs, explicit supersession, and a next decision or restart event. Unknown stays unknown. The response's authority ceiling is always false for origin authentication, owner acceptance, scientific qualification, rights, execution, score eligibility, protected use, and launch.

The checked-in response is deliberately test-authored. Its issuer is `GOAL_WORKBENCH_06_TEST_PRODUCER`, never a human owner. Its source-derived declaration says the accepted bridge emitted an intent-preserved public synthetic Burgers `Dynamics` DEVELOPMENT proposal. Its C-05 relationship says the exact fixture contains four measurements and six physics observations for one fixed case, all with unresolved limits/uncertainty. Its assessment answers technical expressibility, partially identifies retained context, and leaves scientific applicability, intended-use suitability, and rights unanswered.

`fixtures/field_provenance.json` labels each field group as copied source fact, bridge-derived fact, test-authored request field, test-authored expected response, or contract invariant. No owner-supplied assessment exists in the example.

## Origin and trust table

| Input | What can be established | What must not follow |
|---|---|---|
| User-imported JSON with a claimed owner name | A statement attributed by the submitter | Authenticated source ownership or approval |
| A file matching a pinned public fixture | Correspondence with those exact pinned fixture bytes | Live execution, independent review, or human acceptance |
| An artifact from the accepted local authoring bridge | The bridge's existing verified artifact/semantic facts | New source-owner assessment or qualification |
| A GitHub link or comment locator | A locator and reported status | Verified authority or permission to fetch/transmit |
| A future accepted authenticated assessment | Only the statement and scope its issuer is authorized to make | Global design qualification or unrelated rights |

The future authenticated route is `NOT_IMPLEMENTED`. Before it could exist, the source owner must accept the verifier owner, issuer-to-scope mapping, trust-anchor source, public fixture, and fail-closed behavior. A producer-supplied key, URL, `trustedSource`, or native provenance enum cannot be its own trust anchor. Verification failure must reject without a partial receipt or workspace mutation.

## Cumulative review interpretation

The detached preview adds a proposed source response without modifying the workspace. A later accepted consumer could address only named reason IDs within the exact request, source evidence, dependency domains, issuer authority, and snapshot scope. It must retain each reason's original identity, cause, revision, and source evidence.

A partial or unsupported response leaves unaddressed reasons pending. An authoring declaration cannot resolve reference accuracy, uncertainty, target-population adequacy, or rights. A technical confirmation cannot supersede a rights prohibition. An older response, editorial edit, or child revision cannot clear debt. Two conflicting source responses require explicit reconciliation; import order is not authority. Supersession must identify the earlier response and match exact scope while retaining history.

Even a future valid scoped applicability confirmation has qualification effect `NONE`. `SOURCE_OWNER_CONFIRMED` applicability must never project to `QUALIFIED_SCOPED`.

## Detached conformance command

From the repository root:

```sh
node Business/Carbon_Fit/workbench/tools/build_source_assessment_fixtures.cjs
node Business/Carbon_Fit/workbench/tools/source_assessment_conformance.cjs \
  --profile Business/Carbon_Fit/workbench/source_assessment/v1/fixtures/profile.json \
  --request Business/Carbon_Fit/workbench/source_assessment/v1/fixtures/request.json \
  --response Business/Carbon_Fit/workbench/source_assessment/v1/fixtures/response.json \
  --output-dir /path/to/new/output-directory
```

The output directory must not exist. The command reads only frozen public records and writes `validation_receipt.json`, `interpretation_preview.md`, and `output_manifest.json` after complete validation. It performs zero solver runs, training runs, network requests, or account actions. The reference implementation is test-owned and is not imported by the standalone application.

## Activation boundary

The current v0.6 generic response importer and routing model continue to reject source-owner authority claims and this candidate envelope. No ordinary workspace import can create source-owner confirmation or rights authorization. Production consumption remains unavailable until a later bounded ticket has the source owner's exact semantic/trust/fixture acceptance and implements a reviewed consumer without weakening cumulative review state.
