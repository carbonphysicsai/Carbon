## 2026-10-10 — GRAPHITE-LAUNCH-PREFLIGHT-01: one preflight before every Graphite launch, a heartbeat and a stall rule

**Authority.**
- **The direction.** The owner's "Fix this system", relayed by the Test Lead
  as the top priority.
- **The cause.** Stage A failed four times on launch conditions: the wrong
  lane, keys in the wrong distro, two runs on one controller root, and pods
  refused at launch.
- **The scope.** This is engineering tooling. It grants and spends nothing.
  The `--probe` pod is the one spend, made in real use only.

**Decision.**
- **`carbon.agent_campaign.graphite.preflight`** is one command, and it
  reports every failure at once. It checks:
  - the lane signer and Control Center over HTTP;
  - the tunnel ports over TCP;
  - the key files, for existence and mode 600, by path only;
  - that HEAD is the profile's `accepted_revision`;
  - one distinct, non-nested, out-of-repository controller root per
    concurrent run, within the grant's `max_concurrency`;
  - the grant arithmetic;
  - with `--probe`, a real minimal pod: the launch's own offer check,
    created, running, terminated and verified gone.

  Owner-only fixes are collected in `owner_needs`. The lane file is the
  executor's and is never committed.
- **`carbon.agent_campaign.graphite.heartbeat`.**
  - Every live phase-3 and phase-4 run (`run_session`) writes
    `heartbeat.json` every 2 minutes, built from the run's own files.
  - It also writes to `$CARBON_GRAPHITE_HEARTBEAT_DIR` when that is set.
  - A heartbeat failure never stops a run.
- **The stall rule.** A run reads STALLED when its heartbeat is more than 15
  minutes old while it is alive, or when every pod launch was refused.

**Tests.** `tests/cpu/test_graphite_launch_preflight.py`, 20, all on
fixtures:
- the lane, with up and down endpoints and the owner need for the signer;
- the keys, by mode;
- the revision;
- the roots;
- the grant;
- the probe's paths: OK, no stock, refused, never running and still
  listed, with the pod always terminated;
- one command listing every owner need at once;
- the heartbeat's fields, the shared copy, its mode, both stall rules, the
  finished state and the writer thread.

**Not claimed.**
- **The probe has not run against the live account.** The executor runs it
  first.
- **No security review.** The heartbeat holds no secret; the lane file
  holds paths only.
