"""The battery truth environment: hash-locked overlay, verified before any solve.

Offline: the wheels are built in memory and the container run is a fixture.
Materializing the real overlay and running the pinned image happen on the
operator's host (`operate truth-materialize`, `operate truth-verify`).
"""

from __future__ import annotations

import hashlib
import io
import json
import types
import zipfile
from pathlib import Path

import pytest

from carbon.battery import truth_env
from carbon.battery.truth import LOCK_PATH, TRUTH_IMAGE

REPOSITORY = Path(__file__).resolve().parents[2]


def wheel(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return buffer.getvalue()


def fake_repository(tmp_path, wheels):
    lock = {
        "schema": "carbon.exam-design.wheel-overlay-lock.v1",
        "base_image": TRUTH_IMAGE["base_image"],
        "root_requirement": TRUTH_IMAGE["root_requirement"],
        "provided_by_base_image": {"numpy": "2.4.6", "scipy": "1.17.1"},
        "wheels": [
            {
                "filename": name,
                "url": "https://example.invalid/" + name,
                "sha256": hashlib.sha256(body).hexdigest(),
                "size": len(body),
            }
            for name, body in wheels.items()
        ],
    }
    path = tmp_path / "repo" / LOCK_PATH
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(lock))
    return tmp_path / "repo"


def served(wheels):
    by_url = {"https://example.invalid/" + n: b for n, b in wheels.items()}
    calls = []

    def fetch(url):
        calls.append(url)
        return by_url[url]

    return fetch, calls


def test_the_repository_lock_pins_the_truth_image():
    lock, digest = truth_env.load_lock(REPOSITORY)
    assert truth_env.pinned_version(lock) == "26.8.0.0"
    assert len(digest) == 64 and lock["wheels"]


def test_materialize_extracts_hash_checked_wheels_once(tmp_path):
    wheels = {
        "pybamm-26.8.0.0-py3-none-any.whl": wheel(
            {"pybamm/__init__.py": "__version__ = '26.8.0.0'\n"}
        ),
        "extra-1.0-py3-none-any.whl": wheel(
            {
                "extra-1.0.data/purelib/extra.py": "X = 1\n",
                "extra-1.0.data/scripts/tool": "#!/bin/sh\n",
            }
        ),
    }
    repository = fake_repository(tmp_path, wheels)
    fetch, calls = served(wheels)
    target = tmp_path / "overlay"
    manifest = truth_env.materialize(target, repository=repository, fetch=fetch)
    assert (target / "pybamm" / "__init__.py").exists()
    assert (target / "extra.py").exists() and not (target / "tool").exists()
    assert manifest["wheels"] == 2 and target.stat().st_mode & 0o077 == 0
    # Idempotent for the same lock: nothing is fetched again.
    assert truth_env.materialize(target, repository=repository, fetch=fetch) == manifest
    assert len(calls) == 2


def test_a_wheel_with_the_wrong_hash_is_refused(tmp_path):
    good = {"a-1-py3-none-any.whl": wheel({"a.py": "A = 1\n"})}
    repository = fake_repository(tmp_path, good)
    tampered = {"a-1-py3-none-any.whl": wheel({"a.py": "A = 2\n"})}
    fetch, _ = served(tampered)
    with pytest.raises(truth_env.TruthEnvironmentError, match="hash mismatch"):
        truth_env.materialize(tmp_path / "overlay", repository=repository, fetch=fetch)


@pytest.mark.parametrize("member", ["../escape.py", "/abs.py", "pkg/../../escape.py"])
def test_a_member_escaping_the_overlay_is_refused(tmp_path, member):
    wheels = {"evil-1-py3-none-any.whl": wheel({member: "x = 1\n"})}
    repository = fake_repository(tmp_path, wheels)
    fetch, _ = served(wheels)
    with pytest.raises(truth_env.TruthEnvironmentError, match="escapes"):
        truth_env.materialize(tmp_path / "overlay", repository=repository, fetch=fetch)
    assert not (tmp_path / "escape.py").exists()


def verified_target(tmp_path):
    wheels = {"p-1-py3-none-any.whl": wheel({"p.py": "P = 1\n"})}
    repository = fake_repository(tmp_path, wheels)
    fetch, _ = served(wheels)
    target = tmp_path / "overlay"
    truth_env.materialize(target, repository=repository, fetch=fetch)
    return repository, target


def runner_reporting(versions, returncode=0):
    seen = []

    def run(command, **kwargs):
        seen.append(command)
        return types.SimpleNamespace(
            returncode=returncode, stdout=(json.dumps(versions) + "\n").encode()
        )

    return run, seen


