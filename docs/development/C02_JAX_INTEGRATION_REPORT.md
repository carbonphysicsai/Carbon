# C-02 JAX development integration report

**Scope:** bounded offline DEVELOPMENT engineering only
**Primary map:** `WAVE-C/C-02`
**Current profile:** `carbon.c02.jax-development-profile.v2` (the v1 snapshot is retained)

## Outcome

Carbon now has a lazy, package-local adapter for the supplied
`carbon_jax_lab` 0.1.0 implementation. It consumes only a compiler- or
decoder-verified `ResolvedConstructionPlan`, initially supports the real FNO
path and a second real DeepONet family through the same interface, uses only
public TRAIN archives, consumes all 32 bytes of an A4 `DerivedSeed`, and emits
immutable job/plan/profile/data/seed/checkpoint-bound artifacts. Reloaded
prediction accepts no target labels and preserves requested-time order.

The continuation hardens the artifact boundary and adds a bounded repeat
runner. It does not select a production repeat count: the runner accepts only
an already-frozen set of B-02C `BoundReconstructionReplicate` identities and
already-issued C-01 `ExecutionAttemptRef` values.

This is not an official reference, score, grade, reward, qualification, public
network, production, or LIVE path. C-03 isolation and the later C1 scientific
and evidence chain remain outside this change.

## Source intake and provenance

- Supplied wheel:
  `sha256:3941af49fb7441b9ee37408db2b759bdc65088f0bda089f2a774adc3506935db`.
- The extracted wheel source and `RECORD` were checked against the supplied
  `INPUT_MANIFEST.json` and `INPUT_VERIFICATION.json` before integration.
- Supplied current test record: 50 passed, 2 failed because the distribution
  omitted `third_party.transolver_reference`; the earlier historical record of
  52 passed is retained as a separate claim.
- PR #146 repaired source identity remains historical evidence. The prospective
  v2 source identity is
  `sha256:385c7d0b5908257f1828228f5a1906fae5bb96c4a26c3b834108883b082d247f`.
- Bundled MIT notices for Transolver and NeuralOperator are retained under the
  vendored package. The new NumPy Transolver test adapter identifies pinned
  upstream commit `75e0f67643806a81cd1d3f6adc88dd8c02416fe7` and is not presented as
  upstream code. Installed source evidence records `Physics_Attention.py`
  SHA-256 `f7feffd40e21863a2bd5809d9548a3417a7221a817f9e675ea969712c1d45a36`
  and LICENSE SHA-256
  `2c919cd03fa823bf7eefc00a957ff8324c865cd22aa5285e563dc4b558084f25`.

## KEEP → WRAP → REPAIR → REPLACE

| Disposition | Content |
|---|---|
| KEEP | All six functional model families, optimizer equations, public trajectory contract, predictor, PR40 parameter bridge, and source-defined timing separation. |
| WRAP | Exact Strategy compiler plan mapping, public TRAIN archive descriptor, A4 seed adapter, C-01 execution-attempt binding, immutable artifact manifest, strict resume, and target-free prediction receipt. |
| REPAIR | Full-width 32-byte PRNG derivation; checkpoint runtime-seed binding; duplicate/extra/symlink/path/encryption/size/type/shape/nonfinite rejection for JSON, NPZ, and trajectory archives; package notices; exact dependency bounds. |
| REPLACE | The omitted PyTorch attention helper is not reconstructed from memory. A declared independent NumPy equation adapter restores the pinned forward and directional-gradient comparison without adding Torch to the required lane. |

Formatting-only changes were applied across the vendored Python files so the
repository's canonical formatter can validate them. The wheel digest remains
the provenance identity; the repaired source digest is the execution identity.

## Exact environment and interfaces

The canonical acceptance environment is Linux x86-64, Python 3.11, JAX and
JAXlib 0.9.0.1, NumPy 2.3.5, SciPy 1.17.0, and PyYAML 6.0.3. Its semantic pin
is `sha256:b74ca853cf2f0db808a14b034ae1ca1c8373a828fbc6baab125019e17eb7495d`.
The repository `uv.lock` remains Linux-only and the CI `science-jax` group is
required on canonical and clean-image acceptance.

