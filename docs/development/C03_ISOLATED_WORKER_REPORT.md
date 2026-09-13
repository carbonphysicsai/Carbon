# C-03 DEVELOPMENT isolated-worker report

**Decision:** `OWNER-C03-DEV-ISOLATION-01`
**Scope:** first bounded public-data DEVELOPMENT slice
**Current state:** implementation candidate; final Linux service acceptance and
merge evidence pending

## Owner summary

An already admitted reconstruction is copied into a per-attempt input snapshot,
run by the existing C-02 adapter in a pinned CPU-only Docker worker, copied out
through a capped provisional snapshot, stopped with all descendants, validated
by the controller, and only then attached to the C-01 attempt. A miner sees no
new action, fee, reveal, request field or interface.

The source baseline is PR #148 merge
`83186be004a4087b27b07278da490dad36785acb` (historical tested head
`5e3d47039a52f601789f0495f8c3127f8b4a3cf4`, run `34758720071`). This report
does not reuse that historical run as C-03 acceptance.

## Exact pinned inputs

- Python 3.11; JAX/JAXlib 0.10.2; NumPy 2.4.6; SciPy 1.17.1; Optax 0.2.8;
  Chex 0.1.92; Equinox 0.13.8; Einops 0.8.2; Foundax 0.2.0; PyYAML 6.0.3.
- `uv.lock`:
  `sha256:9de64d6c5ca9a0a73d141ca403de1d2bee8bb85e68cd7ea20195b163a7c2cf11`.
- Mac CPU lock:
  `sha256:bacfb721c78ebf438f74c145e154e1daa0a7c0309472188c27682a8048916165`.
- Linux CPU environment pin:
  `sha256:2ed4187d9add70afcd18a8faaa1b3acdd50f5ffe6e9b0f1d402f04dc34e13c1e`.
- Foundax source `b02b1da52bb03cfad8e437983fc1d1e411e78b04` and wheel
  `sha256:9240526f8bcf9860033807404c6e2402dfb10a73ed75088409c37aa58a6fc9b2`.
- Missing v0.2 file-set
  `sha256:1e539a856a35701ec7ff85880ba9e5a84eaf13970a6212e56f13a32b9d65955e`
  remains `NOT VERIFIED` and is not substituted.
- Ubuntu 24.04 base image
  `sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517`.

The final source-tree, built-wheel, recipe, entrypoint and Docker image/config
digests are mechanically assigned by `c03_worker_image.sh` for the exact tested
head and retained as the CI image-manifest artifact. They are deliberately not
self-embedded as the final image digest.

## Selected limits

The exact values are in `c03_worker_profile_v1.json`: one worker; two logical
CPUs with cpuset and two-CPU CFS quota; 4 GiB cgroup memory and zero swap; 600
seconds productive deadline; five seconds graceful stop; thirty seconds cleanup
confirmation; 256 tasks; 512 MiB aggregate scratch and 8,192 inodes; 128 MiB
input and expanded input; 1 MiB closed control; 128 MiB output and expansion,
1,024 regular files; 1 MiB bounded diagnostics; 1,024 descriptors per process;
no core dump; no accelerator (`NOT_APPLICABLE`). These are engineering ceilings,
not workload measurements, reservations, scientific tolerances or production
budgets.

## Control and trace matrix

| Trace/control | Implementation and expected observed disposition | Limitation |
|---|---|---|
| Lab FNO | real C-02 updates, artifact/checkpoint export, direct scientific-state byte comparison, target-free reload | small public deterministic fixture |
| Foundax FNO | exact source-pinned profile, 512-point TRAIN input, same association and finite shape/dtype checks | development profile, not backend qualification |
| Duplicate/recovery | one durable create owner; create-response loss finds exact name/label; associated replay returns the same immutable bytes with no new partial | daemon and host are trusted |
| Resource rejection | cgroup memory/PID and tmpfs byte/inode denial use lower frozen test subprofiles; CPU/cpuset/swap read from live cgroup | lower subprofiles are test-only |
| Output/late write | links/special files/traversal/duplicate JSON/oversize/member/expanded/cross-attempt/nonfinite/shape/dtype mismatches reject; accepted copy is immutable | not exhaustive exploit coverage |
| Cancellation | blocked native-like operation and parent/child process tree are removed by exact-label external cleanup | five-plus-thirty-second ceilings, no availability promise |
| Network/filesystem | controlled canary proves connected negative control and `network=none` denial; root/input writes and Docker/host canaries are absent | private loopback/socket syscalls remain |
| Cleanup uncertainty | slot becomes `QUARANTINED`; no successful association; later independent capacity is not globally barred | operator reconciliation remains necessary |

Failures found by local unit tests are repaired in the candidate history; the
required Linux lane must report zero failing service controls before bounded
completion is claimed. The final delivery response supplies the exact passing
head, workflow/run, merge, counts and observed timing. Phase timing separates
staging/create, numerical work (including import/JIT/training), export,
validation, cleanup and total. Fixture timing is descriptive; worker CPU and
host overhead are not treated as an official 600-second adequacy study. Docker
cgroup memory is a ceiling; this slice does not claim a calibrated per-model
peak requirement.

## Remaining boundary

Full C-02 and protected/production C-03 remain open. There is no production
repeat count, protected exam, confidential-customer claim, host-root defense,
independent security acceptance, scientific qualification, official judge,
archive acknowledgement, reward, public-network or LIVE authority. Foundax's
conservative EPL-2.0 source/wheel notice remains; no commercial permission is
inferred.

## Owner commands

```bash
./scripts/dev/c03_worker.sh doctor
./scripts/dev/c03_worker.sh smoke
./scripts/dev/c03_worker.sh reconcile
```

The third command reports status, performs exact scoped reconciliation/cleanup
where needed, then reports final status for the smoke's retained runs. On
macOS, Docker Desktop must
already be installed and open; any run is an optional Linux-VM diagnostic, not
native-Mac isolation evidence. Without it, use the required eligible Linux CI
lane. These commands require no wallet, cloud credential or input ZIP.
