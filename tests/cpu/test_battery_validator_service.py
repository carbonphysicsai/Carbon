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


def test_parity_holds_practice_to_the_validators_images(tmp_path, monkeypatch):
    """OWNER-LAUNCHPAD-PROD-02, answer 10: the validator's pinned images are
    the standard miners practise against. A practice image that differs is
    named against the validator's, and the fix publishes the validator's
    image for practice; the validator's image is never the one to change."""
    made, images = carrier(tmp_path, monkeypatch, practice=False)
    found = checks(svc.parity_report(made.service, repository=REPOSITORY))
    assert found["parity"]["refused"] == "practice_image_unnamed"
    assert found["parity"]["standard"] == "sha256:" + "1" * 64
    assert "validator's pinned image" in found["parity"]["next_step"]
    other = manifest(images / "practice.json", "2", lock_digest="sha256:" + "f" * 64)
    rewrite(made.service, practice_images={"image_manifest": str(other)})
    report = svc.parity_report(made.service, repository=REPOSITORY)
    assert not report["ready"]
    differs = checks(report)["parity"]
    assert differs["refused"] == "practice_image_differs"
    assert differs["fields"] == ["image_id", "config_digest", "lock_digest"]
    assert (differs["standard"], differs["practice"]) == (
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
    )
    assert "is the standard and is not changed" in differs["next_step"]
    # The CLI: one JSON document, exit 2 on a refusal.
    assert main(["parity", "--config", str(made.service)]) == 2
    # An unreadable practice manifest is named as practice's.
    garbled = images / "garbled.json"
    garbled.write_text("{")
    rewrite(made.service, practice_images={"image_manifest": str(garbled)})
    found = checks(svc.parity_report(made.service, repository=REPOSITORY))
    assert found["parity"]["refused"] == "practice_manifest_unreadable"
    # The validator's image under another manifest file is the same image.
    same = manifest(images / "copy.json", "1")
    rewrite(made.service, practice_images={"image_manifest": str(same)})
    report = svc.parity_report(made.service, repository=REPOSITORY)
    assert report["ready"]
    detail = checks(report)["parity"]["detail"]
    assert detail["practice_standard"] == svc.PRACTICE_STANDARD
    assert detail["images"] == {"jax": "sha256:" + "1" * 64}


def test_practice_on_the_validators_images_reaches_no_hidden_test_condition(
    tmp_path, monkeypatch
):
    """OWNER-LAUNCHPAD-PROD-02, answer 10: "practice on validator images as
    long as NO ACCESS to hidden test conditions". What practice is held to is
    the validator's images' public build identity alone: no private case,
    seed, root, reference or per-case result reaches it, nor any report the
    parity check prints. The hidden conditions here are the deployment's own:
    its private root and the screening cases, seeds and duplicates it would
    draw from that root."""
    from carbon.battery import seeds

    made, _images = carrier(tmp_path, monkeypatch)
    target = deployment.validator(made.deployment, repository=REPOSITORY)
    root_bytes = (made.validator / "root.bin").read_bytes()
    root = seeds.PrivateRoot.load(made.validator / "root.bin")
    pin = json.loads((made.validator / "journal.jsonl").read_text().splitlines()[0])[
        "seed_pin"
    ]
    batch = seeds.make_batch(root, pin, "pscreen-b00", 12)
    hidden = [root_bytes.hex(), batch.fingerprint]
    for case_id, inputs in batch.cases:
        hidden.append(case_id)
        hidden.append(json.dumps(dict(inputs), sort_keys=True))
    hidden += [dup for dup, _ in batch.duplicates]
    seed = str(seeds.reconstruction_seed(root, "fixture-submission"))
    if len(seed) >= 8:  # a short number could occur inside any digest
        hidden.append(seed)
    private_paths = [
        str(made.validator / name)
        for name in ("root.bin", "journal.jsonl", "state.sqlite3", "work")
    ]

    # The standard is the validator's image identity, field for field.
    standard = svc.practice_standard(json.loads(made.deployment.read_text()))
    assert set(standard) == {"jax"}
    assert set(standard["jax"]) == set(svc.IDENTITY_FIELDS)
    assert standard["jax"]["image_id"] == "sha256:" + "1" * 64

    printed = [
        json.dumps(standard),
        json.dumps(svc.parity_report(made.service, repository=REPOSITORY)),
        json.dumps(svc.preflight(made.service, repository=REPOSITORY)),
    ]
    detail = checks(json.loads(printed[1]))["parity"]["detail"]
    assert detail["withheld_from_practice"] == [
        "private_cases",
        "seeds",
        "private_root",
        "references",
        "per_case_results",
    ]
    for text in printed:
        for secret in hidden + private_paths:
            assert secret not in text, secret
    # Specimen: the scan finds a hidden condition where one is printed.
    assert batch.cases[0][0] in json.dumps(batch.document())
    assert root.commitment() == target.root.commitment()


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


