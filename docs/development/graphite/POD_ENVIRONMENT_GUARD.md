# Graphite environment CI guard (PLT-33)

The small-job environment test preserves 8,000 characters below the registered
runtime cap (currently 108,000 under OWNER-POD-ENV-LIMIT-RAISE-01). It does not
exercise the separately declared 60,000-character
L4 submission transport budget. The added guard uses `RunPodPods._env` for
both JAX and PyTorch with small and full-L4-budget configurations. Its L4
payload is synthetic sizing material, not a valid submission or execution.

The CI test is `test_current_ship_fits_the_declared_l4_transport_budget`.
Failure names total characters, the CI line, cap, reserve and largest
variable. It runs as part of the normal CPU suite. The runtime refusal,
provider calls, reservation and pre-dispatch settlement paths are unchanged.

For an offline count and an optional public-source comparison, use:

```sh
python -m scripts.dev.exam_design.runpod.environment_guard --ref HEAD \
  --base-ref 97037df6d3bb76d81372fa22280322234c4fc2cc
```

Output contains counts and variable names only. It exits nonzero if a current
profile consumes the existing reserve or no configured public CA root is
present. The factory's existing omission of absent optional roots is preserved.
A Windows count without any CA roots is incomplete, not a passing
launch-readiness measurement. No provider, key, training or private data is
used. A pass establishes this declared transport budget, not every possible
strategy size, provider acceptance, or security qualification.

History uses exactly one current factory, scoring config, job and codec at
both source refs. Only the source snapshot and derived manifest differ.
Added/removed/changed-file counts, raw manifest bytes and carrier deltas
describe that controlled comparison. They do not reproduce deployed #991
or L4 incident environments, whose configurations are not established as
identical. No growth rate or replacement threshold is inferred from the
unlike incident summaries.

After PLT-29's merged upload transport, report schema
`carbon.graphite.environment-ci.v2` counts manifest anchor names and values
in `manifest_env_chars`. The legacy payload-only `manifest_carrier_chars`
and `manifest_compressed_bytes` retain their original meanings and are zero/
null when no inline payload exists. Comparison adds `manifest_env_char_delta`;
the old carrier delta still describes inline payload only. The frozen factory
fingerprint includes both upload helpers. Comparisons refuse changed schema,
registered limit, reserve or CI line as well as recipe/job mismatches.

Historical D1's 90,000 cap and 82,000 CI line describe the original base.
Current boundary tests derive the line from the actual registered cap and
unchanged reserve; this integration changes no provider or runtime limit.

Platform's PLT-29 owns moving the manifest out of the environment while
preserving its request anchor and per-file pins. This ticket leaves that
transport, the cap, reserve and existing closure test untouched. An over-
budget result remains a real dependency failure until the transport is
repaired; no successful host rerun or trim is claimed by adding the guard.
