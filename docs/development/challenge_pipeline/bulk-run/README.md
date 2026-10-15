# Bulk reference-data runner: operator runbook

`scripts/dev/reference_packages/bulk_run.py` runs many families' frozen
reference decks on **one large hourly cloud VM at once**, under enforced
per-case, per-family and per-machine caps, with a crash-safe ledger. It is the
multi-family form of `triage_run.py`. `triage_run.py` is unchanged and still
serves OWNER-REFERENCE-ROUTE-TRIAGE-GRANT-01; `tests/cpu/test_bulk_run.py`
pins its caps.

**Authority boundary.** This is engineering tooling. No plan runs on paid
hardware without an owner decision that grants the machine and its spend. The
plan's `authority` field names that decision, and the machine caps, EUR cap
and family ceilings come from it. Only public decks and pinned public images
go to the VM. Never hidden EVAL, STRESS, quiz or tuning material, seeds,
labels, validator state or private roots. Ledger timings are DEVELOPMENT cost
measurements labelled with the plan's `host_profile`. They are not canonical
pipeline timing fields, and they are not a qualification, adequacy or
reference-agreement claim.

| File | Role |
|---|---|
| `scripts/dev/reference_packages/bulk_run.py` | the runner (stdlib only, Python 3.11+) |
| `scripts/dev/reference_packages/bulk_host_setup.sh` | fresh Ubuntu/Debian VM bootstrap |
| `scripts/dev/reference_packages/bulk_collect.sh` | packs ledger, summaries and outputs for download |
| `scripts/dev/reference_packages/bulk_smoke.py` | writes a tiny real-docker rehearsal plan |
| `run-plan.template.json` | plan template; its placeholders fail validation until filled |
| `smoke-2026-10-15/` | the local real-docker smoke evidence (below) |
| `tests/cpu/test_bulk_run.py` | unit tests with a fake docker |

**RunPod note.** A RunPod pod is itself a container, with no Docker daemon
inside it, so this runner cannot run there. Use a VM with Docker: Hetzner
Cloud CCX, AWS EC2 or similar. The pilot-caps exported-tree route
(`../pilot-caps/README.md`) is the alternative for pods.

## 1. Run plan: `carbon.reference-bulk.run-plan.v1`

Unknown keys are refused, so a typo cannot silently drop a cap.

| Field | Meaning |
|---|---|
| `plan_id` | `[A-Za-z0-9._-]`; labels containers (`carbon.bulk.plan`) and archives |
| `authority`, `host_profile` | recorded in every RUN_START row and summary |
| `machine.cpus`, `machine.memory_gib` | the machine's totals; refused if above the host's `nproc`/MemTotal |
| `machine.reserve_cpus`, `reserve_memory_gib` | kept free for the OS, docker and the runner (default 0) |
| `machine.node_hours` | node-hour cap, counted from `clock_start` |
| `machine.eur_cap`, `eur_per_hour`, `billing_quantum_s` | optional EUR cap: allowed hours = floor(cap / rate / quantum) quanta (default quantum 3600 s, i.e. hourly billing) |
| `machine.margin_minutes` | tail kept for collection and deletion (default 15) |
| `machine.clock_start` | `boot` (default: host boot time, about server creation), `first_run` (first RUN_START in the ledger) or a unix time |
| `machine.starvation_s` | a case that has not fit for this long stops backfill until it fits (default 900) |
| `machine.min_case_window_s` | do not start a case with less machine or family time than min(timeout, max(this, 2 x estimated wall)) (default 600) |
| `families[].family` | must equal the manifest cases' `family` |
| `families[].manifest_dir` | relative to the plan file; holds `manifest.json` and `<family>/<case>/` |
| `families[].image` | what `docker run` uses: an image ID `sha256:...` or `repo@sha256:...`; tags are refused |
| `families[].priority` | lower runs first; equal priorities interleave by reservation, then manifest order |
| `families[].case_limits` | `cpus` (`--cpus`, may be fractional), `memory_gib` (`--memory` = `--memory-swap`), `pids` (`--pids-limit`; leave about 4 for the wrapper and a stop `docker exec`), `wall_timeout_s` |
| `families[].ceilings` | `launches` (STARTED rows) and `cpu_hours` (allocated = wall x cpus) |
| `families[].acceptance` | optional `{command, timeout_s, cpus?, memory_gib?}` run once in the image before any case; nonzero exit leaves the family BLOCKED_ACCEPTANCE |
| `families[].entrypoint` | `override` (default: `--entrypoint sh`) or `image` (keep the image's entrypoint, e.g. OpenFOAM's `/openfoam/run`, which sets up the environment) |
| `families[].shell` | the shell that runs the case `command` (default `sh`; `bash` for Allrun scripts) |
| `families[].env` | extra environment, e.g. `{"OMP_NUM_THREADS": "1"}`. The runner always sets `CARBON_CPUS`, `CARBON_MEMORY_BYTES` and `HOME=/tmp` |
| `families[].reservation_order` | default: `triage_run.PRIORITY` (primary first) |

