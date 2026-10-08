"""A40 acceptance legs over SSH on an owner-rented Linux box (no pod).

For a rented host that already has Docker and the NVIDIA container toolkit
(for example a Vast.ai A40). Operator side, stdlib only. The script never
creates or destroys the rental: it prints what it left on the box and the
owner stops the rental. DEVELOPMENT evidence; digest equality only; the same
legs as the pod run (`a40_acceptance.py`), minus the PyTorch fno (known GPU
device bug, to be re-run on the v3 images).

    python -m scripts.dev.exam_design.runpod.a40_ssh \\
        --host user@host --port 22 --key ~/.ssh/a40-executor \\
        --record RUN_RECORD.json --code-ref SHA --out DIR --deadline-minutes 120

Order: (1) pre-flight `nvidia-smi` (exactly one A40, driver build readable);
(2) `docker pull` of the released digests, digest equality and the worker python
checked; (3) the pinned CODE_REF streamed as a tar, every file's sha256 checked
against the manifest, mounted read-only at /w; (4) per backend a GPU probe, then
per recipe two repeats, each in a FRESH container (`--gpus all --network none`),
hashing weights and predictions; (5) results written in the shape `compare`
reads, with cloud `VAST_SSH`. One host gives within-host equality only; an
across-host comparison needs a second host (another rental or the RunPod run).

The SSH key is a file path only: nothing here reads it, puts it in an
environment or in an argument other than `-i PATH`.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shlex
import subprocess
import sys
import tarfile
import time
from pathlib import Path

from scripts.dev.exam_design.runpod import a40_acceptance as a40
from scripts.dev.exam_design.runpod import a40_pod_phase as phase

CLOUD = "VAST_SSH"
TARGETS = a40.TARGET_DEVICES
REMOTE_ROOT = "/tmp/a40-ssh"
SKIPPED_FNO = {
    "fno": {
        "skipped": True,
        "reason": "known GPU device bug (neuralop CPU/CUDA device mismatch); "
        "to be re-run on v3 images",
    }
}


class SshRefused(RuntimeError):
    """The run stops; nothing further is attempted on the box."""


class Deadline(RuntimeError):
    """The hard deadline passed."""


def real_run(argv, input=None, timeout=None):
    """The only process runner: no shell, no environment passed on purpose
    beyond the caller's own (nothing is added)."""
    return subprocess.run(
        argv, input=input, capture_output=True, check=False, timeout=timeout
    )


