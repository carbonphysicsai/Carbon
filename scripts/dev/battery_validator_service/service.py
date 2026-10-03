"""The service configuration, its preflight, image parity and status.

The service configuration is an owner-only JSON file (schema
`carbon.battery.validator-service.v1`), outside every checkout:

- `intake`: the intake configuration (`carbon.battery.intake.v1`). It names
  the deployment, so the service never names a second one;
- `state_dir`: owner-only directory for the supervisor's lock, state file
  and logs, and the validator daemon's heartbeat and its lock;
- `backups`: owner-only directory backups are written to;
- `practice_images` (required for a carrier deployment): the worker image
  manifests miners practise against, under the deployment's own keys -
  `image_manifest` (JAX) and, when the deployment serves PyTorch,
  `torch_image_manifest`. Parity compares them with the images the
  validator scores with;
- `run_every_s` (optional, default 60): the validator daemon's period;
- `allow_direct_backend` (optional, default false): accept a `direct`
  deployment (`DIRECT_TRUSTED_PROCESS`, recipes rebuilt in process) for
  local development. Only on loopback: a public bind never accepts one.

Every check answers with a closed code and, where there is one, the next
step. Nothing here starts, recovers, locks or advances the deployment, and
nothing prints a key, seed, root or case.

**What runs is read from locks**, the same however the service was started
(`supervise` or the systemd units): the supervisor holds
`<state_dir>/supervisor.lock`, the intake `<inbox>.serve.lock`, and the
validator daemon `<state_dir>/daemon-heartbeat.json.lock` beside the
heartbeat it keeps (`operate run --every --heartbeat`). Each is probed
shared and non-blocking, for an instant (`lock_held`).
"""

from __future__ import annotations

import fcntl
import hashlib
import http.client
import json
import os
import ssl
import stat
import time
from dataclasses import dataclass
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
SCHEMA = "carbon.battery.validator-service.v1"
REPORT_SCHEMA = "carbon.battery.validator-service-report.v1"
REQUIRED = frozenset({"schema", "intake", "state_dir", "backups"})
OPTIONAL = frozenset({"practice_images", "run_every_s", "allow_direct_backend"})
#: The deployment's image keys; `practice_images` names its manifests the same.
IMAGE_KEYS = {"image_manifest": "jax", "torch_image_manifest": "pytorch"}
#: The validator daemon's default period: an engineering value. The intake's
#: own worker advances every submission it receives at once.
RUN_EVERY_S = 60.0
#: The validator daemon's heartbeat, in `state_dir`.
HEARTBEAT = "daemon-heartbeat.json"
#: A daemon between passes is fresh while its heartbeat is at most twice its
#: period plus a margin old. A pass in flight is never stale: rebuilds and
#: scoring run for minutes. Engineering values.
STALE_PERIODS, STALE_MARGIN_S = 2.0, 30.0
#: `preflight --wait-for-host` and `supervise` re-check this long, this
#: often, while the only refusal is the host's passing state (Docker not
#: answering). Engineering values; a unit's start timeout allows for them.
HOST_WAIT_S, HOST_POLL_S = 300.0, 5.0
#: A pinned worker image's identity, every field compared by parity.
IDENTITY_FIELDS = (
    "image_id",
    "config_digest",
    "source_tree_digest",
    "wheel_digest",
    "lock_digest",
    "base_image_digest",
    "build_recipe_digest",
    "entrypoint_digest",
)


class ServiceRefused(Exception):
    """A named, closed refusal, with the operator's next step if any."""

    def __init__(self, code, *, next_step=None, **detail):
        super().__init__(code)
        self.code, self.next_step, self.detail = code, next_step, detail

    def as_dict(self):
        found = {"refused": self.code, **self.detail}
        if self.next_step:
            found["next_step"] = self.next_step
        return found


@dataclass(frozen=True)
class Service:
    """One loaded service configuration."""

    path: Path
    config: dict

    @property
    def intake_path(self):
        return Path(self.config["intake"])

    @property
    def state_dir(self):
        return Path(self.config["state_dir"])

    @property
    def backups(self):
        return Path(self.config["backups"])

    @property
    def run_every_s(self):
        return float(self.config.get("run_every_s", RUN_EVERY_S))

    @property
    def allow_direct_backend(self):
        return self.config.get("allow_direct_backend", False)


