# POD-JOBS-01: the shared pod launcher (CLOUD-FIRST-COMPUTE-01 items 1 and 3)

**Owner:** Data Collection. **Reviewer:** Graphite Testing Manager. **First user:**
the Graphite executor (value_panel and public-improvement rebuilds).

From 2026-10-13 a heavy public job (over 2 GB of memory, 1 CPU-hour or 5 GB of
writes) runs on a RunPod pod rather than the PC. This is the one launcher every
session uses for that. It is DEVELOPMENT tooling: it grants no scientific,
security or LIVE authority, and only public or non-sensitive work may run on it.
Sealed and hidden material stays on the AX42 under its custody records.

## Using it

```bash
python -m carbon.agent_campaign.pod_jobs uploads LOCAL_DIR            # the spec's `uploads` field
python -m carbon.agent_campaign.pod_jobs plan SPEC.json               # validate, worst case, ship size
python -m carbon.agent_campaign.pod_jobs check SPEC.json --root NEW   # the real code path, RunPod in memory
python -m carbon.agent_campaign.pod_jobs run SPEC.json --out DIR --key-file KEY [--uploads LOCAL_DIR]
```

`run` uses Carbon's RunPod key by file path only (owner-only file); the launcher
never prints, logs or stores it. Until an agent session is given that key file,
the owner runs `run` on the operator host.

## The spec (`carbon.pod-job.spec.v1`, closed fields)

| Field | Meaning |
|---|---|
| `job_id` | lower-case slug; also the ledger key and the provider intent. One run per id |
| `code_ref` | a 40-hex pushed commit. The pod fetches every shipped file at that commit and refuses any whose sha256 differs (`bootstrap.py`) |
| `module`, `args` | what runs: `python -m module args...`, no shell. `{out}`, `{root}` and `{inputs}` are the only substitutions |
| `inputs` | repository paths at `code_ref`, shipped beside the code. The ship guard (`pods.shippable`, `FORBIDDEN_DATA`) refusing any of them refuses the job |
| `uploads` | `{path: {sha256, bytes}}`: files that are not in git, sent once the pod waits for them. The pod writes each only at its declared size and sha256 and starts the job when all have arrived. At most 95 MB a file and 1 GB a job |
| `collect` | paths under the uploads directory copied into the results after the job |
| `image` | `study`: the pinned EV4 study image (CPU, or JAX on GPU); `pytorch`: the released torch-gpu worker image |
| `overlays` | `{name: lock path}`, hash-locked wheel overlays (for example `battery`: `scripts/dev/exam_design/locks/battery-overlay.lock.json`) |
| `compute` | `{"kind": "cpu", "flavor", "vcpus"}` (flavors the operator layer accepts) or `{"kind": "gpu", "type", "count"}` |
| `minutes`, `disk_gb` | the job's own allowance; the pod self-terminates 5 minutes after it |
| `rate_ceiling_usd_per_hr`, `cap_usd` | the worst case (minutes plus export at the ceiling, disk, pod_control's cleanup reserve) must fit under `cap_usd`, and `cap_usd` under the per-run cap |

## What a run does

1. Refuses a spec, an input the ship guard refuses, or uploads that differ from the
   spec, before anything is claimed.
2. Claims the job in the host ledger (`grant_runs`, store `pod-jobs`, OWNER-TEST-GRANT-01:
   USD 300 per rolling week, USD 50 per run). The Test Engineer's `pod_job` kind
   replaces the local `JobGrant` stand-in.
3. Launches through Graphite's live backend, unchanged (`graphite.pods.RunPodPods` on
   `operator_compute`), in its own campaign `pod-jobs`: durable intent before the create,
   ownership-tag recovery of a lost create response, the account balance floor, a priced
   offer at or below the ceiling (GPU), the created pod's rate checked against the
   ceiling, refusal codes from `pods.refusal_code`.
4. Uploads the declared inputs, waits, and fetches every result file checked against the
   pod's own sha256 listing (`pods.fetch_limits`: 64 files, 256 MB).
5. Terminates the pod whatever happened, deletion verified by absence. The pod's own
   watchdog (`bootstrap.py`) terminates it at its deadline in any case.
6. Settles: zero for a refusal before any provider write; else the provider's charge, or
   the full reservation left pending (`grant_runs`' reservation basis).
7. Writes `OUT/receipt.json` (`carbon.pod-job.receipt.v1`): spec digest, code manifest
   digest, image, pod, outcome, files with sha256, uploads, teardown, cost and the week's
   ledger line.

## The image (item 3)

No new image. The job runs in the pinned EV4 study image, the one the A40 value_panel
pods and the public-dev decision pod already ran in, with its code fetched hash-pinned
at `code_ref` and its Python dependencies from hash-locked overlays. The repository is
therefore pinned by REF without baking it into an image, and no registry release (an
owner step) is needed. A dependency the study image and the overlays lack is the trigger
for a new image version.

The pod watchdog `scripts/dev/battery/pod_watchdog.py` (#1176) stays CONFIRM-02's: it
waits for the AX42's teardown marker and shreds a sealed pod. A public job needs only the
bootstrap's own deadline self-terminate, which every code-ship pod already runs.

## Not covered

Sealed or hidden material, AX42 work, miner compute, mainnet, a run over the per-run cap
(it needs its own owner record), and any job module that needs network on the pod beyond
the code fetch.