class Box:
    """One SSH host. `run` is injectable (tests use a stub)."""

    def __init__(
        self, host, port, key, *, run=real_run, deadline_at=None, clock=time.monotonic
    ):
        self.host, self.port, self.key = host, int(port), str(key)
        self.run, self.deadline_at, self.clock = run, deadline_at, clock
        self.commands: list[str] = []

    def _timeout(self):
        if self.deadline_at is None:
            return None
        left = self.deadline_at - self.clock()
        if left <= 0:
            raise Deadline("hard deadline passed")
        return left

    def _ssh_argv(self, remote):
        return [
            "ssh", "-i", self.key, "-p", str(self.port),
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            self.host, remote,
        ]  # fmt: skip

    def sh(self, remote, *, input=None, check=True):
        """Run a remote command; (returncode, stdout, stderr) as text."""
        timeout = self._timeout()
        self.commands.append(remote)
        try:
            done = self.run(self._ssh_argv(remote), input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise Deadline("hard deadline passed") from None
        out = done.stdout.decode() if isinstance(done.stdout, bytes) else done.stdout
        err = done.stderr.decode() if isinstance(done.stderr, bytes) else done.stderr
        if check and done.returncode != 0:
            raise SshRefused(
                f"remote command failed ({done.returncode}): {remote[:120]}"
            )
        return done.returncode, out or "", err or ""

    def fetch(self, remote_path, local_path):
        """scp one file back."""
        argv = [
            "scp", "-i", self.key, "-P", str(self.port),
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            f"{self.host}:{remote_path}", str(local_path),
        ]  # fmt: skip
        done = self.run(argv, input=None, timeout=self._timeout())
        if done.returncode != 0:
            raise SshRefused("scp failed for " + remote_path)


# ------------------------------------------------------------------ 1. pre-flight
def preflight(box, target="A40"):
    """Exactly one GPU of the target device and a readable driver build, else
    refuse. A40: the name must contain 'A40'. RTX 4090: the name must be exactly
    'NVIDIA GeForce RTX 4090'. The exact name is recorded as the device kind.
    Returns the identity in the shape `compare` reads plus what the box exposes."""
    _rc, out, _err = box.sh(
        "nvidia-smi --query-gpu=name,driver_version,uuid --format=csv,noheader"
    )
    rows = [
        [cell.strip() for cell in line.split(",")]
        for line in out.splitlines()
        if line.strip()
    ]
    if len(rows) != 1 or len(rows[0]) != 3:
        raise SshRefused(f"refused: expected exactly one GPU, found {len(rows)}")
    name, driver, uuid = rows[0]
    wrong = name != TARGETS["RTX 4090"] if target == "RTX 4090" else "A40" not in name
    if target not in TARGETS or wrong:
        raise SshRefused(f"refused: the GPU is not the target {target}: " + name[:60])
    if not driver or not uuid:
        raise SshRefused("refused: driver build or GPU uuid is unreadable")
    _rc, host_info, _err = box.sh(
        'hostname; . /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"; uname -r',
        check=False,
    )
    return {
        "identity": {
            "index": 0,
            "uuid": uuid,
            "name": name,
            "driver_version": driver,
            "device_kind": name,
            "target_device": target,
        },
        "host": [line.strip() for line in host_info.splitlines()][:3],
        # A rented box exposes no datacenter field; recorded as unknown, not guessed.
        "datacenter": None,
    }


# ------------------------------------------------------------------ 2. images
def pull_images(box, backends):
    """Pull each released digest; verify the digest and the worker python.
    Returns the images this run pulled (not already on the box)."""
    pulled = []
    for backend in backends:
        image = a40.check_image(a40.IMAGES[backend])
        rc, _o, _e = box.sh(f"docker image inspect {shlex.quote(image)}", check=False)
        if rc != 0:
            box.sh(f"docker pull {shlex.quote(image)}")
            pulled.append(image)
        _rc, digests, _e = box.sh(
            "docker image inspect --format '{{join .RepoDigests \"\\n\"}}' "
            + shlex.quote(image)
        )
        if image not in {line.strip() for line in digests.splitlines()}:
            raise SshRefused(
                "refused: the image digest on the box is not " + image[-20:]
            )
        box.sh(
            "docker run --rm --network none --entrypoint "
            f"{a40.PYTHON} {shlex.quote(image)} -c pass"
        )
    return pulled


# ------------------------------------------------------------------ 3. code
def ship_files(ref, repository):
    """{path: bytes} of the harness's shipped files at `ref`: the same paths as
    the pod manifest (`a40.ship_paths`), read in one `git cat-file --batch`."""
    paths = a40.ship_paths(ref, repository)
    request = "".join(f"{ref}:{p}\n" for p in paths).encode()
    blob = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "--batch"],
        input=request, capture_output=True, check=True,
    ).stdout  # fmt: skip
    files, offset = {}, 0
    for path in paths:
        end = blob.index(b"\n", offset)
        header = blob[offset:end].split()
        if len(header) != 3 or header[1] != b"blob":
            raise SshRefused(f"refused: {path} is not a blob at {ref}")
        size = int(header[2])
        files[path] = blob[end + 1 : end + 1 + size]
        offset = end + 1 + size + 1
    return files


def ship_code(box, files, run_id):
    """Stream the files as a tar, then check every sha256 on the box against
    the manifest. Returns the remote code directory."""
    code = f"{REMOTE_ROOT}-{run_id}/code"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for path, data in sorted(files.items()):
            info = tarfile.TarInfo(path)
            info.size, info.mode = len(data), 0o644
            tar.addfile(info, io.BytesIO(data))
    box.sh(
        f"mkdir -p {shlex.quote(code)} && tar -x -C {shlex.quote(code)}",
        input=buffer.getvalue(),
    )
    manifest = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {path}\n"
        for path, data in sorted(files.items())
    )
    box.sh(
        f"cd {shlex.quote(code)} && sha256sum --check --quiet -",
        input=manifest.encode(),
    )
    return code