def owner_only_file(path, prefix):
    """A regular, unlinked, owner-only file, or a refusal named `prefix_*`."""
    try:
        info = os.lstat(path)
    except OSError:
        raise ServiceRefused(prefix + "_missing") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ServiceRefused(prefix + "_not_regular")
    if info.st_mode & 0o077:
        raise ServiceRefused(
            prefix + "_not_owner_only", next_step="chmod 600 the file named"
        )
    return Path(path)


def owner_only_directory(path, *, create=False):
    """An owner-only directory; with `create`, made `0700` when missing."""
    path = Path(path)
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        info = os.lstat(path)
    except OSError:
        return path  # made on first use, owner-only
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise ServiceRefused(
            "service_directory_not_owner_only",
            next_step="chmod 700 the directory, owned by the operator",
            directory=str(path),
        )
    return path


def lock_held(path):
    """Whether a process holds an exclusive `flock` on `path` right now.

    Probed shared and non-blocking, for an instant: two probes never
    conflict, and every holder retries its own lock briefly when it starts,
    so a probe never makes a start fail.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def running(service):
    """Whether a supervisor holds this service's lock right now."""
    return lock_held(service.state_dir / "supervisor.lock")


def heartbeat_path(service):
    """Where the validator daemon keeps its heartbeat (`--heartbeat`)."""
    return service.state_dir / HEARTBEAT


def daemon_lock_path(service):
    return Path(str(heartbeat_path(service)) + ".lock")


def running_parts(service, intake_config):
    """Which of the service's processes run right now, read from their locks
    whoever started them: `supervisor`, `intake`, `daemon`."""
    from carbon.battery.intake import serve_lock_path

    locks = {
        "supervisor": service.state_dir / "supervisor.lock",
        "intake": serve_lock_path(intake_config),
        "daemon": daemon_lock_path(service),
    }
    return sorted(name for name, path in locks.items() if lock_held(path))


def load_service(path):
    """An owner-only service configuration, checked field by field."""
    owner_only_file(path, "service_config")
    try:
        config = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        raise ServiceRefused("service_config_schema") from None
    if type(config) is not dict or config.get("schema") != SCHEMA:
        raise ServiceRefused("service_config_schema")
    if not REQUIRED <= set(config) or set(config) - REQUIRED - OPTIONAL:
        raise ServiceRefused("service_config_fields")
    paths = [config[k] for k in ("intake", "state_dir", "backups")]
    practice = config.get("practice_images", {})
    if type(practice) is not dict or set(practice) - set(IMAGE_KEYS):
        raise ServiceRefused("service_config_fields")
    paths += list(practice.values())
    if any(type(p) is not str or not Path(p).is_absolute() for p in paths):
        raise ServiceRefused("service_config_fields")
    every = config.get("run_every_s", RUN_EVERY_S)
    from carbon.battery.operate import MIN_EVERY_S

    if type(every) not in (int, float) or not every >= MIN_EVERY_S:
        raise ServiceRefused("service_config_fields")
    if type(config.get("allow_direct_backend", False)) is not bool:
        raise ServiceRefused("service_config_fields")
    service = Service(Path(path), config)
    owner_only_directory(service.state_dir)
    owner_only_directory(service.backups)
    return service


# --- the checks -----------------------------------------------------------------


def _intake(service, repository):
    from carbon.battery.intake import IntakeUnavailable, load_config

    try:
        return load_config(service.intake_path, repository=repository)
    except IntakeUnavailable as refused:
        raise ServiceRefused(refused.code) from None


def _deployment(intake_config):
    from carbon.battery import deployment

    try:
        return deployment.load_config(intake_config["deployment"])
    except deployment.EvaluationUnavailable as refused:
        raise ServiceRefused(refused.code) from None


def check_exposure(intake_config, deployment_config):
    """Loopback needs nothing more. A public bind needs the owner's recorded
    exposure decision (checked when the intake configuration loads), its TLS
    certificate and an owner-only key that load, and the isolated carrier."""
    from carbon.battery import intake

    if intake.is_loopback(intake_config["host"]):
        return {"bind": "loopback", "host": intake_config["host"]}
    try:
        info = os.lstat(intake_config["tls_cert"])
    except OSError:
        info = None
    if info is None or not stat.S_ISREG(info.st_mode):
        raise ServiceRefused("intake_tls_cert_missing")
    owner_only_file(intake_config["tls_key"], "intake_tls_key")
    try:
        intake.tls_context(intake_config)
        intake.require_isolation(intake_config, deployment_config)
    except intake.IntakeUnavailable as refused:
        raise ServiceRefused(refused.code) from None
    return {
        "bind": "public",
        "host": intake_config["host"],
        "exposure_record": intake_config["exposure_record"],
        "tls": True,
    }


