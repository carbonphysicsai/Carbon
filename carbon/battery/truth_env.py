"""The battery truth environment: the pinned study image plus its PyBaMM overlay.

The truth image (`truth.TRUTH_IMAGE`) is a base image pinned by digest. PyBaMM
is not in the base image; it comes from a wheel overlay pinned by
`scripts/dev/exam_design/locks/battery-overlay.lock.json`. The exam-design
campaign installed that overlay on each pod
(`scripts/dev/exam_design/runpod/bootstrap.py`). This module does the same on
an operator host, in three steps:

1. `materialize`: fetch each locked wheel, or read it from a local wheel
   directory. Check its size and SHA-256, then extract it into an owner-only
   directory. Extraction refuses any member that would leave the directory.
2. `verify`: run the pinned base image with no network, the overlay mounted
   read-only, and `pybamm` imported. The version must be exactly the lock's
   root requirement. A verification record is written.
3. `solve` (run inside the image, `solve_command`): the truth service over
   one batch's jobs file (`operate jobs`), into an owner-only records file
   that `operate ingest` reads. It first checks PyBaMM is at the pinned
   version (`require_truth_runtime`), so a reference is never produced by an
   unverified environment. Every record it writes carries
   `solver_provenance`: the image digest, the overlay lock sha256 and the
   PyBaMM version. The container has no network and sees only the
   overlay, Carbon's source (read-only) and the jobs/records directory -
   never the validator state, private root or journal.

Base-image presence alone is never treated as a runnable truth solver.
"""

from __future__ import annotations

import functools
import hashlib
import io
import json
import os
import stat
import subprocess
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from .truth import LOCK_PATH, TRUTH_IMAGE

MANIFEST = ".carbon-overlay.json"
VERIFIED = ".carbon-overlay-verified.json"
SCHEMA = "carbon.battery.truth-overlay.v1"
PROVENANCE = "carbon.battery.solver-provenance.v1"
#: Every reference record names what solved it, in the record itself.
PROVENANCE_FIELD = "solver_provenance"
INTERPRETER = "/opt/carbon-worker/bin/python"


class TruthEnvironmentError(RuntimeError):
    """The truth environment is not usable; nothing may be solved in it."""


def _sha256(body):
    return hashlib.sha256(body).hexdigest()


def load_lock(repository="."):
    path = Path(repository) / LOCK_PATH
    body = path.read_bytes()
    lock = json.loads(body)
    if lock.get("base_image") != TRUTH_IMAGE["base_image"]:
        raise TruthEnvironmentError("overlay lock names another base image")
    if lock.get("root_requirement") != TRUTH_IMAGE["root_requirement"]:
        raise TruthEnvironmentError("overlay lock names another root requirement")
    return lock, _sha256(body)


def pinned_version(lock):
    name, _, version = lock["root_requirement"].partition("==")
    if name != "pybamm" or not version:
        raise TruthEnvironmentError("the root requirement is not an exact pybamm pin")
    return version


def _fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def _member_target(target, name):
    """Where a wheel member lands, or None to skip it. Never outside target."""
    parts = PurePosixPath(name).parts
    if not parts or name.endswith("/"):
        return None
    if parts[0].endswith(".data"):
        if len(parts) > 2 and parts[1] in ("purelib", "platlib"):
            parts = parts[2:]
        else:
            return None  # scripts and headers are not needed
    if PurePosixPath(name).is_absolute() or any(p in ("..", "") for p in parts):
        raise TruthEnvironmentError("wheel member escapes the overlay: " + name)
    destination = (target / Path(*parts)).resolve()
    if target.resolve() not in destination.parents:
        raise TruthEnvironmentError("wheel member escapes the overlay: " + name)
    return destination