# ------------------------------------------------------------------ 4. rebuilds
def _docker_run(box, image, code, out_dir, env, command, name):
    flags = [
        "docker", "run", "--rm", "--name", name, "--gpus", "all", "--network", "none",
        "--user", "$(id -u):$(id -g)",
        "-v", f"{code}:/w:ro", "-v", f"{out_dir}:/out", "-w", "/w",
        "-e", "TMPDIR=/tmp", "-e", "HOME=/tmp", "-e", "XDG_CACHE_HOME=/tmp/cache",
        "-e", "JAX_COMPILATION_CACHE_DIR=/tmp/jax-cache",
        "-e", "PYTHONPATH=/w", "-e", "PYTHONDONTWRITEBYTECODE=1",
    ]  # fmt: skip
    for key, value in sorted(env.items()):
        flags += ["-e", f"{key}={value}"]
    # `--user` is a command substitution, so the head of the line is joined
    # unquoted for that one word and every other word is quoted.
    head = " ".join(w if w == "$(id -u):$(id -g)" else shlex.quote(w) for w in flags)
    line = f"{head} --entrypoint {a40.PYTHON} {shlex.quote(image)} " + " ".join(
        shlex.quote(c) for c in command
    )
    return box.sh(line, check=False)


def run_backend(box, backend, record, device, code, run_id, remote_out, counter):
    """The probe, then every recipe's repeats, each repeat in a fresh container."""
    from carbon.agent_campaign.graphite import pod_phase

    image = a40.IMAGES[backend]
    env = phase.pinned_environment(backend, device=device)
    out_dir = f"{remote_out}/{backend}"
    box.sh(f"mkdir -p -m 777 {shlex.quote(out_dir)}")
    probe_code = phase.TORCH_PROBE if backend == "pytorch" else pod_phase.PROBE
    counter[0] += 1
    rc, _o, _e = _docker_run(
        box, image, code, out_dir, env,
        ["-I", "-c", probe_code, "/out/probe.json"], f"a40-{run_id}-{counter[0]}",
    )  # fmt: skip
    probe = None
    if rc == 0:
        _rc, text, _e = box.sh(f"cat {shlex.quote(out_dir)}/probe.json", check=False)
        probe = json.loads(text) if text.strip() else None
    if rc != 0 or not (probe and probe.get("ok") is True):
        return {
            "backend": backend,
            "outcome": "FAILED_INFRA",
            "rows": [],
            "probe": probe,
        }
    rows = []
    for recipe in record["recipes_by_backend"][backend]:
        if recipe["id"] == record["fno"]["id"]:
            continue  # --skip-fno semantics: the fno waits on the v3 images
        for repeat in range(record["repeats"]):
            counter[0] += 1
            started = time.monotonic()
            rc, text, err = _docker_run(
                box, image, code, out_dir, env,
                ["-c", phase.CHILD, json.dumps(recipe["strategy"]), str(record["seed"]), "/w"],
                f"a40-{run_id}-{counter[0]}",
            )  # fmt: skip
            row = {
                "recipe_id": recipe["id"],
                "repeat": repeat,
                "wall_seconds": round(time.monotonic() - started, 3),
            }
            record_json = None
            if rc == 0 and text.strip():
                try:
                    record_json = json.loads(text.strip().splitlines()[-1])
                except ValueError:
                    record_json = None
            if (
                record_json
                and phase.hexdigest_ok(record_json.get("params_sha256"))
                and phase.hexdigest_ok(record_json.get("predictions_sha256"))
            ):
                row.update(record_json)
            else:
                row["error"] = f"exit {rc}"
                row["stderr_tail"] = err[-400:]
            rows.append(row)
    complete = bool(rows) and all("error" not in r for r in rows)
    return {
        "backend": backend,
        "outcome": "COMPLETE" if complete else "FAILED",
        "rows": rows,
        "probe": probe,
    }


