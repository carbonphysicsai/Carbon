"""The battery truth environment: hash-locked overlay, verified before any solve.

Offline: the wheels are built in memory and the container run is a fixture.
Materializing the real overlay and running the pinned image happen on the
operator's host (`operate truth-materialize`, `operate truth-verify`).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
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
    assert any(
        part.startswith("type=bind,") and part.endswith(",target=/overlay,readonly")
        for part in command
    )
    assert (target / truth_env.VERIFIED).stat().st_mode & 0o077 == 0


def test_verify_and_solve_run_as_the_owner_of_the_owner_only_overlay(tmp_path):
    """materialize makes the overlay 0700 for the invoking user. The pinned
    image's own user is someone else, so a container without --user cannot
    enter the overlay and PyBaMM looks absent. Both runs must use the owner."""
    owner = f"{os.getuid()}:{os.getgid()}"
    for command in (
        truth_env.verify_command(tmp_path / "overlay"),
        truth_env.solve_command(
            tmp_path / "overlay", tmp_path / "work", repository=REPOSITORY
        ),
    ):
        assert command[command.index("--user") + 1] == owner


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
    mounts = [command[i + 1] for i, part in enumerate(command) if part == "--mount"]
    assert mounts == [
        f"type=bind,source={(tmp_path / 'overlay').resolve()},target=/overlay,readonly",
        f"type=bind,source={REPOSITORY.resolve()},target=/carbon,readonly",
        f"type=bind,source={(tmp_path / 'work').resolve()},target=/work",
    ]
    assert "-v" not in command
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command and TRUTH_IMAGE["base_image"] in command
    assert command[-8:-6] == ["--jobs", "/work/jobs.json"]


def test_a_colon_in_a_work_path_mounts_and_a_comma_is_refused(tmp_path):
    """A design bank's tranche directory holds ':' (`bank-design:battery-q3-T1`):
    `-v` split it ("too many colons"); `--mount` carries it whole. `--mount`
    splits on ',', so a path holding one is refused, never mis-mounted."""
    work = tmp_path / "work" / "bank-design:battery-q3-T1"
    command = truth_env.solve_command(tmp_path / "overlay", work, repository=REPOSITORY)
    assert f"type=bind,source={work.resolve()},target=/work" in command
    with pytest.raises(truth_env.TruthEnvironmentError, match="','"):
        truth_env.solve_command(
            tmp_path / "overlay", tmp_path / "a,b", repository=REPOSITORY
        )


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


def _fake_reference(job):
    if job["case_id"] == "fails":
        raise ValueError("solver fault")
    if job["case_id"] == "slow":
        import time

        time.sleep(30)
    return {"status": "OK", "value": job["c1"]}


def test_every_record_a_solve_writes_names_its_image_and_overlay_lock(
    tmp_path, monkeypatch
):
    import sys

    from carbon.battery import truth

    lock, lock_sha = truth_env.load_lock(REPOSITORY)
    monkeypatch.setitem(
        sys.modules,
        "pybamm",
        types.SimpleNamespace(__version__=truth_env.pinned_version(lock)),
    )
    monkeypatch.setattr(truth, "reference_solver", _fake_reference)
    inputs = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.1}
    jobs = tmp_path / "jobs.json"
    jobs.write_text(
        json.dumps(
            {
                "fingerprint": "fp",
                "jobs": [
                    {"case_id": c, **inputs} for c in ("ok", "fails", "slow", "earlier")
                ],
            }
        )
    )
    records = tmp_path / "records.jsonl"
    # A record from an earlier run is kept exactly as it was written.
    earlier = json.dumps({"case_id": "earlier", "status": "OK"}, sort_keys=True) + "\n"
    records.write_text(earlier)
    records.chmod(0o600)
    result = truth_env.solve(
        jobs, records, repository=REPOSITORY, workers=3, timeout_s=2.0
    )
    assert result["fingerprint"] == "fp"
    lines = records.read_text().splitlines()
    assert lines[0] + "\n" == earlier
    written = {r["case_id"]: r for r in map(json.loads, lines[1:])}
    assert {c: r["status"] for c, r in written.items()} == {
        "ok": truth.OK,
        "fails": truth.SOLVER_FAILED,
        "slow": truth.TIMEOUT,
    }
    expected = {
        "schema": truth_env.PROVENANCE,
        "solver_image": TRUTH_IMAGE["base_image"],
        "overlay_lock": LOCK_PATH,
        "overlay_lock_sha256": "sha256:" + lock_sha,
        "pybamm": truth_env.pinned_version(lock),
    }
    assert expected["solver_image"].split("@")[1] == (
        "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
    )
    for record in written.values():
        assert record[truth_env.PROVENANCE_FIELD] == expected
    # v3 record bytes are frozen (the v3 golden): core-seconds are v4-only.
    assert not any("core_s" in record for record in written.values())
    assert records.stat().st_mode & 0o077 == 0
    assert not list(tmp_path.glob("*.stamping"))


def test_a_design_bank_tranche_identity_survives_the_truth_worker_and_resume(
    tmp_path, monkeypatch
):
    import sys

    from carbon.battery import truth
    from carbon.challenge_validator import design_bank

    lock, _ = truth_env.load_lock(REPOSITORY)
    monkeypatch.setitem(
        sys.modules,
        "pybamm",
        types.SimpleNamespace(__version__=truth_env.pinned_version(lock)),
    )
    monkeypatch.setattr(truth, "reference_solver", _fake_reference)
    work = tmp_path / "bank-design:toy-T1"
    work.mkdir(mode=0o700)
    jobs = [
        {
            "case_id": "public-q1",
            "c1": 1.0,
            "c2": 0.5,
            "t_amb_c": 25.0,
            "soc0": 0.1,
        }
    ]
    tranche = "bank-design:toy-T1"
    design_bank._write_jobs(work, tranche, jobs)
    job_document = json.loads((work / "jobs.json").read_bytes())
    assert job_document == {"tranche": tranche, "jobs": jobs}

    runs = []
    real_run = truth.TruthService.run

    def fail_after_first_completed_run(service, jobs):
        summary = real_run(service, jobs)
        runs.append(summary)
        if len(runs) == 1:
            raise RuntimeError("simulated post-solve failure")
        return summary

    monkeypatch.setattr(truth.TruthService, "run", fail_after_first_completed_run)

    with pytest.raises(RuntimeError, match="post-solve"):
        truth_env.solve(
            work / "jobs.json", work / "records.jsonl", repository=REPOSITORY
        )
    record = json.loads((work / "records.jsonl").read_text().splitlines()[0])
    assert record[truth_env.PROVENANCE_FIELD]["schema"] == truth_env.PROVENANCE

    resumed = truth_env.solve(
        work / "jobs.json", work / "records.jsonl", repository=REPOSITORY
    )
    assert resumed["tranche"] == tranche
    assert "fingerprint" not in resumed
    assert resumed["skipped_completed"] == 1
    assert resumed["counts"][truth.OK] == 0
    assert len((work / "records.jsonl").read_text().splitlines()) == 1
    assert len(runs) == 2


@pytest.mark.parametrize(
    "identity_fields",
    [
        {},
        {"fingerprint": "fp", "tranche": "bank-design:toy-T1"},
        {"fingerprint": ""},
        {"tranche": None},
    ],
)
def test_malformed_job_identity_refuses_before_creating_records_or_solving(
    tmp_path, monkeypatch, identity_fields
):
    import sys

    from carbon.battery import truth

    lock, _ = truth_env.load_lock(REPOSITORY)
    monkeypatch.setitem(
        sys.modules,
        "pybamm",
        types.SimpleNamespace(__version__=truth_env.pinned_version(lock)),
    )
    calls = []
    real_run = truth.TruthService.run

    def observed_run(service, jobs):
        calls.append(jobs)
        return real_run(service, jobs)

    monkeypatch.setattr(truth.TruthService, "run", observed_run)
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({**identity_fields, "jobs": []}))
    records = tmp_path / "records.jsonl"

    with pytest.raises(truth_env.TruthEnvironmentError, match="identity"):
        truth_env.solve(jobs, records, repository=REPOSITORY)

    assert calls == []
    assert not records.exists()