The native Apple-silicon diagnostic is deliberately separate:
`requirements/jax-macos-arm64.lock` is a hash-locked Python 3.11 CPU profile,
installed only into `.venv-jax-macos`. The doctor requires Darwin arm64,
Python 3.11, at least 5 GiB free disk, and importable exact dependencies. It
needs no credentials and modifies no global environment. Canonical acceptance
remains Linux; a Mac pass is only developer diagnostics.

Input interface: public finite floating arrays `u0[case,point]`,
`nu[case]`, `t[case,time]`, `y[case,time,point]`, and `x[point]` on one shared
endpoint-excluded uniform periodic grid. Output interface:
`prediction[case,time,point]`, finite float32, in exact requested-time order.

## Actual native development run

On Apple arm64 with Python 3.11.16 and CPU JAX/JAXlib 0.9.0.1, the initial
two-update FNO job completed, saved a checkpoint, reloaded it in the inference-
only path, and produced a finite `[2,2,16]` result. Observed component timings
were 0.9785 s compile, 0.0189 s train execution, and 0.1364 s reloaded
prediction. These are one local DEVELOPMENT observation, not a benchmark or
capacity claim. The final rerun produced artifact digest
`sha256:73cbabc4e829fe2cda2d96506d53988d371f5394ba81e9fbfcb6d7489628c35d`,
checkpoint digest
`sha256:a0547d58fd72f679eb01acf109e2f39491e107dc9dcdb7b34ea9679f8fba68e1`,
and prediction digest
`sha256:13e592dafcdfc7ca35c574f599e6ec2a75bea70b299664c242015a8ee6c368f5`.

## Test coverage

- CPU: exact compiler mapping for FNO and DeepONet, non-plan rejection, lazy
  JAX/NumPy imports, source digest/notices, wheel and outside-tree imports.
- Science: finite forward and parameter gradient for all six families; FNO and
  DeepONet update/checkpoint/reload/predict via one outer interface; arbitrary
  requested-time order; full-width seed and exact direct plus outer-service
  resume; strict checkpoint rejection; PR40 bridge round-trip; independent
  Transolver forward and directional-gradient comparison.
- Existing Carbon invariant, package, full CPU, Hub, canonical Linux, and clean
  image lanes remain required before merge.

## Hardening findings F1–F4

- **F1 reproduced and repaired.** A digest-altered outer receipt was accepted
  far enough to load its named checkpoint because only selected fields were
  compared. One shared validator now checks the full outer tree, receipt,
  manifest, checkpoint, configuration, source/environment, TRAIN fingerprint,
  full key, normalization, optimizer/step, status and inference-weight
  association before restore. Compatible wrong checkpoints and stale outer
  claims reject.
- **F2 reproduced and repaired.** Computed NaN/Inf, wrong-shape and wrong-dtype
  outputs previously reached the generic request-error path. The completed
  boundary now checks exact `[case,time,point]` float32 and finiteness; fp64
  inputs that overflow fp32 reject; the endpoint-excluded grid is checked;
  arbitrary time order remains supported. Request, nonfinite output, output
  contract, numerical failure and unavailable runtime have distinct stable
  codes, while process interruption propagates. Ordinary prediction accepts
  only `COMPLETE` artifacts.
- **F3 reproduced and repaired.** Receipt timings previously admitted NaN and
  positive infinity, and loaded JSON used scalar coercions. Constructors and
  manifests now require exact finite floats, exact non-Boolean counters,
  closed status/step combinations and closed checkpoint metadata.
- **F4 confirmed and repaired.** GitHub rejects the former SHA with no commit;
  the corrected immutable revision and file/license hashes above are retained
  in package data. The test remains a Carbon-authored NumPy equation adapter
  used for forward and directional-gradient comparison—not an executed
  upstream PyTorch implementation or independent institutional validation.

## Bounded repeat and recovery demonstration

The fixed local fixture freezes three replicas per admitted backbone before
execution: two complete builds with distinct A4-derived key material and one
declared cancellation. Training data and the target-free prediction request
are common. Each replica binds Strategy plan, research-resource policy,
resource class, replica identity, C-01 attempt, randomness, TRAIN archive and
request. Resume continues the same replica; it is not a fresh build. Plan and
outcome files are immutable, one-writer, fsynced local records. A recordless
artifact reopens as `RECONCILIATION_REQUIRED`; completed, cancelled and failed
members are never silently resampled or extended.

