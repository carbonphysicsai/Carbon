# Public Graphite test model retention

This optional local test mechanism applies to Launchpad's Graphite miner edition
for the battery DEVELOPMENT Challenge, through `battery.campaign.compose` and
`BatteryPractice`. It never uploads weights, changes an official worker, or
admits a model to ScoreLab. Default campaigns and existing CPU/JAX-GPU/Torch-GPU
program identities remain unchanged. Both GPU variants have source-level
applicability; actual CUDA retention requires Root's runtime evidence.

Before launching a **new** Root-owned public test campaign, Root places this
owner-only UTF-8 JSON file in that campaign's actual root directory:
`public-model-retention-opt-in.json`.

```json
{
  "schema": "carbon.battery.public-model-retention-opt-in.v1",
  "campaign_id": "REPLACE_WITH_ACTUAL_NEW_CAMPAIGN_ID",
  "scope": "PUBLIC_GRAPHITE_TEST",
  "program_version": "carbon.battery.public-graphite-model-retention.v1",
  "source_commit": "REPLACE_WITH_ACTUAL_40_CHARACTER_SOURCE_COMMIT"
}
```

There is no new CLI flag or public API request field. Root uses the existing
launch command/profile and binds the file to that command's exact campaign ID,
source/image release and owner. The launch freezes this descriptor under
`public_model_retention` in `campaign-manifest.json`; attachments and resumes
use that frozen descriptor, regardless of a later local marker. A marker cannot
retrofit an old campaign. Wrong agent/Challenge/owner/scope/version, extra fields,
symlinks and oversized marker files are refused. A `source_commit` is the
operator's declaration: the sidecar independently hashes every staged byte and
the actual program. Root must verify the source/image relation at execution.
The existing Launchpad launch identity is deterministic: `run_id` is the first
32 hexadecimal characters of the SHA256 of canonical JSON
`[profile.principal, request.idempotency_key]`; the directory is
`profile.campaigns_root/run_id`, and the campaign ID is `cmp-` plus `run_id`.
Root can therefore stage the named opt-in before the existing launch request;
no supervisor race, new public request field or new launch harness is needed.

For each callback invocation, an owner-only workspace record appears before
compile, named `trial-<identity-hash-prefix>-public-model.json`. It begins
`INCOMPLETE / NOT_RETAINED`. Compile/backend/run failures stay in that roster
with their stage and exception type, without changing infrastructure failures
into scientific failures. Calls refused before reaching the practice callback
remain in the existing research task/operation ledger; Root includes those
records in the complete campaign export. Winner selection never filters the
practice inventory. `selected: null` means selection is not asserted here;
Root binds actual selection from the campaign ledger in its export.

A successful opted-in worker writes `state.npz` with the existing
`recipes.state_bytes` format, plus `model-retention.json`, beside the existing
predictions/fit/runtime files. The carrier's existing output parser, 128 MiB
output bound, retained-byte admission/accounting, isolation and cleanup apply.
The state is additionally limited to 64 MiB. An over-bound or unserializable
state fails the opted-in worker; it is never reported as retained. Model bytes
remain in the operation snapshot, with no second model copy in the workspace.
The producer does not load untrusted weights on the trusted controller.

The sidecar binds compiled recipe, seed, parameter hash, exact serialized-state
hash/size, TRAIN/OCV/public-input/staged-code hashes, program version/hash, image,
runtime package inventory and measured fit/prediction/retention cost intervals.
Host-process CPU seconds are not GPU cost or complete multi-process core-seconds.
The inventory links the sidecar, original fit/predictions, feedback summary and
observed backend. These are separate recipe, parameter and state identities.
The original inputs are `c1,c2,t_amb_c,soc0`; original trajectory/quantity semantics
are recorded. These models do not acquire missing cooling/switch outputs.

Root extracts the original accounted operation snapshots and workspace inventory
through existing owned artifact handling. `public_model_retention.inventory`
reads every callback record without loading a model. Root supplies the actual
directory, source/image verification, all trial/selection/task statuses and
file byte hashes to ScoreLab. The consumer can load NPZ with the existing
`recipes.model_from_bytes` / backend inference path, with pickling disabled and
without refitting. Serialization is not security acceptance. ScoreLab verifies
observer/condition/quantity compatibility before any truth join or measurement.
The frozen18 cohort is unchanged. No reference acquisition or hidden/EVAL read
is part of retention. Historical original weights remain `NOT_RETAINED`; a
recipe or parameter hash cannot replace an absent original serialized artifact.