def check_deployment(service, intake_config, deployment_config, repository):
    """The deployment builds read-only (its root, journal and work directory
    are owner-only, its rule matches its seed pin), and a `direct` one is
    accepted only where the service allows it for development."""
    from carbon.battery import deployment

    try:
        deployment.validator(
            intake_config["deployment"], repository=repository, readonly=True
        )
    except deployment.EvaluationUnavailable as refused:
        raise ServiceRefused(refused.code) from None
    backend = deployment_config["backend"]
    if backend == "direct" and not service.allow_direct_backend:
        raise ServiceRefused(
            "deployment_backend_direct",
            next_step=(
                "serve through the isolated carrier (backend: carrier with "
                "image_manifest); a direct deployment is development only"
            ),
        )
    return {
        "backend": backend,
        "evidence": "DEVELOPMENT",
        **(
            {"development_only": "DIRECT_TRUSTED_PROCESS"}
            if backend == "direct"
            else {}
        ),
    }


def _identity(path, code):
    from carbon.reconstruction.worker.docker_runtime import load_image_identity
    from carbon.reconstruction.worker.model import WorkerFailure

    try:
        return load_image_identity(Path(path))
    except WorkerFailure:
        raise ServiceRefused(code, manifest=str(path)) from None


def validator_images(deployment_config):
    """The images the validator scores with: `{key: WorkerImageIdentity}`."""
    return {
        key: _identity(deployment_config[key], "image_manifest_unreadable")
        for key in IMAGE_KEYS
        if deployment_config.get(key)
    }


def check_images(deployment_config, repository, doctor=None):
    """Each pinned worker image is present by digest and the host's doctor
    finds it eligible; a PyTorch image is the one built on the JAX image
    from this checkout's exact-hashed export (as the deployment requires)."""
    if deployment_config["backend"] != "carrier":
        return {"status": "not_applicable", "reason": "no pinned images (direct)"}
    if doctor is None:
        from carbon.reconstruction.worker.docker_runtime import doctor
    images = validator_images(deployment_config)
    torch_image = images.get("torch_image_manifest")
    if torch_image is not None:
        from carbon.reconstruction.torch_profile import requirements_digest

        if torch_image.base_image_digest != images[
            "image_manifest"
        ].image_id or torch_image.lock_digest != requirements_digest(repository):
            raise ServiceRefused(
                "torch_image_not_built_on_worker",
                next_step="rebuild with scripts/dev/torch_worker_image.sh",
            )
    found = {}
    for key, image in images.items():
        report = doctor(image_id=image.image_id, image_identity=image)
        if not report.eligible:
            raise ServiceRefused(
                "image_not_eligible",
                image=IMAGE_KEYS[key],
                doctor=report.code,
                next_step=(
                    "load or build the pinned image named by the manifest, "
                    "then rerun the doctor"
                ),
            )
        found[IMAGE_KEYS[key]] = image.image_id
    return {"images": found, "doctor": "eligible"}


def check_upgraded(intake_config, repository):
    """The stored binding is the one a start would make from this checkout:
    `operate upgrade` has carried the deployment over to the current
    contract, implementation, images and envelope. An unbound deployment
    binds at its first start."""
    from carbon.battery import deployment, operate
    from carbon.battery.pool_store import CARRY_OVER_KEYS

    path = intake_config["deployment"]
    try:
        serving = operate.serving_identities(path, repository=repository)
        bound = deployment.validator(
            path, repository=repository, readonly=True
        ).store.identities()
    except deployment.EvaluationUnavailable as refused:
        raise ServiceRefused(refused.code) from None
    if bound is None:
        return {"bound": False, "binds_at_start": True}
    changed = sorted(
        k for k in set(bound) | set(serving) if bound.get(k) != serving.get(k)
    )
    fixed = sorted(set(changed) - CARRY_OVER_KEYS)
    if fixed:
        raise ServiceRefused(
            "deployment_identities_not_carryable",
            fields=fixed,
            next_step="a changed rule, public material or seed pin needs a new deployment",
        )
    if changed:
        raise ServiceRefused(
            "deployment_not_upgraded",
            fields=changed,
            next_step="python -m carbon.battery.operate upgrade --config " + str(path),
        )
    return {"bound": True, "contract_digest": serving["contract_digest"]}


