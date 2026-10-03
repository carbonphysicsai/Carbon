"""The battery validator service (LP-PROD-G): preflight, parity, backup, supervision.

Every deployment here is a throwaway made by `operate init` in a temporary
directory, never an operator's. A `direct` deployment (`DIRECT_TRUSTED_PROCESS`,
recipes rebuilt in process) is used where the pinned worker images are not
the subject; it is development-only, and the service accepts it only on
loopback with `allow_direct_backend`. Carrier deployments use fixture image
manifests and a fixture doctor: nothing here reaches Docker, a chain or a
network beyond loopback. These tests hold behaviour; they are not a security
audit, and nothing here is SECURITY_QUALIFIED.
"""

from __future__ import annotations

import calendar
import contextlib
import datetime
import fcntl
import io
import ipaddress
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.battery import deployment, operate
from carbon.battery import intake as ib
from carbon.battery.daemon import BatteryValidator
from carbon.reconstruction.worker.docker_runtime import DockerDoctor
from scripts.dev.battery_validator_service import backup as bk
from scripts.dev.battery_validator_service import service as svc
from scripts.dev.battery_validator_service import supervisor as sup
from scripts.dev.battery_validator_service.__main__ import main

REPOSITORY = Path(__file__).resolve().parents[2]

#: The receiver hotkey the throwaway intake names (a well-known dev key).
RECEIVER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(deployment, "_VALIDATORS", {})


@pytest.fixture
def signals():
    """A command's `main` installs SIGTERM/SIGINT handlers; put pytest's back."""
    saved = {
        number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)
    }
    yield
    for number, handler in saved.items():
        signal.signal(number, handler)


def write(path, value, mode=0o600):
    path.write_text(json.dumps(value))
    path.chmod(mode)
    return path


def manifest(path, tag, **changes):
    """A pinned worker image manifest (fixture identity, never built)."""
    value = {
        "schema": "carbon.c03.worker-image.v1",
        "image_id": "sha256:" + tag * 64,
        "config_digest": "sha256:" + tag * 64,
        "source_tree_digest": "sha256:" + "a" * 64,
        "wheel_digest": "sha256:" + "b" * 64,
        "lock_digest": "sha256:" + "c" * 64,
        "base_image_digest": "sha256:" + "0" * 64,
        "build_recipe_digest": "sha256:" + "d" * 64,
        "entrypoint_digest": "sha256:" + "e" * 64,
        **changes,
    }
    return write(path, value, mode=0o644)


def throwaway(
    tmp_path,
    *,
    allow_direct=True,
    deployment_changes=None,
    intake_changes=None,
    service_changes=None,
    port=8467,
):
    """A fresh deployment (`operate init`), intake and service configuration,
    all owner-only under `tmp_path`."""
    tmp_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    validator = tmp_path / "validator"
    deployment_path = write(
        tmp_path / "deployment.json",
        {
            "schema": deployment.SCHEMA,
            "state": str(validator / "state.sqlite3"),
            "private_root": str(validator / "root.bin"),
            "journal": str(validator / "journal.jsonl"),
            "work": str(validator / "work"),
            "backend": "direct",
            "require_commitment": False,
            **(deployment_changes or {}),
        },
    )
    assert operate.init(deployment_path)["root_created"]
    (tmp_path / "intake").mkdir(mode=0o700)
    intake_path = write(
        tmp_path / "intake.json",
        {
            "schema": ib.SCHEMA,
            "deployment": str(deployment_path),
            "transport_journal": str(tmp_path / "intake" / "transport.sqlite3"),
            "inbox": str(tmp_path / "intake" / "inbox.sqlite3"),
            "receiver": RECEIVER,
            "host": "127.0.0.1",
            "port": port,
            **(intake_changes or {}),
        },
    )
    service_path = write(
        tmp_path / "service.json",
        {
            "schema": svc.SCHEMA,
            "intake": str(intake_path),
            "state_dir": str(tmp_path / "service"),
            "backups": str(tmp_path / "backups"),
            "allow_direct_backend": allow_direct,
            **(service_changes or {}),
        },
    )
    return SimpleNamespace(
        root=tmp_path,
        deployment=deployment_path,
        intake=intake_path,
        service=service_path,
        validator=validator,
    )


