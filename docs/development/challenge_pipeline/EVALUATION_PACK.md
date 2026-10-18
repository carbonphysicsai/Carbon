# Challenge evaluation data (DEVELOPMENT)

Keep one operator-edited `evaluation-pack.json` under each Challenge's
validator-owned directory, for example
`<private-root>/synthetic-linear-field-2d/evaluation-pack.json`. The trusted
receiver configuration selects this file, Challenge ID and Challenge version.
At admission, `prepare_pack` reads this one editable draft, derives artifact
hashes, and returns fully pinned bytes. The receiver retains those bytes
write-once in its existing private artifact store, records their digest in
the run registration, and calls `load_pack` on the retained snapshot. An
operator edits one manifest and runs the normal validation/admission flow;
they do not copy hashes into a second form.
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
    "score_pack": "HUMAN_INPUT",
    "source_registration": "HUMAN_INPUT"
  }
}
```

`source_registration` is an optional private role in this still-prospective
v1 manifest. The original four-role private manifest remains valid and keeps
its exact byte identity. Omission or `HUMAN_INPUT` means the normal scoring
source is unavailable; it does not prevent pack selection, construction, or
task retention. Unknown roles still fail admission. The role must reference
an owner-private artifact by relative path, never an inline object or a miner
path. `prepare_pack` pins its SHA-256 from the file without asking the operator
to copy a digest into the draft. The pinned artifact has this closed envelope:

```json
{
  "schema": "carbon.challenge-evaluation-source-registration.v1",
  "evaluation_version": "<explicit owner-registered version>",
  "trusted_job": {"<existing trusted job fields>": "<owner-supplied values>"},
  "benchmark_registration": {"<existing benchmark v3 fields>": "<owner-supplied values>"}
}
```

`snapshot.read_source_registration(private_root)` reads the exact pinned
artifact and validates only the envelope. The trusted normal caller must
validate the job against the retained task and selected construction material,
re-register the benchmark document with the existing benchmark validator,
check its computed digest and identity, and derive the one static query from
the verified `case_bank` bytes. A manifest label or fixture registration does
not provide those proofs. No population, case weight, timing profile, job
identity, reference rule, or evaluation version is synthesized. This role is
never included in `public_projection()` or a miner result. A dynamic
`HiddenBatchStore` remains a separate Challenge-specific adapter, not a
fallback to this static query path.

Replace a role with `{"path":"relative/file"}` only when the underlying
existing artifact and its own contract are known. Paths are relative to a
trusted public or private artifact root supplied by the caller.
`prepare_pack` calculates the role's SHA-256 from the actual file and writes
`{"path":"relative/file","sha256":"sha256:..."}` into the returned
**sealed bytes**, leaving the editable draft alone. A stale `sha256` in the
draft is refreshed for a prospective run. `load_pack` accepts only a sealed
manifest with all provided roles pinned. It checks each role on every read;
downstream consumers still use their existing interface, physics, measurement
and ScorePack validators. A digest match does **not** qualify the science.
Small public definitions (`construction_kit`, `interface`, `physics_contract`,
`accuracy_definition`, `important_limit_definition`, `design_objective`) may
instead be edited directly in the one manifest as
`{"inline": {"existing": "contract fields"}}`. `prepare_pack` derives the
inline digest automatically and the sealed snapshot retains immutable encoded
bytes. TRAIN, case banks, reference rows, solver evidence and the exact-byte
Score Pack cannot be embedded this way. The inline object must still satisfy its existing
contract-specific parser when the receiver uses it; this loader never
interprets or invents physical values.
`case_bank` may instead be `{"kind":"hidden_batch_store"}`. The validator
supplies its existing `HiddenBatchStore` and separately records the selected
batch fingerprint and references digest in the run. `resolve_hidden_batch`
requires those exact run pins, `COMPLETE` state, matching Challenge identity,
and the stored document/reference digests. This avoids copying or hashing a
mutable SQLite database as if it were an immutable case snapshot. A sealed
pack may also contain a fixed fingerprint and references digest for a
deliberately static development batch.
`snapshot.run_bindings_required()` names a dynamic `case_bank` until those
run-specific pins have been selected and checked; storage availability alone
does not make the run ready to score.

`prepare_pack(root, relative_path, public_root=..., private_root=...,
challenge_id=..., challenge_version=...)` returns `sealed_bytes` and a parsed
snapshot. The trusted caller retains `sealed_bytes` write-once and records
`snapshot.manifest_digest` automatically. `freeze_pack` is a narrow helper for
an already fully pinned manifest.
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

For JSON roles, `snapshot.read_json_role(root, scope, role,
max_bytes=...)` applies the same verified read and strict decoder, including
typed duplicate-key, nonfinite and malformed-input refusals. The consumer
still applies the role's existing semantic validator. Use `read_role` for an
exact-byte Score Pack so its established loader controls parsing and pinning.

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

For a selected pack and an actual registered private evaluation, the trusted
operator path calls
`carbon.scoring.private_evaluation_source.build_pack_source_receipt` with the
retained `EvaluationPackSnapshot`, saved graph entry, trusted job, registered
cases, actual reference rows and ordered original query bytes. It returns v2
private source-receipt bytes and their SHA-256. The operator stores those bytes
write-once and independently registers their digest; the existing private
evidence binder verifies the exact source and selected pack pin. This helper
refuses missing material used by this v3 source route or a selected TRAIN
digest that differs from the trusted entry. The public
`accuracy_definition`, `important_limit_definition`, and `design_objective`
roles are informational until an actual scoring core consumes them; their
`HUMAN_INPUT` status does not gate v3 source emission or imply an applied
rule. The validated ScorePack and benchmark registration define the applied
v3 rule. The normal caller must also reload and verify the selected
role bytes against the actual construction, case, reference, solver and
ScorePack materials; a matching Challenge ID/version and manifest digest
alone do not prove that relationship. Missing role-specific provenance is
typed source unavailability. The helper does not select a pack, run a solver,
expose private rows publicly, score a candidate or make the source receipt
authoritative by itself. The legacy
no-pack v1 source path keeps its historical meaning.
