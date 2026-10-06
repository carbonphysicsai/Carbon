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
- `torch_image_manifest` (optional, carrier only): the pinned PyTorch worker
  image (OWNER-PYTORCH-BACKEND-01). Without it the deployment serves JAX
  recipes only, and a PyTorch recipe is answered `backend_not_served`, an
  unavailability that is never recorded against the miner;
- `rule` (optional): `"v1"` (the default; OD-2's count-based rotation) or
  `"v2"` (OWNER-BATTERY-SCORING-WINDOW-01: one scored submission per hotkey
  per tempo, block-based rotation). The seed root is committed for one rule,
  so a deployment never changes rule in place;
- `require_commitment`: whether an on-chain commitment (OD-7) is checked.
  A deployment that requires one but has no chain reader configured refuses
  every submission as `commitment_reader_unavailable`; it never skips the
  check;
- `commitment_reader` (optional; VALIDATOR-14): the chain the commitments
  are read from, as `{network, endpoint, provider, genesis_hash, netuid}`
  (`chain.models.ChainContext`). It is read-only
  (`chain.commitments.ChainCommitmentReader`). A chain failure while reading is
  `commitment_reader_unavailable`: infrastructure, never the miner's;
- `service_key` (optional): the Carbon service key (OD-6) results are signed
  with. Named by path; never read into a log or an outcome.
- `development_only` (optional, default false; VALIDATOR-13, the owner's
  opt-in): a Graphite development deployment that may admit a registered
  development variant from a `graphite-dev:` identity. It requires
  `require_commitment: false` and no `commitment_reader`, and the winner-weight
  publisher refuses it: a development deployment never sets weights and never
  serves miners.

Loading fails closed: a missing, group-readable or linked file, an unknown
field or a changed identity binding is `EvaluationUnavailable`, never a score.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import stat
import threading
from pathlib import Path

SCHEMA = "carbon.battery.validator-deployment.v1"
REQUIRED = {"schema", "state", "private_root", "journal", "work", "backend"}
OPTIONAL = {
    "archived",
    "require_commitment",
    "service_key",
    "image_manifest",
    "torch_image_manifest",
    "seconds",
    "rule",
    "commitment_reader",
    "development_only",
}
READER_FIELDS = {"network", "endpoint", "provider", "genesis_hash", "netuid"}
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


def rule_for(config):
    """The exam rule a deployment runs: `rule` in its configuration, else v1."""
    from .exam import RULES

    return RULES[config.get("rule", "v1")]


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
    if config.get("torch_image_manifest") and config["backend"] != "carrier":
        raise EvaluationUnavailable("evaluation_config_image")
    from .exam import RULES

    if config.get("rule", "v1") not in RULES:
        raise EvaluationUnavailable("evaluation_config_rule")
    if type(config.get("require_commitment", True)) is not bool:
        raise EvaluationUnavailable("evaluation_config_fields")
    if "archived" in config and (
        type(config["archived"]) is not str
        or not config["archived"].startswith("OWNER-")
    ):
        raise EvaluationUnavailable("evaluation_config_fields")
    if "commitment_reader" in config:
        _commitment_reader(config)  # refuses a malformed chain context now
    if type(config.get("development_only", False)) is not bool:
        raise EvaluationUnavailable("evaluation_config_fields")
    if config.get("development_only") and (
        config.get("require_commitment", True) is not False
        or "commitment_reader" in config
    ):
        # A development deployment serves no miner and sets no weights.
        raise EvaluationUnavailable("evaluation_config_development_only")
    return config


def _commitment_reader(config):
    """The configured read-only commitment reader, or None."""
    spec = config.get("commitment_reader")
    if spec is None:
        return None
    from carbon.chain.commitments import ChainCommitmentReader
    from carbon.chain.models import ChainContext, ChainFailure

    if type(spec) is not dict or set(spec) != READER_FIELDS:
        raise EvaluationUnavailable("evaluation_config_commitment_reader")
    try:
        return ChainCommitmentReader(ChainContext(**spec))
    except (ChainFailure, TypeError, ValueError):
        raise EvaluationUnavailable("evaluation_config_commitment_reader") from None


@contextlib.contextmanager
def writer(target):
    """The single writer of one deployment's state, across processes.

    An exclusive `flock` on `<state>.lock`, held for the whole operation,
    so an operator command never recovers (abandons) or races a run that
    another process - a campaign submitting, the daemon advancing - is
    executing. Threads in this process queue on `_LOCK` first.
    """
    with _LOCK:
        fd = os.open(target.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield target
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def _owner_only_directory(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        # Runs stage private case inputs here.
        raise EvaluationUnavailable("evaluation_work_not_owner_only")
    return path


def require_live(config):
    """Refuse a deployment the owner archived (its `archived` field names the
    owner record). An archived deployment is never run, upgraded or used as a
    weight source again; it stays readable, so a study that pinned its
    journal or root can still regenerate from it."""
    if config.get("archived"):
        raise EvaluationUnavailable("evaluation_config_archived")


def build(config, *, repository, readonly=False):
    """A daemon for one configuration. Never dispatches work.

    `readonly` builds one for status and listing only: nothing is started,
    recovered or locked, and it must not be used to advance anything.
    """
    from . import seeds
    from .daemon import BatteryValidator
    from .pool_store import PoolStore, StateError
    from .signing import ServiceKey
    from .worker import CarrierBackend, DirectBackend, WorkLedger

    if not readonly:
        require_live(config)
    root = seeds.PrivateRoot.load(_private(config["private_root"]))
    journal = seeds.SeedJournal(config["journal"])
    store = PoolStore(config["state"], rule=rule_for(config))
    work = _owner_only_directory(config["work"])
    if config["backend"] == "carrier" and not readonly:
        from carbon.reconstruction.worker.docker_runtime import (
            doctor,
            load_image_identity,
        )

        image = load_image_identity(Path(config["image_manifest"]))
        torch_image = (
            load_image_identity(Path(config["torch_image_manifest"]))
            if config.get("torch_image_manifest")
            else None
        )
        if torch_image is not None:
            from carbon.reconstruction.torch_profile import requirements_digest

            # The PyTorch image is the one built on this JAX image from this
            # checkout's exact-hashed science-torch export, nothing else.
            if (
                torch_image.base_image_digest != image.image_id
                or torch_image.lock_digest != requirements_digest(repository)
            ):
                raise EvaluationUnavailable("evaluation_config_image")
        for pinned in (image, torch_image):
            if (
                pinned is not None
                and not doctor(image_id=pinned.image_id, image_identity=pinned).eligible
            ):
                raise EvaluationUnavailable("evaluation_host_unavailable")
        backend = CarrierBackend(
            WorkLedger(store, work),
            image,
            torch_image=torch_image,
            root=repository,
            seconds=int(config.get("seconds", 600)),
        )
    else:
        backend = DirectBackend(repository)
    key = config.get("service_key")
    try:
        validator = BatteryValidator(
            store=store,
            backend=backend,
            root=root,
            journal=journal,
            repository=repository,
            commitments=_commitment_reader(config),
            require_commitment=config.get("require_commitment", True),
            service_key=None if key is None else ServiceKey.load(key),
            development_only=config.get("development_only", False),
        )
    except StateError as mismatch:
        raise EvaluationUnavailable("evaluation_" + mismatch.code) from None
    validator.lock_path = str(config["state"]) + ".lock"
    validator.readonly = readonly
    if readonly:
        return validator
    try:
        with writer(validator):
            validator.start()
    except StateError as changed:
        raise EvaluationUnavailable("evaluation_" + changed.code) from None
    except ValueError:
        raise EvaluationUnavailable("evaluation_journal_refused") from None
    return validator


def validator(config_path, *, repository, readonly=False):
    """One daemon per configuration (and mode) for this process."""
    key = (str(Path(config_path).resolve()), readonly)
    with _LOCK:
        if key not in _VALIDATORS:
            _VALIDATORS[key] = build(
                load_config(key[0]), repository=repository, readonly=readonly
            )
        return _VALIDATORS[key]


def evaluate(target, submission):
    """Admit and advance one authenticated submission; return its outcome.

    Runs under the deployment's single-writer lock (`writer`).
    """
    from carbon.chain.commitments import CommitmentUnavailable

    from .daemon import BackendNotServed, CommitmentRequired
    from .pool_store import HotkeyWindowUsed

    if getattr(target, "readonly", False):
        raise EvaluationUnavailable("evaluation_readonly")
    with writer(target):
        try:
            admitted = target.admit(submission)
        except HotkeyWindowUsed as used:
            # Rule v2: not a refusal of the recipe; admissible next window.
            refused = EvaluationUnavailable(
                "hotkey_window_used" if used.next_block else "receipt_block_missing"
            )
            refused.next_block = used.next_block
            raise refused from None
        except CommitmentUnavailable:
            # The chain could not be read: infrastructure, never the miner's.
            raise EvaluationUnavailable("commitment_reader_unavailable") from None
        except CommitmentRequired:
            code = (
                "commitment_reader_unavailable"
                if target.commitments is None
                else "commitment_required"
            )
            raise EvaluationUnavailable(code) from None
        except BackendNotServed:
            raise EvaluationUnavailable("backend_not_served") from None
        sid = admitted["submission_id"]
        if admitted["state"] != "INVALID_CONSTRUCTION":
            target.process(sid)
            target.run_pending()
        return target.outcome(sid)
