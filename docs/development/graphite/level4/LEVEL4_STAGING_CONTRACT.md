# Level 4 staging contract (v1)

**Status.** Development and testnet only (OWNER-L4-G5-COMPILE-ISOLATION-01).
Written once, by the Level 4 engineer, for the two sessions that build
against it:
- the Launchpad's Level 4 slot (LAUNCHPAD-LEVELS-01 S3), which sends;
- the validator's `v2-ladder-l4` slot (VALIDATOR-25), which receives, stores
  and stages.

**The reference implementation is `carbon/level4/staging.py`**, with tests in
`tests/cpu/test_level4_staging.py`. Both sides call it rather than
re-implementing this page; if the page and the module ever disagree, the
module is right and the page is fixed.

**It closes** the development Level 4 rebuild blocker
`level4_submission_documents_not_staged` (`carbon/battery/level4_worker.py`).
That happens once both slots carry a submission's bytes to the rebuild
worker in the workspace form below.

## 1. What a submission is

- A **manifest**, `carbon.development.level4-submission.v0`, plus the
  **documents** it names: `forward`, an optional `loss`, and exactly one of
  `init` (a graph) or `init_spec` (a declaration). See
  `carbon/level4/submission.py`.
- **Canonical bytes.** Every file is JSON with sorted keys, no whitespace
  and ASCII escapes (`submission.canonical`). The miner's tooling writes
  them; nobody re-serializes them afterwards.
- **Document name.** `sha256:<hex>` of the document's bytes.
- **Submission digest.** `sha256:<hex>` of the manifest's canonical bytes.
  This one string is the submission's identity. The strategy carries it in
  the Challenge's Level 4 graph field: battery's `composition_graphs`
  (`battery-l4-graph-v1`). The strategy is what the miner signs, so the
  signature covers every byte through the digests.

## 2. Three forms, one content

| Form | Where | Layout |
|---|---|---|
| **Directory** | the miner's machine; written by `python -m carbon.level4.tooling lower SPEC OUT --challenge ID --interface sha256:… [--batch N]` | `manifest.json` and one `<hex>.json` per document, where `<hex>` is the document digest without `sha256:`. Nothing else: no subdirectories, symlinks or other files. |
| **Envelope** | any JSON transport: the Launchpad slot to the validator's intake | `{"schema": "carbon.level4.staging-bundle.v1", "submission": "sha256:…", "manifest": "<base64>", "documents": {"sha256:…": "<base64>"}}`. Exactly these four keys. Base64 is standard, padded, with no whitespace, and one encoding per byte string. |
| **Workspace** | a rebuild worker's flat staging, beside the record `level4-graph.json` | `level4-manifest.json` and `level4-doc-<hex>.json` per document |

**Conversions** (`staging.py`):
- `read_directory` / `write_directory`;
- `envelope` / `from_envelope`;
- `workspace` / `from_workspace`.

Each conversion checks every name against its bytes and the submission
digest against the manifest.

## 3. Checks, in order, and who owns a failure

| Step | Where | Check | Failure |
|---|---|---|---|
| Transport | validator intake | the envelope's own size, against the transport bound (the validator's) | the transport's refusal |
| Structure | `staging.from_envelope` | four keys and the schema; names are `sha256:<64 hex>`; strict base64; each name is the digest of its bytes; the declared submission is the manifest's digest | `GraphRefused`: `staging_malformed`, `staging_schema`, `staging_name`, `staging_base64`, `document_digest_mismatch`, `staging_submission_mismatch`. **The candidate's.** |
| G0 sizes | `intake.intake` | the manifest, each document and the whole submission against `intake.BOUNDS` | `oversized_manifest`, `oversized_document`, `oversized_submission`. **The candidate's.** |
| G3 parse | `intake` → `_parse_worker`, isolated | strict JSON, canonical bytes, the manifest's documents exactly, roles and the allowlist pin (`submission.verify`) | `json_*`, `not_canonical`, `submission_*`, `role_mismatch`, `allowlist_version_mismatch`, `parse_deadline`, `parse_resource_limit`. **The candidate's.** |
| G4 | `validate.validate_submission` | allowlist, declared shapes, interface, batch, init data flow, caps | typed `GraphRefused` codes. **The candidate's.** |
| Store | validator | content-addressed by submission digest, the bytes as received, immutable | a storage failure is `FAILED_INFRA`, **Carbon's** |
| Stage | rebuild worker | `staging.from_workspace` against the record's submission digest | `StagingCorrupt` is `FAILED_INFRA`, **Carbon's**: the bytes already passed G0, so a mismatch here is never charged to the miner |

- **Unset bounds.** Every G0 bound is `HUMAN_INPUT` until the owner sets it.
  Unset, intake is `IntakeBlocked`, which refuses nothing on the miner's
  account. The proposed values are in `LEVEL4_VALUES_PROPOSAL.md`.
- **Infra failures.** A G3 worker that cannot start is
  `IntakeInfraFailure` (`FAILED_INFRA`).

## 4. What each side builds

**Launchpad (sender, S3 slot).**
1. Run the lowering CLI on the miner's machine.
2. Show the submission digest.
3. Put that digest in the strategy's Level 4 field.
4. Read the directory with `staging.read_directory`.
5. Send `staging.envelope(...)` beside the signed strategy.

It never re-serializes a document.

**Validator (receiver, `v2-ladder-l4` slot).**
1. Apply the transport bound.
2. Run `staging.from_envelope`.
3. Check that the declared submission equals the strategy's Level 4 field.
4. Run `intake.intake` (G0, G3) under the owner's bounds, then G4.
5. Store the bytes by submission digest.
6. At rebuild, stage `staging.workspace(...)` beside the record.

**Rebuild worker (Carbon).** The worker runs `staging.from_workspace` against
the record's `submission`, then G4 again, G5, G6 and G7.

## 5. Unchanged

- **Visibility.** This contract adds no disclosure: a submission's documents
  follow the existing submission artifact policy. Who may see a miner's
  graph is not decided here.
- **Not for miners yet.** Development variants are never served to miners.
  Opening Level 4 to miners is still a locked, released contract that the
  owners choose.
- **Versioning.** Any change to a form is a new schema version; v1 stays
  readable.
