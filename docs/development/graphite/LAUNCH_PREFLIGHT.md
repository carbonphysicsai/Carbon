# Graphite launch preflight and heartbeat (GRAPHITE-LAUNCH-PREFLIGHT-01)

Stage A failed four times on things a check would have caught:
- the wrong lane;
- keys in the wrong distro;
- two runs on one controller root;
- pods refused at launch.

This page is the executor's routine.

## 1. Before every launch, and after any restart

```bash
python -m carbon.agent_campaign.graphite.preflight \
  --lane LANE.json --profile PROFILE.json --grant GRANT.json \
  --root ROOT_RUN1 --root ROOT_RUN2 \
  --probe --key-file RUNPOD_KEY_PATH --code-ref PUSHED_SHA
```

- **`--root`:** one per run that will be live at the same time.
- **`--probe`:** creates one real pod and terminates it. That pod is the
  only spend.
- **Without `--probe`,** nothing is spent.
- **`--key-file` alone** (no spend; GRANT-POD-CEILING-01) checks two
  things:
  - the operator's balance-floor file (`~/.runpod/campaigns.json`) exists in
    this distro and names a floor;
  - the live offer is within the grant's pod rate ceiling.

  An offer above the ceiling fails with `owner decision: offer X/h > grant
  ceiling Y/h`.
- **Every failure is printed,** and `owner_needs` lists the owner-only
  fixes together: a password, a key copy, a mode change, or a grant
  re-approval.
- **The exit code** is 0 only when everything passes.

The lane file (`carbon.graphite.preflight-lane.v1`) is the executor's and is
never committed. It names the lane's endpoints and key paths:

```json
{
  "schema": "carbon.graphite.preflight-lane.v1",
  "signer": {"url": "http://127.0.0.1:<port>/health"},
  "control_center": {"url": "http://127.0.0.1:<port>/"},
  "tunnels": [{"name": "validator", "host": "127.0.0.1", "port": 0}],
  "keys": [{"name": "engy", "path": "<path>"}]
}
```

**The checks:**
- the signer and Control Center answer;
- every tunnel port accepts a connection;
- every key file exists with mode 600 (paths only; no key is read);
- HEAD is the profile's `accepted_revision`;
- the roots are distinct and none sits inside another or inside the
  repository, and there are no more of them than the grant's
  `max_concurrency`;
- `runs x worst case + cleanup <= ceiling`;
- with `--probe`: the launch's own offer check, a pod created and running,
  then terminated and gone from the provider's listing. The probe pod is
  built by the real launch's `RunPodPods.pod_spec`, with the full
  environment (code manifest, CA bundle, phase config); only its start
  command is a sleep (`PROBE_COMMAND`). So the env-size guard below applies
  to the probe too (GRAPHITE-POD-ENV-SIZE-01).

**The pod environment.** RunPod answers a create request whose environment
is over about 118,000 characters with an opaque HTTP 500, which the
operator layer records as `pod_launch_ambiguous`. A Graphite pod therefore
ships only the import closure of what it runs (`pods.ship_list`:
`ENTRY_MODULES`, `DYNAMIC_PACKAGES`, the non-code files beside them, and the
scoring's data, never the lessons register, a `private` directory or a path
the guard names). Each shipped file is still sha-pinned. `pod_spec` refuses
an environment over 90,000 characters (`pod_env.ENV_LIMIT_CHARS`) with
`pod_env_too_large`, before any provider call.

## 2. While a run is live: the heartbeat

Every live phase-3 and phase-4 run writes `heartbeat.json` beside its run
every 2 minutes. To have all runs in one shared directory, set
`CARBON_GRAPHITE_HEARTBEAT_DIR` before launching. Each run then also writes
`<run id>.json` there.

**Fields:**
- `alive` and `phase`;
- `last_agent_call_at` and `last_event`;
- `pods`: launched, refused, settled;
- `booked_usd`;
- `last_error`;
- `status` and `status_reason`.

**`status` is STALLED** when the heartbeat is more than 15 minutes old while
the run is alive, or when every pod launch so far was refused.
`heartbeat.read(path)` recomputes it at read time, so an old file reads
STALLED.