Native Apple-arm64 observation on 2026-09-13, concurrency 1:

| Backbone | Complete / required | Retained incomplete | Total wall | Process CPU | Conditional mean pointwise sample SD |
|---|---:|---:|---:|---:|---:|
| FNO | 2 / 3 | 1 cancelled | 5.5700 s | 12.4421 s | 0.00293151 |
| DeepONet | 2 / 3 | 1 cancelled | 2.1961 s | 6.2241 s | 0.000142607 |

Those dispersion values describe only the successful subset on one authored
numerical fixture; the fixture is not asserted to solve Burgers. With fewer
than two completed replicas the report returns unresolved, never zero. No
threshold, winner, repeat recommendation, independence claim, score, result or
reward follows. Re-running the same output directory completed in 1.5 s and
created no additional replicas, attempts or predictions.

## C-03 decision handoff (proposal only)

For owner/security review, the smallest first DEVELOPMENT profile is one
trusted host running pinned worker code with untrusted declarative parameters
and arrays, CPU-only local resources, no outbound network, bounded scratch and
output, and no validator keys, protected EVAL/reference assets or signing
credentials. The worker needs authorized TRAIN inputs and one replica's
derived reconstruction randomness—not A4 master entropy, protected EVAL
seeds, answer keys or signing material. Host-root corruption and hardware side
channels remain outside this proposal unless an approved mechanism covers
them; a JAX function or checkpoint hash is not a sandbox.
JAX's current [security considerations](https://docs.jax.dev/en/latest/security.html)
also state that several coordination/collective connections are unauthenticated
or plaintext by default and rely on external network controls; this reinforces,
rather than replaces, C-03's required isolation evidence.

One grouped MQ-015 decision is still required: named threat actors and trust
boundary; execution image and hardware class; source-owned CPU, memory, wall,
PID and output limits; filesystem and network controls; cancellation and
descendant cleanup; audit evidence; and accepted residual risk. C-02 now
provides the validated adapter prerequisite and optional repeat composition.
C-03 must be selected, implemented and security-accepted separately before
its resource envelope can satisfy full C-02 completion.

## C2 and downstream dependency status

| Successor | Status after this change | Still required |
|---|---|---|
| C-03 isolated worker | Unblocked by C-02 source/interface availability, but not selected or implemented | MQ-015 hostile-worker threat-model decisions, resource limits, isolation and security acceptance |
| C-04 real reference | Still blocked | Authorized/qualified Julia/SciML primary and independent witness, solver configuration, applicability and uncertainty |
| C-05 measurement/score composition | Still blocked | C-04 plus human-approved comparison, thresholds, populations and uncertainty policy |
| C-06 signed result | Still blocked | C-05, signer/custody policy and real provenance |
| C-07 orchestration | Still blocked | C-03 through C-06, retry/cancellation/reconciliation operations policy |
| C-EA2 real archive | Still blocked | Implemented real C1 lifecycle and human-approved real archive profile/acknowledgement |
| C-08 miner MCP | Still blocked | C-07, authenticated operational policy and current A9 boundary integration |
| C-09 publication | Still blocked | Qualified signed result, real archive acknowledgement and current A10 publication policy |
| C-W1 / C2 testnet | Still unselected and blocked | Exact retained G2 scope, C-07/C-09 completion, security/science qualification and owner public-network authorization |

The implementation therefore resolves the previously missing JAX
source/interface prerequisite but does not imply that any downstream ticket is
safe to activate.

## Commands

```bash
./scripts/dev/setup_jax_macos.sh
.venv-jax-macos/bin/python scripts/dev/jax_macos_diagnostic.py doctor
.venv-jax-macos/bin/python scripts/dev/jax_macos_diagnostic.py smoke
.venv-jax-macos/bin/python scripts/dev/jax_macos_diagnostic.py repeat-demo /new/output/directory
PYTHONPATH=tests/cpu .venv-jax-macos/bin/python -m pytest tests/science -q
CARBON_UV_GROUPS="chain archive science-jax" ./scripts/dev/ci.sh
```
