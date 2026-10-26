# Pool-graded sealed pack: schema and custody runbook (M3)

A pool-graded Challenge version (F08 1.6, F02 2.5, Motor 1.5, Cooling 1.5) grades a
model on its sealed cells and probes **and** on a pool of pre-solved designs that a
seeded optimiser searches through the model. This note is the exact shape the
pool rows take in the sealed bank, so a sealed pack and its per-validator copies can
be built in custody. It states structure only; no pool value, truth, constant or
policy is chosen here. Owner constants stay `HUMAN_INPUT` in
`carbon/scoring/pool_constants.json`; a pool version refuses to grade until they are
registered.

## What the pack carries

One sealed batch (`sealed-batch.json`: the A batch's document and terminal records)
plus the **pool material** under `document["pool"]`. The bank is rebuilt from that
batch by `sealed_batch_source.resolve`; nothing about the pool is in a public file.

Pool material (`carbon.pool.sealed-material.v1`), built by
`pool_version.material_from_set_dir`:

| field | meaning |
| --- | --- |
| `schema` | `carbon.pool.sealed-material.v1` |
| `kind` | the pool kind of the Challenge (`pool_version.KINDS`) |
| `version` | the pool version (for example `1.5`) |
| `input_names` | the model's input order |
| `design_names` | the design inputs (a subset of `input_names`) |
| `input_dtype` | the bank's input dtype (pool rows are quantised to it) |
| `set_digest` | digest of the pool set (given, or the hash of the pool documents' digests) |
| `sets` | list of groups; each group a list of `pool_grader.dump_pool` documents (digest-checked on load) |

## Bank rows added for the pool

Each distinct pool query is one bank row:

- **cohort** `pool_design` (`probe_design.POOL_COHORT`, equal to `pool_exam.POOL_COHORT`).
- **inputs** the target's fixed conditions plus the design, in `input_names` order,
  quantised to `input_dtype`. Identical queries (across targets) are one row. No row
  names its target.
- **case_id** `pool-` + first 16 hex of sha256(`carbon.exam-pool-row/1\n` + canonical JSON of the
  float input values) (`pool_version.case_id_of`): a function of the input content only.
- **record** `{"kind": "pool_design"}`; **reference** absent (NaN, `reference_present` false).
- **order** one seeded permutation over cells, private probes and pool rows
  together (`probe_design.with_probes(..., pool=rows)` appends pool rows after the
  probes before the permutation; the seed is the cell-input content seed, so every
  validator copy yields the same single interleaving). A model cannot tell a pool
  query from a cell or probe.
- Copies: `copy_derivation.canonicalize` treats pool rows as derived rows (sorted by
  content, or by id for a Challenge whose ids carry meaning); they are excluded from
  the shuffle cell inputs. `copy_package.canonical_batch` and per-validator
  `make_copy` carry the material unchanged and canonicalise to the same exam.

## Building the pack in custody

```bash
python scripts/dev/sealed_exam/pool_pack.py build \
    --challenge electric-motor-magnetics --version 1.5 \
    --batch-dir CUSTODY/<A batch dir holding sealed-batch.json> \
    --set-dir   CUSTODY/<phase-1 set dir with sets.json + pool-source-<tid>.json> \
    --out-dir   OUT --inference-image-id sha256:<image id> [--set-digest sha256:<digest>]
```

Outputs under `OUT`: `pack/` (the receiver pack; `sealed-batch.json` canonical, pool
included, beside the roles) and `record.json` (digests and row counts only). The
A batch must be the plain batch the predecessor version carries (no `pool` key);
Motor 1.5 / Cooling 1.5 reuse their predecessors' sealed batches, F08 1.6 / F02 2.5
likewise. Signing and per-validator copies are the Lead's `copy_issuance` step on
this pack; this script touches no key.

## Refusals to expect

- `pool_material_malformed`, `sealed_pool_material_mismatch` (pool on a non-pool
  version, or none on a pool version), `pool_inputs_do_not_complete_the_model_row`.
- `PoolConstantsNotRegistered` at grade time while any owner constant is `HUMAN_INPUT`.
- A pool store directory must be writable (SQLite WAL) at grade time.
