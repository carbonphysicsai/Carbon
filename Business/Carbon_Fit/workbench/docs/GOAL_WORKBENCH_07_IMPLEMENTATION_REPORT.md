# GOAL-WORKBENCH-07 implementation report

## Outcome

The v0.7 standalone workbench implements an operational, read-only source-assessment request and consumer path for the exact public Burgers/Dynamics profile. Its trust root is an application-installed repository snapshot, never a workspace/imported manifest. Request subjects are sealed and content-digested; accepted response bytes must match job, design, revision, questions, source identities, permitted issuer domains, exact owner-adoption reference, raw hash, canonical digest, and the current installed snapshot before an atomic receipt is committed.

The production approved index is deliberately empty. The prepared public statement has status `PENDING_EXACT_OWNER_ADOPTION`. The shipped app therefore exercises request preparation/export and fail-closed import, while the trust-positive path is proven only by an isolated `test_only: true` snapshot that production installation rejects.

## Owner policy and limited supersession

Decision `OWNER-GW07-RYAN-SNAPSHOT-01` records Ryan / `github:jbequ5` as final interface and verifier-policy owner. Harsh remains consultative when Ryan requests it. This supersedes only the old Harsh-only prerequisite for this source-assessment interface; it does not rewrite the Workbench-06 notification history, create a Harsh response, or move scientific, security, rights, spending, runtime, or launch authority.

The user-supplied direction is the provenance for implementation policy. It is not OAuth authentication or exact assessment adoption. The real candidate retains GOAL-WORKBENCH-07 Engineering as preparer and labels Ryan as claimed/proposed issuer; consumer verification remains unavailable until a separate exact adoption is admitted to a later repository snapshot.

The single public-safe adoption request was delivered to the existing Ryan owner inbox as [issue #41 comment 5680762605](https://github.com/carbonphysicsai/Carbon/issues/41#issuecomment-5680762605). GitHub reports the posting actor as `fitz-lang6`, not Ryan. The readback contains the exact request/assessment IDs and digests. Its state is posted and `PENDING_EXACT_OWNER_ADOPTION`; it is not an acknowledgement or adoption and will not be polled.

## Implemented boundary

- `src/source_assessment.js`: closed request/response/state parsing, canonical identity, installed-snapshot matching, replay/conflict/withdrawal handling, atomic import, workspace revalidation, and non-authoritative projection.
- `source_assessment/repository_snapshot/v1/`: Ryan-controlled profile, empty production index, schemas, deterministic candidate/test fixtures, manifest, and adoption packet.
- `src/workflow.js`: additive v0.7 workspace and v0.1–v0.6 migration. Historical Workbench-06 fixtures are never promoted.
- `src/goal_app.js`: normal freeze/prepare/export/import/inspect flow and installed-snapshot/as-of display. No network request, approval checkbox, trust-root import, or dispatch is present.
- `src/routing.js`: Owner Console uses the current source-assessment request to show exact-adoption waiting or scoped returned-answer review. A result is never active computation.

## Trust and custody limits

`MATCHED_APPROVED_SOURCE_SNAPSHOT` establishes correspondence to exact bytes and scope admitted in the installed Carbon build. It assumes a genuine accepted build and trusted repository/release administrators. It does not resist a malicious release administrator, altered application, compromised browser/host, or deliberate use of an older build. Offline operation cannot learn of later withdrawal until a newer accepted snapshot is installed. CODEOWNERS, green CI, a digest, link, or ordinary merge is not Ryan adoption.

## Source and evidence scope

No solver, training, measurement campaign, 72-member matrix, cell-7 study, witness study, protected workflow, chain transaction, or external account operation ran. The fixture builder replays the already retained public C-05 bundle through its exact reader solely to bind the historical case/result identity. Four measurements, six physics diagnostics, null limits and null uncertainty remain unchanged and unresolved. The accepted Workbench-06 `source_assessment/v1/` experiment remains detached test-authored material.

## Verification and delivery

The focused suite covers production-empty admission, isolated test-positive verification, wrong associations and semantic subject changes, raw/canonical identity, forged names/flags, test-root isolation, replay/conflict/withdrawal/supersession, partial answers, cumulative review, child history, save/reload revalidation, tampered cache rejection, v0.6 migration, and v1 rejection. A withdrawn or superseded installed record remains historical and cannot resolve a current review reason. After integrating current main, 225 JavaScript checks and 43 Python source/schema/bridge checks passed locally with zero failures or skips. Generated standalone Chrome journeys passed separately at 40, 29, 19, and 10 checks with zero page errors or external requests. Inherited engine, routing, F1–F7, workflow, C-05, Workbench-06/06A conformance, and rehearsal suites are included in those runs. Safari/WebKit was unavailable and is not claimed. Repository exact-head acceptance identities are added at delivery closeout.

Completion axes at report authoring:

- Engineering delivery: pending normal PR exact-head acceptance and merge.
- Source-assessment admission: `PENDING_EXACT_OWNER_ADOPTION`; production index contains zero records.
- Next action: Ryan adopts, changes, or rejects the single exact candidate in `candidate/RYAN_ADOPTION_PACKET.md`.

The prerequisite delivery boundary is closed without merging feature work into it. The dependency-light C-W1 invariant repair passed run `34967546351` and merged as PR #186 at `d3e285790f722d76270d517947a865d5e5c6bbb1`. GOAL-WORKBENCH-06A then passed its corrected exact-head contract lane in run `34971837843` and merged as PR #184 at `5b68da95580c659f8555d1f5a9caaddb049eb487`. Its corrected issue comment remains historical delivery by its actual API actor; no Ryan or Harsh response is inferred.

Authority remains unchanged: no scientific qualification, rights grant, fresh execution, score eligibility, protected reuse, official grade, reward, or launch.
