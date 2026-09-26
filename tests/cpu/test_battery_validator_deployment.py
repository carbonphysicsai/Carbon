"""The operator's battery validator deployment and its commands.

The deployment is the only way a campaign reaches battery evaluation. These
tests check that it fails closed - bad configuration, a changed identity
binding, a required commitment with no chain reader - and that the operator
commands never print a case, seed or key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    PIN_G,
    PIN_S,
    batch,
    refs,  # noqa: F401 - fixture
    submission,
)

from carbon.battery import deployment, operate, seeds, signing
from carbon.battery.pool_store import PoolStore


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(deployment, "_VALIDATORS", {})


def write(path, value, mode=0o600):
    path.write_text(json.dumps(value))
    path.chmod(mode)
    return path


def config(tmp_path, **overrides):
    tmp_path.chmod(0o700)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin(PIN_G, PIN_S))
    value = {
        "schema": deployment.SCHEMA,
        "state": str(tmp_path / "state.sqlite3"),
        "private_root": str(tmp_path / "root.bin"),
        "journal": str(tmp_path / "journal.jsonl"),
        "work": str(tmp_path / "work"),
        "backend": "direct",
        "require_commitment": False,
        **overrides,
    }
    return write(tmp_path / "deployment.json", value)


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            {"schema": "carbon.battery.evaluation-deployment.v1"},
            "evaluation_config_schema",
        ),
        ({"batches": "x"}, "evaluation_config_fields"),
        ({"backend": "pytorch"}, "evaluation_config_backend"),
        ({"backend": "carrier"}, "evaluation_config_image"),
        ({"require_commitment": "no"}, "evaluation_config_fields"),
    ],
)
def test_a_bad_configuration_is_refused(tmp_path, change, code):
    path = config(tmp_path, **change)
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == code


def test_configuration_files_must_be_owner_only(tmp_path):
    path = config(tmp_path)
    path.chmod(0o640)
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == "evaluation_input_not_owner_only"


def test_a_changed_identity_binding_stops_the_deployment(tmp_path):
    path = config(tmp_path)
    PoolStore(tmp_path / "state.sqlite3").bind({"schema": "another deployment"})
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == "evaluation_identities_changed"


def test_a_required_commitment_is_never_skipped(tmp_path, refs):  # noqa: F811
    path = config(tmp_path, require_commitment=True)
    target = deployment.validator(path, repository=REPOSITORY)
    target.allow_published_cases = True
    for b in range(3):
        fp = target.import_batch(batch(refs, f"pscreen-B0{b}"), kind="screening")
        target.ingest_references(fp, list(refs.values()))
    target.open_pool()
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.evaluate(target, submission("hk1"))
    assert refused.value.code == "commitment_reader_unavailable"
    assert target.status()["pool"]["admitted"] == 0


def test_operator_commands_disclose_no_case_seed_or_key(
    tmp_path,
    refs,  # noqa: F811
    capsys,
):
    signing.ServiceKey.create(tmp_path / "service.key")
    path = config(tmp_path, service_key=str(tmp_path / "service.key"))
    target = deployment.validator(path, repository=REPOSITORY)
    target.allow_published_cases = True
    for b in range(3):
        fp = target.import_batch(batch(refs, f"pscreen-B0{b}"), kind="screening")
        records = tmp_path / f"records-{b}.jsonl"
        records.write_text("".join(json.dumps(r) + "\n" for r in refs.values()))
        records.chmod(0o600)
        assert (
            operate.main(
                [
                    "ingest",
                    "--config",
                    str(path),
                    "--batch",
                    fp,
                    "--records",
                    str(records),
                ]
            )
            == 0
        )
    # A fresh batch generated from the private root, committed before use.
    assert (
        operate.main(
            [
                "prepare",
                "--config",
                str(path),
                "--role",
                "pscreen-B03",
                "--kind",
                "screening",
            ]
        )
        == 0
    )
    assert operate.main(["open", "--config", str(path)]) == 0
    deployment.evaluate(target, submission("hk1"))
    assert operate.main(["run", "--config", str(path)]) == 0
    assert operate.main(["batches", "--config", str(path)]) == 0
    assert operate.main(["status", "--config", str(path)]) == 0
    out = tmp_path / "export"
    assert operate.main(["export", "--config", str(path), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    for case_id in refs:
        assert case_id not in printed
    assert (tmp_path / "root.bin").read_bytes().hex() not in printed
    assert (tmp_path / "service.key").read_bytes().hex() not in printed
    exported = sorted(out.iterdir())
    assert all(p.stat().st_mode & 0o077 == 0 for p in exported)
    intent = json.loads((out / "weight-intent.json").read_text())
    assert signing.verify(intent) and intent["payload"]["mode"] == "ALL_BURN"
    outcomes = [
        json.loads(p.read_text()) for p in exported if p.name.startswith("bsub-")
    ]
    assert len(outcomes) == 1 and all(signing.verify(o) for o in outcomes)
    assert outcomes[0]["payload"]["state"] == "SCORED"


def test_a_shared_work_directory_is_refused(tmp_path):
    work = tmp_path / "work"
    work.mkdir(mode=0o755)
    work.chmod(0o755)
    path = config(tmp_path)
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == "evaluation_work_not_owner_only"


def test_status_never_recovers_a_run_another_process_is_executing(
    tmp_path, capsys, monkeypatch
):
    """status and batches are read-only: they never start or recover the
    daemon, so they can never abandon a run in flight in another process."""
    from carbon.battery.daemon import BatteryValidator

    path = config(tmp_path)
    deployment.validator(path, repository=REPOSITORY)  # bind identities once
    monkeypatch.setattr(deployment, "_VALIDATORS", {})

    def forbidden(self):
        raise AssertionError("a read-only command started or recovered")

    monkeypatch.setattr(BatteryValidator, "start", forbidden)
    monkeypatch.setattr(BatteryValidator, "recover", forbidden)
    assert operate.main(["status", "--config", str(path)]) == 0
    assert operate.main(["batches", "--config", str(path)]) == 0
    capsys.readouterr()


def test_the_writer_lock_excludes_other_processes(tmp_path):
    import subprocess
    import sys

    path = config(tmp_path)
    target = deployment.validator(path, repository=REPOSITORY)
    probe = (
        "import fcntl, os, sys\n"
        "fd = os.open(sys.argv[1], os.O_RDWR)\n"
        "try:\n"
        "    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        "except BlockingIOError:\n"
        "    sys.exit(7)\n"
    )
    with deployment.writer(target):
        held = subprocess.run(
            [sys.executable, "-c", probe, target.lock_path], check=False
        )
    free = subprocess.run([sys.executable, "-c", probe, target.lock_path], check=False)
    assert held.returncode == 7 and free.returncode == 0


def test_a_readonly_deployment_cannot_evaluate(tmp_path):
    path = config(tmp_path)
    target = deployment.validator(path, repository=REPOSITORY, readonly=True)
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.evaluate(target, submission("hk1"))
    assert refused.value.code == "evaluation_readonly"


def bare_config(tmp_path):
    """A deployment whose root and journal do not exist yet (for `init`)."""
    tmp_path.chmod(0o700)
    validator = tmp_path / "validator"
    value = {
        "schema": deployment.SCHEMA,
        "state": str(validator / "state.sqlite3"),
        "private_root": str(validator / "root.bin"),
        "journal": str(validator / "journal.jsonl"),
        "work": str(validator / "work"),
        "backend": "direct",
        "require_commitment": False,
    }
    return write(tmp_path / "deployment.json", value)


def test_init_creates_and_commits_the_root_once(tmp_path, capsys):
    path = bare_config(tmp_path)
    assert operate.main(["init", "--config", str(path)]) == 0
    first = json.loads(capsys.readouterr().out)
    root_path = tmp_path / "validator" / "root.bin"
    journal_path = tmp_path / "validator" / "journal.jsonl"
    assert first["root_created"] and first["root_committed"]
    assert root_path.stat().st_mode & 0o777 == 0o600
    assert root_path.stat().st_size == 32
    assert journal_path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "validator").stat().st_mode & 0o777 == 0o700
    pin = first["seed_pin"]
    assert pin["generator_digest"] == seeds.generator_digest(REPOSITORY)
    from carbon.battery.daemon import rule_digest

    assert pin["scoring_digest"] == rule_digest()
    # Nothing printed reveals the root.
    root = root_path.read_bytes()
    assert root.hex() not in json.dumps(first)
    # A second run keeps the root and its binding.
    before = (root, journal_path.read_bytes())
    assert operate.main(["init", "--config", str(path)]) == 0
    second = json.loads(capsys.readouterr().out)
    assert not second["root_created"] and not second["root_committed"]
    assert second["seed_pin"] == pin
    assert (root_path.read_bytes(), journal_path.read_bytes()) == before
    # The deployment now builds and reports the committed pin.
    assert operate.main(["status", "--config", str(path)]) == 0
    capsys.readouterr()


def test_init_refuses_a_journal_bound_to_another_root(tmp_path, capsys):
    path = bare_config(tmp_path)
    assert operate.main(["init", "--config", str(path)]) == 0
    capsys.readouterr()
    root_path = tmp_path / "validator" / "root.bin"
    root_path.unlink()
    # A missing committed root is refused, and no replacement is written.
    assert operate.main(["init", "--config", str(path)]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "unavailable": "evaluation_journal_other_root"
    }
    assert not root_path.exists()
    # Another existing root is refused too.
    seeds.PrivateRoot.create(root_path)
    assert operate.main(["init", "--config", str(path)]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "unavailable": "evaluation_journal_other_root"
    }


def test_init_keeps_and_refuses_a_group_readable_root(tmp_path, capsys):
    path = bare_config(tmp_path)
    (tmp_path / "validator").mkdir(mode=0o700)
    root_path = tmp_path / "validator" / "root.bin"
    root_path.write_bytes(b"x" * 32)
    root_path.chmod(0o640)
    assert operate.main(["init", "--config", str(path)]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "unavailable": "evaluation_root_refused"
    }
    assert root_path.read_bytes() == b"x" * 32
    assert not (tmp_path / "validator" / "journal.jsonl").exists()


def test_the_generator_digest_is_a_stable_tagged_identity():
    value = seeds.generator_digest(REPOSITORY)
    assert value == seeds.generator_digest(REPOSITORY)
    assert value.startswith("sha256:") and len(value) == 71


def test_a_carrier_deployment_reads_its_image_manifest_as_a_path(tmp_path, monkeypatch):
    """The deployment file holds the manifest path as JSON text, and
    `load_image_identity` reads a `Path`. Building a writable carrier
    deployment must hand it a `Path`, or every export, run and prepare fails
    before doing anything."""
    from carbon.reconstruction.worker import docker_runtime

    seen = []

    class Stop(Exception):
        pass

    def capture(path):
        seen.append(path)
        raise Stop

    monkeypatch.setattr(docker_runtime, "load_image_identity", capture)
    manifest = tmp_path / "worker-image.json"
    path = config(tmp_path, backend="carrier", image_manifest=str(manifest))
    with pytest.raises(Stop):
        deployment.validator(path, repository=REPOSITORY)
    assert seen == [manifest] and isinstance(seen[0], Path)