def parity(service, intake_config, deployment_config, repository):
    """The validator scores with the images miners practise against, under the
    contract they practise under.

    Every image the deployment scores with needs the manifest miners
    practise with under the same key (`parity_reference_unnamed`), and the
    two must be one image: every identity field equal (`parity_image_differs`
    names the fields). The contract the deployment is bound to must be this
    checkout's registered battery contract, the one every miner campaign on
    this checkout freezes (`parity_contract_differs`). A `direct` deployment
    has no pinned image to compare; its contract is still compared.
    """
    from carbon.battery import deployment
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        contract_digest,
    )

    current = contract_digest(BATTERY_CHALLENGE)
    try:
        bound = deployment.validator(
            intake_config["deployment"], repository=repository, readonly=True
        ).store.identities()
    except deployment.EvaluationUnavailable as refused:
        raise ServiceRefused(refused.code) from None
    scored = None if bound is None else bound["contract_digest"]
    if scored is not None and scored != current:
        raise ServiceRefused(
            "parity_contract_differs",
            validator=scored,
            miners=current,
            next_step=(
                "python -m carbon.battery.operate upgrade --config "
                + str(intake_config["deployment"])
            ),
        )
    result = {"contract_digest": current, "contract_bound": scored is not None}
    if deployment_config["backend"] != "carrier":
        return {**result, "images": "not_applicable"}
    practice = service.config.get("practice_images", {})
    images = {}
    for key, scoring in validator_images(deployment_config).items():
        if key not in practice:
            raise ServiceRefused(
                "parity_reference_unnamed",
                image=IMAGE_KEYS[key],
                next_step="name the practised manifest under practice_images." + key,
            )
        practised = _identity(practice[key], "parity_manifest_unreadable")
        differs = [
            f for f in IDENTITY_FIELDS if getattr(scoring, f) != getattr(practised, f)
        ]
        if differs:
            raise ServiceRefused(
                "parity_image_differs",
                image=IMAGE_KEYS[key],
                fields=differs,
                validator=scoring.image_id,
                miners=practised.image_id,
                next_step=(
                    "score with the image miners practise against, or publish "
                    "the validator's image for practice"
                ),
            )
        images[IMAGE_KEYS[key]] = scoring.image_id
    return {**result, "images": images}


# --- the reports ----------------------------------------------------------------


def _run_checks(checks):
    """Run each named check; one that depends on a refused one is skipped.

    A check that fails in a way it does not name (an unreadable store, a
    malformed root) is still a refusal, `check_failed` with the exception's
    type only: the preflight never passes by crashing, and never prints a
    private value.
    """
    report, values = [], {}
    for name, needs, run in checks:
        if any(values.get(n) is None for n in needs):
            report.append({"check": name, "status": "skipped"})
            values[name] = None
            continue
        try:
            value = run(values)
        except ServiceRefused as refused:
            report.append({"check": name, "status": "refused", **refused.as_dict()})
            values[name] = None
        except Exception as failure:  # noqa: BLE001 - reported by type, fail closed
            report.append(
                {
                    "check": name,
                    "status": "refused",
                    "refused": "check_failed",
                    "type": type(failure).__name__,
                }
            )
            values[name] = None
        else:
            report.append({"check": name, "status": "ok", "detail": value})
            values[name] = value if value is not None else {}
    ready = all(item["status"] == "ok" for item in report)
    return {"schema": REPORT_SCHEMA, "ready": ready, "checks": report}


def preflight(path, *, repository=REPOSITORY, doctor=None):
    """Every check a start needs, all reported at once (`ready`)."""

    def loaded(values):
        return values["service"]

    checks = [
        ("service", (), lambda v: load_service(path)),
        ("intake", ("service",), lambda v: _intake(loaded(v), repository)),
        ("deployment_config", ("intake",), lambda v: _deployment(v["intake"])),
        (
            "exposure",
            ("intake", "deployment_config"),
            lambda v: check_exposure(v["intake"], v["deployment_config"]),
        ),
        (
            "deployment",
            ("deployment_config",),
            lambda v: check_deployment(
                loaded(v), v["intake"], v["deployment_config"], repository
            ),
        ),
        (
            "images",
            ("deployment",),
            lambda v: check_images(v["deployment_config"], repository, doctor),
        ),
        (
            "upgraded",
            ("deployment",),
            lambda v: check_upgraded(v["intake"], repository),
        ),
        (
            "parity",
            ("deployment",),
            lambda v: parity(
                loaded(v), v["intake"], v["deployment_config"], repository
            ),
        ),
    ]
    report = _run_checks(checks)
    for item in report["checks"]:
        # The loaded configurations are inputs, not findings: report them
        # by outcome only.
        if item["check"] in ("service", "intake", "deployment_config"):
            item.pop("detail", None)
    return report