def test_only_a_configuration_refusal_exits_2(tmp_path):
    """Before this review fix every `EvaluationUnavailable` exited 2, so a
    carrier start refused only because Docker was down or still starting
    (`evaluation_host_unavailable`) was treated as a refused configuration:
    the supervisor stopped both children and systemd never restarted them."""
    assert operate.exit_code("evaluation_host_unavailable") == 1
    for code in (
        "evaluation_input_not_owner_only",
        "evaluation_config_image",
        "evaluation_journal_refused",
        "evaluation_identities_changed",
        "run_every_too_short",
    ):
        assert operate.exit_code(code) == 2, code
    # A code not known as a configuration costs restarts, never an outage.
    assert operate.exit_code("evaluation_some_future_state") == 1


def test_run_every_waits_out_the_host_and_keeps_a_heartbeat(tmp_path, monkeypatch):
    made = throwaway(tmp_path)
    state = svc.owner_only_directory(tmp_path / "service", create=True)
    heartbeat = state / svc.HEARTBEAT
    stop = threading.Event()
    attempts = []
    real = deployment.validator

    def docker_down_twice(config_path, *, repository, readonly=False):
        attempts.append(1)
        if len(attempts) <= 2:
            raise deployment.EvaluationUnavailable("evaluation_host_unavailable")
        return real(config_path, repository=repository, readonly=readonly)

    passes = []
    run_pending = BatteryValidator.run_pending

    def counted(self):
        passes.append(1)
        stop.set()
        return run_pending(self)

    monkeypatch.setattr(operate, "validator", docker_down_twice)
    monkeypatch.setattr(BatteryValidator, "run_pending", counted)
    monkeypatch.setattr(operate, "MIN_EVERY_S", 0.01)
    out = io.StringIO()
    made_passes = operate.run_every(
        made.deployment, 0.01, stop=stop, out=out, heartbeat=heartbeat
    )
    assert made_passes == 3
    events = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [e["event"] for e in events] == [
        "started",
        "pass_unavailable",
        "pass_unavailable",
        "pass",
        "stopped",
    ]
    assert events[1]["code"] == "evaluation_host_unavailable"
    beat = json.loads(heartbeat.read_text())
    assert (beat["passes"], beat["last_pass"], beat["stopped"]) == (3, "ok", True)
    assert beat["in_pass"] is False and beat["pid"] == os.getpid()
    assert heartbeat.stat().st_mode & 0o777 == 0o600
    # The liveness lock is released when the daemon returns.
    assert not svc.lock_held(Path(str(heartbeat) + ".lock"))
    # A configuration refusal on a later attempt still propagates.
    attempts.clear()

    def refused(config_path, *, repository, readonly=False):
        raise deployment.EvaluationUnavailable("evaluation_identities_changed")

    monkeypatch.setattr(operate, "validator", refused)
    with pytest.raises(deployment.EvaluationUnavailable) as stopped:
        operate.run_every(made.deployment, 0.01, stop=threading.Event(), out=out)
    assert stopped.value.code == "evaluation_identities_changed"


