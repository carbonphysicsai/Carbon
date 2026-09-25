"""The operator's battery validator deployment: one configuration, one daemon.

A campaign (the Launchpad's or the autonomous agent's) reaches battery
evaluation only here, and only through the M3 daemon (`daemon.BatteryValidator`).
There is no second battery submission or evaluation path.

The configuration is an owner-only JSON file (schema
`carbon.battery.validator-deployment.v1`). Every path it names is the
operator's; none is reachable from a miner surface:

- `state`: the daemon's durable SQLite state (`pool_store.PoolStore`);
- `private_root`, `journal`: the private seed root and its append-only journal;
- `work`: the directory the isolated worker stages runs in;
- `backend`: `"carrier"` (the isolated reconstruction worker; needs
  `image_manifest`) or `"direct"` (in-process, trusted, reported as
  `DIRECT_TRUSTED_PROCESS` in every outcome);
- `require_commitment`: whether an on-chain commitment (OD-7) is checked.
  A deployment that requires one but has no chain reader configured refuses
  every submission as `commitment_reader_unavailable`; it never skips the
  check;
- `service_key` (optional): the Carbon service key (OD-6) results are signed
  with. Named by path; never read into a log or an outcome.

Loading fails closed: a missing, group-readable or linked file, an unknown
field or a changed identity binding is `EvaluationUnavailable`, never a score.
"""

from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path

SCHEMA = "carbon.battery.validator-deployment.v1"
REQUIRED = {"schema", "state", "private_root", "journal", "work", "backend"}
OPTIONAL = {"require_commitment", "service_key", "image_manifest", "seconds"}
BACKENDS = ("carrier", "direct")

_VALIDATORS = {}
_LOCK = threading.RLock()


class EvaluationUnavailable(RuntimeError):
    """The deployment cannot evaluate: an infrastructure state, never a score."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _private(path):
    path = Path(path)
    try:
        info = os.lstat(path)
    except OSError:
        raise EvaluationUnavailable("evaluation_input_missing") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise EvaluationUnavailable("evaluation_input_not_regular")
    if info.st_mode & 0o077:
        raise EvaluationUnavailable("evaluation_input_not_owner_only")
    return path


def load_config(path):
    config = json.loads(_private(path).read_bytes())
    if type(config) is not dict or config.get("schema") != SCHEMA:
        raise EvaluationUnavailable("evaluation_config_schema")
    if not REQUIRED <= set(config) or set(config) - REQUIRED - OPTIONAL:
        raise EvaluationUnavailable("evaluation_config_fields")
    if config["backend"] not in BACKENDS:
        raise EvaluationUnavailable("evaluation_config_backend")
    if config["backend"] == "carrier" and not config.get("image_manifest"):
        raise EvaluationUnavailable("evaluation_config_image")
    if type(config.get("require_commitment", True)) is not bool:
        raise EvaluationUnavailable("evaluation_config_fields")
    return config


def build(config, *, repository):
    """A started daemon for one configuration. Never dispatches work."""
    from . import seeds
    from .daemon import BatteryValidator
    from .pool_store import PoolStore, StateError
    from .signing import ServiceKey
    from .worker import CarrierBackend, DirectBackend, WorkLedger

    root = seeds.PrivateRoot.load(_private(config["private_root"]))
    journal = seeds.SeedJournal(config["journal"])
    store = PoolStore(config["state"])
    work = Path(config["work"])
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    if config["backend"] == "carrier":
        from carbon.reconstruction.worker.docker_runtime import (
            doctor,
            load_image_identity,
        )

        image = load_image_identity(config["image_manifest"])
        if not doctor(image_id=image.image_id, image_identity=image).eligible:
            raise EvaluationUnavailable("evaluation_host_unavailable")
        backend = CarrierBackend(
            WorkLedger(store, work),
            image,
            root=repository,
            seconds=int(config.get("seconds", 600)),
        )
    else:
        backend = DirectBackend(repository)
    key = config.get("service_key")
    validator = BatteryValidator(
        store=store,
        backend=backend,
        root=root,
        journal=journal,
        repository=repository,
        commitments=None,
        require_commitment=config.get("require_commitment", True),
        service_key=None if key is None else ServiceKey.load(key),
    )
    try:
        validator.start()
    except StateError as changed:
        raise EvaluationUnavailable("evaluation_" + changed.code) from None
    except ValueError:
        raise EvaluationUnavailable("evaluation_journal_refused") from None
    return validator


def validator(config_path, *, repository):
    """One daemon per configuration for this process."""
    key = str(Path(config_path).resolve())
    with _LOCK:
        if key not in _VALIDATORS:
            _VALIDATORS[key] = build(load_config(key), repository=repository)
        return _VALIDATORS[key]


def evaluate(target, submission):
    """Admit and advance one authenticated submission; return its outcome.

    Serialized per process: the daemon's state file is the single writer's.
    """
    from .daemon import CommitmentRequired

    with _LOCK:
        try:
            admitted = target.admit(submission)
        except CommitmentRequired:
            code = (
                "commitment_reader_unavailable"
                if target.commitments is None
                else "commitment_required"
            )
            raise EvaluationUnavailable(code) from None
        sid = admitted["submission_id"]
        if admitted["state"] != "INVALID_CONSTRUCTION":
            target.process(sid)
            target.run_pending()
        return target.outcome(sid)