The manifest is `carbon.reference-triage.frozen-decks.v1`, unchanged:
`manifest.json` holds `image` (the identity pin) and
`cases[{family, case, reservation, command, files{relpath: sha256}, mesh?}]`.
The bulk runner also reads these optional per-case fields:
`estimate_cpu_s`, `estimate_wall_s` and `estimate_mem_mib`. They come from
measured costs, and the dry run's schedule estimate uses them. An f17 case is
one `Allrun` per case dir: `"command": "./Allrun > log.Allrun 2>&1"` with
`"shell": "bash"`, plus `"entrypoint": "image"` unless the Allrun sources the
OpenFOAM bashrc itself.

The manifest's `image` pin must be among the identities docker reports for
the family's `image`. Those are the ID, the descriptor digest, every
RepoDigest, the linux/amd64 manifest digest and, as a fallback, the config
digest read from `docker image save`'s `manifest.json`. A containerd image
store names an image by its manifest digest, while older pins are config
digests. Both are accepted, and nothing else is.

## 2. What the runner enforces

- **Before any launch:** the plan and every manifest validate; every
  family's image carries its pin; every case file matches its sha256. Any
  failure refuses the whole run (exit 2), and nothing starts.
- **Per case:** the files are copied to a fresh `OUT/cases/<family>/<case>/work`
  and hashed again. A mismatch writes a REFUSED row and stops that family.
  The case then runs in `docker run --rm --network none --read-only --tmpfs /tmp
  --cpus C --memory M --memory-swap M --pids-limit P --cap-drop ALL
  --security-opt no-new-privileges --user <runner uid>`, with `work` at
  `/case`. A POSIX-sh wrapper runs the command, then writes the container
  cgroup's CPU usage and memory peak to `meta/cgroup.txt`. On cgroup v2 these
  come from `cpu.stat usage_usec` and `memory.peak` (kernel 5.19 or later).
  On cgroup v1 they come from `cpuacct.usage` and `memory.max_usage_in_bytes`,
  which includes page cache. `meta/outputs.json` lists every output file's
  sha256.
- **Wall timeout:** at `timeout - grace` the wrapper gets SIGTERM through
  `docker exec`. It stops the case and still records the stats. At `timeout`
  the container is killed. The grace is min(20 s, timeout/4).
- **Bin-packing:** cases are taken in priority order, first-fit, by their
  `cpus` and `memory_gib` limits (the caps, not the estimates). The running
  sum never exceeds the machine totals minus the reserve.
- **Ceilings under concurrency:** a launch appends STARTED before the
  container starts. That row counts the launch and reserves `timeout x cpus`.
  A case starts only if booked plus reserved CPU leaves its full timeout. If
  not, it waits while its family has cases running. With nothing running, it
  runs clipped to what is left and is CENSORED_FAMILY_CAP if it reaches the
  clip. FINISHED then books the real `wall x cpus`.