def test_a_heartbeat_needs_an_owner_only_directory_and_one_daemon(
    tmp_path, monkeypatch
):
    made = throwaway(tmp_path)
    open_dir = tmp_path / "open"
    open_dir.mkdir(mode=0o755)
    open_dir.chmod(0o755)
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        operate.run_every(made.deployment, 5.0, heartbeat=open_dir / "beat.json")
    assert refused.value.code == "run_heartbeat_not_owner_only"
    state = svc.owner_only_directory(tmp_path / "service", create=True)
    heartbeat = state / svc.HEARTBEAT
    fd = os.open(str(heartbeat) + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    monkeypatch.setattr(operate, "LOCK_TRIES", 2)
    try:
        with pytest.raises(deployment.EvaluationUnavailable) as refused:
            operate.run_every(made.deployment, 5.0, heartbeat=heartbeat)
        assert refused.value.code == "run_daemon_already_running"
        assert operate.exit_code(refused.value.code) == 2
    finally:
        os.close(fd)


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


@contextlib.contextmanager
def holding(path):
    """Hold an exclusive `flock` on `path`, as a running process does."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        yield
    finally:
        os.close(fd)


def test_a_restore_is_refused_while_the_service_runs(tmp_path, monkeypatch):
    made = throwaway(tmp_path)
    deployment.validator(made.deployment, repository=REPOSITORY)
    folder = Path(bk.backup(made.service, repository=REPOSITORY)["backup"])
    state = svc.owner_only_directory(tmp_path / "service", create=True)
    monkeypatch.setattr(sup, "LOCK_TRIES", 2)
    with holding(state / "supervisor.lock"):
        with pytest.raises(svc.ServiceRefused) as refused:
            bk.restore(made.service, folder, repository=REPOSITORY)
        assert refused.value.code == "restore_service_running"
        assert refused.value.detail["running"] == ["supervisor"]
        with pytest.raises(svc.ServiceRefused) as refused:
            sup.supervise(made.service, repository=REPOSITORY)
        assert refused.value.code == "supervisor_already_running"
    # Under the systemd units no supervisor runs: before this review fix the
    # restore saw nothing and only its target check stood in the way. The
    # intake's and the daemon's own locks are read now.
    service = svc.load_service(made.service)
    intake_config = json.loads(made.intake.read_text())
    for part, lock in (
        ("intake", ib.serve_lock_path(intake_config)),
        ("daemon", svc.daemon_lock_path(service)),
    ):
        with holding(lock):
            with pytest.raises(svc.ServiceRefused) as refused:
                bk.restore(made.service, folder, repository=REPOSITORY)
            assert refused.value.code == "restore_service_running"
            assert refused.value.detail["running"] == [part]
            assert "systemctl --user stop" in refused.value.next_step


def emptied(tmp_path, name):
    """A throwaway whose root and journal are removed: a fresh host's paths."""
    folder = tmp_path / name
    folder.mkdir()
    made = throwaway(folder)
    for member in ("root.bin", "journal.jsonl"):
        (made.validator / member).unlink()
    return made


def leftovers(made):
    """Every file under the throwaway's validator and intake directories."""
    return sorted(
        str(p.relative_to(made.root))
        for folder in (made.validator, made.root / "intake")
        for p in folder.rglob("*")
        if p.is_file()
    )


def test_a_restore_is_all_or_nothing(tmp_path, monkeypatch):
    """Before this review fix a destination directory was made and checked,
    and each member written in place, inside the write loop: a failure after
    the first member (a group-readable intake directory, a full disk) left
    root and journal without their state, and a rerun was then refused."""
    source = throwaway(tmp_path / "a")
    deployment.validator(source.deployment, repository=REPOSITORY)
    ib.Inbox(tmp_path / "a" / "intake" / "inbox.sqlite3")
    folder = Path(bk.backup(source.service, repository=REPOSITORY)["backup"])
    assert (
        "inbox.sqlite3" in json.loads((folder / "manifest.json").read_text())["files"]
    )
    # A directory that is not owner-only is refused before any byte lands.
    made = emptied(tmp_path, "b")
    before = leftovers(made)
    (made.root / "intake").chmod(0o750)
    with pytest.raises(svc.ServiceRefused) as refused:
        bk.restore(made.service, folder, repository=REPOSITORY)
    assert refused.value.code == "service_directory_not_owner_only"
    assert leftovers(made) == before
    (made.root / "intake").chmod(0o700)
    # A failure while linking the members into place removes what it made.
    real_link, linked = os.link, []

    def full_disk(src, dst, **kwargs):
        if len(linked) == 2:
            raise OSError(28, "No space left on device")
        linked.append(dst)
        return real_link(src, dst, **kwargs)

    monkeypatch.setattr(bk.os, "link", full_disk)
    with pytest.raises(OSError):
        bk.restore(made.service, folder, repository=REPOSITORY)
    assert leftovers(made) == before
    # A check that fails after every member landed removes them too.
    monkeypatch.setattr(bk.os, "link", real_link)
    manifest = json.loads((folder / "manifest.json").read_text())
    (folder / "manifest.json").write_text(
        json.dumps({**manifest, "root_commitment": "sha256:" + "0" * 64})
    )
    with pytest.raises(svc.ServiceRefused) as refused:
        bk.restore(made.service, folder, repository=REPOSITORY)
    assert refused.value.code == "restore_root_differs"
    assert leftovers(made) == before
    (folder / "manifest.json").write_text(json.dumps(manifest))
    # So a rerun completes, owner-only, with nothing staged left behind.
    restored = bk.restore(made.service, folder, repository=REPOSITORY)
    assert restored["root_commitment"] == manifest["root_commitment"]
    assert not [p for p in leftovers(made) if p.endswith(bk.RESTORING)]
    assert (made.root / "intake" / "inbox.sqlite3").stat().st_mode & 0o777 == 0o600


def test_a_restore_never_lands_a_database_beside_a_stale_log(tmp_path):
    source = throwaway(tmp_path / "a")
    deployment.validator(source.deployment, repository=REPOSITORY)
    folder = Path(bk.backup(source.service, repository=REPOSITORY)["backup"])
    made = emptied(tmp_path, "b")
    (made.validator / "state.sqlite3-wal").write_bytes(b"stale")
    with pytest.raises(svc.ServiceRefused) as refused:
        bk.restore(made.service, folder, repository=REPOSITORY)
    assert refused.value.code == "restore_target_exists"
    assert refused.value.detail["member"] == "daemon_state"
    assert not (made.validator / "root.bin").exists()


def test_a_failed_backup_leaves_no_copy_of_the_root(tmp_path, monkeypatch):
    import sqlite3

    made = throwaway(tmp_path)
    deployment.validator(made.deployment, repository=REPOSITORY)

    def broken(source, destination):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(bk, "_sqlite_copy", broken)
    with pytest.raises(sqlite3.OperationalError):
        bk.backup(made.service, repository=REPOSITORY)
    assert list((tmp_path / "backups").iterdir()) == []


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


def test_an_intake_start_refused_for_the_host_is_restarted(tmp_path, quick, signals):
    """The intake's own `main`, in a child process, refused only because the
    host cannot serve yet (`evaluation_host_unavailable`): exit 1, which the
    supervisor restarts. Before this review fix it exited 2, and the
    supervisor stopped both children for good."""
    made = throwaway(tmp_path)
    marker = tmp_path / "ran"
    child = (
        "import pathlib, sys, time\n"
        "from carbon.battery import deployment, intake\n"
        f"p = pathlib.Path({str(marker)!r})\n"
        "n = int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n + 1))\n"
        "if n == 0:\n"
        "    def docker_down(*args, **kwargs):\n"
        "        raise deployment.EvaluationUnavailable('evaluation_host_unavailable')\n"
        "    intake.serve = docker_down\n"
        "    sys.exit(intake.main(['serve', '--config', 'unused']))\n"
        "time.sleep(60)\n"
    )
    stop = threading.Event()
    codes = []
    thread = threading.Thread(
        target=lambda: codes.append(
            sup.supervise(
                made.service,
                repository=REPOSITORY,
                preflight=ready,
                commands={"intake": script(child)},
                stop=stop,
                poll_s=0.02,
            )
        )
    )
    thread.start()
    try:
        deadline = time.monotonic() + 60
        while not (marker.exists() and marker.read_text() == "2"):
            assert time.monotonic() < deadline and thread.is_alive()
            time.sleep(0.05)
    finally:
        stop.set()
        thread.join(30)
    assert codes == [0]
    logs = tmp_path / "service" / "logs"
    events = [json.loads(line) for line in (logs / "supervisor.jsonl").open()]
    exited = [e for e in events if e["event"] == "child_exited"]
    assert [e["exit"] for e in exited] == [1]
    assert "child_refused" not in [e["event"] for e in events]
    lines = (logs / "intake.log").read_text()
    assert '"event": "unavailable"' in lines
    assert "evaluation_host_unavailable" in lines


def test_the_intake_exit_code_follows_the_refusal(monkeypatch, capsys, signals):
    def raising(error):
        def serve(*args, **kwargs):
            raise error

        return serve

    for error, code in (
        (deployment.EvaluationUnavailable("evaluation_host_unavailable"), 1),
        (deployment.EvaluationUnavailable("evaluation_config_image"), 2),
        (ib.IntakeUnavailable("intake_config_fields"), 2),
        (OSError(98, "Address already in use"), 1),
    ):
        monkeypatch.setattr(ib, "serve", raising(error))
        assert ib.main(["serve", "--config", "unused"]) == code, error
    assert "Address already in use" not in capsys.readouterr().err


def test_the_intake_waits_out_the_host_before_it_listens(monkeypatch, capsys):
    monkeypatch.setattr(ib, "HOST_RETRY_MIN_S", 0.01)
    attempts = []

    def docker_down_twice(config_path, *, repository, readonly=False):
        attempts.append(1)
        if len(attempts) <= 2:
            raise deployment.EvaluationUnavailable("evaluation_host_unavailable")
        return "built"

    monkeypatch.setattr(deployment, "validator", docker_down_twice)
    config = {"deployment": "unused"}
    assert ib._when_host_ready(config, REPOSITORY, threading.Event()) == "built"
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [line["event"] for line in lines] == ["waiting_for_host"] * 2
    assert [line["retry_in_s"] for line in lines] == [0.01, 0.02]
    # Stopped while waiting: nothing is built and nothing listens.
    attempts.clear()
    stop = threading.Event()
    stop.set()
    assert ib._when_host_ready(config, REPOSITORY, stop) is None
    # A refused configuration is answered at once.

    def refused(config_path, *, repository, readonly=False):
        raise deployment.EvaluationUnavailable("evaluation_identities_changed")

    monkeypatch.setattr(deployment, "validator", refused)
    with pytest.raises(deployment.EvaluationUnavailable):
        ib._when_host_ready(config, REPOSITORY, threading.Event())


def test_one_intake_serves_an_inbox(tmp_path, monkeypatch):
    monkeypatch.setattr(operate, "LOCK_TRIES", 2)
    config = {"inbox": str(tmp_path / "inbox.sqlite3")}
    held = ib._serving_lock(config)
    try:
        assert svc.lock_held(ib.serve_lock_path(config))
        with pytest.raises(ib.IntakeUnavailable) as refused:
            ib._serving_lock(config)
        assert refused.value.code == "intake_already_serving"
    finally:
        os.close(held)
    assert not svc.lock_held(ib.serve_lock_path(config))


def docker(code):
    return {
        "ready": False,
        "checks": [
            {"check": "service", "status": "ok"},
            {
                "check": "images",
                "status": "refused",
                "refused": "image_not_eligible",
                "doctor": code,
            },
        ],
    }


def test_a_start_waits_out_a_docker_that_is_still_starting():
    reports = iter([docker("worker.doctor.docker_unavailable")] * 2 + [ready()])
    ticks, slept = iter(range(100)), []
    report = svc.wait_for_host(
        lambda: next(reports),
        wait_s=30,
        poll_s=5,
        clock=lambda: next(ticks),
        sleep=slept.append,
    )
    assert report["ready"] and slept == [5, 5]
    # A missing image is the operator's to fix: answered at once.
    missing = docker("worker.doctor.image_unavailable")
    assert svc.wait_for_host(lambda: missing, wait_s=30, sleep=slept.append) is missing
    assert len(slept) == 2
    # Docker still down when the wait runs out: not ready, by its code.
    down = docker("worker.doctor.docker_unavailable")
    clock = iter([0, 4, 8, 12])
    found = svc.wait_for_host(
        lambda: down, wait_s=10, poll_s=5, clock=lambda: next(clock), sleep=slept.append
    )
    assert found is down and svc.host_not_ready(found)


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
        "--heartbeat",
        str(tmp_path / "service" / "daemon-heartbeat.json"),
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
    # A Docker still starting after a reboot is waited out inside the start.
    assert f"preflight --config {made.service} --wait-for-host 300" in text
    assert "TimeoutStartSec=360" in text
    assert (out / "carbon-battery-intake.service").stat().st_mode & 0o777 == 0o600
    daemon = (out / "carbon-battery-validator.service").read_text()
    assert "carbon.battery.operate run --config" in daemon and "--every 60.0" in daemon
    assert (
        "--heartbeat " + str(tmp_path / "service" / "daemon-heartbeat.json") in daemon
    )
    # The daemon keeps its heartbeat there; no supervisor runs to make it.
    assert (tmp_path / "service").stat().st_mode & 0o777 == 0o700
    with pytest.raises(svc.ServiceRefused) as refused:
        sup.units(made.service, out, python="/venv/python")
    assert refused.value.code == "unit_exists"


def answering(config):
    return {"listening": True, "answer": "ok"}


def test_status_is_unhealthy_until_the_intake_answers(tmp_path):
    """Before this review fix `healthy` was only "the intake answers" when no
    supervisor ran, as under the systemd units: a failed or restart-limited
    daemon unit still read healthy. Every part is now seen by its own lock,
    and the daemon by its heartbeat too."""
    made = throwaway(tmp_path)
    found = svc.status(
        made.service,
        repository=REPOSITORY,
        probe=lambda config: {"listening": False, "answer": "intake_not_listening"},
    )
    assert found["healthy"] is False
    assert found["supervisor"] == {"state": "not_running"}
    assert found["daemon"] == {"state": "not_running", "healthy": False}
    assert found["intake"]["serving"] is False
    assert found["inbox"] is None and found["latest_backup"] is None
    assert found["deployment"]["bound"] is False
    # The intake answering is not enough while the daemon cannot be seen.
    service = svc.load_service(made.service)
    intake_config = json.loads(made.intake.read_text())
    with holding(ib.serve_lock_path(intake_config)):
        found = svc.status(made.service, repository=REPOSITORY, probe=answering)
    assert found["intake"]["serving"] is True and found["healthy"] is False
    # With the daemon running and fresh, it is healthy, then not once it ends.
    svc.owner_only_directory(service.state_dir, create=True)
    stop, passed = threading.Event(), threading.Event()
    daemon = threading.Thread(
        target=operate.run_every,
        args=(made.deployment, 5.0),
        kwargs={
            "stop": stop,
            "out": io.StringIO(),
            "heartbeat": svc.heartbeat_path(service),
        },
    )
    real = BatteryValidator.run_pending

    def noted(self):
        try:
            return real(self)
        finally:
            passed.set()

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(BatteryValidator, "run_pending", noted)
        daemon.start()
        try:
            assert passed.wait(60)
            deadline = time.monotonic() + 10
            while svc.daemon_view(service).get("last_pass") != "ok":
                assert time.monotonic() < deadline
                time.sleep(0.05)
            with holding(ib.serve_lock_path(intake_config)):
                found = svc.status(made.service, repository=REPOSITORY, probe=answering)
        finally:
            stop.set()
            daemon.join(30)
    assert found["daemon"]["state"] == "running"
    assert found["daemon"]["passes"] >= 1
    assert found["healthy"] is True
    with holding(ib.serve_lock_path(intake_config)):
        found = svc.status(made.service, repository=REPOSITORY, probe=answering)
    assert found["daemon"]["state"] == "not_running" and found["healthy"] is False


def beating(service, **fields):
    """Write a heartbeat as the daemon does, for a daemon the test plays."""
    value = {
        "schema": operate.HEARTBEAT_SCHEMA,
        "pid": os.getpid(),
        "every_s": 60.0,
        "passes": 4,
        "in_pass": False,
        "last_pass": "ok",
        "stopped": False,
        "updated_unix": time.time(),
        **fields,
    }
    write(svc.heartbeat_path(service), value)


def test_a_stuck_failing_or_waiting_daemon_is_unhealthy(tmp_path):
    made = throwaway(tmp_path)
    service = svc.load_service(made.service)
    svc.owner_only_directory(service.state_dir, create=True)
    with holding(svc.daemon_lock_path(service)):
        assert svc.daemon_view(service)["state"] == "starting"
        beating(service)
        assert svc.daemon_view(service)["healthy"] is True
        # Between passes for longer than twice the period plus a margin.
        beating(service, updated_unix=time.time() - 200)
        assert svc.daemon_view(service)["state"] == "stale"
        # A pass in flight is never stale: rebuilds run for minutes.
        beating(
            service,
            in_pass=True,
            updated_unix=time.time() - 900,
            pass_started_unix=time.time() - 900,
        )
        view = svc.daemon_view(service)
        assert (view["state"], view["healthy"]) == ("running", True)
        assert view["pass_running_s"] >= 899
        beating(service, last_pass="failed")
        view = svc.daemon_view(service)
        assert (view["state"], view["healthy"]) == ("running", False)
        beating(service, last_pass="unavailable")
        assert svc.daemon_view(service)["state"] == "waiting_for_host"
        # The previous daemon's last word, before a new one has written.
        beating(service, stopped=True)
        assert svc.daemon_view(service)["state"] == "starting"
    # Its lock released, a heartbeat however fresh is a daemon not running.
    beating(service)
    assert svc.daemon_view(service)["state"] == "not_running"


def test_a_probe_never_makes_a_start_fail(tmp_path):
    """`status` and `restore` probe the supervisor's lock shared, for an
    instant; the supervisor retries its own lock, so a probe at the moment it
    starts is never `supervisor_already_running`."""
    made = throwaway(tmp_path)
    service = svc.load_service(made.service)
    svc.owner_only_directory(service.state_dir, create=True)
    lock = service.state_dir / "supervisor.lock"
    lock.touch(mode=0o600)
    fd = os.open(lock, os.O_RDONLY)
    fcntl.flock(fd, fcntl.LOCK_SH)
    threading.Timer(0.3, os.close, args=(fd,)).start()
    held = sup._lock(service)
    try:
        assert svc.running(service) is True
    finally:
        os.close(held)
    assert svc.running(service) is False
