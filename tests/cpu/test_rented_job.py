"""The one-job server a rented pod runs, and the controller's client.

The server runs in-process on 127.0.0.1 here. The program, the token checks,
the stage-once rule, the carrier's working-directory layout and the bounded,
flat-file archives are all real; only the pod around them is absent.
"""

from __future__ import annotations

import gzip
import io
import json
import tarfile
import threading
import urllib.error
import urllib.request

import pytest

from carbon.compute import job_server
from carbon.compute.remote_job import RemoteJob, RemoteJobFailure, new_token

PROGRAM = b"""
import json
from pathlib import Path
work = Path.cwd()
out = work.parent / "output"
data = json.loads((work / "inputs.json").read_text())
(out / "predictions.json").write_text(json.dumps({"sum": sum(data)}))
"""


@pytest.fixture
def pod(tmp_path, monkeypatch):
    # Localhost is never sent through a configured proxy.
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    token, ready = new_token(), threading.Event()
    port = []

    def started(bound):
        port.append(bound)
        ready.set()

    thread = threading.Thread(
        target=job_server.serve,
        kwargs={
            "token": token,
            "port": 0,
            "seconds": 30,
            "lifetime": 60,
            "root": tmp_path,
            "ready": started,
        },
        daemon=True,
    )
    thread.start()
    assert ready.wait(10)
    yield f"http://127.0.0.1:{port[0]}", token, thread
    thread.join(timeout=1)


def test_a_job_runs_once_in_the_carriers_layout_and_returns_its_output(pod):
    base, token, thread = pod
    job = RemoteJob(base, token, sleep=lambda _: None)
    result, files = job.run(
        {"program.py": PROGRAM, "inputs.json": b"[1, 2, 3]"},
        ready_deadline=job.clock() + 10,
        run_deadline=job.clock() + 30,
    )
    assert result["state"] == "DONE" and result["returncode"] == 0
    assert json.loads(files["predictions.json"]) == {"sum": 6}
    # The output is fetched once; the server then exits.
    thread.join(timeout=10)
    assert not thread.is_alive()


def test_every_request_but_status_needs_the_job_token(pod):
    base, token, _ = pod
    stranger = RemoteJob(base, new_token())
    assert stranger.state() == "WAITING"
    with pytest.raises(RemoteJobFailure, match="stage: http 401"):
        stranger.stage({"program.py": PROGRAM})
    with pytest.raises(RemoteJobFailure, match="run: http 401"):
        stranger.start()
    with pytest.raises(RemoteJobFailure, match="output: http 401"):
        stranger.output()
    # The real job is untouched by the stranger's attempts.
    assert RemoteJob(base, token).state() == "WAITING"


def test_a_job_is_staged_once_and_run_only_after_staging(pod):
    base, token, _ = pod
    job = RemoteJob(base, token)
    with pytest.raises(RemoteJobFailure, match="run: http 409"):
        job.start()
    job.stage({"program.py": PROGRAM, "inputs.json": b"[1]"})
    with pytest.raises(RemoteJobFailure, match="stage: http 400"):
        job.stage({"program.py": PROGRAM, "inputs.json": b"[2]"})


def test_a_failing_program_is_reported_as_failed_with_its_stderr(pod):
    base, token, _ = pod
    job = RemoteJob(base, token, sleep=lambda _: None)
    result, files = job.run(
        {"program.py": b"raise SystemExit('no inputs')"},
        ready_deadline=job.clock() + 10,
        run_deadline=job.clock() + 30,
    )
    assert result["state"] == "FAILED" and result["returncode"] == 1
    assert b"no inputs" in files["carbon-job-stderr.txt"]


def archive(members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "link":
                info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
                tar.addfile(info)
            else:
                info.size = 1
                tar.addfile(info, io.BytesIO(b"x"))
    return gzip.compress(buffer.getvalue())


@pytest.mark.parametrize(
    "members",
    [
        [("../escape", "file")],
        [("dir/nested", "file")],
        [("link", "link")],
        [("same", "file"), ("same", "file")],
    ],
)
def test_archives_carry_flat_regular_files_only(members):
    with pytest.raises(ValueError, match="flat regular files only"):
        job_server.unpack(archive(members), 1024**2)


def test_archives_are_bounded():
    with pytest.raises(ValueError, match="bound"):
        job_server.unpack(job_server.pack({"a": b"x" * 2048}), 64)


def test_a_rented_job_is_reached_over_https():
    with pytest.raises(ValueError, match="https"):
        RemoteJob("http://pod.example.org:8000", new_token())


def test_the_server_refuses_to_start_without_a_job_token():
    with pytest.raises(ValueError, match="job token"):
        job_server.serve(token="", port=0, seconds=1, lifetime=1)


def test_unknown_paths_are_not_found(pod):
    base, _, _ = pod
    request = urllib.request.Request(base + "/anything", method="GET")
    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(request, timeout=5)
    assert refused.value.code == 404
