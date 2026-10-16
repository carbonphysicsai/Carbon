# SCORELAB-GUARDED419-T128-WORKER-01

Status: IN_PROGRESS. Root delegated the missing T128 execution route on
2026-10-16 from normally merged main `0e7b2999d603d15c734451b053ef29f26d302276`.
The original `fc01a4407db8ee6fe5fef829dfa670041d9fbbd6` G0, T9 and CAL
source/records remain immutable. The diagnostic repair on a separate branch
is parked and is not a dependency.

## Working contract

KEEP the existing 128 exact input offers and literal role mapping in
`guarded419_t128.py`. WRAP its binding, prerequisite, manifest and delivery
APIs with one closed file-based CLI for a Root-selected partition 1 (60) or 2
(59). Reuse the existing bounded process-pool collection loop, solver worker,
truth provenance stamp, and CAL file constructor. The route loads actual T9
and complete nominal CAL15 from pinned public resource keys and authenticates
them before opening output or submitting work. A plain PASS, partial CAL,
foreign source, wrong role, anchor offer or mixed stage is refused.

The runner is a new module outside T128's frozen 13-file scientific inventory.
It has its own exact source hash in the invocation specification and must run
from the newly published execution commit, which is bound by T128's existing
`execution_binding`. Every existing scientific/worker file must match that
binding locally. The historical `fc01` T9/CAL identities remain original;
new T128 rows bind the new execution commit. No record is relabelled.

Each invocation uses a separately pinned closed file spec, prior T128 manifest
and raw chunks, and exactly one existing partition. Partition 1 starts with
an empty prior manifest. Partition 2 requires all 60 original partition-1
rows, with line/source/membership proof. No automatic continuation, retry,
TRAIN fit, EVAL access, stage release or qualification. Root owns pod selection,
external 2-CPU/90-minute/USD2 per-partition limits and the USD4 aggregate
ceiling; this CLI does not claim to enforce provider billing or wall time.

Raw records stream to fresh output; per-job `NOT_DISPATCHED`, `SUBMITTED`,
`FAILED_INFRA` and returned status are kept in an atomic native receipt with
raw/manifest/source digests. Interruptions retain partial bytes and a refusal
status. Any observed failed/malformed/tracking-incompatible row remains
visible and cannot create a success/release claim. A complete partition means
all offered rows returned; it does not mean scientific qualification.

The exact in-image entry is:

```text
python -B -m scripts.dev.score_lab.guarded419_t128_worker \
  --spec /work/t128-spec.json --spec-sha256 <raw-64-hex> \
  --public-root /work/public --records /work/records.jsonl --workers 2
```

The closed `carbon.scorelab.guarded419.t128-worker-files.v1` spec contains
`scope`, `partition`, pinned `binding` and `prior_manifest` resource entries,
`prior_raw_chunks` keyed by original chunk ID, an exact CAL `FILE_SPEC`
subdocument, independent binding/prior-manifest digests and the raw SHA256 of
this new runner module. Each `{path,sha256}` entry names a relative opaque
resource key under the declared public input root. Partition 1 uses
`delivery_manifest(binding,[])`; partition 2 uses partition 1's native
manifest and raw bytes unchanged. The new binding names the published runner
commit and all 13 T128 required source hashes. Root's upload map must include
this runner and every imported module. The receipt is
`records.jsonl.t128.json`; it carries the generated current manifest and raw
digest for independent T128 `validate_delivery` after collection.

Owned paths: this ticket, matching decision, one new runner module, and
exclusive synthetic tests. No edits to the 14 frozen `fc01` CAL scientific
sources, including the CAL module and existing worker/guard; no new provider
harness or physical/registration value.

Author validation is AST/format/lint/Git/source-hash only. Root runs focused
canonical tests, integration, CI, provider and merge. Maturity ceiling is
DEVELOPMENT software. Historical map_ref `SYSTEM/AGENT-EXECUTION`; Hub is
retired under OWNER-WORKFLOW-SPEED-01, with no change to placement or maturity.
