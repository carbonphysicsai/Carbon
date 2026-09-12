# C-EP3 public-reference input acquisition and component evidence

**Status:** bounded DEVELOPMENT acquisition/probe implementation complete;
applicable automated acceptance pending
**Baseline:** `96099aeac9e5022bda9d94730b1d7d955cb6c1d5`
**Frozen implementation/probe revision:**
`bed9331e1983b4218af7df99679293e0c83837f9`
**Primary Hub map_ref:** `WAVE-C/C-EP3`

The repository owner's ordered follow-on assignment selected only bounded input
acquisition and one eligible public DEVELOPMENT numerical component probe after
C-EP2 merged. C-EP2's corrected recommendation remains `COLLECT MISSING INPUTS
FIRST`. No Variant-B runtime or real C1 implementation ticket is selected.

## Acquired evidence

The owner-supplied `Carbon_Challenge_Authoring_Workbench_V1.zip` has SHA-256
`40f1fd47d62dd2269f8e141e6bb398d03a403aa6eb3ac08750b49dd68018bcdc`.
All 85 archive entries were safely listed, and all 84 manifest-governed files
passed byte-count and SHA-256 verification. Its release digest is
`sha256:7805f87c3b4745454ec9c8fa852a20de6731d8f85e1356eb5d91a708cdafa7ac`.
The source is public DEVELOPMENT research, `SYNTHETIC_INTERNAL`, unqualified
and not runtime-integrated.

One source-defined archived `REFERENCE_AUDIT` case was actually executed with
the pinned ETDRK4 primary, refinement, Cole-Hopf witness, diagnostics and NPZ
round trip. On the declared one-thread Apple M3 CPU host, the primary cold call
used 297.089 ms, two repeated warm calls used 288.438 and 289.821 ms, the
refinement used 1,906.978 ms, and 1,024/2,048-node witnesses used 33.183 and
64.702 ms. These are one public component's observations, not an integrated
exam, adequate-reference floor, capacity forecast or B savings claim.

The first attempt is retained: the source-supported NumPy 2.4.3 environment
changed last-bit generated floats and therefore the case digest. The successful
run used the manifest-verified archived case whose content digest is exact and
records the generator replay mismatch. The source's saved exact dependency
lock was not downloaded because public-network installation was not authorized.

No intended authorized JAX reconstruction source/interface or eligible real
submission trace was found. PR #40 remains a non-authoritative shared-weight
fp32 forward-parity candidate only. B overhead and common-comparison semantics
remain unavailable.

## Evidence records

- `.agent/evidence/wave_c/c-ep3-inputs/acquisition_record_v1.json`
- `.agent/evidence/wave_c/c-ep3-inputs/probe_observation_summary_v1.json`
- `.agent/evidence/wave_c/c-ep3-inputs/profiler_component_summary_v1.json`
- `.agent/evidence/wave_c/c-ep3-inputs/OWNER_SCIML_INPUT_REQUEST.md`
- `docs/development/c_ep3_reference_probe_protocol_v1.json`
- `docs/development/C_EP3_INPUT_ACQUISITION_AND_COMPONENT_REPORT.md`

## Local verification

```text
python -m pytest -q tests/cpu/test_c_ep3_reference_probe.py
29 passed

python -m pytest -q tests/cpu/test_c_ep1_evaluation_packs.py tests/cpu/test_c_ep2_measurement_study.py
38 passed

python -m pytest -q tests/cpu/test_c_ep3_reference_probe.py tests/cpu/test_c_ep2_measurement_study.py tests/cpu/test_c_ep1_evaluation_packs.py tests/cpu/test_c01_durable_execution.py
90 passed

python -m pytest -q tests/invariants
208 passed
```

Final formatting, lint, Hub, classified acceptance and delivery identities are
recorded only after they run at the final head.

## Decision

`COMPONENT_DATA_COLLECTED; SHARING_STILL_UNSUPPORTED`.

C-EP2's `COLLECT MISSING INPUTS FIRST` recommendation remains correct. The next
useful owner action is to supply the immutable permission-cleared JAX
source/interface package so existing C-02 can be evaluated for selection. C-02
is not selected by this evidence, and C-04 remains a later distinct scientific,
isolation and protected-custody dependency.

No C-02, C-04, Variant-B/C, reward, production, network or qualification
capability is authorized or implemented by this delivery. AT-09, AT-16, AT-19,
AT-22 and AT-30 remain blocked.
