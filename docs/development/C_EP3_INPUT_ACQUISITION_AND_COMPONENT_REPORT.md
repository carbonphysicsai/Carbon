# C-EP3 input acquisition and public component report

## Decision

**COMPONENT_DATA_COLLECTED; SHARING_STILL_UNSUPPORTED.**

C-EP3 replaces one unknown with a scoped observation of an actual numerical
calculation. It does not supply the intended JAX reconstruction source,
compatible miner demand, common-comparison semantics, protected-reference
qualification or Variant-B control/recovery overhead. C-EP2's recommendation
therefore remains **COLLECT MISSING INPUTS FIRST**. The smallest useful next
investment is for the owner or Physics/SciML lead to supply the one immutable,
permission-cleared JAX source/interface package in the consolidated request so
existing C-02 can be considered for selection.

## C-EP2 closeout

PR #144's old replay incorrectly described its zero-overhead dynamic grouping
as a universal lower bound. The corrected module reproduces the required four-
job counterexample: zero overhead produces groups `[a]`, `[b]`, `[c,d]`, 38
work units and c/d release at 39; four assumed units per group changes the
endogenous grouping to `[a]`, `[b,c,d]`, 36 total units and release at 36.
Unknown B overhead now leaves actual work and release times unknown, while each
numeric synthetic overhead is an explicitly assumption-conditioned scenario.
Contradictory reference requirements fail closed. This correction did not
change the recommendation.

Corrected head `89f06eda74b15dd336e57a512f228c6b37cca77d` passed canonical
RUNTIME_FULL run `34718392697` and merged in PR #144 as
`96099aeac9e5022bda9d94730b1d7d955cb6c1d5`. The earlier queued run
`34715504603` was cancelled after the corrected head and was never counted as
acceptance. PR #140 remains open at its proposal head; issue #141 remains open.

## What C-EP1/C-EP2 already establish

The executable miner-facing policy remains the simple DEVELOPMENT Variant-A
loop: a separately admitted immutable candidate receives one durable private
child pack; copies, retries and replays keep that entitlement; evidence remains
private; and the permitted fixture summary appears only after durable closure.
C-01 still owns dispatch, retry and reconciliation. C-EP2 adds observation and
an offline replay, not sharing. C-EP3 does not import the public solver into that
path and does not touch candidate, pack, reward, accepted-result or production
owners.

## Input acquisition

| Missing decision input | What was found and measured | What remains unavailable | Smallest next owner action |
|---|---|---|---|
| Actual reconstruction source | PR #40 is only non-authoritative fp32 forward parity; the workbench declares public TRAIN array shapes but no JAX implementation. | Intended source/revision/rights/build, train/infer interfaces, state/checkpoints, RNG/data loader, JIT/hardware and failures. | Owner/Physics-SciML supplies the consolidated immutable source/interface package; then consider C-02 selection. |
| Numerical reference component | Verified public workbench ZIP and ran one archived source-defined Burgers audit case through ETDRK4, refinement, Cole-Hopf witness, diagnostics and NPZ round trip. | Adequacy, official identity, protected runtime/custody, production sampling/tolerances and integrated C-EP1 cost. | Treat this as C-02/C-04 authoring input only; scientific reference owner later decides whether C-04 research is warranted. |
| Compatible demand | No eligible real/miner submission trace exists; C-EP2 streams are authored scenarios. | Offered requests, canonical methods, admissions, compatibility at dispatch, censoring and adaptive rounds. | When a permitted service exists, freeze a bounded private collection period on the existing observation boundary. |
| B overhead/comparison meaning | Corrected C-EP2 replay and existing scientific/runtime owners were inspected. | Membership/seal/recovery work, per-member failures, last-member closure, TRAIN/EVAL decision, evidence depth, field-size and promotion rules. | Keep B cost unknown until source, demand and comparison rules support a separately authorized experiment. |

The machine-readable acquisition table records source and owner state without
treating missing demand as zero or a synthetic parameter as evidence.

## Public numerical component actually run

The source was the owner-supplied
`Carbon_Challenge_Authoring_Workbench_V1.zip`, SHA-256
`40f1fd47d62dd2269f8e141e6bb398d03a403aa6eb3ac08750b49dd68018bcdc`.
The archive contained 85 entries; all 84 manifest-governed files passed byte
count and SHA-256 verification. Its release digest is
`sha256:7805f87c3b4745454ec9c8fa852a20de6731d8f85e1356eb5d91a708cdafa7ac`.
The source is `PUBLIC_DEVELOPMENT_ONLY`, `SYNTHETIC_INTERNAL`, and explicitly
not scientifically qualified or runtime-integrated.

The frozen case is the first public `REFERENCE_AUDIT` row: source-defined cell
0, ordinal 0, harmonic family, low-Re regime, periodic unforced
positive-viscosity one-dimensional Burgers. The immutable archived case digest
is `sha256:ff69bc0b6f3ef4d556f0abde790b9aed89279f4dc7909eac32c4e156a0ee6f9d`.
It is one source-defined case, not representative evidence for every regime.