# ------------------------------------------------------------------ 5. the run
def run_all(
    box, record, ref, repository, out, *, files=None, run_id=None, target="A40"
):
    run_id = run_id or hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "cloud": CLOUD,
        "target_device": target,
        "run_id": run_id,
        "skipped": SKIPPED_FNO,
        "status": "COMPLETE",
        "images_pulled": [],
    }
    remote_out = f"{REMOTE_ROOT}-{run_id}/out"
    counter = [0]
    results = []
    try:
        info = preflight(box, target)
        summary["device_kind"] = info["identity"]["device_kind"]
        summary["driver_version"] = info["identity"]["driver_version"]
        summary["identity"], summary["host"], summary["datacenter"] = (
            info["identity"], info["host"], info["datacenter"],
        )  # fmt: skip
        # The driver build is recorded and read before any rebuild; across hosts
        # it is matched by `compare` (REFUSED_DRIVER_MISMATCH, never hidden).
        summary["images_pulled"] = pull_images(box, a40.BACKENDS)
        code = ship_code(
            box, files if files is not None else ship_files(ref, repository), run_id
        )
        device = {"uuid": info["identity"]["uuid"], "name": info["identity"]["name"]}
        for backend in a40.BACKENDS:
            leg = run_backend(
                box, backend, record, device, code, run_id, remote_out, counter
            )
            summary.setdefault("legs", {})[backend] = leg["outcome"]
            try:
                box.fetch(
                    f"{remote_out}/{backend}/probe.json", out / f"probe-{backend}.json"
                )
            except SshRefused:
                pass
            if leg["outcome"] != "COMPLETE":
                summary["status"] = (
                    "FAILED_INFRA" if leg["outcome"] == "FAILED_INFRA" else "FAILED"
                )
            results.append(
                {
                    "backend": backend,
                    "label": "A",
                    "identity": info["identity"],
                    "datacenter": None,
                    "cloud": CLOUD,
                    "target_device": target,
                    "device_kind": info["identity"]["device_kind"],
                    "driver_version": info["identity"]["driver_version"],
                    "rows": leg["rows"],
                }
            )
    except Deadline:
        summary["status"] = "DEADLINE"
    except SshRefused as refusal:
        summary["status"] = "REFUSED"
        summary["reason"] = str(refusal)
    finally:
        summary["left_on_the_box"] = leftovers(box, run_id, summary["images_pulled"])
    (out / "results.json").write_text(
        json.dumps(results, indent=1, sort_keys=True) + "\n"
    )
    (out / "summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n"
    )
    return summary, results


def leftovers(box, run_id, pulled):
    """What this run left that the owner may want to remove; the rental itself
    is the owner's to stop."""
    box.deadline_at = None  # reporting is allowed after the deadline
    try:
        _rc, ps, _e = box.sh(
            f"docker ps -a --filter name=a40-{run_id} --format '{{{{.Names}}}}'",
            check=False,
        )
    except SshRefused:
        ps = ""
    return {
        "images_pulled_by_this_run": pulled,
        "containers": [n for n in ps.split() if n],
        "remote_directory": f"{REMOTE_ROOT}-{run_id}",
        "rental": "not touched; stop it yourself",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", required=True, help="user@host")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument(
        "--key", required=True, help="SSH key FILE path; never read here"
    )
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--code-ref", required=True)
    parser.add_argument("--repository", default=str(a40.REPOSITORY))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--deadline-minutes", type=int, required=True)
    parser.add_argument(
        "--target-device",
        choices=sorted(TARGETS),
        default="A40",
        help="A40 (default) or RTX 4090 (an unqualified development device)",
    )
    args = parser.parse_args(argv)
    try:
        record = a40.load_record(args.record)
    except a40.Refused as refusal:
        print(str(refusal), file=sys.stderr)
        return 2
    box = Box(
        args.host, args.port, args.key,
        deadline_at=time.monotonic() + args.deadline_minutes * 60,
    )  # fmt: skip
    summary, _results = run_all(
        box,
        record,
        args.code_ref,
        Path(args.repository),
        args.out,
        target=args.target_device,
    )
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0 if summary["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