- **No retries, crash-safe resume:** the ledger is fsynced row by row. On
  restart, every STARTED without FINISHED becomes ABANDONED_ON_RESUME. It is
  booked at its full reservation and never relaunched. Containers that the
  dead runner left running (label `carbon.bulk.plan`) are killed first. A
  resume under a changed plan is refused unless `--accept-plan-change` is
  given. Only one runner can hold an `OUT` dir (`OUT/.lock`).
- **Global stops:** the deadline is clock start + min(node-hours, EUR hours)
  − margin. Cases are clipped to it (CENSORED_MACHINE_CAP), and nothing
  starts once it has passed. `touch OUT/STOP` (or one SIGTERM/SIGINT to the
  runner) drains: nothing new starts and running cases finish.
  `touch OUT/STOP_NOW` (or a second signal) stops running cases
  (CENSORED_OPERATOR_STOP).

| Outcome | Meaning |
|---|---|
| COMPLETED | exit 0 |
| FAILED | nonzero exit; `oom_suspected` when it is 137 without a timeout |
| FAILED_INFRA | docker could not create the container (125), or the runner raised; not a scientific failure |
| CENSORED_CASE_TIMEOUT / _FAMILY_CAP / _MACHINE_CAP / _OPERATOR_STOP | stopped by that cap; its consumed cost is booked |
| ABANDONED_ON_RESUME | the runner died while it ran; booked at its reservation |

Cases that never start are counted in each summary's `not_launched` by
reason: FAMILY_LAUNCH_CEILING, FAMILY_CPU_CEILING, MACHINE_CAP, STOP,
STOP_NOW, BLOCKED_ACCEPTANCE or REFUSED_HASH_MISMATCH.

**Outputs.** `OUT/ledger.jsonl` (`carbon.reference-bulk.ledger.v1`; events
RUN_START, ACCEPTANCE, STARTED, FINISHED, REFUSED, ABANDONED_ON_RESUME),
`OUT/cases/<family>/<case>/{work,meta}`, `OUT/summary/<family>.json` and
`OUT/summary/all.json` (`carbon.reference-bulk.summary.v1`). Each family
summary gives counts by outcome, launches, allocated and cgroup CPU-hours,
wall total/p50/p95/max, and memory peak p50/p95/max in MiB. `all.json` adds
elapsed node-hours and the EUR estimate in billed quanta. `--summarize`
rewrites the summaries from the ledger alone.

## 3. Sizing the machine

1. Each family track measures its case kinds (CPU-s, wall-s, peak memory) and
   writes `estimate_*` into its manifest.
2. Set each family's `case_limits.memory_gib` to about 1.5 x its largest
   measured peak, rounded up. Bin-packing reserves the limit, so a loose
   limit wastes the machine and a tight one gives OOM FAILED rows.
3. The most memory-hungry family sets the GiB-per-CPU ratio. For example,
   f08 at 1 CPU and 12 GiB is 12 GiB/CPU, while f02 at 1 CPU and 4 GiB is
   4 GiB/CPU. A mix of them wants about 4 to 8 GiB per vCPU. A
   CPU-dominated mix (Elmer 1-CPU cases) fits 2 to 4 GiB per vCPU.
4. Keep 1 to 2 CPUs and 4 to 8 GiB in `reserve_*` for the OS, docker, the
   runner's hashing and the page cache.
5. Run the dry run on the dev box against the filled plan. Its estimated
   makespan, plus setup and collection, gives the node-hours to request.
