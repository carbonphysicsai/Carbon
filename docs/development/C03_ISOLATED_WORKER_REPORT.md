# C-03 DEVELOPMENT isolated-worker report

**Decision:** `OWNER-C03-DEV-ISOLATION-01`
**Scope:** first bounded public-data DEVELOPMENT slice
**Current state:** implementation candidate with passing Linux service evidence
at `9fccb2cc28a88b5771410148d8b80f688d4f1ff6`; final exact-head CI and merge
evidence pending

## Owner summary

An already admitted reconstruction is copied into a per-attempt input snapshot,
run by the existing C-02 adapter in a pinned CPU-only Docker worker, streamed
out through a capped length-prefixed provisional snapshot, stopped with all
descendants, validated
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

The first passing implementation campaign, run `34769816925`, built image/config
`sha256:0440ef4d42012c5fffb80af0d43e413e1ad0d7728d1db2a3b8b5e80b712f0cca`
from source-tree digest
`sha256:fc8117dd22421a5f4808f6ebff38d3e9b52d8c9be7e16054120a245a8d526bab`,
wheel digest
`sha256:3ce9e0e5ec925fd9b40be873584217ab1689ce2a8eb434d757fbbcbfabe317b6`,
recipe digest
`sha256:db26a9a222da45563087209a1d167e112a91e3e2c9e49fdb8928fe962e42ec54`
and entrypoint digest
`sha256:5a26105e26d73c2364a7cb1f9699330f705a336a1ef5390180e2763fbeb069b2`.
Its exact worker-policy digest was
`sha256:0f81f3f6d4daff01e0f4f2c36ba08d66837afe9eabce51ffdf4f9f8df6f54bdb`.
These are historical identities for that passing implementation head; the
final delivery run mechanically assigns a new source/image identity after this
report-only update and retains it in its own manifest artifact.

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

Run `34769816925` passed seven required service tests in 67.14 seconds with zero
failures/skips, then passed doctor, smoke (one test in 16.97 seconds), and exact
status/reconciliation. Its required campaign retained two ordinary COMPLETE
traces, one reconciled COMPLETE continuation, two cancellation traces, one
bounded resource rejection and one network denial: successful `3`, failed `0`,
cancelled `2`, reconciliation `1`, other enforcement rejections `2`. The owner
smoke retained one additional COMPLETE trace separately.

The lab FNO trace completed in 12.709 seconds (9.042 numerical, 0.456 export,
1.240 validation, 0.411 cleanup). Foundax FNO at 512 points completed in 11.384
seconds (8.589 numerical, 0.458 export, 0.631 validation, 0.425 cleanup). The
create-response-loss/continuation trace reconciled and completed in 11.550
seconds with the same checkpoint digest as uninterrupted execution. Bounded
memory denial exited `137`, its finite removed-guard control reached sentinel
`12`, PID/scratch byte/scratch inode probes denied at their limits, and blocked
worker cleanup took 5.119 seconds. Network-none denied both controlled address
and DNS probes while the same canary was reachable under the deliberately
connected negative control.

The runtime was Ubuntu 24.04.5 LTS, Linux `6.17.0-1022-azure`, x86-64, Docker
Engine `28.0.4` API `1.48`, cgroup v2 with the systemd driver, and reported
AppArmor, built-in seccomp and cgroup namespace support. Inspection observed
`cpu.max=200000 100000`, cpuset `0-1`, `memory.max=4294967296`,
`memory.swap.max=0`, `pids.max=256`, zero effective capabilities,
`NoNewPrivs=1`, seccomp mode `2`, read-only root, `network=none`, private
PID/IPC, exact 528,482,304-byte/8,192-inode scratch plus 8,388,608-byte
`/dev/shm`, and Docker's `docker-default` AppArmor profile. No peak RSS was
measured; 4 GiB is only the enforced ceiling, so this slice makes no calibrated
per-model memory or official 600-second adequacy claim.

## Acceptance repair history

The first service-backed candidate run, `34767534562`, failed and remains
failed evidence. It found that Linux-created NPZ members can carry permission
bits without explicit regular-file type bits, and that Docker's private PID
namespace is selected by the empty/default PID mode rather than the literal
CLI value `private`. The repaired audit still rejects explicit non-regular ZIP
members, while the launch now verifies and rejects any host/container PID mode
after creation. The same run also found strict Black/import-order debt and a
missing `SYSTEM/PROTOCOL-AUTHORITY` Hub-impact declaration; both were repaired
without weakening a runtime control. Passing replacement evidence remains
required before this bounded slice is called tested.

Later failed/cancelled candidates are also retained. Run `34767928064` confirmed
the ZIP/PID repairs but exposed Docker start failure. Diagnostic run
`34768569365` identified the exact cause: the local log driver's default
compression is incompatible with the selected one-file rotation, so the
profile now pins and inspects `compress=false` while retaining its 1 MiB,
one-file ceiling. Run `34768731597` then found and repaired the GNU `df` inode
field invocation. Run `34768907825` passed four controls and exposed both a
permission-denied host-path probe interpretation and Docker's inability to copy
the live tmpfs with `docker cp`; run `34769257159` confirmed the path-probe
repair and the tmpfs-copy limitation. The final implementation uses a fixed
installed exporter and controller-capped closed stream, never unrestricted
archive extraction. Run `34769816925` passed all service controls. Its later
owner smoke overwrote the main JUnit pathname, so the candidate now separates
smoke JUnit/trace files from the required campaign; this evidence-retention
repair still requires final exact-head CI before merge.

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