Hardware was one Apple M3 MacBook Pro with 8 CPU cores and 8 GB RAM, macOS
15.6 arm64, one configured numerical thread, and no GPU measurement. The local
environment used Python 3.11.11, NumPy 2.4.3, SciPy 1.17.1 and Pydantic 2.13.4.
Those versions lie inside the source-declared supported ranges, but they do not
reproduce its saved exact evidence lock (NumPy 2.3.5, SciPy 1.17.0, Pydantic
2.13.5). Public-network package installation was not authorized.

| Actually executed operation | Wall time |
|---|---:|
| Archive verification | 267.351 ms |
| Source extraction | 2.440 ms |
| Source import/initialization | 757.089 ms |
| Archived-case materialization | 0.824 ms |
| ETDRK4 primary, first/cold call | 297.089 ms |
| ETDRK4 primary, warm repeated calls | 288.438 ms; 289.821 ms |
| ETDRK4 refinement | 1,906.978 ms |
| Cole-Hopf witness, 1,024 / 2,048 nodes | 33.183 ms; 64.702 ms |
| Diagnostics | 51.978 ms |
| NPZ serialization / retrieval | 175.813 ms; 17.473 ms |

The six numerical calls consumed 2,880.211 ms wall time in total: three full
primary calls on the same case, one refinement and two witness calls. That is
one distinct physical case and six attempts, not six cases. The two warm
primary observations average 289.130 ms; two observations cannot establish a
production latency distribution or quantile.

The primary produced a `[193,512]` array in 2,752 source-reported ETDRK4 steps;
the refinement produced `[769,1024]` in 11,008 steps. Outputs were finite, the
three primary arrays were byte-equal, and the compressed NPZ round trip was
exact. Refinement, witness and five source-proposed physics diagnostics were
recorded. Their within-proposed-limit labels are source diagnostics, not
scientific qualification, continuum error bounds or customer-physics
validation.

### Retained generator replay defect

The first attempt correctly stopped before numerical work: redrawing the same
case under NumPy 2.4.3 changed last-bit floats and produced digest
`sha256:9db39226980bde62e42a7741eaedb5e03dd186f1bf4620a6eecad27fbc81d0ff`
instead of the archived digest. The failed record was retained. The successful
probe used the verified immutable archived case, whose stored content
recomputes to its claimed digest, and records the current-environment generator
replay mismatch. No digest was relabeled and no source code was patched.

## What could theoretically be shared

Only the reference calculation for an identical physical case could be a
candidate for reuse, and only if reference identity, sampling, evidence depth,
uncertainty, custody, disclosure and comparison requirements all match.
Candidate reconstruction, candidate inference, required repetitions,
candidate-specific evidence and TRAIN-role obligations remain per candidate or
under their own owners. This probe does not show that compatible jobs actually
co-occur, that A and B select scientifically interchangeable cases, or that the
measured public method is adequate for official truth.

Shared-pack feedback delay remains unknown because B is not implemented and no
eligible workload exists. C-EP2's model correctly says a fast candidate would
wait for the slowest unresolved member. No acceptable delay or timeout policy
has been invented.

## Verification and rerun

Focused C-EP3 tests cover archive/path/configuration mismatch, closed authority,
unknown-not-zero values, units/counts, privacy, retained failed calls, exact
cold/warm accounting, duplicate-output refusal and absence of runtime/sharing
imports. The unchanged C-EP1/C-EP2 focused suites are rerun separately. Final
canonical counts, CI, PR and merge status are filled only from the delivered
head; C-EP1/C-EP2 historical counts are not copied into C-EP3 acceptance.

```text
python -m pytest -q tests/cpu/test_c_ep3_reference_probe.py
python -m pytest -q tests/cpu/test_c_ep1_evaluation_packs.py tests/cpu/test_c_ep2_measurement_study.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  python scripts/dev/run_c_ep3_reference_probe.py \
  --archive /path/to/Carbon_Challenge_Authoring_Workbench_V1.zip \
  --protocol docs/development/c_ep3_reference_probe_protocol_v1.json \
  --output-dir /fresh/private/output/directory
```

The output directory must not already exist. The harness refuses duplicate
runs, safely verifies the entire archive and exact source pins before import,
and retains a failed operation if execution stops.

## Boundaries and next decision

No numerical result was sent into C-EP1, A5/A6, accepted-result, reward,
archive, network or production routes. No Variant-B/C mechanism, membership,
wait, early summary, answer publication, provider entropy or real finalization
was added. AT-09, AT-16, AT-19, AT-22 and AT-30 remain blocked. Public-root
confidentiality, hostile plaintext hosts, reference lineage/freshness, honest
execution and future-case overlap remain unresolved.

The next implementation dependency is not sharing. C-02 still lacks the actual
authorized source/interface package, so it is not ready to select today. Once
that package arrives, **C-02 is the existing dependency to evaluate for
selection**. C-04 remains later and separately blocked by isolated execution,
scientific adequacy, protected custody and reference-policy decisions.
