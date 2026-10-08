"""The SSH path for a rented A40 box: a stub runner stands in for ssh and scp.

No host is contacted and nothing is rented or spent.
"""

from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path

import pytest

from scripts.dev.exam_design.runpod import a40_acceptance as a40
from scripts.dev.exam_design.runpod import a40_ssh as ssh

A40_ROW = "NVIDIA A40, 580.159.03, GPU-aaaa-bbbb\n"
KEY = "/home/operator/.ssh/a40-executor"
RECORD = {
    "repeats": 2,
    "seed": 0,
    "fno": {"id": "fno_defaults"},
    "recipes_by_backend": {
        "jax": [
            {"id": "r1", "strategy": {"id": "r1"}},
            {"id": "r2", "strategy": {"id": "r2"}},
        ],
        "pytorch": [
            {"id": "r1", "strategy": {"id": "r1", "backend": "pytorch"}},
            {"id": "r2", "strategy": {"id": "r2", "backend": "pytorch"}},
            {"id": "fno_defaults", "strategy": {"id": "fno"}},
        ],
    },
}
FILES = {"carbon/a.py": b"print(1)\n", "docs/x/train-v1.jsonl.gz": b"data"}


class Done:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


class FakeSsh:
    """Answers each remote command by its shape and records every argv."""

    def __init__(
        self,
        *,
        smi=A40_ROW,
        salt="s",
        python_ok=True,
        sha_ok=True,
        probe_ok=True,
        digest_ok=True,
        preexisting=False,
    ):
        self.smi, self.salt, self.python_ok, self.sha_ok = smi, salt, python_ok, sha_ok
        self.probe_ok, self.digest_ok, self.preexisting = (
            probe_ok,
            digest_ok,
            preexisting,
        )
        self.argvs, self.remotes, self.stdin, self.containers = [], [], [], []
        self.probes = {}

    def __call__(self, argv, input=None, timeout=None):
        self.argvs.append(argv)
        if argv[0] == "scp":
            Path(argv[-1]).write_text(json.dumps({"ok": self.probe_ok}))
            return Done()
        remote = argv[-1]
        self.remotes.append(remote)
        self.stdin.append(input)
        if remote.startswith("nvidia-smi"):
            return Done(0, self.smi)
        if remote.startswith("hostname"):
            return Done(0, "box1\nUbuntu 24.04\n6.8.0\n")
        if remote.startswith("docker image inspect --format"):
            image = shlex.split(remote)[-1]
            return Done(0, image if self.digest_ok else "ghcr.io/x@sha256:" + "0" * 64)
        if remote.startswith("docker image inspect"):
            return Done(0 if self.preexisting else 1)
        if remote.startswith("docker pull"):
            return Done(0)
        if remote.startswith("sha256sum") or "sha256sum --check" in remote:
            return Done(0 if self.sha_ok else 1)
        if remote.startswith("docker ps"):
            return Done(0, "\n".join(self.containers))
        if remote.startswith("docker run"):
            return self.docker_run(remote)
        if remote.startswith("cat "):
            return Done(0, json.dumps({"ok": self.probe_ok}))
        return Done(0)  # mkdir, tar

    def docker_run(self, remote):
        words = shlex.split(remote.replace("$(id -u):$(id -g)", "1000:1000"))
        if words[-2:] == ["-c", "pass"]:
            return Done(0 if self.python_ok else 127)
        self.containers.append(words[words.index("--name") + 1])
        if "/out/probe.json" in words:
            return Done(0)
        strategy = json.loads(words[words.index("-c") + 2])
        backend = "pytorch" if strategy.get("backend") == "pytorch" else "jax"
        tag = f"{backend}:{strategy['id']}:{self.salt}"
        return Done(
            0,
            "noise\n"
            + json.dumps(
                {
                    "params_sha256": hashlib.sha256(("w" + tag).encode()).hexdigest(),
                    "predictions_sha256": hashlib.sha256(
                        ("p" + tag).encode()
                    ).hexdigest(),
                    "seconds": 1.0,
                }
            )
            + "\n",
        )


def box(fake, **kw):
    return ssh.Box("user@host", 2222, KEY, run=fake, **kw)


def run(fake, tmp_path, **kw):
    return ssh.run_all(
        box(fake), RECORD, "a" * 40, Path("."), tmp_path, files=FILES, run_id="t1", **kw
    )


