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
  then terminated and gone from the provider's listing.

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