def rewrite(path, **changes):
    value = json.loads(path.read_text())
    value.update(changes)
    for key in [k for k, v in changes.items() if v is None]:
        del value[key]
    return write(path, value)


def checks(report):
    return {item["check"]: item for item in report["checks"]}


def eligible(**_kwargs):
    return DockerDoctor(True, "worker.doctor.eligible", {}, None)


# --- preflight ------------------------------------------------------------------


def test_a_fresh_development_deployment_on_loopback_is_ready(tmp_path):
    made = throwaway(tmp_path)
    report = svc.preflight(made.service, repository=REPOSITORY)
    assert report["ready"], report
    found = checks(report)
    assert found["exposure"]["detail"]["bind"] == "loopback"
    assert found["deployment"]["detail"]["development_only"] == "DIRECT_TRUSTED_PROCESS"
    assert found["images"]["detail"]["status"] == "not_applicable"
    # `init` binds nothing; the first start binds this checkout's identities.
    assert found["upgraded"]["detail"] == {"bound": False, "binds_at_start": True}
    # Nothing printed carries the root.
    root = (made.validator / "root.bin").read_bytes().hex()
    assert root not in json.dumps(report)


def test_the_command_runs_from_the_repository_root(tmp_path):
    """As a systemd unit runs it: a fresh process, the repository as its
    working directory, one JSON document out."""
    import subprocess

    made = throwaway(tmp_path)
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.dev.battery_validator_service",
            "preflight",
            "--config",
            str(made.service),
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["ready"] is True


def test_a_direct_deployment_needs_the_development_allowance(tmp_path):
    made = throwaway(tmp_path, allow_direct=False)
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["deployment"]["refused"] == "deployment_backend_direct"
    assert "isolated carrier" in found["deployment"]["next_step"]
    # Checks that need the deployment are skipped, not guessed.
    assert found["images"]["status"] == found["parity"]["status"] == "skipped"


def test_every_refusal_is_named_and_the_rest_reported(tmp_path):
    made = throwaway(tmp_path)
    made.service.chmod(0o640)
    report = svc.preflight(made.service, repository=REPOSITORY)
    assert not report["ready"]
    first = report["checks"][0]
    assert first["refused"] == "service_config_not_owner_only"
    assert {c["status"] for c in report["checks"][1:]} == {"skipped"}
    made.service.chmod(0o600)
    (tmp_path / "service").mkdir(mode=0o755)
    (tmp_path / "service").chmod(0o755)
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["service"]["refused"] == "service_directory_not_owner_only"
    (tmp_path / "service").chmod(0o700)
    rewrite(made.service, unknown_field=1)
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["service"]["refused"] == "service_config_fields"


def test_a_check_that_fails_unnamed_is_still_a_refusal(tmp_path):
    """A malformed root raises inside the deployment's own loader; the
    preflight reports it by type, refuses, and prints nothing of it."""
    made = throwaway(tmp_path)
    root = made.validator / "root.bin"
    root.write_bytes(b"PRIVATE" * 3)
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["deployment"]["refused"] == "check_failed"
    assert found["deployment"]["type"] == "ValueError"
    assert "PRIVATE" not in json.dumps(found)