# ----------------------------------------------------------------- pre-flight
@pytest.mark.parametrize(
    "smi",
    [
        "",
        A40_ROW + A40_ROW,
        "NVIDIA GeForce RTX 3060, 580.1, GPU-1\n",
        "NVIDIA A40, , GPU-1\n",
        "NVIDIA A40, 580.1, \n",
    ],
)
def test_preflight_refuses_anything_but_one_readable_a40(smi, tmp_path):
    fake = FakeSsh(smi=smi)
    summary, results = run(fake, tmp_path)
    assert summary["status"] == "REFUSED" and results == []
    assert not any(r.startswith(("docker pull", "docker run")) for r in fake.remotes)


def test_preflight_records_the_identity_and_the_driver_build():
    info = ssh.preflight(box(FakeSsh()))
    assert info["identity"] == {
        "index": 0, "uuid": "GPU-aaaa-bbbb", "name": "NVIDIA A40", "driver_version": "580.159.03"
    }  # fmt: skip
    assert info["datacenter"] is None and info["host"][0] == "box1"


# ----------------------------------------------------------------- images and code
def test_a_wrong_image_digest_or_missing_python_is_refused(tmp_path):
    summary, _ = run(FakeSsh(digest_ok=False), tmp_path)
    assert summary["status"] == "REFUSED" and "digest" in summary["reason"]
    summary, _ = run(FakeSsh(python_ok=False), tmp_path / "b")
    assert summary["status"] == "REFUSED"


def test_images_are_pulled_by_released_digest_only(tmp_path):
    fake = FakeSsh()
    summary, _ = run(fake, tmp_path)
    pulls = [shlex.split(r)[-1] for r in fake.remotes if r.startswith("docker pull")]
    assert pulls == [a40.IMAGES["jax"], a40.IMAGES["pytorch"]]
    assert summary["images_pulled"] == pulls
    pre = FakeSsh(preexisting=True)
    summary, _ = run(pre, tmp_path / "c")
    assert summary["images_pulled"] == []


def test_a_code_hash_mismatch_stops_before_any_rebuild(tmp_path):
    fake = FakeSsh(sha_ok=False)
    summary, results = run(fake, tmp_path)
    assert summary["status"] == "REFUSED" and results == []
    assert not any("--gpus" in r for r in fake.remotes)


def test_the_tar_and_its_hash_list_match_the_shipped_files(tmp_path):
    import io
    import tarfile

    fake = FakeSsh()
    run(fake, tmp_path)
    tar_bytes = next(
        i
        for r, i in zip(fake.remotes, fake.stdin, strict=True)
        if r.startswith("mkdir -p") and "tar -x" in r
    )
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        assert {m.name for m in tar.getmembers()} == set(FILES)
    listing = next(
        i
        for r, i in zip(fake.remotes, fake.stdin, strict=True)
        if "sha256sum --check" in r
    ).decode()
    for path, data in FILES.items():
        assert f"{hashlib.sha256(data).hexdigest()}  {path}" in listing


# ----------------------------------------------------------------- the legs
def test_the_driver_is_read_before_any_rebuild_and_flags_are_exact(tmp_path):
    fake = FakeSsh()
    run(fake, tmp_path)
    assert fake.remotes[0].startswith("nvidia-smi")
    rebuilds = [r for r in fake.remotes if r.startswith("docker run") and "--gpus" in r]
    assert rebuilds and fake.remotes.index(rebuilds[0]) > 0
    for r in rebuilds:
        for flag in (
            "--gpus all",
            "--network none",
            "--user $(id -u):$(id -g)",
            ":/w:ro",
        ):
            assert flag in r
        for env in (
            "TMPDIR=/tmp",
            "HOME=/tmp",
            "XDG_CACHE_HOME=/tmp/cache",
            "JAX_COMPILATION_CACHE_DIR=/tmp/jax-cache",
        ):
            assert env in r
        assert "CUDA_VISIBLE_DEVICES=GPU-aaaa-bbbb" in r and "JAX_PLATFORMS=cuda" in r
        assert "NVIDIA_TF32_OVERRIDE=0" in r and "--rm" in r


