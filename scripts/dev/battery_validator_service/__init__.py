"""The battery validator as a long-lived service on the operator host (LP-PROD-G).

    python -m scripts.dev.battery_validator_service <command> --config SERVICE.json

The service is two processes over one deployment, under the deployment's
single-writer lock:

- the **intake** (`python -m carbon.battery.intake serve`): the submission
  endpoint a miner's machine reaches (OD-7(b)). Its worker admits each signed
  `battery_submit` and advances it through the deployment's daemon;
- the **validator daemon** (`python -m carbon.battery.operate run --every
  --heartbeat`): one `run` per period, which also advances what reached the
  deployment by another path (a campaign on this host submitting in
  process) and opens finalist comparisons.

Each holds a lock while it runs (and the daemon keeps a heartbeat), so
`status` and `restore` see it however it was started. Neither exits while
the host cannot serve the deployment yet (Docker down or starting); they
wait it out.

Commands (each prints one JSON document; exit 0 ok, 2 refused by a named
code, 3 unhealthy):

- ``preflight``: every check a start needs, all reported at once - the
  service, intake and deployment configurations are valid and owner-only;
  the pinned worker images are present by digest and doctor-eligible; the
  deployment is bound to this checkout's contract (`operate upgrade` done);
  miners practise on the validator's own pinned images (parity); and, only
  for a non-loopback bind, the exposure record is named and recorded and the
  TLS certificate and key exist (`service.preflight`). With
  ``--wait-for-host SECONDS`` it re-checks while Docker is not answering yet;
- ``parity``: the parity check alone (`service.parity`). The validator's
  pinned images are the standard miners practise against
  (OWNER-LAUNCHPAD-PROD-02, answer 10): each practice manifest must be the
  validator's image, and practice reaches nothing of the hidden test
  conditions (no private case, seed, root, reference or per-case result);
- ``status``: the intake (its lock and its own public answer over its bound
  address), the daemon (its lock and heartbeat), the supervisor's children,
  the inbox and deployment counts and the latest backup; healthy only when
  every part is seen running;
- ``backup`` / ``restore``: the private root, seed journal and daemon state
  snapshotted together under the writer lock, with the intake's inbox and
  transport journal (`backup`); a restore is all or nothing and never
  overwrites a file;
- ``supervise``: run both processes, restart one that fails (with backoff and
  a burst limit), never one that refused its configuration (exit 2), and
  write structured logs (`supervisor`);
- ``units``: write `systemd --user` units for the same two processes, for a
  host that runs systemd. It writes files only; enabling them is the
  operator's step.

Bounds kept, unchanged: the default bind is loopback; a public bind needs the
owner's exposure record and TLS in the intake (OWNER-INTAKE-EXPOSURE-01) and
the isolated carrier; Carbon holds no hotkey (the miner signs); nothing here
writes to a chain, sets weights or spends. Scores stay DEVELOPMENT evidence.
This tooling is engineering, tested on loopback only: it is not a security
audit and qualifies nothing (AGENTS §13).
"""