def materialize(target, *, repository=".", wheels_dir=None, fetch=_fetch):
    """Build the overlay directory from the lock. Idempotent for the same lock."""
    lock, lock_sha = load_lock(repository)
    target = Path(target)
    manifest_path = target / MANIFEST
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_bytes())
        if manifest.get("lock_sha256") != lock_sha:
            raise TruthEnvironmentError(
                "overlay built from another lock; use a new dir"
            )
        return manifest
    if target.exists() and any(target.iterdir()):
        raise TruthEnvironmentError(
            "target exists and is not an overlay; use a new dir"
        )
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    for wheel in lock["wheels"]:
        local = None if wheels_dir is None else Path(wheels_dir) / wheel["filename"]
        body = local.read_bytes() if local is not None and local.exists() else None
        if body is None:
            body = fetch(wheel["url"])
        if len(body) != wheel["size"] or _sha256(body) != wheel["sha256"]:
            raise TruthEnvironmentError("wheel hash mismatch: " + wheel["filename"])
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            for info in archive.infolist():
                destination = _member_target(target, info.filename)
                if destination is None:
                    continue
                mode = (info.external_attr >> 16) & 0o777
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise TruthEnvironmentError("wheel member is a link")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(info))
                executable = mode & 0o111 or destination.suffix == ".so"
                destination.chmod(
                    0o755 if executable or ".so." in destination.name else 0o644
                )
    manifest = {
        "schema": SCHEMA,
        "lock_path": LOCK_PATH,
        "lock_sha256": lock_sha,
        "base_image": lock["base_image"],
        "root_requirement": lock["root_requirement"],
        "wheels": len(lock["wheels"]),
    }
    fd = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(manifest, handle, sort_keys=True, indent=2)
    return manifest


def bind(source, target, *, readonly):
    """One bind mount as `--mount`, never `-v`: `-v` splits its argument on
    ':', so a host path holding one (a design bank's tranche
    `bank-design:battery-q3-T1`) failed as "too many colons". `--mount`
    splits on ',' only, and a path holding one is refused."""
    path = str(Path(source).resolve())
    if "," in path:
        raise TruthEnvironmentError("a bind-mounted path may not contain ','")
    return [
        "--mount",
        f"type=bind,source={path},target={target}" + (",readonly" if readonly else ""),
    ]


def mounted_work(command):
    """The host work directory a `solve_command` mounts at `/work` (for
    scripted test containers that play the truth solve)."""
    for part in command:
        if part.startswith("type=bind,") and ",target=/work" in part:
            fields = dict(f.split("=", 1) for f in part.split(",") if "=" in f)
            return Path(fields["source"])
    raise TruthEnvironmentError("the command mounts no /work")


def verify_command(target, repository="."):
    """The exact read-only, network-less container run that verifies the overlay."""
    probe = (
        "import json, pybamm, numpy, scipy; "
        "print(json.dumps({'pybamm': pybamm.__version__, "
        "'numpy': numpy.__version__, 'scipy': scipy.__version__}))"
    )
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=256m",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        # The overlay is owner-only (0700); the image's own user could not
        # enter it, and PyBaMM would look absent. Run as the owner, as solve does.
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        *bind(target, "/overlay", readonly=True),
        "-e",
        "PYTHONPATH=/overlay",
        "--entrypoint",
        INTERPRETER,
        TRUTH_IMAGE["base_image"],
        "-c",
        probe,
    ]


def verify(target, *, repository=".", runner=subprocess.run):
    """Import PyBaMM in the pinned image over the overlay; record the result."""
    target = Path(target)
    lock, lock_sha = load_lock(repository)
    manifest = json.loads((target / MANIFEST).read_bytes())
    if manifest.get("lock_sha256") != lock_sha:
        raise TruthEnvironmentError("overlay built from another lock")
    result = runner(
        verify_command(target, repository),
        capture_output=True,
        timeout=600,
        check=False,
    )
    if result.returncode != 0:
        raise TruthEnvironmentError("pybamm did not import in the truth image")
    versions = json.loads(result.stdout.decode().strip().splitlines()[-1])
    expected = pinned_version(lock)
    provided = lock["provided_by_base_image"]
    if versions.get("pybamm") != expected:
        raise TruthEnvironmentError("pybamm version differs from the lock")
    if any(versions.get(k) != provided[k] for k in ("numpy", "scipy")):
        raise TruthEnvironmentError("base image numpy/scipy differ from the lock")
    record = {
        "schema": SCHEMA + ".verified",
        "base_image": TRUTH_IMAGE["base_image"],
        "lock_sha256": lock_sha,
        "versions": versions,
        "network": "none",
    }
    path = target / VERIFIED
    path.write_text(json.dumps(record, sort_keys=True, indent=2))
    path.chmod(0o600)
    return record


