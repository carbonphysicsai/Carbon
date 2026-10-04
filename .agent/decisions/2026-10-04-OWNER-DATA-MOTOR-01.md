# 2026-10-04 — OWNER-DATA-MOTOR-01: motor reference data collection: image, host, timing route and counted compute

**Authority.** The owner approved this in two places on 2026-10-04:

- In the Data Collection session, approving its three requests:

  > approve all three, publish the image

- In chat to the Test Lead session, relayed by the Test Lead:

  > approve

  This covered the operator-host platform and the image publish.

**Context.** CHALLENGE-MOTOR-03 (`.agent/tickets/CHALLENGE-MOTOR-03_decision_foundation.md`,
CHALLENGE-MOTOR-DECISION-FOUNDATION-01) left two things blocking counted GetDP
execution: a digest-pinned image, and compute approval for the registered
48 + 12 campaign. The registered runner refuses `--native` for counted plans,
so every counted case is a `docker run`. A RunPod pod cannot host that.

**Scope.** Internal DEVELOPMENT data collection under
OWNER-GRAPHITE-TEST-WAVE-01. It makes no scientific, security, network,
production or customer qualification. It creates no reward, weight or LIVE
authority.

## 1. The motor reference image is published, pinned by digest

`ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05`

- Built from `scripts/dev/motor/reference/Dockerfile` at main
  `75330721b`, on the operator's Linux host.
- **Visibility is organisation-internal, not public.** The Dockerfile records
  that GetDP and Gmsh are GPL and that Carbon "does not redistribute them".
  Making the package public would redistribute those binaries. That is a
  licensing decision for the owner under OWNER-LICENSE-01, and this record
  does not take it. Pinning by digest works either way.

## 2. The counted motor campaign runs on the operator host

The operator WSL host runs the counted campaign with Docker: 20 threads, a
12th Gen Intel Core i7-12700H. Following the Test Lead's conditions, every
counted run records:
- the CPU model;
- each case's wall time and allocated core-seconds;
- the concurrency.

The host has no approved USD rate. Its cost is reported in core-seconds with
the hardware named, and never priced (OWNER-GRAPHITE-TEST-WAVE-01 §5).

The raw artifacts and the SQLite campaign ledger are kept outside every
worktree, with hashes, plus one off-machine copy. The repository carries only
the manifest, identities, hashes, result and report.

## 3. A small cpu5c timing study on RunPod gives the priced unit

| Field | Value |
| --- | --- |
| Campaign | `motor-timing` in `pod_control.py` |
| Route | `runpod-cpu5c-16vcpu`: flavor cpu5c only, no fallback flavor |
| Monetary ceiling | USD 5.00, including pod time and the USD 0.25 cleanup reserve |
| Per-pod rate guard | USD 1.00/h; a pod created above it is terminated at once |
| Pods | 1 at a time |
| Execution | native, non-counted, 6 concurrent cases, single-threaded GetDP |
| Plan | `docs/development/evidence/motor-timing-2026-10-04/plans/motor-timing-calibration.json` |

The plan has 12 cases: the 6 slowest public TRAIN geometries, each run at
the study's boundary-stress conditions b01 and b02. The selection rule was
fixed before any calibration solve. The 8 study designs are excluded (see
`selection.json`). The same 12 cases also run on the operator host in
Docker, which gives paired host-to-cpu5c timings.

These timings are not decision evidence and never enter the counted
comparator. The ceiling is operator configuration (`~/.runpod/campaigns.json`)
and stays out of the repository's code. Spend totals and balances stay in
the private ledger.

## 4. Compute for the counted campaign is approved for its registered envelope

The approved envelope:
- 48 initial executions, up to 12 retries, and a hard cap of 60 attempts;
- 2 CPUs each, 6 concurrent;
- artifact retention `all`;
- the operator host, with no rented compute.

The per-case timeout is the one exception. The registered 3,600 s is too
tight for this host: the motor pilot's maximum was 5,983 s. The timeout is
therefore set from the operator-host calibration, at no less than twice the
observed p95. That change goes in its own PR before the image-bound plan is
generated, because it changes the campaign identity.

Before dispatch, the exact plan and envelope go to the Test Lead and the
owner. Dispatch also waits for a host window agreed with the Graphite Test
executor.

**Unchanged.**
- The motor exam, its pools and the private pool, whose commitment never
  reaches rented compute.
- The study's designs, conditions and requirements
  (OWNER-GRAPHITE-TEST-WAVE-01 §6).
- Every scoring rule, gate and tolerance.
- EV5.