6. Large x86-64 hourly examples (check current specs, prices and quotas when
   ordering; prices are not recorded here): Hetzner Cloud **CCX53** (32
   dedicated vCPU, 128 GB) and **CCX63** (48 dedicated vCPU, 192 GB). AWS
   **c7a.16xlarge** (64 vCPU, 128 GiB) and **c7a.24xlarge** (96 vCPU,
   192 GiB) for CPU-heavy mixes. **m7a.16xlarge** (64 vCPU, 256 GiB) when
   memory per case is high. Check whether a provider's vCPU is a physical
   core or an SMT thread, because CPU-s measured on one are not comparable to
   the other. Record the type in `host_profile`.
7. Disk: images (Elmer about 0.3 GB, CalculiX about 0.2 GB, OpenFOAM about
   2.2 GB unpacked), each case's copied decks, outputs, and the
   collection archive. Size the root disk at about 3x the expected outputs.

## 4. Moving the images

The image a family's manifest pins must reach the VM byte-identical.

- **Tarball (no credentials):** on the box that holds the image,
  `docker save <tag-or-id> | zstd -T0 -19 -o bundle/images/<name>.tar.zst`,
  then record its sha256. `bulk_host_setup.sh` loads every
  `bundle/images/*.tar.zst`. It also prints each loaded image's ID and
  digests. Use the ID as the family's plan `image`; the dry run proves it
  carries the manifest pin.
- **Registry by digest:** `docker tag <id> ghcr.io/<org>/<repo>:<tag> && docker push ...`
  prints a digest. Set the plan `image` to `ghcr.io/<org>/<repo>@sha256:<digest>`
  and pass the same reference to `--pull`. A private registry needs a
  `docker login` token on the VM. That credential is the owner's to issue.
  Without it, use tarballs.
- `--mirror https://mirror.gcr.io` makes the daemon use that registry mirror
  for Docker Hub pulls. Image identity is still checked by digest.

## 5. Operator commands

On the dev box, build the bundle:

```bash
B=$HOME/bundle-<plan_id>; mkdir -p $B/images $B/decks
cp -a <family frozen-manifest dir> $B/decks/f02        # one per family
docker save carbon-ref-elmer:26.2.1 | zstd -T0 -19 -o $B/images/elmer.tar.zst
cp docs/development/challenge_pipeline/bulk-run/run-plan.template.json $B/plan.json
#   fill: plan_id, authority, machine caps, each family's image, limits, ceilings
python3 scripts/dev/reference_packages/bulk_run.py --plan $B/plan.json \
    --out /tmp/bulk-check --dry-run --skip-image-check   # shape, hashes, estimate
sha256sum $B/images/*.tar.zst > $B/images/SHA256SUMS
```

The owner creates the VM under the grant. Then, from the dev box:

```bash
rsync -a $B/ root@<vm>:/root/bundle/
scp scripts/dev/reference_packages/bulk_host_setup.sh root@<vm>:/root/
#   without repo access on the VM: git archive --format=tar.gz -o carbon.tar.gz <sha>,
#   scp it, and pass --repo-tarball /root/carbon.tar.gz instead of --repo/--commit
ssh root@<vm> 'bash /root/bulk_host_setup.sh --bundle /root/bundle \
    --repo <repo-url> --commit <sha> --mirror https://mirror.gcr.io'
#   read /srv/bulk/dry-run.json: images, hashes, makespan vs available node-hours
ssh root@<vm> 'bash /root/bulk_host_setup.sh --bundle /root/bundle \
    --repo <repo-url> --commit <sha> --start'
```

While it runs:

```bash
ssh root@<vm> tail -f /srv/bulk/run.log
ssh root@<vm> cat /srv/bulk/out/summary/all.json      # written at the end
ssh root@<vm> touch /srv/bulk/out/STOP                # drain
ssh root@<vm> touch /srv/bulk/out/STOP_NOW            # stop now
```

After the run (or at the cap):

```bash
ssh root@<vm> 'bash /opt/carbon/scripts/dev/reference_packages/bulk_collect.sh'
#   prints /srv/bulk/bulk-<plan_id>-<stamp>.tar.zst and its sha256
rsync -a root@<vm>:/srv/bulk/bulk-*.tar.zst ./        # check the sha256
```