def require_truth_runtime(repository="."):
    """Refuse to solve unless this interpreter has PyBaMM at the pinned version."""
    lock, _ = load_lock(repository)
    try:
        import pybamm
    except ImportError:
        raise TruthEnvironmentError(
            "pybamm is not importable here; run solve inside the verified truth "
            "environment"
        ) from None
    if pybamm.__version__ != pinned_version(lock):
        raise TruthEnvironmentError("pybamm version differs from the lock")
    return pybamm.__version__


def provenance(repository="."):
    """What solves a record here: the pinned solver image digest, the overlay
    lock's path and sha256, and the PyBaMM version this interpreter runs.

    A container cannot read its own image digest. The image is the one
    `solve_command` runs, and the lock (`load_lock`) must name that same
    base image; the PyBaMM version is checked by `require_truth_runtime`.
    """
    _lock, lock_sha = load_lock(repository)
    return {
        "schema": PROVENANCE,
        "solver_image": TRUTH_IMAGE["base_image"],
        "overlay_lock": LOCK_PATH,
        "overlay_lock_sha256": "sha256:" + lock_sha,
        "pybamm": require_truth_runtime(repository),
    }


def stamp(record, solver_provenance):
    """The record with its solver provenance; a record already stamped keeps
    its own."""
    return {PROVENANCE_FIELD: solver_provenance, **record}


def _stamped(solver, solver_provenance, job):
    return stamp(solver(job), solver_provenance)


def _stamp_from(records, offset, solver_provenance, record_schema=None):
    """Stamp the records this run appended after `offset` that the service
    wrote itself (timeouts, worker exits); earlier lines are left as they
    are."""
    body = records.read_bytes()
    lines = body[offset:].decode().splitlines()
    tail = "".join(
        json.dumps(
            stamp(
                {
                    **json.loads(x),
                    **({"schema": record_schema} if record_schema else {}),
                },
                solver_provenance,
            ),
            sort_keys=True,
        )
        + "\n"
        for x in lines
        if x.strip()
    )
    temporary = records.with_name(records.name + ".stamping")
    temporary.write_bytes(body[:offset] + tail.encode())
    temporary.chmod(0o600)
    os.replace(temporary, records)


def solve_command(
    target, workdir, *, repository=".", workers=1, timeout_s=1200.0, output_version="v3"
):
    """The exact container run that solves `workdir/jobs.json` into
    `workdir/records.jsonl`: no network, read-only root, overlay and source
    mounted read-only, only the work directory writable."""
    if output_version not in ("v3", "v4"):
        raise TruthEnvironmentError("unknown prospective output version")
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,size=1g",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        *bind(target, "/overlay", readonly=True),
        *bind(repository, "/carbon", readonly=True),
        *bind(workdir, "/work", readonly=False),
        "-w",
        "/carbon",
        "-e",
        "PYTHONPATH=/carbon:/overlay",
        "--entrypoint",
        INTERPRETER,
        TRUTH_IMAGE["base_image"],
        "-m",
        "carbon.battery.truth_env",
        "solve-v4" if output_version == "v4" else "solve",
        "--jobs",
        "/work/jobs.v4.json" if output_version == "v4" else "/work/jobs.json",
        "--records",
        "/work/records.v4.jsonl" if output_version == "v4" else "/work/records.jsonl",
        "--workers",
        str(int(workers)),
        "--timeout-s",
        str(float(timeout_s)),
    ]


