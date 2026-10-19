# Normal signed construction retry after infrastructure failure

Ryan requires the normal construction path to rebuild real backbones and custom
math graphs from fixed Challenge TRAIN before separate inert evaluation. Root
assigns this concrete lifecycle repair after actual CR03 signed replay returned
the original infrastructure-failed task even after the UV environment was repaired.

Starting base is PR1424 head199c45fa9/tree f8b7f526. Its useful CI remains on
that immutable public head while this separate behavior is implemented on
`codex/construction-infrastructure-retry`; no new checkout is required.

## Working decision and compatibility

Classify IMPLEMENTATION_LAG in DEVELOPMENT construction lifecycle. Preserve
ordinary submit/status and historical request keys, records and terminal states.
An explicit retry of an authenticated owner's FAILED_INFRA task creates one new
normal task for the exact same immutable candidate, Challenge kit, TRAIN,
interface, limits, measurement mode and selected evaluation pack. It does not
restart or overwrite the old task. No official A7 fee/retry-credit, settlement,
scientific failure, qualification or production semantics change.

The existing signed `construction_submit` tool accepts an optional closed field
`retry_of_submission_id`. A prospective `construction_retry` capability in the
existing public discovery document advertises its exact schema/field/eligible
state. The tools list and existing fields remain unchanged; clients without the
extension continue ordinary submission. A new client refuses explicit retry
when the receiver does not advertise this capability. The signed transport
binds the predecessor field and authentic owner/context normally.

Reuse Validator screening/outcome/attempt recording, LeanRecipeAdapter, the
existing DirectStartTaskRequestV3 and normal provider start/admission. A retry
request changes only its idempotency key to `lean-recipe-retry-<predecessor ID>`;
this auditable parent reference fits the existing key bound. One failed parent
has one idempotent retry child. The parent and every ancestor must be authentic,
same-candidate FAILED_INFRA records; a retry child may itself be retried only
after its genuine infrastructure failure. Do not add a blanket retry cap; existing
owner/provider storage, admission, resource, time and cleanup bounds still apply.

Require settled predecessor children through the existing ledger/reconciliation
semantics before admitting fresh work. Unknown, active, successful, refused,
cancelled, unresolved, mismatched and other-owner predecessors refuse without
new work. Repeated retries and concurrent calls for the same predecessor return
the same child, including after process restart or response loss. Preserve the
failed parent receipt/children and all old status queries.

Before fresh bundle retry, a bounded successful read-only Docker query must
establish that no Carbon UV-copy helper remains. This closes the legacy auxiliary
cleanup uncertainty that main-child terminal states alone do not establish. The
request never removes containers or reconciles workers; busy or unknown helper
state refuses fresh work. An already admitted retry child remains observable
without repeating fresh-admission checks.

Client retry uses a distinct retained attempt journal keyed by the same local
epoch plus the actual predecessor identity; the ordinary journal filename stays
unchanged. It records the predecessor
binding before observation and polls only the admitted child after admission.
Each actual ordinary/retry HTTP transmission uses a fresh signed transport
request ID. Durable candidate/attempt keys remain unchanged, so an admission
response lost before journal creation can be recovered by an explicit new call
without replaying a gateway receipt or creating duplicate tasks. Network errors
still propagate; this adds no automatic ambiguous-request retry.

It never silently turns polling into another attempt, mutates the recipe, resets
a database or blindly resubmits. Existing rate pacing/deadlines still apply.

## Plan, scope and validation

1. Reuse normal provider admission with explicit predecessor validation and
   durable identity, preserving historical records and child cleanup.
2. Thread explicit retry through the authenticated intake, existing screen/
   result envelope and adapter; validate ownership/status through the lineage.
3. Extend the maintained client and callers needed to expose the retry action,
   with unchanged defaults and exact capability checks.
4. Run canonical focused provider/intake/client, owner/context, replay/restart,
   concurrency, malformed/binding/resource/cleanup refusals; keep original
   failure records byte-stable. Then real fixed-TRAIN fresh construction,
   separate source-free inference, retained bank and independent rebuild.

Source authors use static checks; Product owns actual canonical/model/host work.
The initial baseline is actual CR03 replay of the same FAILED_INFRA task; focused
baseline validation on the immutable199 parent is requested from Product. No
parent test result is copied to this changed tree. Existing request identity and
worker isolation are KEEP/REPAIR; no new retry service or execution framework.

Primary domain is construction submission lifecycle. The Development Hub is
frozen under current delivery policy; no map edit or regeneration. Maturity is
SPECIFIED until source and tests land; implementation/static checks cannot earn
TESTED, security qualification, scientific acceptance, launch or LIVE authority.
Completion requires actual scope-required canonical acceptance and normal PR
review/merge. This ticket cannot be called complete from CI fixes alone.
