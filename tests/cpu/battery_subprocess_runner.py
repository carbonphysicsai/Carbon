"""A test stand-in for the Docker research carrier: same stage, same program.

It stages exactly the files the carrier would, runs the fixed program with the
carrier's working-directory layout in a separate interpreter, charges the same
ledger reservation and returns the carrier's result shape. It is NOT isolated:
no container, no network or memory bound. Tests pass it as the practice
runner and practice feedback then names `SUBPROCESS_TEST_ONLY_NOT_ISOLATED` as
its backend, so a result can never claim the carrier's isolation.
"""

from __future__ import annotations

import subprocess
import sys

from carbon.development_session.profile import canonical, digest

BACKEND = {"kind": "SUBPROCESS_TEST_ONLY_NOT_ISOLATED"}


def run(
    ledger,
    *,
    owner,
    identity,
    source,
    files,
    image,
    seconds,
    provenance,
    extra_resources,
):
    request = {
        "source": digest(source.encode()),
        "files": {n: digest(b) for n, b in files.items()},
        "seconds": seconds,
        "provenance": provenance,
    }
    resources = {"numerical_milliseconds": seconds * 1000, **extra_resources}
    admission = ledger.reserve(
        identity, owner=owner, phase="research", request=request, resources=resources
    )
    if not admission["dispatch"]:
        return admission["result"]
    operation = ledger.root / ("operation-" + digest(canonical([owner, identity]))[7:])
    work, out = operation / "scratch" / "workspace", operation / "scratch" / "output"
    work.mkdir(parents=True)
    out.mkdir()
    for name, body in files.items():
        (work / name).write_bytes(body)
    (operation / "program.py").write_text(source)
    completed = subprocess.run(
        [sys.executable, "-I", str(operation / "program.py")],
        cwd=work,
        capture_output=True,
        check=False,
        timeout=seconds,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode()[-4000:])
    snapshot = operation / "snapshot"
    out.rename(snapshot)
    result = {
        "schema": "carbon.autoresearch.worker-result.v1",
        "provenance": provenance,
        "output_digest": digest(
            b"".join(p.read_bytes() for p in sorted(snapshot.iterdir()))
        ),
        "files": {p.name: digest(p.read_bytes()) for p in sorted(snapshot.iterdir())},
        "operation": operation.name,
        "scientific_qualification": False,
        "official_eligible": False,
    }
    ledger.finish(
        identity, owner=owner, state="SUCCEEDED", actual=resources, result=result
    )
    return result