def solve(
    jobs_path,
    records_path,
    *,
    repository=".",
    workers=1,
    timeout_s=1200.0,
    output_version="v3",
):
    """Solve a jobs file (inside the truth image). Resumable: terminal records
    are kept, FAILED_INFRA is retried."""
    from .truth import TruthService, reference_solver

    if output_version not in ("v3", "v4"):
        raise TruthEnvironmentError("unknown prospective output version")
    solver_provenance = provenance(repository)
    document = json.loads(Path(jobs_path).read_bytes())
    records = Path(records_path)
    record_schema = None
    binding = records.with_name(records.name + ".output-contract.json")
    if output_version == "v3" and binding.exists():
        raise TruthEnvironmentError(
            "v3 refuses a version-bound prospective records file"
        )
    if output_version == "v3":
        from . import outputs_v4

        if document.get("schema") == "carbon.battery.truth-jobs.v4":
            raise TruthEnvironmentError("v3 refuses prospective v4 jobs")
        if records.exists():
            for line in records.read_text().splitlines():
                if json.loads(line).get("schema") == outputs_v4.SCHEMA:
                    raise TruthEnvironmentError("v3 refuses prospective v4 records")
    if output_version == "v4":
        from . import outputs_v4
        from .reference_v4 import reference_solver

        record_schema = outputs_v4.SCHEMA
        if (
            document.get("schema") != "carbon.battery.truth-jobs.v4"
            or document.get("output_contract_digest") != outputs_v4.digest()
        ):
            raise TruthEnvironmentError(
                "v4 jobs must bind the prospective output contract"
            )
        identity = {
            "schema": record_schema,
            "output_contract_digest": outputs_v4.digest(),
        }
        if binding.exists():
            if json.loads(binding.read_bytes()) != identity:
                raise TruthEnvironmentError("records belong to another output contract")
        elif records.exists() and records.stat().st_size:
            raise TruthEnvironmentError(
                "v4 refuses pre-existing unversioned or v3 records"
            )
        else:
            fd = os.open(binding, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as handle:
                json.dump(identity, handle, sort_keys=True)
        if records.exists():
            for line in records.read_text().splitlines():
                prior = json.loads(line)
                if prior.get("schema") != record_schema:
                    raise TruthEnvironmentError("v4 records contain another schema")
                if prior.get("status") == "OK":
                    try:
                        outputs_v4.validate(prior)
                    except outputs_v4.OutputV4Refused as exc:
                        raise TruthEnvironmentError(
                            "existing v4 record violates its output contract"
                        ) from exc
    if not records.exists():
        records.touch(mode=0o600)
    if records.stat().st_mode & 0o077:
        raise TruthEnvironmentError("the records file must be owner-only")
    offset = records.stat().st_size
    service = TruthService(
        records,
        solver=functools.partial(_stamped, reference_solver, solver_provenance),
        workers=workers,
        timeout_s=timeout_s,
    )
    try:
        summary = service.run(document["jobs"])
    finally:
        _stamp_from(records, offset, solver_provenance, record_schema)
    return {"fingerprint": document["fingerprint"], **summary}


def main(argv=None):
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="python -m carbon.battery.truth_env")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("solve", "solve-v4"):
        run = sub.add_parser(command)
        run.add_argument("--jobs", required=True)
        run.add_argument("--records", required=True)
        run.add_argument("--workers", type=int, default=1)
        run.add_argument("--timeout-s", type=float, default=1200.0)
    args = parser.parse_args(argv)
    try:
        result = solve(
            args.jobs,
            args.records,
            repository=".",
            workers=args.workers,
            timeout_s=args.timeout_s,
            output_version="v4" if args.command == "solve-v4" else "v3",
        )
    except TruthEnvironmentError as refused:
        print(json.dumps({"refused": str(refused)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    from carbon.battery.truth_env import main as _main

    raise SystemExit(_main())