def host_not_ready(report):
    """Whether a preflight refused for nothing but the host's passing state:
    every refusal is a pinned image the doctor could not check because
    Docker is not answering (down, or still starting after a reboot)."""
    refused = [item for item in report["checks"] if item["status"] == "refused"]
    return bool(refused) and all(
        item.get("refused") == "image_not_eligible"
        and item.get("doctor") == "worker.doctor.docker_unavailable"
        for item in refused
    )


def wait_for_host(
    check, *, wait_s, poll_s=HOST_POLL_S, clock=time.monotonic, sleep=time.sleep
):
    """Run `check` (a preflight) until it is ready, refuses for anything but
    the host's passing state (`host_not_ready`), or `wait_s` has passed, and
    return its last report. A unit's or a supervisor's start therefore waits
    out a Docker that is still starting instead of failing into its restart
    limit; a refused configuration is still answered at once."""
    deadline = clock() + wait_s
    while True:
        report = check()
        if report["ready"] or not host_not_ready(report):
            return report
        if clock() + poll_s > deadline:
            return report
        sleep(poll_s)


def parity_report(path, *, repository=REPOSITORY):
    """The parity check alone, with what it needs."""
    report = _run_checks(
        [
            ("service", (), lambda v: load_service(path)),
            ("intake", ("service",), lambda v: _intake(v["service"], repository)),
            ("deployment_config", ("intake",), lambda v: _deployment(v["intake"])),
            (
                "parity",
                ("deployment_config",),
                lambda v: parity(
                    v["service"], v["intake"], v["deployment_config"], repository
                ),
            ),
        ]
    )
    for item in report["checks"][:3]:
        item.pop("detail", None)
    return report


def _leaf_sha256(cert_file):
    """SHA-256 of the first certificate in a PEM file: the leaf the intake
    serves (a full chain lists it first)."""
    text = Path(cert_file).read_text(encoding="ascii")
    begin, end = "-----BEGIN CERTIFICATE-----", "-----END CERTIFICATE-----"
    first = text[text.index(begin) : text.index(end) + len(end)]
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(first)).hexdigest()


def probe_intake(intake_config, *, timeout=5.0):
    """The intake's own public answer, read over its bound address.

    A wildcard bind is probed on loopback. Over TLS the handshake verifies
    against the configured certificate file (the host name is not checked,
    since the probe connects by address), and then the leaf the listener
    presents must be the file's first certificate, byte for byte: another
    certificate from the same issuer is `intake_certificate_differs`. Only
    the public facts are read: the probe sends nothing signed.
    """
    from carbon.battery.intake import INFO_PATH

    host = intake_config["host"]
    host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
    port = intake_config["port"]
    tls = "tls_cert" in intake_config
    try:
        if tls:
            context = ssl.create_default_context(cafile=intake_config["tls_cert"])
            context.check_hostname = False
            context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
            connection = http.client.HTTPSConnection(
                host, port, timeout=timeout, context=context
            )
        else:
            connection = http.client.HTTPConnection(host, port, timeout=timeout)
        try:
            connection.connect()
            if tls:
                served = connection.sock.getpeercert(binary_form=True) or b""
                if hashlib.sha256(served).hexdigest() != _leaf_sha256(
                    intake_config["tls_cert"]
                ):
                    return {"listening": True, "answer": "intake_certificate_differs"}
            connection.request("GET", INFO_PATH)
            response = connection.getresponse()
            status, body = response.status, response.read(65536)
        finally:
            connection.close()
    except (OSError, ValueError, http.client.HTTPException):
        return {"listening": False, "answer": "intake_not_listening"}
    try:
        facts = json.loads(body or b"{}")
    except ValueError:
        facts = None
    if type(facts) is not dict:
        return {"listening": True, "answer": "intake_answer_unrecognised"}
    if status != 200:
        return {"listening": True, "answer": facts.get("refused", status)}
    snapshot = facts.get("snapshot") or {}
    stamp = snapshot.get("timestamp_ms")
    return {
        "listening": True,
        "answer": "ok",
        "finalized_block": snapshot.get("finalized_block"),
        "snapshot_age_s": (
            None if type(stamp) is not int else round(time.time() - stamp / 1000, 1)
        ),
    }