def test_each_repeat_is_its_own_container_and_the_fno_is_skipped(tmp_path):
    fake = FakeSsh()
    summary, results = run(fake, tmp_path)
    assert (
        summary["status"] == "COMPLETE" and summary["skipped"]["fno"]["skipped"] is True
    )
    by_backend = {r["backend"]: r for r in results}
    for backend in ("jax", "pytorch"):
        rows = by_backend[backend]["rows"]
        assert [(r["recipe_id"], r["repeat"]) for r in rows] == [
            ("r1", 0), ("r1", 1), ("r2", 0), ("r2", 1)
        ]  # fmt: skip
        assert by_backend[backend]["cloud"] == "VAST_SSH"
    assert len(set(fake.containers)) == len(fake.containers)
    assert not any("fno" in r for r in fake.remotes if "-c pass" not in r)


def test_a_failed_probe_is_failed_infra_and_runs_no_rebuild(tmp_path):
    fake = FakeSsh(probe_ok=False)
    summary, results = run(fake, tmp_path)
    assert summary["status"] == "FAILED_INFRA"
    assert all(r["rows"] == [] for r in results)


def test_results_feed_compare_and_one_host_is_within_host_only(tmp_path):
    _summary, results = run(FakeSsh(), tmp_path)
    document = a40.compare(results)
    cells = {(c["backend"], c["recipe_id"]): c for c in document["cells"]}
    assert set(cells) == {
        ("jax", "r1"),
        ("jax", "r2"),
        ("pytorch", "r1"),
        ("pytorch", "r2"),
    }
    for cell in cells.values():
        assert cell["within_host_equal"] is True
        assert cell["across_hosts"]["outcome"] == "REFUSED_ONE_UNIT"
        assert cell["driver_builds"] == ["580.159.03"]
    assert json.loads((tmp_path / "results.json").read_text()) == results


def test_two_hosts_agree_or_differ_through_compare(tmp_path):
    _s, one = run(FakeSsh(), tmp_path / "a")
    second = json.loads(json.dumps(one))
    for r in second:
        r["label"] = "B"
        r["identity"]["uuid"] = "GPU-other"
    document = a40.compare(one + second)
    assert {c["across_hosts"]["outcome"] for c in document["cells"]} == {"AGREE"}
    third = json.loads(json.dumps(second))
    for r in third:
        r["identity"]["driver_version"] = "580.159.04"
    refused = a40.compare(one + third)
    assert {c["across_hosts"]["outcome"] for c in refused["cells"]} == {
        "REFUSED_DRIVER_MISMATCH"
    }


# ----------------------------------------------------------------- deadline, credentials, leftovers
def test_the_hard_deadline_stops_the_run(tmp_path):
    fake = FakeSsh()
    clock = iter([0.0, 0.0, 0.0, 0.0, 99.0] + [99.0] * 500)
    b = ssh.Box(
        "user@host", 22, KEY, run=fake, deadline_at=10.0, clock=lambda: next(clock)
    )
    summary, _ = ssh.run_all(
        b, RECORD, "a" * 40, Path("."), tmp_path, files=FILES, run_id="t1"
    )
    assert summary["status"] == "DEADLINE"


def test_the_key_is_a_path_only_and_no_environment_is_passed(tmp_path):
    fake = FakeSsh()
    run(fake, tmp_path)
    for argv in fake.argvs:
        assert argv[argv.index("-i") + 1] == KEY
        assert sum(1 for a in argv if KEY in a) == 1
    secret_like = [
        r for r in fake.remotes if "KEY" in r or "TOKEN" in r or "SECRET" in r
    ]
    assert not secret_like


def test_the_run_lists_what_it_left_and_never_touches_the_rental(tmp_path):
    fake = FakeSsh()
    summary, _ = run(fake, tmp_path)
    left = summary["left_on_the_box"]
    assert left["rental"].startswith("not touched")
    assert left["remote_directory"] == "/tmp/a40-ssh-t1"
    assert set(left["images_pulled_by_this_run"]) == {
        a40.IMAGES["jax"],
        a40.IMAGES["pytorch"],
    }
    assert not any(
        w in r
        for r in fake.remotes
        for w in ("vastai", "destroy", "docker rm", "docker rmi")
    )


def test_the_cli_requires_a_matching_run_record(tmp_path):
    with pytest.raises(a40.Refused):
        a40.load_record(tmp_path / "none.json")