Then delete the VM. Delete it, do not stop it: a stopped server still bills.
Release its IP. Record the final node-hours and EUR in the private spend
ledger.

If the runner dies (VM reboot, OOM-killer), rerun the same `--start`
command, or the `runuser` line it prints. The ledger resumes: interrupted
cases become ABANDONED_ON_RESUME and are not retried.

## 6. Local smoke, 2026-10-15 (real docker, no solver)

Host: `local-dev-4vcpu-15g-contended` (4 vCPU Intel Xeon @ 2.10 GHz, 15 GiB,
Docker 29.8.2 with the containerd image store, **cgroup v1**), shared with
other tracks. The plan comes from `bulk_smoke.py`: 1 CPU and 1 GiB in total,
two 0.5-CPU, 0.5-GiB cases at a time. The busybox family is pinned by
**config digest** and run by `mirror.gcr.io/library/busybox@sha256:73aaf0...`,
so it exercised the `docker image save` fallback. The debian family is
pinned and run by image ID. Evidence is in `smoke-2026-10-15/`.

| Family / case | Outcome | wall s | cgroup CPU s | peak MiB |
|---|---|---|---|---|
| (both) acceptance `true` | passed | 0.8 | n/a | n/a |
| smoke-busybox / hello | COMPLETED | 0.87 | 0.046 | 4.7 |
| smoke-busybox / burn | COMPLETED | 5.72 | 0.793 | 4.7 |
| smoke-busybox / memory (200 MiB tmpfs write) | COMPLETED | 1.68 | 0.193 | 202.4 |
| smoke-busybox / fails (`exit 3`) | FAILED (exit 3) | 0.77 | 0.040 | 4.9 |
| smoke-debian / hello | COMPLETED | 0.57 | 0.059 | 4.9 |
| smoke-debian / too-slow (`sleep 300`, 8 s timeout) | CENSORED_CASE_TIMEOUT (exit 143, stats recorded) | 6.71 | 0.085 | 4.6 |

- Two cases ran at a time, and the two families interleaved (ledger STARTED
  times).
- Crash and resume (`crash-resume-ledger.jsonl`; same decks, plan
  `bulk-smoke-crash` with a 200 s debian timeout): the runner got SIGKILL 6 s
  in, while `burn` and `too-slow` were running. On restart, the one container
  still alive was killed (`stale_containers_killed: 1`). Both cases became
  ABANDONED_ON_RESUME, booked at their reservations (60 and 100 CPU-s), and
  were not relaunched. The remaining cases then ran.
- STOP_NOW (`stop-now-ledger.jsonl`): `touch OUT/STOP_NOW` 5 s in turned both
  running cases into CENSORED_OPERATOR_STOP, with cgroup stats, and
  `not_launched: {"STOP_NOW": 2}`.
- `bulk_collect.sh` packed the output (it fell back to gzip because this box
  has no zstd).
- Found and fixed during the smoke: dash rejects `kill -s TERM -1`, so the
  wrapper uses `kill -TERM -1`, which works in dash and busybox. A timeout's
  overshoot is now bounded by the timeout itself.

Not exercised locally: cgroup v2 `memory.peak` (this host is v1),
`bulk_host_setup.sh` (it needs a fresh VM; checked with `bash -n` only), and
any real solver image under the bulk runner.

## 7. Limits

- Bin-packing uses each family's single `case_limits`. A family whose cases
  differ widely in size (f08 meshes) packs at its largest case's memory. A
  per-case limit override would need a schema bump.
- Abandoned cases are booked at their full reservation (the conservative
  side). A case that finished inside its container while the runner was dead
  still counts as abandoned, even though its outputs are in its work dir.
- EUR is wall-clock x rate in billed quanta. It is not the provider's
  invoice: IPs, traffic and VAT are outside it, so keep them inside the
  grant's margin.
