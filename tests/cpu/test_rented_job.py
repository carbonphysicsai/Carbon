"""The one-job server a remote worker container runs, and the controller's
client.

The server runs in-process on 127.0.0.1 here. The program, the token checks,
the stage-once rule, the carrier's working-directory layout and the bounded,
flat-file archives are all real; only the container around them is absent.
"""

from __future__ import annotations

import gzip
import io
import json
import tarfile
import threading
import urllib.error
import urllib.request
import zlib

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


def zeros(size):
    """A gzip stream of `size` zero bytes, built without ever holding them."""
    deflate = zlib.compressobj(9, zlib.DEFLATED, 31)
    chunk = bytes(1 << 20)
    parts = [deflate.compress(chunk) for _ in range(size >> 20)]
    parts.append(deflate.flush())
    return b"".join(parts)


def test_a_small_archive_of_zeros_is_refused_without_inflating_in_memory():
    """The 2026-10-03 review: a 1 MB response took about 2 GiB, because the
    whole archive was inflated before its size was checked. Now it is
    abandoned as soon as it passes twice its bound."""
    import tracemalloc

    maximum = 1 << 20
    bomb = zeros(256 << 20)
    assert len(bomb) < maximum
    tracemalloc.start()
    try:
        with pytest.raises(ValueError, match="bound"):
            job_server.unpack(bomb, maximum)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 8 * maximum, peak
    # Specimen: the same stream within a generous bound inflates to its size,
    # so the refusal above is the bound, not a broken stream.
    inflater = zlib.decompressobj(wbits=31)
    assert len(inflater.decompress(zeros(2 << 20))) == 2 << 20


def tar_of(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, body in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


MALFORMED_OUTPUTS = {
    "not gzip": b"not a gzip stream at all",
    "truncated gzip": job_server.pack({"a": b"x" * 4096})[:40],
    "gzip of no tar": gzip.compress(b"not a tar archive" * 64),
    "no job result": job_server.pack({"a": b"1"}),
    "result not a record": job_server.pack({"carbon-job-result.json": b"[1]"}),
    "result not json": job_server.pack({"carbon-job-result.json": b"{"}),
    "trailing bytes": job_server.pack({"carbon-job-result.json": b"{}"}) + b"tail",
    "two gzip members": job_server.pack({"carbon-job-result.json": b"{}"}) * 2,
    "a link": archive([("link", "link")]),
    "a nested name": gzip.compress(tar_of({"dir/carbon-job-result.json": b"{}"})),
}


@pytest.mark.parametrize("shape", sorted(MALFORMED_OUTPUTS))
def test_malformed_output_is_the_jobs_typed_failure(shape):
    """Whatever the response holds, RemoteJob.output raises RemoteJobFailure,
    which the runner's handler settles, so no operation is left RESERVED."""
    body = MALFORMED_OUTPUTS[shape]
    job = RemoteJob(
        "https://pod.example.org", new_token(), transport=lambda *a, **k: (200, body)
    )
    with pytest.raises(RemoteJobFailure) as failed:
        job.output()
    assert failed.value.stage == "output"
    # Specimen: a well-formed output reads.
    good = job_server.pack({"carbon-job-result.json": b'{"returncode": 0}', "a": b"1"})
    result, files = RemoteJob(
        "https://pod.example.org", new_token(), transport=lambda *a, **k: (200, good)
    ).output()
    assert result == {"returncode": 0} and files == {"a": b"1"}


def test_an_oversized_output_is_refused_by_the_controller(monkeypatch):
    from carbon.compute import remote_job

    monkeypatch.setattr(remote_job, "MAX_OUTPUT_BYTES", 1 << 20)
    bomb = zeros(64 << 20)
    job = RemoteJob(
        "https://pod.example.org", new_token(), transport=lambda *a, **k: (200, bomb)
    )
    with pytest.raises(RemoteJobFailure, match="output"):
        job.output()


ZEROS_PROGRAM = (
    b"from pathlib import Path\n"
    b"(Path.cwd().parent / 'output' / 'z.bin').write_bytes(bytes(3 << 20))\n"
)


def test_the_server_never_reads_output_past_its_bound(tmp_path, monkeypatch):
    """Agent code can write as much as it likes to ../output; the server reads
    at most twice the wire bound of it, so a compressible file can no longer
    pass on its compressed size alone."""
    monkeypatch.setattr(job_server, "MAX_OUTPUT_BYTES", 1 << 20)
    job = job_server.Job(tmp_path, 30)
    job.stage({"program.py": ZEROS_PROGRAM})
    job.run()
    assert job.finished.wait(30) and job.state == "DONE"
    with pytest.raises(job_server.OutputRefused):
        job.output()


def test_an_oversized_output_is_answered_413_never_not_finished(pod, monkeypatch):
    monkeypatch.setattr(job_server, "MAX_OUTPUT_BYTES", 1 << 20)
    base, token, _ = pod
    job = RemoteJob(base, token, sleep=lambda _: None)
    with pytest.raises(RemoteJobFailure, match="output: http 413"):
        job.run(
            {"program.py": ZEROS_PROGRAM},
            ready_deadline=job.clock() + 10,
            run_deadline=job.clock() + 30,
        )


def test_a_remote_job_is_reached_over_https_or_a_local_tunnel():
    # Plain HTTP to another host is refused, with no flag to allow it: the
    # only plain-HTTP route is this machine's end of an SSH port forward.
    for url in ("http://pod.example.org:8000", "http://10.0.0.5:8000"):
        with pytest.raises(ValueError, match="https"):
            RemoteJob(url, new_token())
    with pytest.raises(TypeError):
        RemoteJob("http://pod.example.org:8000", new_token(), plain_http=True)
    RemoteJob("https://pod.example.org", new_token())
    RemoteJob("http://127.0.0.1:41000", new_token())


def test_the_server_refuses_to_start_without_a_job_token():
    with pytest.raises(ValueError, match="job token"):
        job_server.serve(token="", port=0, seconds=1, lifetime=1)


def test_unknown_paths_are_not_found(pod):
    base, _, _ = pod
    request = urllib.request.Request(base + "/anything", method="GET")
    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(request, timeout=5)
    assert refused.value.code == 404
