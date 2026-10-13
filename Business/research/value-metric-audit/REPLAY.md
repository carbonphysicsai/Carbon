# Replay the original RES-07 public analysis

**DEVELOPMENT research only.** The [Validator's source-publication request](https://github.com/carbonphysicsai/Carbon/pull/1218#issuecomment-6133571737) authorizes this follow-up in the same PR. No algorithm, historical result, physical limit, score registration or economics changes.

The [retained Python executable](res07-analyze.py.txt) is published byte for byte: 39,511 bytes; SHA-256 `e91f89f9cae53cd7b5e1f252910f197f8a0334adbf47e2bb492d7601dffa91ff`. It has the `.py.txt` suffix as an immutable historical source asset, preserving the exact measured source rather than reformatting or rewriting it. Python can execute the staged copy. The original code performs top-level analysis and writes results beside itself: **stage it outside Business before executing; do not run it in the publication directory.** It imports no Carbon package, solver or model, and makes no network call.

A clean checkout now supplies the executable and [source pin](source-pin.json). Both studies still require the explicitly public prediction/reference input copy and the original RES-08 rev-1 draft; publishing source does not publish those raw inputs. The old source is retained evidence, not production execution authority or a new scoring implementation.

## Original RES-07 staging contract

Use a new task-specific working directory, for example `tmp/res07-public-replay/`, with repository root as the current directory. Copy the asset to `tmp/res07-public-replay/analyze.py`, verifying its digest above. Stage these public files without modifying their originals:

| Staged path relative to repository root | Source | Required identity |
| --- | --- | --- |
| `tmp/res07-public-replay/source-pin.json` | This directory's source-pin.json | Pinned historical public provenance |
| `tmp/res07-public-replay/decision.py` | carbon/battery/value/decision.py at the [research pin](SOURCES.md) | LF-normalized Git blob `b1d899d116317bd190ad6812f0aae5d3e8a16c0c` |
| `tmp/res07-public-replay/ev4-contract.json` | EV4 contract linked in SOURCES | LF-normalized Git blob `3961b89a98c8877190bc010579852497057d3518` |
| `tmp/res07-public-replay/ev5-contract.json` | EV5 contract linked in SOURCES | Git blob `7cb89a3787a172427ae7024922a6e1641172eb91` |
| `tmp/res07-public-replay/refined.b64` | Base64 encoding of public refined-EV4 records bytes linked in SOURCES | Decoded bytes' Git blob `c2840676909bae6585e92402a3bc7b86d6b59c27` |
| `tmp/res02-public-inputs/ev4.json` | Public EV4 registered-results bytes linked in SOURCES | Git blob `67ca13b966a2f6fb4b2e68b084e2909657e7ba7f` |
| `tmp/res02-public-inputs/ev5.json` | Public EV5 registered-results bytes linked in SOURCES | Git blob `7d6ccf75a47c2df56c66d0b223300e5fd9398512` |
| `tmp/res06-physics-consistency/measured.json` | Public RES-06 measurements linked in SOURCES | Original retained copy SHA-256 `a320b9c7005b8c6ad21ee22958bc78baf4a20435677826a74ab9795f7c3f3b0e` |
| `codex-queue/inputs/ev4-public-proof/` | Owner-authorized read-only public folders described in SOURCES | Original reference SHA-256 and complete bundle manifest in results.json |

Do not substitute a changed contract or helper. Git blob identities apply to original committed bytes; native CRLF copies need LF normalization where specified. Base64 encodes the original compressed refined-record bytes, not decompressed text. If an explicitly public dependency is absent, obtain that public asset through the owner; never substitute a sealed pack, model artifact or new solver run.

```text
python -X utf8 tmp/res07-public-replay/analyze.py
```

The execution environment was CPython 3.12.14, NumPy 2.5.4 and SciPy 1.18.1. Original outputs are `tmp/res07-public-replay/results.json` and `derived-public-outcomes.json`. Keep all raw/intermediate files outside this publication directory and PR. Compare parsed aggregate results with committed results.json; native newline differences can change byte hashes without changing JSON values. This is a replay of the original public study, including its registered historical comparisons and exploratory sensitivities, never a fresh confirmation or rev-2 rescore.

## RES-08 replay

The RES-08 adapter now accepts this committed source directly, with the same required SHA-256. It defaults to adjacent helper/contract copies if present, otherwise the canonical checkout files; either must match the original pinned Git blobs. Optional `--reference-helper` and `--ev4-contract` arguments allow explicitly staged historical copies. See the [RES-08 replay instructions](../value-metric-v2-stress/README.md). No recorded result or parameter changes when source lookup changes.