def self_signed(folder):
    """A throwaway self-signed certificate for 127.0.0.1 and its key."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = folder / "intake.crt", folder / "intake.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    return cert_path, key_path


def test_a_public_bind_needs_its_record_its_tls_files_and_the_carrier(tmp_path):
    """Only a non-loopback bind is asked for these; the record is the owner's
    real OWNER-INTAKE-EXPOSURE-01 in this repository."""
    tls = tmp_path / "tls"
    tls.mkdir(mode=0o700)
    made = throwaway(
        tmp_path,
        intake_changes={
            "host": "0.0.0.0",
            "exposure_record": "OWNER-INTAKE-EXPOSURE-01",
            "tls_cert": str(tls / "intake.crt"),
            "tls_key": str(tls / "intake.key"),
        },
    )
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["exposure"]["refused"] == "intake_tls_cert_missing"
    self_signed(tls)
    (tls / "intake.key").chmod(0o640)
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["exposure"]["refused"] == "intake_tls_key_not_owner_only"
    (tls / "intake.key").chmod(0o600)
    # A direct deployment is never exposed, whatever the service allows.
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["exposure"]["refused"] == "intake_exposure_needs_carrier"
    # The record is checked when the intake configuration loads.
    rewrite(made.intake, exposure_record=None)
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["intake"]["refused"] == "intake_exposure_unrecorded"


def carrier(tmp_path, monkeypatch, *, practice=True, doctor=eligible):
    """A carrier deployment over fixture manifests, with a fixture doctor."""
    images = tmp_path / "images"
    images.mkdir(mode=0o700)
    jax = manifest(images / "worker-image.json", "1")
    made = throwaway(
        tmp_path,
        allow_direct=False,
        deployment_changes={"backend": "carrier", "image_manifest": str(jax)},
        service_changes=(
            {"practice_images": {"image_manifest": str(jax)}} if practice else {}
        ),
    )
    from carbon.reconstruction.worker import docker_runtime

    monkeypatch.setattr(docker_runtime, "doctor", doctor)
    return made, images


def test_a_carrier_deployment_is_checked_image_by_image(tmp_path, monkeypatch):
    made, _images = carrier(tmp_path, monkeypatch)
    report = svc.preflight(made.service, repository=REPOSITORY)
    assert report["ready"], report
    found = checks(report)
    assert found["images"]["detail"]["images"] == {"jax": "sha256:" + "1" * 64}
    assert found["parity"]["detail"]["images"] == {"jax": "sha256:" + "1" * 64}

    def absent(**_kwargs):
        return DockerDoctor(False, "worker.doctor.image_unavailable", {}, None)

    found = checks(svc.preflight(made.service, repository=REPOSITORY, doctor=absent))
    assert found["images"]["refused"] == "image_not_eligible"
    assert found["images"]["doctor"] == "worker.doctor.image_unavailable"


def test_parity_names_the_reference_and_every_differing_field(tmp_path, monkeypatch):
    made, images = carrier(tmp_path, monkeypatch, practice=False)
    found = checks(svc.parity_report(made.service, repository=REPOSITORY))
    assert found["parity"]["refused"] == "parity_reference_unnamed"
    other = manifest(images / "practice.json", "2", lock_digest="sha256:" + "f" * 64)
    rewrite(made.service, practice_images={"image_manifest": str(other)})
    report = svc.parity_report(made.service, repository=REPOSITORY)
    assert not report["ready"]
    differs = checks(report)["parity"]
    assert differs["refused"] == "parity_image_differs"
    assert differs["fields"] == ["image_id", "config_digest", "lock_digest"]
    assert (differs["validator"], differs["miners"]) == (
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
    )
    # The CLI: one JSON document, exit 2 on a refusal.
    assert main(["parity", "--config", str(made.service)]) == 2
    # The same image under another manifest file is the same image.
    same = manifest(images / "copy.json", "1")
    rewrite(made.service, practice_images={"image_manifest": str(same)})
    assert svc.parity_report(made.service, repository=REPOSITORY)["ready"]


def test_parity_and_the_upgrade_check_compare_the_bound_contract(tmp_path):
    made = throwaway(tmp_path)
    target = deployment.validator(made.deployment, repository=REPOSITORY)
    bound = target.store.identities()
    target.store.rebind(
        {**bound, "contract_digest": "sha256:" + "9" * 64}, decision="fixture"
    )
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["parity"]["refused"] == "parity_contract_differs"
    assert found["parity"]["validator"] == "sha256:" + "9" * 64
    assert found["upgraded"]["refused"] == "deployment_not_upgraded"
    assert found["upgraded"]["fields"] == ["contract_digest"]
    assert "operate upgrade" in found["upgraded"]["next_step"]
    assert operate.upgrade(made.deployment)["changed"] == ["contract_digest"]
    assert svc.preflight(made.service, repository=REPOSITORY)["ready"]


def test_a_changed_rule_is_never_carried_over(tmp_path):
    made = throwaway(tmp_path)
    target = deployment.validator(made.deployment, repository=REPOSITORY)
    with target.store.db() as db:
        db.execute(
            "UPDATE meta SET value=? WHERE key='identities'",
            (
                json.dumps(
                    {**target.store.identities(), "rule_digest": "sha256:" + "8" * 64}
                ),
            ),
        )
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["upgraded"]["refused"] == "deployment_identities_not_carryable"
    assert found["upgraded"]["fields"] == ["rule_digest"]


def test_upgrade_binds_the_carrier_images_not_the_readonly_backend(
    tmp_path, monkeypatch
):
    """`operate upgrade` builds the deployment read-only, and a read-only
    build runs the in-process backend. Before LP-PROD-G it bound that
    backend's identity, so a carrier deployment's next start always refused
    `identities_changed`. It now binds what a start binds."""
    made = throwaway(tmp_path)
    deployment.validator(made.deployment, repository=REPOSITORY)  # binds DIRECT
    images = tmp_path / "images"
    images.mkdir(mode=0o700)
    jax = manifest(images / "worker-image.json", "1")
    rewrite(made.deployment, backend="carrier", image_manifest=str(jax))
    rewrite(
        made.service,
        allow_direct_backend=False,
        practice_images={"image_manifest": str(jax)},
    )
    from carbon.reconstruction.worker import docker_runtime

    monkeypatch.setattr(docker_runtime, "doctor", eligible)
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    found = checks(svc.preflight(made.service, repository=REPOSITORY))
    assert found["upgraded"]["refused"] == "deployment_not_upgraded"
    assert found["upgraded"]["fields"] == ["backend"]
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    assert operate.upgrade(made.deployment)["changed"] == ["backend"]
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    started = deployment.validator(made.deployment, repository=REPOSITORY)
    assert started.store.identities()["backend"] == {
        "backend": "ISOLATED_CARRIER",
        "validator_path": True,
        "image": "sha256:" + "1" * 64,
    }
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    assert svc.preflight(made.service, repository=REPOSITORY)["ready"]


# --- operate run --every ----------------------------------------------------------


def test_run_every_is_one_pass_per_period_until_stopped(tmp_path, capsys, signals):
    made = throwaway(tmp_path)
    stop = threading.Event()
    calls = []
    real = BatteryValidator.run_pending

    def counted(self):
        calls.append(1)
        if len(calls) == 2:
            stop.set()
        return real(self)

    out = io.StringIO()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(BatteryValidator, "run_pending", counted)
        patch.setattr(operate, "MIN_EVERY_S", 0.01)
        assert operate.run_every(made.deployment, 0.01, stop=stop, out=out) == 2
    lines = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [line["event"] for line in lines] == ["started", "pass", "pass", "stopped"]
    assert lines[1]["advanced"] == 0 and lines[1]["pool"] is None
    assert {line["service"] for line in lines} == {"battery-validator-daemon"}
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        operate.run_every(made.deployment, 1.0, stop=stop)
    assert refused.value.code == "run_every_too_short"
    # A deployment that cannot be built is a configuration state: exit 2.
    made.deployment.chmod(0o640)
    assert operate.main(["run", "--config", str(made.deployment), "--every", "5"]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "unavailable": "evaluation_input_not_owner_only"
    }


def test_a_failing_pass_is_logged_by_type_and_retried(tmp_path):
    made = throwaway(tmp_path)
    stop = threading.Event()
    calls = []

    def failing(self):
        calls.append(1)
        if len(calls) == 2:
            stop.set()
        raise RuntimeError("private detail that must never be logged")

    out = io.StringIO()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(BatteryValidator, "run_pending", failing)
        patch.setattr(operate, "MIN_EVERY_S", 0.01)
        operate.run_every(made.deployment, 0.01, stop=stop, out=out)
    assert "private detail" not in out.getvalue()
    events = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [e["event"] for e in events].count("pass_failed") == 2
    assert events[1]["type"] == "RuntimeError"


# --- backup and restore -----------------------------------------------------------


def test_a_backup_holds_root_journal_and_state_taken_under_the_writer_lock(
    tmp_path, monkeypatch
):
    made = throwaway(tmp_path)
    target = deployment.validator(made.deployment, repository=REPOSITORY)
    ib.Inbox(tmp_path / "intake" / "inbox.sqlite3")
    held = []
    real_writer = deployment.writer
    inside = threading.Event()

    @contextlib.contextmanager
    def watched(t):
        with real_writer(t):
            inside.set()
            try:
                yield t
            finally:
                inside.clear()

    real_copy = bk._sqlite_copy

    def copy(source, destination):
        held.append(inside.is_set())
        return real_copy(source, destination)

    monkeypatch.setattr(deployment, "writer", watched)
    monkeypatch.setattr(bk, "_sqlite_copy", copy)
    made_at = calendar.timegm((2026, 10, 3, 12, 0, 0))
    result = bk.backup(made.service, repository=REPOSITORY, clock=lambda: made_at)
    assert held and all(held)
    folder = Path(result["backup"])
    assert folder.name == "battery-validator-20261003T120000Z"
    assert folder.stat().st_mode & 0o777 == 0o700
    assert set(result["files"]) == {
        "root.bin",
        "journal.jsonl",
        "state.sqlite3",
        "inbox.sqlite3",
    }
    for name in result["files"]:
        assert (folder / name).stat().st_mode & 0o777 == 0o600
    assert (folder / "root.bin").read_bytes() == (
        made.validator / "root.bin"
    ).read_bytes()
    assert result["root_commitment"] == target.root.commitment()
    text = (folder / "manifest.json").read_text()
    assert (made.validator / "root.bin").read_bytes().hex() not in text
    # A second backup the same second gets its own name.
    again = bk.backup(made.service, repository=REPOSITORY, clock=lambda: made_at)
    assert Path(again["backup"]).name == "battery-validator-20261003T120000Z-1"
    assert (
        svc._latest_backup(svc.load_service(made.service)) == Path(again["backup"]).name
    )


def test_a_restore_verifies_and_never_overwrites(tmp_path, monkeypatch):
    made = throwaway(tmp_path / "a")
    deployment.validator(made.deployment, repository=REPOSITORY)
    result = bk.backup(made.service, repository=REPOSITORY)
    folder = Path(result["backup"])
    # Into the same, live paths: refused, nothing written.
    with pytest.raises(svc.ServiceRefused) as refused:
        bk.restore(made.service, folder, repository=REPOSITORY)
    assert refused.value.code == "restore_target_exists"
    # Into a fresh host's paths: the same root, journal and binding.
    other = tmp_path / "b"
    other.mkdir()
    fresh = throwaway(other)
    for name in ("root.bin", "journal.jsonl"):
        (fresh.validator / name).unlink()
    restored = bk.restore(fresh.service, folder, repository=REPOSITORY)
    assert restored["root_commitment"] == result["root_commitment"]
    assert (fresh.validator / "root.bin").read_bytes() == (
        made.validator / "root.bin"
    ).read_bytes()
    assert (fresh.validator / "root.bin").stat().st_mode & 0o777 == 0o600
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    back = deployment.validator(fresh.deployment, repository=REPOSITORY)
    original = deployment.validator(made.deployment, repository=REPOSITORY)
    assert back.store.identities() == original.store.identities()
    # A changed byte is found before anything is written.
    third = tmp_path / "c"
    third.mkdir()
    spare = throwaway(third)
    for name in ("root.bin", "journal.jsonl"):
        (spare.validator / name).unlink()
    with (folder / "journal.jsonl").open("a") as handle:
        handle.write("\n")
    with pytest.raises(svc.ServiceRefused) as refused:
        bk.restore(spare.service, folder, repository=REPOSITORY)
    assert refused.value.code == "backup_corrupt"
    assert not (spare.validator / "root.bin").exists()


def test_a_restore_is_refused_while_the_service_runs(tmp_path):
    made = throwaway(tmp_path)
    deployment.validator(made.deployment, repository=REPOSITORY)
    folder = Path(bk.backup(made.service, repository=REPOSITORY)["backup"])
    state = svc.owner_only_directory(tmp_path / "service", create=True)
    fd = os.open(state / "supervisor.lock", os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        with pytest.raises(svc.ServiceRefused) as refused:
            bk.restore(made.service, folder, repository=REPOSITORY)
        assert refused.value.code == "restore_service_running"
        with pytest.raises(svc.ServiceRefused) as refused:
            sup.supervise(made.service, repository=REPOSITORY)
        assert refused.value.code == "supervisor_already_running"
    finally:
        os.close(fd)


# --- supervision and units --------------------------------------------------------


def script(body):
    return [sys.executable, "-c", body]


@pytest.fixture
def quick(monkeypatch):
    monkeypatch.setattr(sup, "BACKOFF_MIN_S", 0.05)
    monkeypatch.setattr(sup, "STOP_GRACE_S", 5.0)


def ready(*_args, **_kwargs):
    return {"ready": True, "checks": []}


def test_a_failing_child_is_restarted_and_a_refusal_stops_everything(tmp_path, quick):
    made = throwaway(tmp_path)
    marker = tmp_path / "ran"
    flaky = (
        "import pathlib, sys, time\n"
        f"p = pathlib.Path({str(marker)!r})\n"
        "n = int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n + 1))\n"
        "sys.exit(1) if n == 0 else (time.sleep(0.3), sys.exit(2))\n"
    )
    code = sup.supervise(
        made.service,
        repository=REPOSITORY,
        preflight=ready,
        commands={
            "flaky": script(flaky),
            "steady": script("import time; time.sleep(60)"),
        },
        poll_s=0.02,
    )
    assert code == 2
    assert marker.read_text() == "2"  # restarted once, then refused
    logs = tmp_path / "service" / "logs"
    events = [json.loads(line)["event"] for line in (logs / "supervisor.jsonl").open()]
    assert events[0] == "started"
    assert "child_exited" in events and "child_refused" in events
    assert events[-1] == "stopped"
    state = json.loads((tmp_path / "service" / "supervisor-state.json").read_text())
    assert state["state"] == "refused"
    assert state["children"]["flaky"]["restarts"] == 1
    assert state["children"]["steady"]["state"] == "stopped"  # stopped with it
    for path in logs.iterdir():
        assert path.stat().st_mode & 0o777 == 0o600


def test_a_child_that_keeps_failing_hits_the_restart_limit(
    tmp_path, quick, monkeypatch
):
    monkeypatch.setattr(sup, "BACKOFF_MAX_S", 0.05)
    made = throwaway(tmp_path)
    code = sup.supervise(
        made.service,
        repository=REPOSITORY,
        preflight=ready,
        commands={"broken": script("import sys; sys.exit(1)")},
        poll_s=0.01,
    )
    assert code == 1
    state = json.loads((tmp_path / "service" / "supervisor-state.json").read_text())
    assert state["state"] == "restart_limit"
    assert state["children"]["broken"]["restarts"] == sup.RESTART_BURST


def test_stopping_the_supervisor_stops_its_children(tmp_path, quick):
    made = throwaway(tmp_path)
    stop = threading.Event()
    pids = tmp_path / "pid"
    child = f"import os, pathlib, time; pathlib.Path({str(pids)!r}).write_text(str(os.getpid())); time.sleep(60)"
    thread = threading.Thread(
        target=lambda: sup.supervise(
            made.service,
            repository=REPOSITORY,
            preflight=ready,
            commands={"long": script(child)},
            stop=stop,
            poll_s=0.02,
        )
    )
    thread.start()
    deadline = time.monotonic() + 20
    while not pids.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    service = svc.load_service(made.service)
    assert sup.read_state(service)["children"]["long"]["state"] == "running"
    stop.set()
    thread.join(30)
    assert not thread.is_alive()
    pid = int(pids.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert sup.read_state(service) == {"state": "not_running"}


def test_the_supervisor_starts_nothing_unless_the_preflight_is_ready(tmp_path):
    made = throwaway(tmp_path, allow_direct=False)
    with pytest.raises(svc.ServiceRefused) as refused:
        sup.supervise(made.service, repository=REPOSITORY, commands={"x": ["false"]})
    assert refused.value.code == "preflight_not_ready"
    assert refused.value.detail["codes"] == ["deployment_backend_direct"]


def test_the_supervised_commands_are_the_intake_and_operate_run(tmp_path):
    made = throwaway(tmp_path, service_changes={"run_every_s": 30})
    argv = sup.children(svc.load_service(made.service), python="/venv/python")
    assert argv["intake"] == [
        "/venv/python",
        "-m",
        "carbon.battery.intake",
        "serve",
        "--config",
        str(made.intake),
    ]
    assert argv["daemon"][1:] == [
        "-m",
        "carbon.battery.operate",
        "run",
        "--config",
        str(made.deployment),
        "--every",
        "30.0",
    ]


def test_units_are_written_owner_only_and_never_over_a_file(tmp_path):
    made = throwaway(tmp_path)
    out = tmp_path / "units"
    written = sup.units(made.service, out, python="/venv/python")
    assert sorted(Path(p).name for p in written["units"]) == [
        "carbon-battery-intake.service",
        "carbon-battery-validator.service",
    ]
    text = (out / "carbon-battery-intake.service").read_text()
    assert "ExecStart=/venv/python -m carbon.battery.intake serve --config" in text
    assert "RestartPreventExitStatus=2" in text and "Restart=on-failure" in text
    assert f"preflight --config {made.service}" in text
    assert (out / "carbon-battery-intake.service").stat().st_mode & 0o777 == 0o600
    daemon = (out / "carbon-battery-validator.service").read_text()
    assert "carbon.battery.operate run --config" in daemon and "--every 60.0" in daemon
    with pytest.raises(svc.ServiceRefused) as refused:
        sup.units(made.service, out, python="/venv/python")
    assert refused.value.code == "unit_exists"


def test_status_is_unhealthy_until_the_intake_answers(tmp_path):
    made = throwaway(tmp_path)
    found = svc.status(
        made.service,
        repository=REPOSITORY,
        probe=lambda config: {"listening": False, "answer": "intake_not_listening"},
    )
    assert found["healthy"] is False
    assert found["supervisor"] == {"state": "not_running"}
    assert found["inbox"] is None and found["latest_backup"] is None
    assert found["deployment"]["bound"] is False
    found = svc.status(
        made.service,
        repository=REPOSITORY,
        probe=lambda config: {"listening": True, "answer": "ok"},
    )
    assert found["healthy"] is True