def _latest_backup(service):
    try:
        names = sorted(
            p.name
            for p in service.backups.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )
    except OSError:
        names = []
    return names[-1] if names else None


def daemon_view(service, *, now=None):
    """The validator daemon as its liveness lock and heartbeat show it.

    `state` is `not_running` (no process holds the lock), `starting` (held,
    no heartbeat of its own yet), `waiting_for_host` (its last pass could not
    build the deployment: Docker down or starting), `stale` (between passes
    for longer than twice its period plus a margin: stuck), or `running`.
    `healthy` only when `running` and its last pass, if it has finished one,
    succeeded. Times, counts and the pass outcome only.
    """
    now = time.time() if now is None else now
    if not lock_held(daemon_lock_path(service)):
        return {"state": "not_running", "healthy": False}
    try:
        beat = json.loads(heartbeat_path(service).read_bytes())
    except (OSError, ValueError):
        beat = None
    if type(beat) is not dict or beat.get("stopped"):
        return {"state": "starting", "healthy": False}

    def number(key):
        value = beat.get(key)
        return value if type(value) in (int, float) else None

    updated, every = number("updated_unix"), number("every_s")
    if updated is None or every is None:
        return {"state": "starting", "healthy": False}
    last = beat.get("last_pass")
    view = {
        "passes": number("passes"),
        "last_pass": last if last in ("ok", "failed", "unavailable") else None,
        "heartbeat_age_s": round(now - updated, 1),
        "in_pass": beat.get("in_pass") is True,
    }
    if view["in_pass"] and number("pass_started_unix") is not None:
        view["pass_running_s"] = round(now - number("pass_started_unix"), 1)
    if view["last_pass"] == "unavailable":
        state = "waiting_for_host"
    elif not view["in_pass"] and now - updated > STALE_PERIODS * every + STALE_MARGIN_S:
        state = "stale"
    else:
        state = "running"
    view["state"] = state
    view["healthy"] = state == "running" and view["last_pass"] in ("ok", None)
    return view


def status(path, *, repository=REPOSITORY, probe=probe_intake):
    """The service as it runs, however it was started (`supervise` or the
    systemd units). Healthy only when the intake holds its serving lock and
    answers its public facts, the validator daemon is alive with a fresh
    heartbeat and its last pass did not fail (`daemon_view`), and, under a
    supervisor, every supervised process is running. A process status
    cannot see is never counted healthy."""
    from carbon.battery import deployment
    from carbon.battery.intake import Inbox, serve_lock_path

    from .supervisor import read_state

    service = load_service(path)
    intake_config = _intake(service, repository)
    found = {"schema": REPORT_SCHEMA, "service": str(service.path)}
    found["supervisor"] = read_state(service)
    found["intake"] = {
        "serving": lock_held(serve_lock_path(intake_config)),
        **probe(intake_config),
    }
    found["daemon"] = daemon_view(service)
    inbox = Path(intake_config["inbox"])
    found["inbox"] = Inbox(inbox).counts() if inbox.exists() else None
    try:
        target = deployment.validator(
            intake_config["deployment"], repository=repository, readonly=True
        )
        now = target.status()
        found["deployment"] = {
            "bound": now["identities"] is not None,
            "pool": now["pool"],
            "pending": now["pending"],
            "open_finals": now["open_finals"],
            "incumbent": now["incumbent"] is not None,
        }
    except deployment.EvaluationUnavailable as refused:
        found["deployment"] = {"refused": refused.code}
    found["latest_backup"] = _latest_backup(service)
    supervised = found["supervisor"].get("children") or {}
    found["healthy"] = (
        found["intake"]["serving"]
        and found["intake"]["answer"] == "ok"
        and found["daemon"]["healthy"]
        and all(child.get("state") == "running" for child in supervised.values())
    )
    return found


def digest_file(path):
    """`sha256:<hex>` of one file, streamed."""
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return "sha256:" + sha.hexdigest()