def test_verify_runs_the_pinned_image_offline_and_records_versions(tmp_path):
    repository, target = verified_target(tmp_path)
    run, seen = runner_reporting(
        {"pybamm": "26.8.0.0", "numpy": "2.4.6", "scipy": "1.17.1"}
    )
    record = truth_env.verify(target, repository=repository, runner=run)
    assert record["versions"]["pybamm"] == "26.8.0.0"
    command = seen[0]
    assert TRUTH_IMAGE["base_image"] in command
    assert command[command.index("--network") + 1] == "none"
    assert any(part.endswith(":/overlay:ro") for part in command)
    assert (target / truth_env.VERIFIED).stat().st_mode & 0o077 == 0


@pytest.mark.parametrize(
    ("versions", "returncode"),
    [
        ({"pybamm": "26.9.0", "numpy": "2.4.6", "scipy": "1.17.1"}, 0),
        ({"pybamm": "26.8.0.0", "numpy": "2.5.0", "scipy": "1.17.1"}, 0),
        ({}, 1),
    ],
)
def test_verify_refuses_any_other_environment(tmp_path, versions, returncode):
    repository, target = verified_target(tmp_path)
    run, _ = runner_reporting(versions, returncode)
    with pytest.raises(truth_env.TruthEnvironmentError):
        truth_env.verify(target, repository=repository, runner=run)
    assert not (target / truth_env.VERIFIED).exists()


def test_solve_refuses_outside_the_verified_truth_runtime(tmp_path, monkeypatch):
    import sys

    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"fingerprint": "fp", "jobs": []}))
    records = tmp_path / "records.jsonl"
    # This interpreter has no PyBaMM: refused before anything runs.
    monkeypatch.setitem(sys.modules, "pybamm", None)
    with pytest.raises(truth_env.TruthEnvironmentError, match="pybamm"):
        truth_env.solve(jobs, records, repository=REPOSITORY)
    assert not records.exists()
    # A different PyBaMM is refused too.
    monkeypatch.setitem(
        sys.modules, "pybamm", types.SimpleNamespace(__version__="25.1.0")
    )
    with pytest.raises(truth_env.TruthEnvironmentError, match="differs"):
        truth_env.solve(jobs, records, repository=REPOSITORY)
    assert (
        truth_env.main(["solve", "--jobs", str(jobs), "--records", str(records)]) == 2
    )


def test_the_solve_container_sees_only_overlay_source_and_workdir(tmp_path):
    command = truth_env.solve_command(
        tmp_path / "overlay", tmp_path / "work", repository=REPOSITORY, workers=6
    )
    mounts = [command[i + 1] for i, part in enumerate(command) if part == "-v"]
    assert mounts == [
        f"{(tmp_path / 'overlay').resolve()}:/overlay:ro",
        f"{REPOSITORY.resolve()}:/carbon:ro",
        f"{(tmp_path / 'work').resolve()}:/work:rw",
    ]
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command and TRUTH_IMAGE["base_image"] in command
    assert command[-8:-6] == ["--jobs", "/work/jobs.json"]


def test_operate_jobs_writes_an_owner_only_file_without_starting(tmp_path, capsys):
    import sys

    sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))
    from test_battery_validator_daemon import PIN_G, PIN_S

    from carbon.battery import deployment, operate, seeds

    tmp_path.chmod(0o700)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin(PIN_G, PIN_S))
    config = tmp_path / "deployment.json"
    config.write_text(
        json.dumps(
            {
                "schema": deployment.SCHEMA,
                "state": str(tmp_path / "state.sqlite3"),
                "private_root": str(tmp_path / "root.bin"),
                "journal": str(tmp_path / "journal.jsonl"),
                "work": str(tmp_path / "work"),
                "backend": "direct",
                "require_commitment": False,
            }
        )
    )
    config.chmod(0o600)
    deployment._VALIDATORS.clear()
    assert (
        operate.main(
            [
                "prepare",
                "--config",
                str(config),
                "--role",
                "pscreen-T00",
                "--kind",
                "screening",
            ]
        )
        == 0
    )
    fingerprint = json.loads(capsys.readouterr().out)["fingerprint"]
    out = tmp_path / "jobs.json"
    assert (
        operate.main(
            ["jobs", "--config", str(config), "--batch", fingerprint, "--out", str(out)]
        )
        == 0
    )
    printed = capsys.readouterr().out
    document = json.loads(out.read_text())
    assert out.stat().st_mode & 0o077 == 0
    # 100 cases, two of them hidden repeats that reuse their originals' solves.
    assert document["fingerprint"] == fingerprint and len(document["jobs"]) == 98
    # The terminal never shows a case; only the owner-only file holds them.
    assert all(job["case_id"] not in printed for job in document["jobs"])
    deployment._VALIDATORS.clear()
