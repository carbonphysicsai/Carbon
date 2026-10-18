# Challenge evaluation data (DEVELOPMENT)

Keep one operator-edited `evaluation-pack.json` under each Challenge's
validator-owned directory, for example
`<private-root>/synthetic-linear-field-2d/evaluation-pack.json`. The trusted
receiver configuration selects this file, Challenge ID and Challenge version.
At admission, `freeze_pack` computes the exact-byte SHA-256 digest and the
receiver persists it in the run registration. The run then calls `load_pack`
with that recorded digest. An operator edits one manifest and runs the normal
validation/admission flow; they do not copy a digest into a second form.
Miner requests never select a manifest path, digest or artifact root. Do not
put a private manifest, case IDs, reference rows, answers or custody paths in
the repository or a public Challenge kit.

The manifest is a small index over existing material, not another bank or
scorer. Its complete shape is:

```json
{
  "schema": "carbon.challenge-evaluation-pack.v1",
  "challenge": {"id": "<registered Challenge ID>", "version": "<version>"},
  "pack_version": "<prospective operator version>",
  "public": {
    "construction_kit": "HUMAN_INPUT",
    "interface": "HUMAN_INPUT",
    "train": "HUMAN_INPUT",
    "physics_contract": "HUMAN_INPUT",
    "accuracy_definition": "HUMAN_INPUT",
    "important_limit_definition": "HUMAN_INPUT",
    "design_objective": "HUMAN_INPUT"
  },
  "private": {
    "case_bank": "HUMAN_INPUT",
    "reference_rows": "HUMAN_INPUT",
    "solver_evidence": "HUMAN_INPUT",
    "score_pack": "HUMAN_INPUT"
  }
}
```

Replace a role with `{"path":"relative/file", "sha256":"sha256:<64 lowercase
hex digits>"}` only when the underlying existing artifact and its own
contract are known. Paths are relative to a trusted public or private artifact
root supplied by the caller. The role bytes are checked on every read and
returned unchanged; downstream consumers must use their existing interface,
physics, measurement and ScorePack validators. A digest match does **not**
qualify the science. `case_bank` may instead be
`{"kind":"hidden_batch_store","fingerprint":"sha256:...",
"references_digest":"sha256:..."}`. The validator supplies its existing
`HiddenBatchStore`; the loader requires that batch to be `COMPLETE` and checks
its document fingerprint and stored reference digest. This avoids copying or
hashing a mutable SQLite database as if it were an immutable case snapshot.

`freeze_pack(root, relative_path, challenge_id=..., challenge_version=...)`
returns the prospective exact pin to the trusted admission caller.
`load_pack(root, relative_path, expected_digest=..., challenge_id=...,
challenge_version=...)` returns `EvaluationPackSnapshot`. Use
`snapshot.read_role(root, scope, role, max_bytes=...)` for an artifact, or
`snapshot.resolve_hidden_batch(store)` for the existing hidden batch. Both
refuse a missing or changed reference as `EvaluationPackUnavailable`; that is
not a candidate error or a zero score. `snapshot.public_projection()` exposes
only the public role names, availability and digests. It excludes private
paths, identities, answers and the full manifest digest. The validator retains
`snapshot.manifest_digest` with the exact run registration and result. An edit
requires a new external digest and prospective registration; old results keep
their old pack identity. There is no latest-file fallback.

At admission, call `snapshot.verify_available(public_root, private_root,
hidden_store=...)`. It verifies each supplied role and returns the sorted
`HUMAN_INPUT` roles still missing. The caller checks the roles required for its
specific evaluation and applies the existing artifact-specific parsers and
scientific contracts. `verify_available` is a storage/integrity check, not a
claim that the physics, accuracy definition, solver or Score Pack is adequate.

For synthetic linear field 2D v1.3, the existing
`carbon.challenge_kit.synthetic_linear_field_2d` construction material and
`synthetic_linear_field_2d_benchmark_source` provide the current public
interface, fixed TRAIN identity and synthetic physics/reference definitions.
The retained CR06 inference and the separately measured analytic reference
row can be bound as artifacts after their exact bytes are saved. The existing
benchmark Score Pack has a null accuracy ceiling; this remains
`PACK_NOT_READY`, without ranking. For motor, the existing
`carbon.challenge_validator.motor_source` family and `HiddenBatchStore` provide
the private batch/reference path, while its published Challenge contract and
scoring modules remain the owners of physical definitions. A motor manifest
must bind their actual exported artifacts and selected complete batch; this
file does not pick an envelope, limit, score weight or design value. These are
two different Challenge source patterns for the same manifest/loader, not
separate receiver implementations.

The loader is a source-level building block. The normal receiver and ScoreLab
must still be wired to the same trusted snapshot and existing scoring core.
Until that integration and relevant scientific inputs exist, a manifest alone
is not a working evaluation or a LIVE qualification.
